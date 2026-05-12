import os
import subprocess
import time

import modal

# ── Build identification ──────────────────────────────────────────────────────
# Computed at deploy time (when `modal deploy` reads this file) and baked into
# the image as env vars. The handler logs these on the first line of every job
# so we can always answer "which build ran this render?" — no guessing about
# warm-container code drift after a deploy. _BUILD_DIRTY is "1" if there are
# uncommitted changes in the working tree at deploy time, "0" otherwise.
def _git(*args):
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return ""

_BUILD_SHA = _git("rev-parse", "HEAD") or "unknown"
_BUILD_DIRTY = "1" if _git("status", "--porcelain") else "0"
_BUILD_TS = str(int(time.time()))

# rebuild trigger v65 — RIFE 4.18 on H100 GPU for source-level frame interpolation, properly verified this time.
#
# What v63 got wrong: assumed RIFE_HDv3.py was in the Practical-RIFE git
# repo (it isn't — it ships with the model archive on Google Drive) AND
# bundled a 12MB flownet.pkl from AlexWortega/RIFE that turned out to
# have a custom `convblock0/1/2` architecture not matching any IFNet
# variant in any official RIFE repo. Both errors caught via local code
# inspection in v64.
#
# What v65 does differently:
#   1. Downloaded the OFFICIAL RIFE 4.18 archive locally via gdown
#      from the Practical-RIFE README's known-good Drive URL.
#   2. Verified the archive contains BOTH the model code (.py files)
#      and matching weights (flownet.pkl, 22MB, ~10M params).
#   3. Loaded the model on CPU locally and ran an end-to-end test
#      pipeline (320x256 30fps -> 60fps via ffmpeg decode + RIFE
#      inference + ffmpeg encode + audio mux). Verified output shape,
#      frame counts, audio passthrough.
#   4. Bundled the verified files into the repo at models/rife-v4.18/
#      (gitignored), shipped via add_local_file — no Drive downloads
#      at build time, no flaky URLs, fully reproducible.
#   5. Added a BUILD-TIME validation step that imports the Model class,
#      loads the weights, and runs a dummy 256x256 CPU inference. Build
#      fails loud if anything is wrong instead of crashing on the first
#      production render.
#
# RIFE 4.18 on H100 should run ~50-100 fps for 1088x1920 (vs 1 fps on
# my local CPU benchmark). Estimated normalize step cost: ~25-50s for
# typical 60s source. Total render time estimate: ~120-180s end-to-end.

# rebuild trigger v64 — Reverted v63's source-level RIFE.

# rebuild trigger v62 — FFmpeg base + Remotion micro-segments architecture. Replaces v61's chunked Remotion fan-out (which delivered 140s, not the projected 60s, because Modal's Function.map only ran ~4 workers in parallel without warm pool, and the per-chunk Remotion startup tax of ~10s didn't amortize on small chunks). Visually-identical fast path:
# (1) PromptlyOverlay (transparent canvas — captions/MG/text overlays) renders once on the orchestrator. ProRes 4444 alpha, unchanged.
# (2) PromptlyMicroSegments (NEW composition) renders ALL transitions (11 types: CardSwipe / FilmStrip / SceneTitle / NewspaperWipe / LightLeak / SlideOver / Stack / CrossfadeZoom / ShutterFlash / StepPush / ZoomThrough) AND composite-effect zoom clips (FocusWindow / LetterboxPush / DepthPull) in ONE Remotion process — segments concatenated end-to-end so ~10s startup tax amortizes across all of them. h264 (no alpha).
# (3) Base video — clip cuts, simple-zoom clips (SmoothPush / SnapReframe / StepZoom / StageZoom) ported to per-frame `crop` expressions, B-roll cutaways, outro fade — built directly by FFmpeg in one big filter_complex. SnapReframe spring (damping=28 mass=0.6 stiffness=260) uses closed-form over-damped step response (1 + (-33.87*exp(-12.79*t) + 12.79*exp(-33.87*t))/21.08); SmoothPush/StageZoom use cubic ease pieces matching the Remotion components exactly.
# (4) Single-pass final ffmpeg invocation: builds each clip segment via filter chains, trims Remotion-rendered segments out of micro_segments.mp4 by frame range, concats in timeline order, overlays B-roll at output windows, applies outro fade, alpha-composites the overlay layer, libx264 ultrafast crf 18 final encode + AAC audio mux.
# Net: Remotion only paints the visual layers it has to (overlay layer + complex-segment windows). Every video-paint frame goes through FFmpeg at native libx264 ultrafast + lanczos resample on 64 cores. Removes render_chunk function, render_volume, render_staging_janitor — all chunked-render infra is dead. handler.py and orchestrator container unchanged in resource shape (H100 + 64 vCPU + 128 GB). Expected end-to-end (warm): ~30-50s for typical talking-head videos (no complex zoom), ~50-70s if a clip uses FocusWindow/LetterboxPush/DepthPull. Quality preserved: every Remotion component renders exactly the frames it always did; FFmpeg-rendered clips use the same scale/origin math the components compute, just with FFmpeg's lanczos resampler instead of Chromium's compositor — visually indistinguishable.

# rebuild trigger v60 — Cut always-on prewarm cost. PromptlyPrewarmWorker had min_containers=1 (always-warm CPU container) costing ~$35/mo regardless of usage. Removed it so the class scales to zero when idle. First prewarm after a quiet period takes 3-5s cold start, but the user is mid-upload to S3 when prewarm fires so it's invisible. GPU class already scales to zero. Net: ~$35/mo saved on idle infrastructure.

# rebuild trigger v59 — Fix Remotion alpha-render validation: imageFormat="png" required for yuva pixel formats. v58's PromptlyOverlay render failed instantly with TypeError "Pixel format was set to 'yuva444p10le' but the image format is not PNG" because Remotion enforces PNG intermediates for any alpha-bearing pixel format (JPEG can't carry alpha). One-line fix in render-full.mjs: add imageFormat="png" to the overlay branch alongside proResProfile="4444" + pixelFormat="yuva444p10le". PNG is theoretically slower per-frame screenshot than JPEG, but the overlay canvas is mostly transparent so PNG compression is near-instant on empty alpha — negligible cost. PromptlyBase keeps default JPEG (faster, no alpha needed). Same v58 architecture otherwise.

# rebuild trigger v58 — Phase A + Phase B: two-renderer split + drop color effects. The user diagnosed correctly that the slowdown was architectural, not a GPU/Vulkan issue: pre-66-pack Remotion was overlay-only (~10-15s renders), while 8a777e1 made Remotion render the full 1080x1920 canvas including video underneath, which made each frame's mixBlendMode/filter passes catastrophically expensive in software. Restored the original architecture: PromptlyBase (h264, video + transitions + zoom + broll, black background) and PromptlyOverlay (ProRes 4444 alpha, captions + MGs + text overlays, transparent background) render as TWO parallel Remotion compositions, then FFmpeg composites the alpha overlay onto the base in a single pass + audio mux. Color effects (12 components) are removed entirely — they were the heaviest mixBlendMode stack, irrelevant for talking-head content, and impossible to translate cleanly between Remotion's CSS blend modes and FFmpeg without quality drift. Zero quality risk: all 21 captions + 18 MGs + 4 text overlays + 11 transitions + 7 zooms + B-roll render through the same React tree they always have, just split into two independent compositions. Per-frame paint cost drops ~10x on each composition (no video paint in overlay, no overlay paint in base). Expected end-to-end render time: ~30-40s on H100 (encoder-bound on libx264 ultrafast), down from 140-180s. Full deletion of color-effects directory + Pydantic schema + Gemini prompt section + validator + render_multi_clip color path.

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("nvidia/cuda:12.6.3-runtime-ubuntu22.04", add_python="3.10")
    # CRITICAL: 'video' capability tells nvidia-container-toolkit to mount libnvidia-encode.so
    # Without this, NVENC silently fails and pipeline falls back to CPU encoding (10-15x slower)
    .env({"NVIDIA_DRIVER_CAPABILITIES": "all"})
    .run_commands(
        "echo 'build v40 - TONE FIRST stripped of taxonomy and examples: previous version named six example tones (storytime/punchy/educational/corporate/comedy/dramatic) and three component-mismatch examples (quote_card on storytime, Banger on corporate, thunder on comedy) which anchored Gemini judgment to those specific cases. Now pure intent: Gemini forms its own understanding of what the video IS in its own words (no taxonomy, no labels, no list) and chooses every component from that understanding. quote_card tone-fit also stripped of explicit allowed/forbidden tone list — only the print-media character description remains, judgment of fit is Gemini.'",
        "apt-get update && apt-get install -y ca-certificates && update-ca-certificates",
        # Remove CUDA stubs AND compat libs that intercept dlopen before Modal's
        # real driver libs. THEN recreate placeholders for every libcuda* file
        # name Modal's nvidia-container-cli might lstat + mount-bind during
        # container creation. The toolkit runs BEFORE our Python; if any target
        # path is missing it hard-fails with "lstat failed: no such file or
        # directory" and the container never starts.
        #
        # We restore TWO placeholders in /usr/local/cuda-12.6/compat/:
        #   - libcuda.so.1 — the canonical SONAME the loader uses (this is
        #     what failed in the original error). Most NVIDIA Container
        #     Toolkit configurations bind-mount the host driver here.
        #   - libcuda.so — the unversioned name some loaders use as the
        #     `dlopen("libcuda.so")` entry point. Defensive in case the
        #     toolkit also wants to mount-bind this path.
        # Both are empty files; the bind-mount at runtime replaces them with
        # the host's real driver lib, so dlopen still falls through to
        # Modal's mounted version (the original goal of the rm -rf).
        "rm -rf /usr/local/cuda/lib64/stubs/libnvidia-encode* /usr/local/cuda/lib64/stubs/libcuda* /usr/local/cuda/compat/libcuda* /usr/local/cuda/lib64/libcuda.so* 2>/dev/null || true",
        "mkdir -p /usr/local/cuda-12.6/compat && touch /usr/local/cuda-12.6/compat/libcuda.so.1 /usr/local/cuda-12.6/compat/libcuda.so",
    )
    .apt_install(
        "ca-certificates",
        "fontconfig",
        "wget",
        "xz-utils",
        "curl",
        "libass-dev",
        "libfontconfig1",
        "fonts-dejavu-core",
        "librubberband-dev",
        "rubberband-cli",
        "build-essential",
        "clang",
        "pkg-config",
        "python3-dev",
        "libaubio-dev",
        "libavcodec-dev",
        "libavformat-dev",
        "libavutil-dev",
        "libswresample-dev",
        "libsndfile1-dev",
        "libsamplerate0-dev",
        # Chromium dependencies for Remotion headless rendering
        "libnss3",
        "libatk1.0-0",
        "libatk-bridge2.0-0",
        "libcups2",
        "libdrm2",
        "libxkbcommon0",
        "libxcomposite1",
        "libxdamage1",
        "libxfixes3",
        "libxrandr2",
        "libgbm1",
        "libpango-1.0-0",
        "libcairo2",
        "libasound2",
        "libatspi2.0-0",
    )
    .run_commands(
        "fc-cache -f",
    )
    .run_commands(
        # Build FFmpeg from source WITH NVENC support (nonfree, not available in prebuilts)
        # Install NVIDIA codec headers (nv-codec-headers) for NVENC/NVDEC
        "apt-get install -y nasm yasm libx264-dev libx265-dev libfdk-aac-dev libmp3lame-dev libopus-dev libvpx-dev libass-dev libfreetype6-dev libfontconfig1-dev libfribidi-dev libharfbuzz-dev git",
        "git clone --depth 1 https://git.videolan.org/git/ffmpeg/nv-codec-headers.git /tmp/nv-codec-headers",
        "cd /tmp/nv-codec-headers && make install",
        # Build FFmpeg with NVENC + NVDEC + key codecs
        "git clone --depth 1 --branch n7.1 https://git.ffmpeg.org/ffmpeg.git /tmp/ffmpeg-src",
        "cd /tmp/ffmpeg-src && ./configure "
        "--prefix=/usr/local "
        "--enable-nonfree --enable-gpl "
        "--enable-nvenc --enable-nvdec --enable-cuda --enable-cuvid "
        "--enable-libx264 --enable-libx265 --enable-libfdk-aac --enable-libmp3lame "
        "--enable-libopus --enable-libvpx --enable-libass --enable-librubberband "
        "--enable-libfreetype --enable-libfontconfig --enable-libfribidi --enable-libharfbuzz "
        "--enable-filter=drawtext --enable-filter=ass --enable-filter=subtitles "
        "--disable-doc --disable-debug --enable-optimizations "
        "&& make -j$(nproc) && make install",
        "ldconfig",
        "which ffmpeg && which ffprobe",
        "ffmpeg -version | head -3",
        "ffmpeg -filters 2>/dev/null | grep drawtext && echo 'DRAWTEXT: OK' || (echo 'DRAWTEXT: MISSING' && ffmpeg -version | head -5 && ffmpeg -filters 2>/dev/null | grep -i 'draw' && exit 1)",
        "ffmpeg -filters 2>/dev/null | grep -E 'ass|subtitles' || echo 'WARNING: ass/subtitles filters not found'",
        "ffmpeg -encoders 2>/dev/null | grep nvenc && echo 'NVENC: OK' || echo 'NVENC: MISSING'",
    )
    .run_commands(
        # Install Node.js 20 LTS for Remotion caption rendering
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "node --version && npm --version",
    )
    .run_commands(
        # Download OpenCV DNN face detector model (much more accurate than Haar cascades)
        "mkdir -p /models/face_detector",
        "wget -q -O /models/face_detector/deploy.prototxt https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
        "wget -q -O /models/face_detector/res10_300x300_ssd_iter_140000.caffemodel https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
        # Pre-cache arnndn noise reduction model (avoids runtime download on every cold start)
        "mkdir -p /usr/share/rnnoise",
        "wget -q -O /usr/share/rnnoise/bd.rnnn https://github.com/GregorR/rnnoise-models/raw/master/beguiling-drafter-2018-08-30/bd.rnnn",
    )
    .pip_install("numpy", "wheel")
    .pip_install("aubio", extra_options="--no-build-isolation")
    .pip_install(
        "certifi",
        "opencv-python-headless",
        "requests",
        "anthropic",
        "google-genai",
        "deepgram-sdk==3.4.0",
        "supabase",
        "boto3[crt]",   # AWS Common Runtime — 2-6× S3 throughput vs stock boto3
        "httpx",
        "fastapi",
        "pydantic",
        "tqdm",
        "Pillow",
    )
    # PyTorch with CUDA 12.4 — for RIFE 4.18 motion-compensated frame
    # interpolation on the H100 GPU at the fps-normalize step. Verified
    # locally: model loads cleanly, inference returns expected shape,
    # full pipeline (ffmpeg decode -> RIFE -> ffmpeg encode + audio mux)
    # produces correct output. ~3GB wheel.
    .pip_install(
        "torch==2.5.1",
        "torchvision==0.20.1",
        extra_options="--index-url https://download.pytorch.org/whl/cu124",
    )
    .run_commands(
        # Clone Practical-RIFE — provides the support modules
        # (model/warplayer.py, model/loss.py) that RIFE_HDv3.py and
        # IFNet_HDv3.py import via `from model.warplayer import warp`
        # and `from model.loss import *`.
        "git clone --depth 1 https://github.com/hzwer/Practical-RIFE.git /opt/rife",
        "mkdir -p /opt/rife/train_log",
    )
    # Bundle pre-verified RIFE 4.18 files (downloaded locally via gdown
    # from Practical-RIFE README's official Drive URL, then unpacked).
    # gitignored locally — bundled into the image via add_local_file so
    # the build is reproducible without runtime downloads.
    .add_local_file(
        "models/rife-v4.18/RIFE_HDv3.py",
        "/opt/rife/train_log/RIFE_HDv3.py",
        copy=True,
    )
    .add_local_file(
        "models/rife-v4.18/IFNet_HDv3.py",
        "/opt/rife/train_log/IFNet_HDv3.py",
        copy=True,
    )
    .add_local_file(
        "models/rife-v4.18/refine.py",
        "/opt/rife/train_log/refine.py",
        copy=True,
    )
    .add_local_file(
        "models/rife-v4.18/flownet.pkl",
        "/opt/rife/train_log/flownet.pkl",
        copy=True,
    )
    .run_commands(
        # Build-time validation: import Model, load weights, run a dummy
        # 256x256 inference on CPU. Catches missing files / wrong arch /
        # API changes at build time instead of crashing on the first
        # production render. The build container has no GPU so this
        # exercises the CPU code path; CUDA path is structurally identical
        # (same Model class, same load_model, same inference) and only
        # differs in `.to(device)` placement.
        "cd /opt/rife && python -c \""
        "import sys; sys.path.insert(0, '/opt/rife');"
        "import torch;"
        "from train_log.RIFE_HDv3 import Model;"
        "m = Model();"
        "m.load_model('/opt/rife/train_log', -1);"
        "m.eval();"
        "img0 = torch.randn(1, 3, 256, 256);"
        "img1 = torch.randn(1, 3, 256, 256);"
        "out = m.inference(img0, img1, 0.5);"
        "assert tuple(out.shape) == (1, 3, 256, 256), f'wrong shape: {out.shape}';"
        "print('[rife-build] model loaded + inference verified');"
        "print('[rife-build] flownet.pkl size:', __import__('os').path.getsize('/opt/rife/train_log/flownet.pkl'));"
        "\"",
    )
    .add_local_dir("src/assets/fonts", "/assets/fonts", copy=True)
    .run_commands(
        # Register fonts system-wide for both Remotion (Chromium) and FFmpeg libass.
        # Every font the 66-component pack references via @remotion/google-fonts/*
        # (those imports are aliased to our no-op shim in prebundle.mjs) MUST be
        # resolvable by fontconfig here, or Chromium will render in a generic
        # sans-serif fallback and the visual identity of each caption style / MG
        # collapses. Fails the build if any required family is missing.
        "cp /assets/fonts/*.ttf /usr/share/fonts/truetype/ && fc-cache -f",
        (
            "for family in Anton 'Caveat Brush' 'Cormorant Garamond' 'DM Sans' "
            "'DM Serif Display' Inter 'JetBrains Mono' Lora Montserrat Oswald "
            "'Playfair Display' Poppins Roboto 'Space Mono' Teko; do "
            "  if ! fc-list | grep -q \"$family\"; then "
            "    echo \"[font-verify] MISSING: $family not registered with fontconfig\" >&2; "
            "    exit 1; "
            "  fi; "
            "done && echo '[font-verify] all 15 required font families registered'"
        ),
    )
    # Remotion: copy source, install deps, download Chromium, pre-bundle
    .add_local_dir("src/remotion", "/remotion", copy=True)
    .run_commands(
        "cd /remotion && npm install 2>&1 | tail -5",
        # Remove macOS Chrome cache copied from local machine, then download Linux version
        "rm -rf /remotion/node_modules/.remotion 2>/dev/null || true",
        # Download Chrome Headless Shell via Remotion's Node API (more reliable than CLI)
        "cd /remotion && node -e \""
        "const {ensureBrowser} = require('@remotion/renderer');"
        "ensureBrowser().then(()=>console.log('[remotion] Browser downloaded OK'))"
        ".catch(e=>{console.error('[remotion] Browser download failed:', e.message); process.exit(1)})"
        "\"",
        # Find and symlink the Chrome binary for reliable runtime discovery
        "CHROME_BIN=$(find / -path '*/node_modules/.remotion/*' -name 'chrome-headless-shell' -type f 2>/dev/null | grep linux | head -1) && "
        "if [ -z \"$CHROME_BIN\" ]; then CHROME_BIN=$(find / -name 'chrome-headless-shell' -type f 2>/dev/null | head -1); fi && "
        "if [ -n \"$CHROME_BIN\" ]; then ln -sf \"$CHROME_BIN\" /usr/local/bin/chrome-headless-shell && "
        "echo \"[remotion] Chrome symlinked: $CHROME_BIN\"; "
        "else echo '[remotion] WARNING: Chrome binary not found'; fi",
        'cd /remotion && node -e "require(\'@remotion/renderer\'); console.log(\'[remotion] renderer OK\')"',
        "cd /remotion && node prebundle.mjs",
    )
    # Build identification — placed AFTER the heavy install/run_commands
    # layers but BEFORE the add_local_* layers (Modal forbids any build
    # step after add_local_*). A SHA bump invalidates only the final layers,
    # which already rebuild on every source change. Handler reads these at
    # job start and logs them as line 1 of every render's output.
    .env({
        "PROMPTLY_BUILD_SHA": _BUILD_SHA,
        "PROMPTLY_BUILD_DIRTY": _BUILD_DIRTY,
        "PROMPTLY_BUILD_TS": _BUILD_TS,
    })
    .add_local_dir("src/assets/sounds", "/assets/sounds")
    .add_local_file("handler.py", "/handler.py")
    .add_local_file("ffmpeg_base.py", "/ffmpeg_base.py")
    .add_local_file("rife_normalize.py", "/rife_normalize.py")
    .add_local_file("render_schemas.py", "/render_schemas.py")
    .add_local_file("cuda_driver_setup.py", "/cuda_driver_setup.py")
)

# ── Secrets ────────────────────────────────────────────────────────────────────
secrets = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
]

# ── App ────────────────────────────────────────────────────────────────────────
app = modal.App("promptly-gpu-worker", image=image, secrets=secrets)

# ── Prewarm cache volume ───────────────────────────────────────────────────────
# Stores source videos downloaded via the /prewarm endpoint, keyed by a hash
# of the S3 bucket+key. When the real render job runs and finds its source in
# this volume, it skips the S3 download entirely (saving ~5-15s depending on
# file size and network). Volume is eventually consistent — commit/reload on
# both ends keeps it coherent across containers.
prewarm_volume = modal.Volume.from_name("promptly-prewarm-cache", create_if_missing=True)

# ── Web endpoint ───────────────────────────────────────────────────────────────
@app.cls(
    timeout=600,          # 10 min — orchestrator runs init + audio + remotion + composite + upload
    scaledown_window=30,  # tear down fast — at $8.27/hr full spec, idle scaledown was costing ~$0.69 per render (83% of total bill). 30s window catches back-to-back jobs without paying for long idle.
    cpu=64,
    memory=131072,        # 128GB — Remotion overlay + Remotion micro-segments run in parallel here, plus per-cut numpy audio resampler, plus the big single-pass ffmpeg composite
    # No GPU on the orchestrator — moved to the dedicated rife_normalize_remote
    # function below. The orchestrator does Remotion (Chromium software paint),
    # ffmpeg libx264 ultrafast on 64 cores, audio numpy work, and network I/O.
    # All CPU/memory-bound. Paying H100 rates for the ~35-50s of non-GPU work
    # in each render was costing ~$0.04 of pure waste per render. NVDEC decode
    # falls back to software automatically (handler.py _HAS_HWACCEL stays False).
    region="us-west",     # colocate with Supabase (West US) for minimal network latency
    volumes={"/prewarm": prewarm_volume},
)
class PromptlyWorker:
    @modal.enter()
    def startup(self):
        """Import handler at container startup, not per-request. Saves ~10-12s
        of Python import overhead (opencv, numpy, google-genai, deepgram, etc.)
        that was being paid on EVERY request even on warm containers."""
        import sys
        sys.path.insert(0, "/")
        from handler import handler as _h
        self._handler = _h
        self._prewarm_volume = prewarm_volume

    @modal.fastapi_endpoint(method="POST")
    def run_job(self, body: dict):
        # Refresh the prewarm volume view so recently-committed sources are
        # visible even if another container did the prewarm. ~50ms when new
        # data is available; free when nothing changed.
        try:
            self._prewarm_volume.reload()
        except Exception:
            pass
        result = self._handler({"input": body})
        return result


# ── Prewarm CPU worker (split off from the GPU render worker) ─────────────────
# Prewarm is pure I/O — S3 download + Deepgram URL call. It has zero use for
# an H100; running it on the GPU class was costing $3.95/hr while doing
# nothing GPU-shaped. This dedicated CPU-only class scales to zero when idle
# (no min_containers) — first prewarm after a quiet period eats a 3-5s cold
# start, but subsequent prewarms within scaledown_window reuse the warm
# container. The user is still mid-upload to S3 when prewarm fires, so a
# few seconds of cold start is invisible.
@app.cls(
    timeout=300,          # 5 min is plenty for an S3 download + Deepgram call
    scaledown_window=600, # stay warm 10 min after last request; idles to zero after
    cpu=8,                # enough to run boto3 CRT multipart + Deepgram in parallel
    memory=4096,          # 4GB for in-flight download buffers + transcript JSON
    region="us-west",     # same region as the S3 bucket + render class
    volumes={"/prewarm": prewarm_volume},
    # NOTE: no min_containers — class scales to zero when idle. This is the
    # primary always-on cost killer (~$35/mo saved vs min_containers=1).
)
class PromptlyPrewarmWorker:
    @modal.enter()
    def startup(self):
        import sys
        sys.path.insert(0, "/")
        # Only need prewarm_handler — no reason to import the full pipeline here.
        from handler import prewarm_handler as _p
        self._prewarm = _p
        self._prewarm_volume = prewarm_volume

    @modal.fastapi_endpoint(method="POST")
    def prewarm(self, body: dict):
        """Lightweight S3→Volume cache warm-up. Called by iOS the moment the
        client-side upload to S3 finishes (well before the user taps Send).
        By the time the real render request arrives, the source is on the
        Modal Volume and the download step is a no-op.
        """
        result = self._prewarm({"input": body})
        try:
            self._prewarm_volume.commit()
        except Exception as e:
            print(f"[prewarm] volume commit failed: {e}", flush=True)
        return result


# ── RIFE GPU function ─────────────────────────────────────────────────────────
# Stateless H100-backed function that the CPU orchestrator calls when a source
# needs frame interpolation. Splitting RIFE off lets the orchestrator drop its
# H100 — the orchestrator does Remotion + ffmpeg + audio (all CPU/memory) for
# 60s, but only ~5-15s of that needs the GPU. Paying H100 rates for the full
# 60s on every render was the main cost driver.
#
# Pricing: H100 + 4 CPU + 16 GB ≈ $4.13/hr. A typical RIFE call is 5-15s + a
# 15-20s cold start when the function isn't warm. With scaledown_window=30,
# back-to-back renders (within 30s) reuse the warm GPU container and pay only
# the 5-15s exec time.
@app.function(
    gpu="H100",
    cpu=4,
    memory=16384,
    # 90s scaledown so a prewarm spawn (fired the moment iOS upload completes)
    # keeps the GPU container warm long enough to absorb the user's typical
    # decision delay before tapping "render". 30s was tight — covered back-to-
    # back renders only. 90s reliably covers prewarm → real render gaps. Each
    # extra 60s of idle warmth costs ~$0.07 of GPU time, but saves 15-20s of
    # critical-path cold start per render — net win.
    scaledown_window=90,
    timeout=480,
    region="us-west",
)
def rife_normalize_remote(source_bytes: bytes, target_fps: int, warmup: bool = False) -> bytes:
    """Interpolate a video to `target_fps` via RIFE 4.18 on H100.

    Input/output are full mp4 bytes. Internally writes to /tmp, runs the
    same /rife_normalize.py script the orchestrator used to call locally,
    reads the output back. Forwards `[rife] ...` log lines so the GPU
    container's logs match what the orchestrator used to print.

    `warmup=True` mode runs the CUDA driver fix + a tiny torch CUDA probe
    and returns immediately (no real RIFE work). Used by PromptlyPrewarmWorker
    to provision the GPU container the moment iOS uploads complete, so the
    real RIFE call ~30-60s later hits a warm container instead of paying
    a 15-20s cold start on the critical path.

    Raises RuntimeError with rc + last 3000 chars of stderr on failure
    (preserves the diagnostics added when chasing the SIGSEGV).
    """
    import os
    import subprocess
    import sys
    import tempfile

    # Modal's NVIDIA driver mount leaves 0-byte stubs at the SONAME paths
    # (libcuda.so / libcuda.so.1) and ships forward-compat libs at version
    # 560.35.05 in /usr/local/cuda*/compat that ABI-mismatch the real 580
    # driver. The setup helper replaces stubs with proper symlinks and
    # excludes compat from LD_LIBRARY_PATH. Idempotent — kept symlinks
    # return immediately, so calling on every invocation is cheap.
    if "/" not in sys.path:
        sys.path.insert(0, "/")
    from cuda_driver_setup import setup_cuda_driver_mount
    setup_cuda_driver_mount()

    if warmup:
        # Provision the container, run the driver-mount fix, do a tiny
        # torch CUDA probe to force CUDA init + libcuda resolution, then
        # return. Real RIFE work skipped. The container stays warm for
        # scaledown_window so the next real call reuses it.
        _r = subprocess.run(
            ["python", "-c",
             "import torch; "
             "assert torch.cuda.is_available(), 'cuda not available'; "
             "_ = torch.zeros(4, device='cuda') + 1.0; "
             "torch.cuda.synchronize(); "
             "print('[rife-warmup] cuda OK on', torch.cuda.get_device_name(0), flush=True)"],
            capture_output=True, text=True, timeout=60,
        )
        for _line in (_r.stdout or "").splitlines():
            if _line.strip():
                print(_line, flush=True)
        if _r.returncode != 0:
            print(f"[rife-warmup] cuda probe failed: {(_r.stderr or '')[:500]}", flush=True)
        return b""

    with tempfile.TemporaryDirectory(prefix="rife-") as work:
        src = os.path.join(work, "src.mp4")
        out = os.path.join(work, "out.mp4")
        with open(src, "wb") as f:
            f.write(source_bytes)
        r = subprocess.run(
            ["python", "/rife_normalize.py",
             "--input", src,
             "--output", out,
             "--target-fps", str(target_fps),
             "--rife-dir", "/opt/rife"],
            capture_output=True, text=True, timeout=420,
        )
        for _line in (r.stdout or "").splitlines():
            if _line.startswith("[rife]"):
                print(_line, flush=True)
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError(
                f"RIFE remote failed: rc={r.returncode} "
                f"stderr={(r.stderr or '')[-3000:]} "
                f"stdout={(r.stdout or '')[-1500:]}"
            )
        with open(out, "rb") as f:
            return f.read()


# ── Prewarm cache janitor ──────────────────────────────────────────────────────
# Runs daily. Walks the volume, deletes any prewarm cache entry older than 48h.
# Prevents the volume from growing unbounded → protects against Modal Volume
# v1's 500k inode hard cap AND unbounded storage cost. CPU-only function so
# running daily costs effectively nothing.
@app.function(
    schedule=modal.Period(days=1),
    volumes={"/prewarm": prewarm_volume},
    cpu=1,
    memory=1024,
    timeout=600,  # 10 min is plenty; a typical sweep is seconds
)
def prewarm_janitor():
    """Delete prewarm cache entries older than 48 hours."""
    import os
    import time
    import shutil

    TTL_SECONDS = 48 * 3600  # 48 hours
    PREWARM_ROOT = "/prewarm"

    # Pull the latest view of the volume before deciding what to delete.
    try:
        prewarm_volume.reload()
    except Exception as e:
        print(f"[janitor] volume reload failed: {e}", flush=True)

    if not os.path.isdir(PREWARM_ROOT):
        print(f"[janitor] {PREWARM_ROOT} does not exist — nothing to clean", flush=True)
        return {"deleted": 0, "bytes_freed": 0}

    now = time.time()
    deleted_count = 0
    bytes_freed = 0
    inspected = 0
    errors = 0

    for entry in os.listdir(PREWARM_ROOT):
        entry_path = os.path.join(PREWARM_ROOT, entry)
        inspected += 1
        try:
            if not os.path.isdir(entry_path):
                continue
            # Use directory mtime — bumped on file creation within, so new
            # writes "refresh" the entry's freshness.
            age = now - os.path.getmtime(entry_path)
            if age < TTL_SECONDS:
                continue
            # Sum bytes before delete for reporting
            entry_bytes = 0
            for root, _dirs, files in os.walk(entry_path):
                for f in files:
                    try:
                        entry_bytes += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            shutil.rmtree(entry_path)
            deleted_count += 1
            bytes_freed += entry_bytes
        except Exception as e:
            errors += 1
            print(f"[janitor] error on {entry}: {e}", flush=True)

    try:
        prewarm_volume.commit()
    except Exception as e:
        print(f"[janitor] volume commit failed: {e}", flush=True)

    freed_mb = bytes_freed / 1024 / 1024
    print(
        f"[janitor] sweep complete: inspected={inspected} deleted={deleted_count} "
        f"freed={freed_mb:.1f}MB errors={errors} ttl={TTL_SECONDS}s",
        flush=True,
    )
    return {"deleted": deleted_count, "bytes_freed": bytes_freed, "errors": errors}
