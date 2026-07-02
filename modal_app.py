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
# (3) Base video — clip cuts, simple-zoom clips (SmoothPush / SnapReframe / StepZoom / StageZoom) ported to per-frame `crop` expressions, B-roll cutaways, outro fade — built directly by FFmpeg in one big filter_complex. SmoothPush / SnapReframe / StepZoom / StageZoom use cubic ease pieces matching the Remotion components exactly.
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
        # libvidstab-dev — the vid.stab library underpinning FFmpeg's
        # vidstabdetect + vidstabtransform filters. We use these for
        # auto-stabilization of handheld phone footage; the older built-in
        # `deshake` filter is too weak for real-world hand shake. vidstab
        # is the same library DaVinci Resolve and Final Cut use under the
        # hood for their Smooth Motion stabilization.
        "apt-get install -y nasm yasm libx264-dev libx265-dev libfdk-aac-dev libmp3lame-dev libopus-dev libvpx-dev libass-dev libfreetype6-dev libfontconfig1-dev libfribidi-dev libharfbuzz-dev libzimg-dev libvidstab-dev git",
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
        "--enable-libzimg --enable-libvidstab "
        "--enable-filter=drawtext --enable-filter=ass --enable-filter=subtitles "
        "--disable-doc --disable-debug --enable-optimizations "
        "&& make -j$(nproc) && make install",
        "ldconfig",
        "which ffmpeg && which ffprobe",
        "ffmpeg -version | head -3",
        "ffmpeg -filters 2>/dev/null | grep drawtext && echo 'DRAWTEXT: OK' || (echo 'DRAWTEXT: MISSING' && ffmpeg -version | head -5 && ffmpeg -filters 2>/dev/null | grep -i 'draw' && exit 1)",
        # zscale required for HDR→SDR tone-mapping at fps-normalize. Without
        # libzimg-backed zscale, iPhone HDR sources render with pink/magenta
        # cast on SDR playback (BT.2020/HLG tags pass through to BT.709 output).
        "ffmpeg -filters 2>/dev/null | grep -E '\\bzscale\\b' && echo 'ZSCALE: OK' || (echo 'ZSCALE: MISSING — HDR tone-mapping will fail' && exit 1)",
        "ffmpeg -filters 2>/dev/null | grep -E '\\btonemap\\b' && echo 'TONEMAP: OK' || echo 'TONEMAP: MISSING'",
        # vidstab is REQUIRED — auto-stabilization for shaky handheld footage
        # depends on vidstabdetect + vidstabtransform. Fail the image build if
        # the FFmpeg configure didn't pick it up.
        "ffmpeg -filters 2>/dev/null | grep -E '\\bvidstabdetect\\b' && echo 'VIDSTABDETECT: OK' || (echo 'VIDSTABDETECT: MISSING — stabilization will fail' && exit 1)",
        "ffmpeg -filters 2>/dev/null | grep -E '\\bvidstabtransform\\b' && echo 'VIDSTABTRANSFORM: OK' || (echo 'VIDSTABTRANSFORM: MISSING — stabilization will fail' && exit 1)",
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
        # google-genai is pinned to a known-good range. The previous floating
        # spec ("google-genai") would let pip resolve breaking minor versions
        # at any rebuild — exactly the failure mode that bit us with Deepgram
        # (keywords→keyterm) and pyannote (use_auth_token→token). Same class
        # of bug, same fix: pin to a tested range.
        "google-genai>=1.0,<2",
        # 3.8.0+ adds Nova-3 keyterm prompting (PrerecordedOptions.keyterm).
        # 3.4.0 was rejecting the keyterm kwarg with
        # `TypeError: PrerecordedOptions.__init__() got an unexpected keyword
        # argument 'keyterm'` — handler.py:_deepgram_options has been
        # passing keyterm for Nova-3 since the Nova-2 → Nova-3 switch.
        # Capped below 4.0 because 4.x is a major version with breaking
        # changes to the listen-streaming API surface; the prerecorded
        # surface we use is stable across the 3.x line and 3.8 → 3.10 is
        # a minor-feature bump only.
        "deepgram-sdk>=3.8.0,<4.0",
        "supabase",
        "boto3[crt]",   # AWS Common Runtime — 2-6× S3 throughput vs stock boto3
        "httpx",
        "fastapi",
        # pydantic v2 syntax (BaseModel + ConfigDict) is used throughout
        # render_schemas.py and the handler. Pin to v2 so a future pip
        # resolve doesn't drop us into a hypothetical v3 with breaking
        # API changes — same class of bug as the Deepgram/pyannote ones.
        "pydantic>=2,<3",
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
        "torchaudio==2.5.1",
        extra_options="--index-url https://download.pytorch.org/whl/cu124",
    )
    # Single-ASR architecture (Deepgram Nova-3 only) as of 2026-05-23.
    # The previous stack of Whisper-large-v3 + wav2vec2 forced alignment +
    # speaker-label merge was removed — it produced more failures
    # (hallucinated word positions, duplicate transcriptions, over-
    # extended boundaries) than its marginal accuracy gain justified.
    # Deepgram alone gives word timing, speakers, and punctuation in one
    # API call with no hallucination/duplication failure modes. Proper-
    # noun accuracy is boosted via the `keywords` parameter (extracted
    # from the user's vibe text at job time).
    #
    # Silero VAD for amplitude-based silence detection on the actual
    # audio waveform. Replaces the previous transcript-word-gap heuristic
    # for dead_air cuts. Word boundaries mark phoneme ends — they're 200-
    # 300ms off from where audio actually drops to silence. Silero VAD is
    # a 2MB neural model that classifies speech/silence per 30ms chunk
    # with 97% ROC-AUC (vs WebRTC's 73%); it correctly distinguishes
    # natural breath/lip noise from true dead air. Industry standard for
    # auto-editors (Captions.ai, Auto-Editor, FireCut, Premiere all use
    # amplitude/VAD signals — never transcript gaps).
    .pip_install("silero-vad>=5.1,<6")
    # pyannote.audio 3.1 — SOTA speaker diarization. Deepgram's per-word and
    # per-utterance speaker labels are unreliable on 2-speaker interview
    # content (frequent mid-utterance speaker swaps, whole-turn misattribution)
    # even on audio where the voices are trivially distinguishable by ear.
    # pyannote runs ECAPA-TDNN embeddings + agglomerative clustering on
    # speaker turns and produces clean segment boundaries; we then override
    # Deepgram's per-word speaker labels by mapping each word's midpoint
    # into the pyannote segment that contains it.
    #
    # The pyannote/speaker-diarization-3.1 + pyannote/segmentation-3.0 models
    # are gated on HuggingFace — the HF_TOKEN env var (provided via the
    # huggingface Modal secret below) is required to download them at first
    # use. Models cache to disk via the standard HF cache so subsequent runs
    # in a warm container reuse them.
    # huggingface_hub MUST be pinned <0.26 — 0.26.0 (Oct 2024) removed the
    # `use_auth_token` argument that pyannote.audio 3.3 still calls
    # internally inside Pipeline.from_pretrained. Without this pin, pip
    # resolves the latest huggingface_hub and every pyannote load fails
    # with "hf_hub_download() got an unexpected keyword argument
    # 'use_auth_token'". 0.25.x is the highest version that still accepts
    # the deprecated arg. Install huggingface_hub BEFORE pyannote so pip
    # doesn't bump it as a transitive dep.
    .pip_install("huggingface_hub>=0.20,<0.26")
    .pip_install("pyannote.audio>=3.3,<4")
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
        # ── Supabase schema overrides for the tier + concurrency gate ──
        # Multi-clip premium concurrency check (handler.py:check_concurrency_gate)
        # reads from these tables. The defaults assumed `user_profiles.user_id`
        # + `jobs`; the actual schema is `profiles.id` (= auth.users.id) +
        # `video_jobs`. These overrides align the worker query to the live
        # schema. PROMPTLY_TIER_COLUMN ("tier"), PROMPTLY_JOB_USER_COLUMN
        # ("user_id"), and PROMPTLY_JOB_STATUS_COLUMN ("status") match the
        # defaults and don't need overrides. Premium values reflect the
        # actual tier vocabulary (no "paid"/"plus" in production — "teams"
        # is the org plan).
        "PROMPTLY_TIER_TABLE": "profiles",
        "PROMPTLY_TIER_USER_COLUMN": "id",
        "PROMPTLY_PREMIUM_VALUES": "pro,teams,premium",
        "PROMPTLY_JOB_TABLE": "video_jobs",
        "PROMPTLY_JOB_ACTIVE_STATUSES": "queued,processing",
        # Durable job-status writes (the progress backbone). Default OFF: flip to
        # "1" ONLY after the video_jobs migration runs (migrations/
        # video_jobs_status.sql) and status ownership is coordinated with the JS
        # server. Off => the worker writes nothing to video_jobs (byte-identical).
        "JOB_STATUS_WRITES_ENABLED": "0",
        # ── Re-edit Layer 3 Phase 2: array-level auto-revert ─────
        # Phase 1 (always on) auto-reverts top-level scalar drift
        # (caption_style / thumbnail_word_index / outro). Phase 2
        # extends auto-revert to anchor-keyed array entries
        # (emphasis_moments, transitions, tight_cut_overlays,
        # broll_clips, text_overlays, motion_graphics,
        # sound_effects, caption_position_changes).
        # Tweak mode only — guided_redraft is log-only in both phases
        # by design (its soft-carry-over contract gives Gemini
        # documented latitude). ROLLBACK: flip to "0" and redeploy if
        # the scope classifier misjudges a legit downstream
        # consequence and reverts a needed change.
        "PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS": "1",
    })
    .add_local_dir("src/assets/sounds", "/assets/sounds")
    .add_local_file("handler.py", "/handler.py")
    # EditPolicy spine (Phase 2). handler.py lazy-imports `edit_policy` only when
    # the per-job/env flag is on; without this entry the flag-on path would hit
    # ModuleNotFoundError (caught + disabled per-job, but the feature wouldn't run).
    .add_local_file("edit_policy.py", "/edit_policy.py")
    # Premium-tier scaffold (Phase 1). handler.py lazy-imports `premium` at the
    # tier fork; mounted so the flag-on premium path can import it (guarded —
    # absence falls back to the base path, never a crash).
    .add_local_file("premium.py", "/premium.py")
    .add_local_file("ffmpeg_base.py", "/ffmpeg_base.py")
    .add_local_file("rife_normalize.py", "/rife_normalize.py")
    .add_local_file("render_schemas.py", "/render_schemas.py")
    # Leaf module — canonical component-type frozensets shared between
    # handler.py + render_schemas.py. Both import from here; without
    # this entry the container starts and immediately crashes on
    # `ModuleNotFoundError: No module named 'type_registries'`.
    .add_local_file("type_registries.py", "/type_registries.py")
    .add_local_file("cuda_driver_setup.py", "/cuda_driver_setup.py")
    # recipe_eval.py was missing from this list since the eval was first
    # wired — handler.py imports it at runtime via `from recipe_eval
    # import evaluate_recipe`, but the module never made it into the
    # image, so every render logged
    # `[recipe-eval] error: No module named 'recipe_eval'` and the
    # rules (dead-zone, tight-no-mask, zoom-arc, payoff-commitment,
    # tight-boundary) never ran in production. Adding it here.
    .add_local_file("recipe_eval.py", "/recipe_eval.py")
)

# ── Secrets ────────────────────────────────────────────────────────────────────
secrets = [
    # promptly-secrets carries HF_TOKEN for pyannote.audio gated model
    # downloads (pyannote/speaker-diarization-3.1 + pyannote/segmentation-3.0)
    # alongside the other API keys. When HF_TOKEN is unset or empty,
    # diarize_with_pyannote falls back to Deepgram's native speaker labels
    # with a warning.
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    # Vertex AI creds — GCP_SERVICE_ACCOUNT_JSON + GOOGLE_CLOUD_PROJECT +
    # GOOGLE_CLOUD_LOCATION. When present, _get_genai_client routes the editorial
    # Gemini call through Vertex (scalable per-project quota) instead of the
    # single AI Studio key. Falls back to GEMINI_API_KEY when these are absent.
    modal.Secret.from_name("gemini-vertex"),
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
    timeout=900,          # 15 min — orchestrator runs init + audio + remotion + composite + upload. Raised from 600 (2026-06-21) to keep ~420s of buffer for non-Gemini work after the Gemini client timeout was raised to 480s (handler.py:_get_genai_client) to accommodate thinking_budget=60000's worst-case wall-clock (~337s). If Gemini took 480s and Modal capped at 600s, only 120s remained for download/render/composite/upload — render alone routinely needs 30-90s. 900s gives comfortable margin; jobs that don't hit Gemini's cap (the typical case) cost the same as before since billing is per-active-second, not per-cap.
    scaledown_window=180, # 3 min — covers the warmup() (fired at upload-start) →
                          # run_job gap so the FIRST render after idle hits a warm
                          # container (no cold start), plus back-to-back jobs. At
                          # A100 rates (~$2.78/hr, down from H100's $8.27) the
                          # extra idle warmth is ~$0.12/render — cheap vs paying a
                          # 15-30s cold start on the user's critical path.
    # NO GPU — the orchestrator does NO GPU work on the critical path. NVENC +
    # CUDA decode are hardcoded off (_HAS_NVENC/_HAS_HWACCEL=False → CPU libx264
    # encode, CPU decode, CPU minterpolate); the Remotion render is Chromium-on-
    # CPU; Deepgram transcription is a CLOUD call; rife_normalize_remote is DEAD
    # CODE. The ONLY local GPU consumer was pyannote diarization — and it runs
    # ONLY when Deepgram detects >=2 speakers (handler.py ~18147), a minority of
    # short-form talking-head jobs. So an A100/H100 was held for the FULL render
    # on 100% of jobs but used on a fraction, capping parallelism at the account's
    # scarce concurrent-GPU quota (renders QUEUED waiting for a free GPU — the
    # recurring "not running in parallel" bug, unfixed by H100->A100 because A100
    # is still GPU-quota-limited). CPU-only removes that ceiling entirely: renders
    # provision from abundant CPU capacity and parallelize freely. Multi-speaker
    # pyannote falls back to CPU on this 64-core host via its existing path
    # (_load_pyannote: .to("cuda") fails with no GPU -> runs on CPU). If CPU
    # diarization proves too slow for multi-speaker jobs, split pyannote into a
    # short-lived small-GPU function (so the long CPU render never holds a GPU).
    cpu=64,
    memory=131072,        # 128GB — Remotion overlay + Remotion micro-segments run in parallel here, plus per-cut numpy audio resampler, plus the big single-pass ffmpeg composite
    region=["us-west", "us-east"],  # prefer us-west colocated with Supabase,
                                     # fall back to us-east when Modal lacks
                                     # 64-CPU/128GB capacity in us-west.
                                     # Cross-region S3 download adds ~0.5-1s
                                     # vs render never starting at all.
    volumes={"/prewarm": prewarm_volume},
)
class PromptlyWorker:
    @modal.enter()
    def startup(self):
        """Import handler at container startup, not per-request. Saves ~10-12s
        of Python import overhead (opencv, numpy, google-genai, deepgram, etc.)
        that was being paid on EVERY request even on warm containers.

        This worker is CPU-ONLY (no GPU — see the @app.cls note). The CUDA
        driver-mount fix is therefore unnecessary; it's kept GUARDED only so a
        no-GPU startup can never break (the helper is already defensive — it
        logs 'nvidia-smi failed' and continues when no GPU is present). pyannote
        diarization (multi-speaker jobs only) runs on CPU here."""
        import sys
        sys.path.insert(0, "/")
        try:
            from cuda_driver_setup import setup_cuda_driver_mount
            setup_cuda_driver_mount()
        except Exception as _cuda_e:
            print(f"[startup] CUDA setup skipped (CPU-only worker): {_cuda_e}", flush=True)
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

    @modal.fastapi_endpoint(method="POST")
    def warmup(self, body: dict):
        """Provision the render container the moment iOS upload BEGINS, so the
        real run_job ~10-90s later hits a WARM container instead of paying the
        cold start (handler import + A100 alloc + CUDA driver setup, ~15-30s on
        the critical path). @modal.enter() already ran on spin-up (the heavy
        import + CUDA driver fix); this endpoint just forces a container to
        exist and keeps it warm for scaledown_window. Fire-and-forget from the
        app server at upload-start — mirrors PromptlyPrewarmWorker hiding the
        CPU prework behind the upload, but for the GPU render container.
        Idempotent and ~free; the value is the side effect of a warm container."""
        cuda = False
        try:
            import torch
            cuda = bool(torch.cuda.is_available())
        except Exception:
            pass
        return {"ok": True, "warm": True, "cuda": cuda}


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


# ── Validator: fast pre-upload talking-head check ────────────────────────────
# iOS calls this BEFORE committing to the full upload + render. iOS extracts
# a small 5-second sample of the user's video, uploads it to S3, then POSTs
# the sample URL here. The validator downloads the sample (~1-2s), runs face
# detection (~1-2s), and returns is_talking_head: bool.
#
# This catches non-talking-head uploads in 3-7s of user wait instead of the
# 30-60s the full pipeline would take. Combined with iOS on-device Vision-
# framework pre-check (sub-second), users get instant feedback on whether
# their video can be edited.
#
# CPU-only, scales to zero when idle. Validation is pure I/O + OpenCV face
# detection (no GPU, no Gemini, no Deepgram). Cheap to keep online.
@app.cls(
    timeout=60,           # Sample download + face detect < 10s; 60s leaves headroom
    scaledown_window=300, # Stay warm 5 min after last request
    cpu=4,                # Concurrent sample downloads + face detection
    memory=2048,          # 2GB plenty for in-memory video buffers
    region="us-west",     # Same region as the S3 bucket
)
class PromptlyValidator:
    @modal.enter()
    def startup(self):
        """Import validate_handler at container start (not per-request).
        Saves ~5-8s of OpenCV + boto3 import cost on every validation call.
        """
        import sys
        sys.path.insert(0, "/")
        from handler import validate_handler as _v
        self._validate = _v

    @modal.fastapi_endpoint(method="POST")
    def validate(self, body: dict):
        """Fast pre-upload validation: is this a talking-head video?

        Expected body:
          {"sample_url": "https://<bucket>.<region>.amazonaws.com/.../sample.mp4"}

        Response:
          {
            "is_talking_head": bool,
            "confidence": float (0-1),
            "face_ratio": float (0-1),
            "face_samples": int,
            "reason": str,
            "user_message": str | null   # null when valid; rejection text when not
          }

        iOS uses `is_talking_head` to decide whether to proceed with the
        full upload. When false, `user_message` is the text to show the
        user with a "Choose Different Video" button.
        """
        return self._validate({"input": body})


# ── Diagnostic: inspect an S3 upload's actual state in real time ─────────────
# When iOS shows "uploading video" forever and then fails, this endpoint tells
# us EXACTLY what S3 sees right now: object exists, multipart in progress,
# zero parts uploaded, parts stalled, etc. Use during a failing upload to
# diagnose which iOS-side step is broken without guessing.
#
# Curl example (run while iOS shows "uploading"):
#   curl -X POST https://...promptlydiagnoseupload-diagnose.modal.run \
#     -H 'Content-Type: application/json' \
#     -d '{"bucket":"thisismybucketagainwooo","key":"sources/<user>/<file>.mp4"}'
@app.cls(
    timeout=30,
    scaledown_window=300,
    cpu=2,
    memory=1024,
    region="us-west",
)
class PromptlyDiagnoseUpload:
    @modal.enter()
    def startup(self):
        import sys
        sys.path.insert(0, "/")
        from handler import diagnose_upload_handler as _d
        self._diagnose = _d

    @modal.fastapi_endpoint(method="POST")
    def diagnose(self, body: dict):
        """Inspect the live S3 state for a specific bucket/key.

        Expected body:
          {"bucket": "<bucket-name>", "key": "<object-key>"}

        Response includes `diagnosis` field with human-readable interpretation
        of what stage the upload is at (or failed at). See handler's
        diagnose_upload_handler for the full schema.
        """
        return self._diagnose({"input": body})


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


# ── Sub-step 1 test entry: generated-image quality gate (INERT) ─────────────
# Standalone harness so Zac can eyeball raw Nano Banana Pro output BEFORE any
# pipeline wiring. NOT called by any job — it exists only to render the
# aesthetic gate. Generates N sample images, uploads them to S3 under
# test-gen/, and returns presigned GET URLs (24h) so they're viewable.
# Gets app-level secrets (gemini-vertex, AWS) automatically.
@app.function(cpu=2, memory=4096, timeout=600)
def generate_test_images_remote(prompts=None, n=3):
    import os
    import sys
    import uuid
    import tempfile

    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler

    _prompts = prompts or handler._TEST_IMAGE_PROMPTS[:n]
    _s3 = handler._aws_s3_client
    if _s3 is None:
        raise RuntimeError("AWS S3 client not configured in handler — cannot publish test images")
    _bucket = (
        os.environ.get("S3_BUCKET_NAME")
        or os.environ.get("SUPABASE_S3_BUCKET")
        or "promptly-video-storage"
    )

    urls = []
    with tempfile.TemporaryDirectory(prefix="gentest-") as work:
        paths = handler._generate_test_images(work, prompts=_prompts)
        for p in paths:
            key = "test-gen/" + uuid.uuid4().hex + ".png"
            _s3.upload_file(p, _bucket, key, ExtraArgs={"ContentType": "image/png"})
            url = _s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": _bucket, "Key": key},
                ExpiresIn=86400,
            )
            urls.append(url)
            print(f"[image-gen] uploaded s3://{_bucket}/{key} -> presigned (24h)", flush=True)
    return urls


@app.local_entrypoint()
def gen_test_images(n: int = 3):
    """Invoke with:  modal run modal_app.py::gen_test_images
    Prints presigned URLs for the generated sample images (the aesthetic gate)."""
    urls = generate_test_images_remote.remote(n=n)
    print("\n=== GENERATED TEST IMAGE URLs (valid 24h) ===")
    for u in urls:
        print(u)
    print("=== END ===\n")


# ── Craft-floor A/B battery: FLOOR (_IMAGE_SYSTEM_PROMPT) vs RAW pass-through ─
# Renders LEAN per-scene briefs — the minimal phrasing Gemini might write — each
# TWICE: once with system_instruction=None (the standing craft floor) and once
# with system_instruction="" (raw, the old pass-through). The delta between the
# two columns IS what the floor contributes. Lean-on-purpose: fully art-directed
# prompts would already contain the craft and hide the floor's effect. Zac
# eyeballs floor-vs-raw side by side and tunes _IMAGE_SYSTEM_PROMPT across a few
# rounds. NOT called by any job.
_COMPARE_BRIEFS = [
    {
        "slug": "product",
        "brief": "A wireless earbud charging case, lid closed.",
    },
    {
        "slug": "padlock-concept",
        "brief": "A closed padlock — the 'restrictions' beat.\n\nPalette "
                 "(the video's committed color world): deep indigo night — "
                 "anchor colors #10132b, #2b3f8c, #e8c15a. Build the whole "
                 "image within it.",
    },
    {
        "slug": "app-ui",
        "brief": "A fitness tracking app dashboard on a phone.",
    },
    {
        "slug": "branded-title",
        "brief": "A title card for a video about morning routines.\n\nPalette "
                 "(the video's committed color world): warm sunrise cream — "
                 "anchor colors #f7efe1, #e8a24c, #3a2f26. Build the whole "
                 "image within it.",
    },
]


@app.function(cpu=2, memory=4096, timeout=900)
def gen_floor_compare_remote(briefs=None):
    import os
    import sys
    import uuid
    import tempfile

    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler

    _briefs = briefs or _COMPARE_BRIEFS
    _s3 = handler._aws_s3_client
    if _s3 is None:
        raise RuntimeError("AWS S3 client not configured in handler — cannot publish compare images")
    _bucket = (
        os.environ.get("S3_BUCKET_NAME")
        or os.environ.get("SUPABASE_S3_BUCKET")
        or "promptly-video-storage"
    )

    def _publish(path):
        key = "test-gen/floor-compare/" + uuid.uuid4().hex + ".png"
        _s3.upload_file(path, _bucket, key, ExtraArgs={"ContentType": "image/png"})
        return _s3.generate_presigned_url(
            "get_object", Params={"Bucket": _bucket, "Key": key}, ExpiresIn=86400,
        )

    results = []
    with tempfile.TemporaryDirectory(prefix="floorcmp-") as work:
        for _b in _briefs:
            slug = _b["slug"]
            brief = _b["brief"]
            row = {"slug": slug, "brief": brief}
            # FLOOR: system_instruction=None → the standing _IMAGE_SYSTEM_PROMPT.
            try:
                fp = os.path.join(work, f"{slug}_floor.png")
                handler._generate_image(brief, out_path=fp)  # None default = floor
                row["floor_url"] = _publish(fp)
                row["floor_ok"] = True
            except Exception as e:
                row["floor_ok"] = False
                row["floor_err"] = f"{type(e).__name__}: {str(e)[:300]}"
                print(f"[floor-compare] {slug} FLOOR failed: {row['floor_err']}", flush=True)
            # RAW: system_instruction="" → no floor (the old pass-through).
            try:
                rp = os.path.join(work, f"{slug}_raw.png")
                handler._generate_image(brief, out_path=rp, system_instruction="")
                row["raw_url"] = _publish(rp)
                row["raw_ok"] = True
            except Exception as e:
                row["raw_ok"] = False
                row["raw_err"] = f"{type(e).__name__}: {str(e)[:300]}"
                print(f"[floor-compare] {slug} RAW failed: {row['raw_err']}", flush=True)
            results.append(row)
            print(f"[floor-compare] {slug}: floor_ok={row.get('floor_ok')} raw_ok={row.get('raw_ok')}", flush=True)
    return results


@app.local_entrypoint()
def gen_floor_compare(only: str = ""):
    """modal run modal_app.py::gen_floor_compare [--only <slug>]
    Renders each lean brief FLOOR vs RAW and prints paired presigned URLs (24h).
    --only <slug> renders just that brief (e.g. re-run one after a transient 429).
    This ALSO proves system_instruction is honored by gemini-3-pro-image: the
    floor column returning valid images that differ from raw is the proof."""
    _briefs = None
    if only:
        _briefs = [b for b in _COMPARE_BRIEFS if b["slug"] == only]
        if not _briefs:
            raise SystemExit(f"no brief with slug={only!r}; have "
                             + ", ".join(b["slug"] for b in _COMPARE_BRIEFS))
    rows = gen_floor_compare_remote.remote(briefs=_briefs)
    print("\n=== CRAFT-FLOOR A/B  (FLOOR = _IMAGE_SYSTEM_PROMPT · RAW = old pass-through) ===")
    for r in rows:
        print(f"\n--- {r['slug']} ---")
        print(f"  brief: {r['brief'][:120]!r}")
        print(f"  FLOOR: {r.get('floor_url') or ('FAILED ' + str(r.get('floor_err')))}")
        print(f"  RAW  : {r.get('raw_url') or ('FAILED ' + str(r.get('raw_err')))}")
    print("\n=== END (URLs valid 24h) ===\n")


# ── Sub-step 2: GeneratedScene schema → Vertex acceptance regression (INERT) ─
# Confirms Vertex ACCEPTS the nested-optional GeneratedScene schema
# (response_json_schema). Proven before folding generated_scenes into
# PostCutPlan; kept as a permanent regression check on the real schema. Not
# called by any job.
@app.function(cpu=2, memory=4096, timeout=300)
def validate_genscene_schema_remote():
    import sys
    import json
    import time

    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler

    schema = handler.PostCutPlan.model_json_schema()
    has_field = "generated_scenes" in (schema.get("properties") or {})
    n_defs = len(schema.get("$defs") or {})
    print(f"[genscene-probe] schema built: generated_scenes={has_field} $defs={n_defs}", flush=True)

    client = handler._get_genai_client()
    types = handler.genai_types
    report = {"schema_has_field": has_field, "defs": n_defs}
    t0 = time.time()
    try:
        resp = client.models.generate_content(
            model=handler.GEMINI_EDITORIAL_MODEL,
            contents=[
                "Return a minimal but schema-valid edit plan: fill required scalar "
                "fields with neutral placeholders and use empty arrays for every "
                "list (including generated_scenes). Keep it tiny."
            ],
            config=types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=8000,
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        try:
            txt = resp.text or ""
        except Exception:
            txt = ""
        report["accepted"] = True
        report["elapsed_s"] = round(time.time() - t0, 1)
        report["resp_len"] = len(txt)
        try:
            parsed = json.loads(txt) if txt else {}
            report["parsed_ok"] = True
            report["generated_scenes_in_output"] = "generated_scenes" in parsed
        except Exception as pe:
            report["parsed_ok"] = False
            report["parse_err"] = str(pe)[:200]
        print(f"[genscene-probe] VERTEX ACCEPTED the schema OK {report}", flush=True)
    except Exception as e:
        report["accepted"] = False
        report["error_type"] = type(e).__name__
        report["error"] = str(e)[:700]
        print(f"[genscene-probe] VERTEX REJECTED {type(e).__name__}: {str(e)[:700]}", flush=True)
    return report


@app.local_entrypoint()
def validate_genscene_schema():
    """modal run modal_app.py::validate_genscene_schema"""
    r = validate_genscene_schema_remote.remote()
    print("\n=== GENSCENE SCHEMA / VERTEX ACCEPTANCE ===")
    print(r)
    print("=== END ===\n")


# ── Phase i2v pre-build confirm: Veo 3.1 reachability on Vertex (INERT) ──────
# CHEAP reachability probe — lists models + metadata-`get`s candidate Veo strings.
# Does NOT generate a video (that costs $0.50-1.20). Not called by any job.
@app.function(cpu=2, memory=4096, timeout=300)
def probe_veo_reachable():
    import sys
    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler
    report = {}
    try:
        client = handler._get_genai_client()
        report["has_generate_videos"] = hasattr(client.models, "generate_videos")
        veo_listed = []
        try:
            for _m in client.models.list():
                _nm = str(getattr(_m, "name", "") or "")
                if "veo" in _nm.lower():
                    veo_listed.append(_nm)
        except Exception as _le:
            report["list_error"] = f"{type(_le).__name__}: {str(_le)[:100]}"
        report["veo_listed"] = veo_listed
        candidates = [
            "veo-3.1-generate-preview", "veo-3.1-fast-generate-preview",
            "veo-3.1-generate-001", "veo-3.0-generate-001", "veo-3.0-fast-generate-001",
            "veo-3.0-generate-preview", "veo-2.0-generate-001", "veo-001",
            "publishers/google/models/veo-3.1-generate-preview",
            "publishers/google/models/veo-3.0-generate-001",
        ]
        reachable = {}
        for _c in candidates:
            try:
                _info = client.models.get(model=_c)
                reachable[_c] = "OK:" + str(getattr(_info, "name", _c))
            except Exception as _ge:
                reachable[_c] = f"{type(_ge).__name__}: {str(_ge)[:70]}"
        report["candidates"] = reachable
        print(f"[veo-probe] {report}", flush=True)
    except Exception as e:
        report["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        print(f"[veo-probe] ERROR {report['error']}", flush=True)
    return report


@app.local_entrypoint()
def veo_probe():
    r = probe_veo_reachable.remote()
    print("\n=== VEO 3.1 REACHABILITY (Vertex) ===")
    for k, v in (r or {}).items():
        print(f"{k}: {v}")
    print("=== END ===\n")


# ── Phase D verify: partial_state column exists + round-trips (INERT) ────────
# Confirms the reserved partial_state jsonb column is APPLIED on the jobs table
# (PostgREST silently drops writes to missing columns → ask-back would resume
# from nothing). Existence probe is non-mutating; the round-trip uses a throwaway
# test row it deletes. Not called by any job.
@app.function(cpu=2, memory=2048, timeout=120)
def probe_partial_state():
    import sys
    import os
    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler
    sb = handler.supabase
    table = os.environ.get("PROMPTLY_JOB_TABLE") or "jobs"
    report = {"table": table}
    if sb is None:
        report["error"] = "supabase client not configured on worker"
        print(f"[partial-state-probe] {report}", flush=True)
        return report
    try:
        sb.table(table).select("partial_state,id").limit(1).execute()
        report["column_exists"] = True
    except Exception as e:
        report["column_exists"] = False
        report["existence_error"] = str(e)[:200]
        print(f"[partial-state-probe] COLUMN MISSING — apply migrations/video_jobs_status.sql. {report}", flush=True)
        return report
    # Genuine round-trip on an EXISTING row (non-destructive: partial_state is a
    # brand-new unused column; we restore the original value after).
    _val = {"probe": True, "n": 42, "nested": {"plan": "ok"}}
    try:
        _row = sb.table(table).select("id,partial_state").limit(1).execute()
        if not _row.data:
            report["roundtrip_note"] = "no rows to round-trip on — existence probe is authoritative"
        else:
            _rid = _row.data[0]["id"]
            _orig = _row.data[0].get("partial_state")
            sb.table(table).update({"partial_state": _val}).eq("id", _rid).execute()
            _r2 = sb.table(table).select("partial_state").eq("id", _rid).limit(1).execute()
            _read = _r2.data[0].get("partial_state") if _r2.data else None
            report["roundtrip_value_survived"] = (_read == _val)
            report["roundtrip_read"] = _read
            sb.table(table).update({"partial_state": _orig}).eq("id", _rid).execute()
            report["restored_original"] = True
    except Exception as e:
        report["roundtrip_error"] = f"{type(e).__name__}: {str(e)[:150]}"
    print(f"[partial-state-probe] {report}", flush=True)
    return report


@app.local_entrypoint()
def partial_state_probe():
    r = probe_partial_state.remote()
    print("\n=== partial_state COLUMN VERIFY ===")
    for k, v in (r or {}).items():
        print(f"{k}: {v}")
    print("=== END ===\n")
