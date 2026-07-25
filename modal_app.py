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
# Single-deployer protocol (directive #10): every deploy names its operator.
# deploy.sh exports PROMPTLY_DEPLOYER (claude-code / codex / zac-manual);
# a phantom deploy then identifies itself in the first line of every job.
_DEPLOYER = os.environ.get("PROMPTLY_DEPLOYER", "unknown")

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
# (2) PromptlyMicroSegments (NEW composition) renders ALL registry transitions (CardSwipe / FilmStrip / NewspaperWipe / SlideOver / Stack / CrossfadeZoom / ShutterFlash / StepPush / ZoomThrough / DipToBlack) AND composite-effect zoom clips (FocusWindow / LetterboxPush / DepthPull) in ONE Remotion process — segments concatenated end-to-end so ~10s startup tax amortizes across all of them. h264 (no alpha).
# (3) Base video — clip cuts, simple-zoom clips (SmoothPush / SnapReframe / StepZoom) ported to per-frame `crop` expressions, B-roll cutaways, outro fade — built directly by FFmpeg in one big filter_complex. SmoothPush / SnapReframe / StepZoom use cubic ease pieces matching the Remotion components exactly.
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
        # MULTILINGUAL A1 (universal script coverage): the full Noto family so
        # every script renders with real glyphs instead of tofu — Devanagari,
        # Arabic, Hebrew, Thai, Bengali, Tamil, Cyrillic-extended (fonts-noto-core),
        # CJK (fonts-noto-cjk), and the long tail (fonts-noto-extra). fc-cache
        # (run below with the app fonts) indexes them; libharfbuzz + libfribidi
        # (already installed) shape + bidi them. Zero risk to Latin rendering —
        # purely additive glyph coverage. A2 makes caption font-selection
        # deliberate; fontconfig fallback may start killing tofu before then.
        "fonts-noto-core",
        "fonts-noto-cjk",
        "fonts-noto-extra",
        # UGC captions are full of emoji — without the color-emoji font every 🔥
        # renders tofu the moment the rest of the sheet goes green. Non-negotiable.
        "fonts-noto-color-emoji",
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
        # EAST text detector (burned-in-text guard, burned_text.py). Self-hosted in
        # the app's S3/CloudFront (not a third-party repo) so the build is under our
        # control. Consumed via cv2.dnn exactly like the face detector above.
        "mkdir -p /models/east",
        "wget -q -O /models/east/frozen_east_text_detection.pb https://d1iax8jos987n3.cloudfront.net/models/east/frozen_east_text_detection.pb",
        # verify it landed intact (real .pb is ~96MB — a truncated/HTML fetch fails loud at build, not at runtime)
        "test $(stat -c%s /models/east/frozen_east_text_detection.pb) -gt 90000000 || (echo 'EAST model download failed/truncated' && exit 1)",
        # Pre-cache arnndn noise reduction model (avoids runtime download on every cold start)
        "mkdir -p /usr/share/rnnoise",
        "wget -q -O /usr/share/rnnoise/bd.rnnn https://github.com/GregorR/rnnoise-models/raw/master/beguiling-drafter-2018-08-30/bd.rnnn",
    )
    # FLOOR-HARDENING (2026-07-20): every runtime dep major-capped so a rebuild
    # can't silently resolve a breaking major — the exact class that bit us with
    # opencv 5.x (readNetFromCaffe), and before it Deepgram/pyannote. numpy held
    # on 2.x (the image runs 2.2.6; opencv 4.13 + aubio both numpy-2-compatible).
    .pip_install("numpy>=2,<3", "wheel")
    .pip_install("aubio", extra_options="--no-build-isolation")
    .pip_install(
        "certifi",
        # PINNED <5 (2026-07-19): the unpinned spec resolved to OpenCV 5.x at the
        # A1 image rebuild (dbffe28), and 5.x DROPPED the legacy Caffe importer —
        # `cv2.dnn.readNetFromCaffe` vanished, so detect_face_positions_dense (the
        # face-DNN loader, model files baked in the image) raised AttributeError
        # and terminalized EVERY talking-head render (line 27973 awaits the face
        # future unguarded). Latent since dbffe28 — surfaced by the multilingual
        # cert, not yet hit by a real job. 4.10/4.11 keep readNetFromCaffe AND
        # support numpy 2.x (verified). Same floating-resolve bug the google-genai
        # / deepgram / pydantic pins below already fixed — opencv was the one left.
        "opencv-python-headless>=4.10,<5",
        "requests>=2,<3",
        "anthropic>=0.40,<1",
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
        "supabase>=2,<3",
        "boto3[crt]>=1,<2",   # AWS Common Runtime — 2-6× S3 throughput vs stock boto3
        "httpx>=0.27,<1",
        "fastapi>=0.115,<1",
        # pydantic v2 syntax (BaseModel + ConfigDict) is used throughout
        # render_schemas.py and the handler. Pin to v2 so a future pip
        # resolve doesn't drop us into a hypothetical v3 with breaking
        # API changes — same class of bug as the Deepgram/pyannote ones.
        "pydantic>=2,<3",
        "tqdm>=4,<5",
        "Pillow>=11,<13",
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
        "PROMPTLY_DEPLOYER": _DEPLOYER,
        # ── Operational flags: ALL moved to the promptly-lang-flags Modal Secret ──
        # PROMPTLY_SPAWN_MODE, PROMPTLY_OUTCOME_GATE, PROMPTLY_PLAN_CAPTURE,
        # PROMPTLY_LEVER3, PROMPTLY_EDIT_IN_LANGUAGE, and PROMPTLY_SCRIPT_DENYLIST are
        # NO LONGER baked here. They used to be baked FROM THE DEPLOY SHELL, so a
        # plain `./deploy.sh` that forgot to set them silently reverted them to their
        # code defaults (this happened: multilingual went Latin-only + lever3 turned
        # off for ~40 min). They now live in the promptly-lang-flags Secret (see
        # secrets[] above), injected at runtime — no deploy can revert them. LIVE
        # production values (do NOT "restore" a documented default):
        #   PROMPTLY_LEVER3=1            degeneration-fix editorial prompt (A/B concluded, live)
        #   PROMPTLY_EDIT_IN_LANGUAGE=1  multilingual render + in-language editorial ON
        #   PROMPTLY_SCRIPT_DENYLIST=""  graduated: every font-backed script renders (Arabic → language=ar)
        #   PROMPTLY_SPAWN_MODE=1        spawn dispatch ON (async worker spawn — prevents ASGI starvation; MUST stay 1)
        #   PROMPTLY_OUTCOME_GATE=shadow salvage-schema gate ledgers only, changes nothing
        #   PROMPTLY_PLAN_CAPTURE=""     the plan-capture corpus hook is inert
        # Change any via `modal secret create promptly-lang-flags KEY=val … --force`.
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
        # Durable job-status writes (the progress backbone). ON as of directive
        # #6 (2026-07-02): the never-fails promise is always-deliver OR
        # always-tell, and a job that can do neither (1a72b344 hung a user's
        # screen) is the failure this kills. Writes are FAIL-OPEN: if the
        # video_jobs migration (migrations/video_jobs_status.sql) hasn't run
        # or PostgREST drops a column, the write logs and the job proceeds —
        # never fatal. JS-server status ownership: worker owns
        # processing/needs_input/complete/failed transitions after accept;
        # the app server owns queued/canceled (hand-off note in the PR).
        # ROLLBACK: flip to "0" and redeploy.
        "JOB_STATUS_WRITES_ENABLED": "1",
        # Gap compression (directive #11 B6, Zac-authorized ON in the #11
        # review): kept inter-word pauses above 0.45s compress to 0.30s at
        # the clip-build layer. ROLLBACK: flip to "0" and redeploy.
        "GAP_COMPRESSION_ENABLED": "1",
        # Pacing budget / MAX COMPRESSION (Slice 3, Zac's EAR ruling 2026-07-06):
        # every kept boundary gap collapses to the 75ms safety floor — boundary
        # dead air dies, within-clip speech rhythm (the human breath, plays 1:1)
        # is untouched. This is now the DEFAULT path for every render. Per-job
        # input `pacing_max_compression` still overrides. ROLLBACK: flip to "0".
        "PACING_MAX_COMPRESSION_ENABLED": "1",
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
    # RenderTimeline (unification pillar 3). handler.py imports it inside the
    # shadow block (Slice 1) — bundle it or the shadow silently self-skips.
    .add_local_file("render_timeline.py", "/render_timeline.py")
    # EditPolicy spine (Phase 2). handler.py lazy-imports `edit_policy` only when
    # the per-job/env flag is on; without this entry the flag-on path would hit
    # ModuleNotFoundError (caught + disabled per-job, but the feature wouldn't run).
    .add_local_file("edit_policy.py", "/edit_policy.py")
    # Burned-in-text guard (burned_text.py) — deterministic EAST detector, lazy-
    # imported only under PROMPTLY_BURNED_TEXT. Bundle it or the flag-on path hits
    # ModuleNotFoundError (fail-safe returns None → behaves as today, but the guard
    # wouldn't run). Pairs with the /models/east model wget above.
    .add_local_file("burned_text.py", "/burned_text.py")
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
    # ZERO-REJECT routing machinery (DARK behind PROMPTLY_ZERO_REJECT): the
    # general-editor perception/router + the caption-less minimal/hype editors +
    # the render bridge. handler.py imports these lazily only on the routed path;
    # with the flag off they are never reached (byte-identical talking-head).
    .add_local_file("general_editor.py", "/general_editor.py")
    .add_local_file("hype_editor.py", "/hype_editor.py")
    .add_local_file("minimal_editor.py", "/minimal_editor.py")
    .add_local_file("hype_render.py", "/hype_render.py")
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
    # promptly-lang-flags — PERSISTENT operational flags that must NOT revert on a
    # deploy that forgets to set them. Moved here (2026-07-23) out of the image
    # .env() block, which baked them from the DEPLOYER'S SHELL: a plain
    # `./deploy.sh` silently reverted them to their code defaults (this actually
    # happened — a deploy Latin-only'd multilingual + turned lever3 off for ~1h).
    # As an app-level Secret they're injected into every container at runtime,
    # sourced from Modal's store — independent of the deploy shell. Contents (the
    # live production state — every operational flag that was shell-baked now lives
    # here so NONE can silently revert):
    #   PROMPTLY_EDIT_IN_LANGUAGE=1   multilingual render + in-language editorial ON
    #   PROMPTLY_SCRIPT_DENYLIST=""   graduated: no script denied (Arabic → language=ar)
    #   PROMPTLY_LEVER3=1             degeneration-fix editorial prompt (live, not pending)
    #   PROMPTLY_SPAWN_MODE=1         spawn dispatch ON (async worker spawn — prevents ASGI starvation; MUST stay 1)
    #   PROMPTLY_OUTCOME_GATE=shadow  salvage-schema gate ledgers only, changes nothing
    #   PROMPTLY_PLAN_CAPTURE=""      plan-capture corpus hook inert
    # To change one: `modal secret create promptly-lang-flags KEY=val … --force`
    # (include ALL keys — --force replaces), then redeploy. Never edit code/shell.
    modal.Secret.from_name("promptly-lang-flags"),
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


# ── Background pipeline (reliability spawn refactor, Phase 3) ──────────────────
# The pipeline as a PLAIN function (not a web endpoint), so Modal gives it proper
# retry/auto-migration semantics on preemption — the web endpoint's preemption
# behavior was "unconfirmed" (see the retries note on PromptlyWorker). run_job
# SPAWNS this and returns a call_id in milliseconds instead of holding the ASGI
# worker for the whole pipeline, which is what starved the health probe into the
# 300s GET/ timeouts + the AnyIO shutdown wedge.
#
# Completion delivery (Phase 2 partner): at pipeline end this POSTs the FULL
# result to the app server's /api/modal-complete (worker-controlled, first-hand,
# reliable) → settles the dispatch's pending promise → the completion tail runs.
# The dispatch's Supabase fallback + the reaper are the backstops if this POST is
# ever lost. Same resources as PromptlyWorker (CPU render host).
@app.function(
    # 1800s (30 min) — raised from 900 (2026-07-23) to support 3-minute sources
    # (CLIP_TOO_LONG 120->180s). LOAD-BEARING: the content-studio reaper's
    # EXEC_WALL_MS (job-reaper.js) MUST be >= this at every moment (2100s = this +
    # 300s slack) or a healthy long render gets false-reaped mid-flight. Deploy the
    # reaper raise FIRST, this SECOND. Billing is per-active-second, so short jobs
    # (the common case) cost the same as before — the cap only bounds the tail.
    timeout=3000, retries=2, cpu=64, memory=131072, region="us",  # A-L3 REVISED (2026-07-25): Modal caps per-function CPU at 64 (128 bounced the deploy: "Must be between 0.125 and 64") — 64 IS the platform max. The achievable A-L3 = 8 chunks × 4 tabs (same 32 total tabs, 2× process parallelism vs Remotion's per-instance fps ceiling, issue #4664). Past-64 scaling = A-L4 cross-container fan-out.
    scaledown_window=180, volumes={"/prewarm": prewarm_volume},
    enable_memory_snapshot=True,
)
def run_pipeline_bg(body: dict):
    import sys as _sys, os as _os
    _sys.path.insert(0, "/")
    import handler as _H
    try:
        _H._install_shutdown_handler()  # Phase 1 safety net on this container too
    except Exception:
        pass
    try:
        prewarm_volume.reload()
    except Exception:
        pass
    result = _H.handler({"input": body})
    # PRIMARY completion delivery — POST the full result (success payload OR the
    # classified error envelope) to the app server. Best-effort: a failed POST
    # falls back to the dispatch's Supabase recovery + the reaper.
    try:
        _call_id = modal.current_function_call_id()
        _app_url = _os.environ.get("APP_URL", "").rstrip("/")
        _secret = _os.environ.get("MODAL_CALLBACK_SECRET", "")
        if _app_url and _call_id:
            import requests as _requests
            _requests.post(
                f"{_app_url}/api/modal-complete",
                json={"call_id": _call_id, "job_id": body.get("job_id"), "result": result},
                headers=({"X-Modal-Secret": _secret} if _secret else {}),
                timeout=15,
            )
            print(f"[run_pipeline_bg] completion POSTed call={_call_id} job={body.get('job_id')}", flush=True)
    except Exception as _e:
        print(f"[run_pipeline_bg] completion POST failed ({_e}) — dispatch fallback + reaper will settle", flush=True)
    return result


# ── Web endpoint ───────────────────────────────────────────────────────────────
@app.cls(
    timeout=3000,         # 50 min (raised 900->1800->3000; 3000 for 5-min support 2026-07-25) — matches run_pipeline_bg so the SYNC-fallback path (SPAWN_MODE=0) can also finish a 5-minute render. Under SPAWN_MODE=1 run_job returns in ms (it spawns run_pipeline_bg), so this cap binds only the sync fallback; kept in lockstep for correctness. Orchestrator runs init + audio + remotion + composite + upload; the Gemini client timeout is 480s (handler.py:_get_genai_client). Billing is per-active-second, so short jobs cost the same — the cap only bounds the tail. INVARIANT: content-studio reaper EXEC_WALL_MS must be >= this (>=3300s) at all times, raised FIRST.
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
    cpu=64,               # platform max (Modal caps per-function CPU at 64); lockstep with run_pipeline_bg
    memory=131072,        # 128GB — Remotion overlay + Remotion micro-segments run in parallel here, plus per-cut numpy audio resampler, plus the big single-pass ffmpeg composite
    region="us",  # COST (Zac 2026-07-12, Tier 1.1): broad "us" is the 1.5x
                  # multiplier tier; the old ["us-west","us-east"] narrow pin was
                  # 1.75x (Modal: narrow=1.75x, broad=1.5x, no-pin=1.0x). Broad
                  # "us" keeps US placement (S3/Supabase co-located — same download
                  # latency as the narrow pin) AND widens capacity to every US
                  # region (better than the 2-region pin) while shaving the region
                  # tax 1.75x→1.5x. Pixel-identical: this only changes WHERE the
                  # container runs. Dropping to no-pin (1.0x, −43%) needs a
                  # cross-region S3 latency measurement first (could place EU →
                  # slow download to the US bucket) — a separate deploy-test.
    retries=2,        # RELIABILITY (Zac 2026-07-12, Tier 1.2): we run preemptible
                      # (nonpreemptible=False default — the cheap tier), so Modal
                      # CAN interrupt the container mid-render. Without retries a
                      # preemption failed the job (frontend had to resubmit); with
                      # retries=2 Modal re-runs the job from scratch on interruption
                      # — invisible to the user. Pixel-identical: same input → a
                      # valid render (a re-run makes a fresh Gemini plan, so it may
                      # differ from the interrupted attempt, but it's a correct,
                      # complete render). CAVEAT to verify in prod: run_job is a
                      # SYNCHRONOUS fastapi_endpoint (blocks through the render), and
                      # Modal's retry/auto-migration behavior for web endpoints on
                      # preemption is not yet confirmed here — worst case this is a
                      # harmless no-op; the fully-robust form spawns the render as a
                      # retriable background function (a Tier-3-adjacent change).
    enable_memory_snapshot=True,  # COLD-START (Zac 2026-07-12, audit #2): the
                      # @modal.enter below re-imports handler (opencv/numpy/genai/
                      # deepgram + ffmpeg checks + model init) — ~10-12s on every
                      # cold container. With snapshot, that import runs ONCE at
                      # snapshot time (snap=True) and every cold start restores the
                      # post-import memory image instantly. Pixel-identical: it only
                      # changes WHEN the import runs. Safe: the import is pure (no
                      # lingering sockets/file handles that wouldn't survive a
                      # snapshot); the prewarm-volume reload + all per-request work
                      # stays in run_job, not startup.
    volumes={"/prewarm": prewarm_volume},
)
class PromptlyWorker:
    @modal.enter(snap=True)
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
        # Reliability Phase 1: install the platform-shutdown signal handler on
        # each container start (main thread, so it survives memory snapshots) —
        # kills render children + flushes the ledger on SIGTERM (preemption/
        # timeout) so no thread wedges runner shutdown. Best-effort; never breaks
        # startup. See handler._on_platform_shutdown.
        try:
            import handler as _handler_mod
            _handler_mod._install_shutdown_handler()
        except Exception as _sh_e:
            print(f"[startup] shutdown-handler install skipped ({_sh_e})", flush=True)
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
        # DUAL-MODE (spawn refactor Phase 3): when PROMPTLY_SPAWN_MODE=1, spawn the
        # pipeline as a retriable background function and return a call_id in
        # milliseconds — the app server (dual-mode dispatch, already deployed)
        # awaits completion via /api/modal-complete + its fallback. Defaults OFF,
        # so THIS deploy is inert until the flag flips — a second safety layer on
        # top of the deploy-order gate (server must understand {spawned} first).
        # Rollback = unset the flag, no redeploy.
        if os.environ.get("PROMPTLY_SPAWN_MODE") == "1":
            _fc = run_pipeline_bg.spawn(body)
            print(f"[run_job] spawned pipeline call={_fc.object_id} job={body.get('job_id')}", flush=True)
            return {"spawned": True, "call_id": _fc.object_id, "job_id": body.get("job_id")}
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


# ── Phase B Part 1 isolation proof: multi-source download+concat (INERT) ─────
# Generates TWO heterogeneous synthetic clips (different resolution + fps),
# uploads them to S3, runs the REAL handler._download_and_concat_sources, and
# verifies the join is ONE continuous uniform file (duration≈sum, 1080x1920,
# single continuous audio). Also verifies the N==1 straight-copy path. Proves the
# concat that the single-input pipeline then treats as one source. Not called by
# any job.
@app.function(cpu=2, memory=4096, timeout=600)
def probe_multi_concat():
    import os, sys, uuid, tempfile, subprocess, json
    if "/" not in sys.path:
        sys.path.insert(0, "/")
    import handler

    _s3 = handler._aws_s3_client
    if _s3 is None:
        raise RuntimeError("AWS S3 client not configured")
    _bucket = (os.environ.get("S3_BUCKET_NAME") or os.environ.get("SUPABASE_S3_BUCKET")
               or "promptly-video-storage")

    def _probe(path):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True,
        )
        d = json.loads(out.stdout or "{}")
        v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
        a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
        return {
            "duration": round(float(d.get("format", {}).get("duration") or 0.0), 2),
            "w": v.get("width"), "h": v.get("height"),
            "vcodec": v.get("codec_name"), "acodec": a.get("codec_name"),
            "asr": a.get("sample_rate"), "ach": a.get("channels"),
        }

    report = {}
    with tempfile.TemporaryDirectory(prefix="multiconcat-") as work:
        # Two DIFFERENT-shape clips: landscape 1280x720@30 (3s) + portrait 1080x1920@24 (2s).
        a_path = os.path.join(work, "a.mp4"); b_path = os.path.join(work, "b.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", a_path], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=1080x1920:rate=24",
                        "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", b_path], check=True, capture_output=True)
        report["clip_a"] = _probe(a_path)
        report["clip_b"] = _probe(b_path)

        keys, urls = [], []
        for p in (a_path, b_path):
            k = "test-gen/multi/" + uuid.uuid4().hex + ".mp4"
            _s3.upload_file(p, _bucket, k, ExtraArgs={"ContentType": "video/mp4"})
            keys.append(k)
            urls.append(f"https://{_bucket}.s3.amazonaws.com/{k}")

        # N==2 concat (the real helper)
        dest2 = os.path.join(work, "concat.mp4")
        durs = handler._download_and_concat_sources(urls, dest2, work)
        report["per_source_durations"] = [round(d, 2) for d in durs]
        report["concat"] = _probe(dest2)
        _exp = round(sum(durs), 2)
        _got = report["concat"]["duration"]
        report["duration_sum_ok"] = abs(_got - _exp) <= 0.6   # small container/keyframe slack
        report["is_1080x1920"] = (report["concat"]["w"] == 1080 and report["concat"]["h"] == 1920)
        report["has_continuous_audio"] = (report["concat"]["acodec"] == "aac" and str(report["concat"]["asr"]) == "48000")

        # N==1 straight-copy path (single == list-of-one, byte-identical intent)
        dest1 = os.path.join(work, "single.mp4")
        d1 = handler._download_and_concat_sources([urls[0]], dest1, work)
        report["single_copy_duration"] = _probe(dest1)["duration"]
        report["single_is_copy"] = (os.path.getsize(dest1) == os.path.getsize(a_path))

        # cleanup uploaded test objects
        for k in keys:
            try: _s3.delete_object(Bucket=_bucket, Key=k)
            except Exception: pass

    report["PASS"] = bool(report.get("duration_sum_ok") and report.get("is_1080x1920")
                          and report.get("has_continuous_audio") and report.get("single_is_copy"))
    print(f"[multi-concat-probe] {report}", flush=True)
    return report


@app.local_entrypoint()
def multi_concat_probe():
    r = probe_multi_concat.remote()
    print("\n=== MULTI-INPUT CONCAT ISOLATION PROOF ===")
    for k, v in (r or {}).items():
        print(f"{k}: {v}")
    print("=== END ===\n")


# ── MULTILINGUAL TIER-1 CERTIFICATION (Workstream C — real-source regression tooling) ──
# Runs the FULL pipeline with PROMPTLY_EDIT_IN_LANGUAGE=1 (set in-process at request
# time — no activation redeploy) on constructed real-source clips: a real human face
# (Pexels talking-head) muxed with a real target-language script spoken by macOS TTS.
# Lives here (not a separate app) because a sibling module can't import modal_app in
# the container (it defines the image → excluded from the mount), which breaks Modal's
# dependency matching. As worker-app functions they share image+secrets natively.
#   Run:  modal run --detach modal_app.py::cert_run
# CAVEAT (recorded verbatim per lang): audio is TTS, not native — certifies the
# in-language MACHINERY end-to-end, not native-accent transcription/prosody.
_CERT_BUCKET = "thisismybucketagainwooo"
_CERT_PREFIX = "multilingual-cert"
_CERT_FACE_KEY = f"{_CERT_PREFIX}/_face/face.mp4"
_CERT_LANG_META = {
    "en": ("English", "Latin"), "es": ("Spanish", "Latin"),
    "pt": ("Portuguese", "Latin"), "fr": ("French", "Latin"),
    "de": ("German", "Latin"), "ru": ("Russian", "Cyrillic"),
    "hi": ("Hindi", "Devanagari"), "ar": ("Arabic", "Arabic"),
    "id": ("Indonesian", "Latin"), "ja": ("Japanese", "Han"),
}
_CERT_TTS_CAVEAT = (
    "AUDIO IS TEXT-TO-SPEECH (macOS say), NOT A NATIVE SPEAKER. Certifies the "
    "in-language MACHINERY end-to-end (multi transcription, plan validity, in-language "
    "verbatim captions, emphasis on real language content, in-language Gemini-authored "
    "chrome, script fonts + RTL, completed render). NOT native-accent transcription or "
    "prosody. A genuine native-clip upgrade can replace this per language, non-blocking."
)


@app.function(cpu=4, memory=8192, timeout=600)
def cert_fetch_face() -> str:
    import os, requests, boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    try:
        s3.head_object(Bucket=_CERT_BUCKET, Key=_CERT_FACE_KEY)
        print(f"[cert-face] already staged")
        return _CERT_FACE_KEY
    except Exception:
        pass
    key = os.environ["PEXELS_API_KEY"]
    best = None
    for q in ("woman talking to camera closeup", "man talking to camera closeup", "person speaking portrait"):
        r = requests.get("https://api.pexels.com/videos/search",
                         headers={"Authorization": key},
                         params={"query": q, "orientation": "portrait", "per_page": 20, "size": "medium"}, timeout=30)
        r.raise_for_status()
        for v in r.json().get("videos", []):
            if v.get("duration", 0) < 6:
                continue
            for f in sorted(v.get("video_files", []), key=lambda x: x.get("height") or 0):
                if f.get("file_type") == "video/mp4" and 700 <= (f.get("height") or 0) <= 1300:
                    best = (v, f); break
            if best: break
        if best: break
    if not best:
        raise RuntimeError("Pexels returned no usable talking-head clip")
    v, f = best
    print(f"[cert-face] pexels id={v['id']} {f.get('width')}x{f.get('height')} dur={v.get('duration')}s")
    vid = requests.get(f["link"], timeout=120); vid.raise_for_status()
    s3.put_object(Bucket=_CERT_BUCKET, Key=_CERT_FACE_KEY, Body=vid.content, ContentType="video/mp4")
    print(f"[cert-face] staged {len(vid.content)/1e6:.1f}MB")
    return _CERT_FACE_KEY


@app.function(cpu=32, memory=65536, timeout=1800)
def cert_certify(lang: str, audio_b64: str, face_key: str) -> dict:
    import os, sys, base64, json, tempfile, subprocess, uuid, time
    os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"       # flag ON for this request
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""         # no phantom video_jobs rows
    os.environ["APP_URL"] = ""                            # no progress posts to prod
    sys.path.insert(0, "/")
    import handler
    s3 = handler._aws_s3_client
    name, expected_script = _CERT_LANG_META[lang]

    work = tempfile.mkdtemp()
    face_p, audio_p, src_p = (os.path.join(work, n) for n in ("face.mp4", "audio.m4a", "source.mp4"))
    s3.download_file(_CERT_BUCKET, face_key, face_p)
    with open(audio_p, "wb") as fh:
        fh.write(base64.b64decode(audio_b64))
    adur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", audio_p]).decode().strip())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", face_p, "-i", audio_p,
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{adur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", src_p], check=True)

    src_key, render_key = f"{_CERT_PREFIX}/{lang}/source.mp4", f"{_CERT_PREFIX}/{lang}/render.mp4"
    s3.upload_file(src_p, _CERT_BUCKET, src_key, ExtraArgs={"ContentType": "video/mp4"})
    video_url = f"https://{_CERT_BUCKET}.s3.amazonaws.com/{src_key}"
    upload_url = f"https://{_CERT_BUCKET}.s3.amazonaws.com/{render_key}"
    # public_url: the real dispatcher always passes it; the HLS export derives its
    # manifest URL from it (splitext → "-hls/master.m3u8"). Omitting it made the
    # HLS step raise AFTER a fully successful MP4 render. Point it at the render.
    public_url = f"https://{_CERT_BUCKET}.s3.amazonaws.com/{render_key}"
    body = {"job_id": str(uuid.uuid4()), "video_url": video_url, "vibe": "viral",
            "user_id": str(uuid.uuid4()), "upload_url": upload_url, "public_url": public_url}
    t0 = time.time()
    try:
        result = handler.handler({"input": body})
    except Exception as e:
        result = {"status": "exception", "error": f"{type(e).__name__}: {e}"}
    elapsed = round(time.time() - t0, 1)

    recipe = (result or {}).get("edit_recipe") or {}
    transcript = (result or {}).get("transcript") or {}
    words = transcript.get("words") or []

    def _script_of(text):
        try:
            return handler._dominant_script([{"word": w} for w in str(text).split()])
        except Exception:
            return "?"

    cap_pages = recipe.get("caption_pages") or []
    cap_text = " ".join(t.get("text", "") for p in cap_pages for t in (p.get("tokens") or [])) \
        or " ".join(w.get("word", "") if isinstance(w, dict) else str(w) for w in words)
    cap_script = _script_of(cap_text)
    chrome = []
    for mg in (recipe.get("motion_graphics") or []):
        for k in ("text", "title", "label", "heading"):
            if isinstance(mg.get(k), str) and mg[k].strip():
                chrome.append(mg[k])
        for it in (mg.get("items") or []):
            if isinstance(it, str):
                chrome.append(it)
    for ov in (recipe.get("text_overlays") or []):
        if isinstance(ov.get("text"), str) and ov["text"].strip():
            chrome.append(ov["text"])
    richness = {k: len(recipe.get(k) or []) for k in
                ("emphasis_moments", "transitions", "broll_clips", "motion_graphics",
                 "sound_effects", "zoom_effects", "text_overlays")}
    richness["caption_pages"] = len(cap_pages)
    caps_in_lang = (cap_script == expected_script) \
        or (lang == "ja" and cap_script in ("Han", "Hiragana", "Katakana")) \
        or (expected_script == "Latin" and cap_script == "Latin")

    cert = {
        "lang": lang, "language": name, "expected_script": expected_script, "caveat": _CERT_TTS_CAVEAT,
        "status": (result or {}).get("status"),
        "plan_validates": bool(recipe) and (result or {}).get("status") == "success",
        "detected_language": transcript.get("detected_language"),
        "captions": {"sample": cap_text[:200], "dominant_script": cap_script,
                     "in_language": caps_in_lang,
                     "token_count": sum(len(p.get("tokens") or []) for p in cap_pages)},
        "emphasis_count": richness["emphasis_moments"], "richness": richness,
        "caption_style": recipe.get("caption_style"),
        "authored_chrome": chrome[:20], "chrome_scripts": sorted({_script_of(c) for c in chrome}),
        "render_url": (result or {}).get("video_url"),
        "render_succeeded": bool((result or {}).get("video_url")),
        "render_time_s": (result or {}).get("render_time"),
        "output_size_mb": (result or {}).get("output_size_mb"),
        "pipeline_wall_s": elapsed, "source_url": video_url,
        "capability_notes": (result or {}).get("capability_notes"),
        "error": (result or {}).get("error") or (result or {}).get("user_message"),
    }
    s3.put_object(Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/{lang}/cert.json",
                  Body=json.dumps(cert, ensure_ascii=False, indent=2).encode("utf-8"),
                  ContentType="application/json")
    print(f"[cert] {lang} status={cert['status']} render={cert['render_succeeded']} "
          f"caps_in_lang={caps_in_lang} emphasis={cert['emphasis_count']}")
    return cert


@app.function(cpu=2, memory=4096, timeout=7200)
def cert_run_all(audio_map: dict) -> dict:
    import json, os, boto3
    face_key = cert_fetch_face.remote()
    print(f"[cert-run-all] face: {face_key}")
    langs = list(audio_map.keys())
    results = list(cert_certify.starmap([(l, audio_map[l], face_key) for l in langs]))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    summary = {
        "n": len(results),
        "all_clean": all(r and r.get("plan_validates") and r.get("render_succeeded")
                         and r.get("captions", {}).get("in_language") for r in results),
        "by_lang": {r.get("lang"): {"status": r.get("status"), "render": r.get("render_succeeded"),
                    "caps_in_lang": r.get("captions", {}).get("in_language"),
                    "emphasis": r.get("emphasis_count"), "richness": r.get("richness"),
                    "render_url": r.get("render_url"), "error": r.get("error")}
                    for r in results if r},
    }
    s3.put_object(Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/_summary.json",
                  Body=json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
                  ContentType="application/json")
    print(f"[cert-run-all] DONE all_clean={summary['all_clean']} n={summary['n']}")
    return summary


@app.function(cpu=2, memory=4096, timeout=300)
def cert_collect() -> list:
    import os, json, boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    out = []
    for lang in _CERT_LANG_META:
        try:
            o = s3.get_object(Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/{lang}/cert.json")
            out.append(json.loads(o["Body"].read()))
        except Exception:
            pass
    print(f"CERT_POLL count={len(out)}/{len(_CERT_LANG_META)}")
    for r in out:
        print(f"CERT_ROW {r.get('lang')} status={r.get('status')} render={r.get('render_succeeded')} "
              f"caps_in_lang={r.get('captions',{}).get('in_language')} emphasis={r.get('emphasis_count')} "
              f"richness_total={sum((r.get('richness') or {}).values())} err={str(r.get('error'))[:60]}")
    try:
        summ = json.loads(s3.get_object(Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/_summary.json")["Body"].read())
        print(f"CERT_SUMMARY all_clean={summ.get('all_clean')} n={summ.get('n')}")
    except Exception:
        print("CERT_SUMMARY pending")
    return out


@app.function(cpu=4, memory=8192, timeout=300)
def cert_bridge_e2e(lang: str, audio_b64: str, graduated: bool = False) -> dict:
    """One clip, full chain, RETURNED INLINE (no S3 race). transcribe multi →
    _looks_confused → language=ar probe → treat. With graduated=True, ALSO runs
    the GRADUATED route on confirmed Arabic (language=ar full re-transcribe) and
    reports the routed transcript's script — the graduated-path regression:
    Arabic in → Arabic-script words (= verbatim captions) out."""
    import os, sys, base64, tempfile
    sys.path.insert(0, "/")
    import handler
    from deepgram import DeepgramClient, PrerecordedOptions
    p = tempfile.mktemp(suffix=".m4a"); open(p, "wb").write(base64.b64decode(audio_b64))
    ab = handler.prepare_audio_for_deepgram(p)
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    tx = handler._parse_deepgram_response(dg.listen.prerecorded.v("1").transcribe_file(
        {"buffer": ab, "mimetype": "audio/flac"},
        PrerecordedOptions(model="nova-3", language="multi", smart_format=True, punctuate=True)))
    script = handler._dominant_script(tx.get("words") or [])
    # mirror the production bridge: Latin AND Cyrillic are suspect scripts
    # (Deepgram transliterates Arabic into either, run-to-run), script-aware LID
    confused = handler._looks_confused(tx, script) if script in ("Latin", "Cyrillic") else False
    treat, probe, routed_script, routed_words = script, None, None, None
    if confused:
        is_ar, _ = handler._probe_confirms_arabic(p)
        probe = is_ar
        if is_ar:
            treat = "Arabic"
            if graduated:
                ar_tx = handler.transcribe_audio(p, language="ar")
                routed_words = len(ar_tx.get("words") or [])
                routed_script = handler._dominant_script(ar_tx.get("words") or [])
    r = {"lang": lang, "multi_script": script, "confused": confused, "ar_probe": probe,
         "treat": treat, "routed_script": routed_script, "routed_words": routed_words,
         "n_words": len(tx.get("words") or []),
         "text": (tx.get("text") or "")[:120]}
    print(f"E2E {r}")
    return r


@app.local_entrypoint()
def cert_e2e():
    import base64, os
    cert_dir = os.environ.get("CERT_AUDIO_DIR") or "/tmp/promptly_cert_audio"
    for lang in [s.strip() for s in os.environ.get("CERT_ONLY", "ar_r140,en").split(",") if s.strip()]:
        with open(os.path.join(cert_dir, f"{lang}.m4a"), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        print("RESULT", cert_bridge_e2e.remote(lang, b64))


# ── ARABIC BRIDGE PERMANENT REGRESSION (Zac 2026-07-20) ──────────────────────
# "A detector that was once proven must stay proven." The clips live durably in
# S3, so `modal run modal_app.py::cert_bridge_regression_run` re-verifies the
# WHOLE chain (real Deepgram transcribe → confusion signature → language=ar probe)
# against the live API anytime. If a future Deepgram change re-breaks the probe
# or the detection, this catches it on the next run — before Arabic speakers
# silently get romanized captions again.
_BRIDGE_REGRESSION_CLIPS = {
    # graduated_expect: with the graduated env, the ROUTE must yield a native-
    # Arabic-script transcript (captions are verbatim words, so Arabic-script
    # words == Arabic-script captions; the render layer was pixel-proven at cert).
    "ar_r140": {"key": f"{_CERT_PREFIX}/_bridge_regression/ar_r140.m4a", "expect": "Arabic",
                "graduated_expect": "Arabic"},
    # second Arabic voice/script — Deepgram transliterates it into Latin OR
    # Cyrillic run-to-run; either way the bridge must land treat=Arabic. This
    # clip is the standing coverage for the Cyrillic-transliteration mode.
    "ar_simple": {"key": f"{_CERT_PREFIX}/_bridge_regression/ar_simple.m4a", "expect": "Arabic",
                  "graduated_expect": "Arabic"},
    "en":      {"key": f"{_CERT_PREFIX}/_bridge_regression/en.m4a",      "expect": "Latin"},
}


@app.function(cpu=2, memory=4096, timeout=300)
def cert_bridge_seed(clips: dict) -> list:
    import os, base64, boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    done = []
    for name, b64 in clips.items():
        spec = _BRIDGE_REGRESSION_CLIPS.get(name)
        if not spec:
            continue
        s3.put_object(Bucket=_CERT_BUCKET, Key=spec["key"],
                      Body=base64.b64decode(b64), ContentType="audio/mp4")
        done.append(spec["key"])
    print(f"SEEDED {done}")
    return done


@app.function(cpu=2, memory=4096, timeout=900)
def cert_bridge_regression() -> dict:
    """Re-verify the bridge end-to-end on the durable clips. Asserts each clip's
    treat == expected (Arabic clip → Arabic, control → Latin)."""
    import os, base64, boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    rows, passed = [], True
    for name, spec in _BRIDGE_REGRESSION_CLIPS.items():
        try:
            b = s3.get_object(Bucket=_CERT_BUCKET, Key=spec["key"])["Body"].read()
        except Exception as e:
            rows.append({"clip": name, "error": f"durable clip missing: {e}"}); passed = False; continue
        _grad = "graduated_expect" in spec
        r = cert_bridge_e2e.remote(name, base64.b64encode(b).decode(), _grad)
        ok = (r or {}).get("treat") == spec["expect"]
        if _grad:
            # graduated-path check: the route's transcript must be native script
            ok = ok and (r or {}).get("routed_script") == spec["graduated_expect"]
        passed = passed and ok
        rows.append({"clip": name, "expect": spec["expect"], "got": (r or {}).get("treat"),
                     "confused": (r or {}).get("confused"), "ar_probe": (r or {}).get("ar_probe"),
                     "routed_script": (r or {}).get("routed_script"),
                     "routed_words": (r or {}).get("routed_words"), "ok": ok})
    print(f"REGRESSION passed={passed}")
    for r in rows:
        print(f"REG {r}")
    return {"passed": passed, "rows": rows}


@app.local_entrypoint()
def cert_bridge_regression_run():
    """Seed the durable clips from local IF present (idempotent), then run the
    permanent regression. After the first seed it re-runs from S3 alone."""
    import base64, os
    cert_dir = os.environ.get("CERT_AUDIO_DIR") or "/tmp/promptly_cert_audio"
    clips = {}
    for name in _BRIDGE_REGRESSION_CLIPS:
        p = os.path.join(cert_dir, f"{name}.m4a")
        if os.path.exists(p):
            with open(p, "rb") as fh:
                clips[name] = base64.b64encode(fh.read()).decode()
    if clips:
        cert_bridge_seed.remote(clips)
        print(f"[regression] seeded {list(clips)} to durable S3")
    print("[regression] result:", cert_bridge_regression.remote())


# ── ARABIC GRADUATION CERT (Session A) ────────────────────────────────────────
# Full pipeline with the GRADUATED env set IN-PROCESS ONLY (PLAN_CAPTURE
# pattern; zero prod impact): bridge detects → route re-transcribes language=ar
# → editorial-in-language → render. The judgment is PIXELS: caption-bearing
# frames are extracted from the render and persisted (+ presigned URLs) for
# inspection — Arabic script, RTL, joining, chrome, zero tofu.
_AR_GRAD_PREFIX = f"{_CERT_PREFIX}/ar-graduation"


@app.function(cpu=32, memory=65536, timeout=1800)
def cert_ar_graduate(clip: str, audio_b64: str, face_key: str) -> dict:
    import os, sys, base64, json, tempfile, subprocess, uuid, time
    # graduated IN-PROCESS: env-gated denylist emptied for THIS request only
    os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"
    os.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""   # no phantom video_jobs rows
    os.environ["APP_URL"] = ""                      # no progress posts to prod
    sys.path.insert(0, "/")
    import handler
    s3 = handler._aws_s3_client

    work = tempfile.mkdtemp()
    face_p, audio_p, src_p = (os.path.join(work, n) for n in ("face.mp4", "audio.m4a", "source.mp4"))
    s3.download_file(_CERT_BUCKET, face_key, face_p)
    with open(audio_p, "wb") as fh:
        fh.write(base64.b64decode(audio_b64))
    adur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", audio_p]).decode().strip())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", face_p, "-i", audio_p,
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{adur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", src_p], check=True)

    src_key = f"{_AR_GRAD_PREFIX}/{clip}/source.mp4"
    render_key = f"{_AR_GRAD_PREFIX}/{clip}/render.mp4"
    s3.upload_file(src_p, _CERT_BUCKET, src_key, ExtraArgs={"ContentType": "video/mp4"})
    video_url = f"https://{_CERT_BUCKET}.s3.amazonaws.com/{src_key}"
    upload_url = f"https://{_CERT_BUCKET}.s3.amazonaws.com/{render_key}"
    body = {"job_id": str(uuid.uuid4()), "video_url": video_url, "vibe": "viral",
            "user_id": str(uuid.uuid4()), "upload_url": upload_url, "public_url": upload_url}
    t0 = time.time()
    try:
        result = handler.handler({"input": body})
    except Exception as e:
        result = {"status": "exception", "error": f"{type(e).__name__}: {e}"}
    elapsed = round(time.time() - t0, 1)

    recipe = (result or {}).get("edit_recipe") or {}
    tx = (result or {}).get("transcript") or {}
    words = tx.get("words") or []

    def _script_of(text):
        try:
            return handler._dominant_script([{"word": w} for w in str(text).split()])
        except Exception:
            return "?"

    cap_pages = recipe.get("caption_pages") or []
    cap_text = " ".join(t.get("text", "") for p in cap_pages for t in (p.get("tokens") or [])) \
        or " ".join(w.get("word", "") if isinstance(w, dict) else str(w) for w in words)
    cap_script = _script_of(cap_text)
    chrome = []
    for mg in (recipe.get("motion_graphics") or []):
        for k in ("text", "title", "label", "heading"):
            if isinstance(mg.get(k), str) and mg[k].strip():
                chrome.append(mg[k])
        for it in (mg.get("items") or []):
            if isinstance(it, str):
                chrome.append(it)
    for ov in (recipe.get("text_overlays") or []):
        if isinstance(ov.get("text"), str) and ov["text"].strip():
            chrome.append(ov["text"])
    richness = {k: len(recipe.get(k) or []) for k in
                ("emphasis_moments", "transitions", "broll_clips", "motion_graphics",
                 "sound_effects", "zoom_effects", "text_overlays")}
    richness["caption_pages"] = len(cap_pages)

    # ── the pixel evidence: a 1fps strip of the WHOLE render (the recipe does
    # not carry a caption_pages key, so page-midpoint sampling was blind — the
    # strip guarantees caption-bearing frames are captured wherever they land) ──
    frames = []
    if (result or {}).get("video_url"):
        rend_p = os.path.join(work, "render.mp4")
        try:
            s3.download_file(_CERT_BUCKET, render_key, rend_p)
            strip_dir = os.path.join(work, "strip")
            os.makedirs(strip_dir, exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", rend_p,
                            "-vf", "fps=1,scale=540:-1",
                            os.path.join(strip_dir, "s_%02d.png")], check=True)
            for f in sorted(os.listdir(strip_dir)):
                fp = os.path.join(strip_dir, f)
                fk = f"{_AR_GRAD_PREFIX}/{clip}/strip/{f}"
                s3.upload_file(fp, _CERT_BUCKET, fk, ExtraArgs={"ContentType": "image/png"})
                url = s3.generate_presigned_url("get_object",
                        Params={"Bucket": _CERT_BUCKET, "Key": fk}, ExpiresIn=86400)
                frames.append({"t": int(f[2:4]), "key": fk, "url": url})
        except Exception as fe:
            frames.append({"error": f"{type(fe).__name__}: {fe}"})

    cert = {
        "clip": clip, "graduated_env": True, "caveat": _CERT_TTS_CAVEAT,
        "status": (result or {}).get("status"),
        "plan_validates": bool(recipe) and (result or {}).get("status") == "success",
        "detected_language": tx.get("detected_language"),
        "transcript_script": handler._dominant_script(words) if words else None,
        "transcript_sample": " ".join((w.get("word", "") if isinstance(w, dict) else str(w)) for w in words[:12]),
        "captions": {"sample": cap_text[:200], "dominant_script": cap_script,
                     "in_arabic": cap_script == "Arabic",
                     "token_count": sum(len(p.get("tokens") or []) for p in cap_pages)},
        "emphasis_count": richness["emphasis_moments"], "richness": richness,
        "caption_style": recipe.get("caption_style"),
        "authored_chrome": chrome[:20], "chrome_scripts": sorted({_script_of(c) for c in chrome}),
        "render_url": (result or {}).get("video_url"),
        "render_succeeded": bool((result or {}).get("video_url")),
        "render_time_s": (result or {}).get("render_time"),
        "pipeline_wall_s": elapsed, "source_url": video_url,
        "frames": frames,
        "error": (result or {}).get("error") or (result or {}).get("user_message"),
    }
    s3.put_object(Bucket=_CERT_BUCKET, Key=f"{_AR_GRAD_PREFIX}/{clip}/cert.json",
                  Body=json.dumps(cert, ensure_ascii=False, indent=2).encode("utf-8"),
                  ContentType="application/json")
    print(f"[ar-grad] {clip} status={cert['status']} render={cert['render_succeeded']} "
          f"caps_arabic={cert['captions']['in_arabic']} emphasis={cert['emphasis_count']} "
          f"frames={len([f for f in frames if 'key' in f])}")
    return cert


@app.function(cpu=2, memory=4096, timeout=7200)
def cert_ar_graduation_all(audio_map: dict) -> dict:
    """Orchestrator (the ONE detached spawn): face → sequential graduated certs →
    summary. Sequential, not starmap — avoids the concurrent-Gemini 429 class."""
    import os, json, boto3
    face_key = cert_fetch_face.remote()
    results = []
    for clip, b64 in audio_map.items():
        results.append(cert_ar_graduate.remote(clip, b64, face_key))
    summary = {
        "n": len(results),
        "all_clean": all(r and r.get("plan_validates") and r.get("render_succeeded")
                         and r.get("captions", {}).get("in_arabic") for r in results),
        "by_clip": {r.get("clip"): {"status": r.get("status"), "render": r.get("render_succeeded"),
                    "caps_arabic": r.get("captions", {}).get("in_arabic"),
                    "emphasis": r.get("emphasis_count"), "error": r.get("error")}
                    for r in results if r},
    }
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    s3.put_object(Bucket=_CERT_BUCKET, Key=f"{_AR_GRAD_PREFIX}/_summary.json",
                  Body=json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
                  ContentType="application/json")
    print(f"[ar-grad-all] DONE all_clean={summary['all_clean']}")
    return summary


@app.function(cpu=2, memory=4096, timeout=120)
def cert_ar_read() -> dict:
    import os, json, boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    out = {}
    for clip in ("ar_r140", "ar_simple"):
        try:
            c = json.loads(s3.get_object(Bucket=_CERT_BUCKET,
                Key=f"{_AR_GRAD_PREFIX}/{clip}/cert.json")["Body"].read())
            print(f"ARGRAD {clip}: status={c.get('status')} render={c.get('render_succeeded')} "
                  f"caps_script={c.get('captions',{}).get('dominant_script')} "
                  f"caps_arabic={c.get('captions',{}).get('in_arabic')} "
                  f"emphasis={c.get('emphasis_count')} richness={c.get('richness')} "
                  f"chrome_scripts={c.get('chrome_scripts')} err={str(c.get('error'))[:70]}")
            print(f"ARGRAD_SAMPLE {clip}: {c.get('captions',{}).get('sample','')[:110]}")
            for f in c.get("frames", []):
                if "url" in f:
                    print(f"ARGRAD_FRAME {clip} t={f['t']} {f['url']}")
            out[clip] = c
        except Exception as e:
            print(f"ARGRAD {clip}: pending ({type(e).__name__})")
    try:
        summ = json.loads(s3.get_object(Bucket=_CERT_BUCKET,
            Key=f"{_AR_GRAD_PREFIX}/_summary.json")["Body"].read())
        print(f"ARGRAD_SUMMARY all_clean={summ.get('all_clean')} n={summ.get('n')}")
    except Exception:
        print("ARGRAD_SUMMARY pending")
    return out


@app.local_entrypoint()
def cert_ar_graduation():
    import base64, os
    cert_dir = os.environ.get("CERT_AUDIO_DIR") or "/tmp/promptly_cert_audio"
    audio_map = {}
    for clip in ("ar_r140", "ar_simple"):
        with open(os.path.join(cert_dir, f"{clip}.m4a"), "rb") as fh:
            audio_map[clip] = base64.b64encode(fh.read()).decode()
    call = cert_ar_graduation_all.spawn(audio_map)
    print(f"[ar-grad] spawned cert_ar_graduation_all → {call.object_id}; poll cert_ar_read")


@app.function(cpu=4, memory=8192, timeout=900)
def cert_bridge_verify(audio_map: dict) -> list:
    """Verify the Arabic bridge on real Deepgram output (Zac's ask: hit rate +
    false fires). For each clip: transcribe language=multi, run the REAL
    _looks_confused signature, and — when it fires — the language=ar probe. An
    Arabic clip should end `treat=Arabic`; every control should not."""
    import os, sys, base64, tempfile, boto3
    sys.path.insert(0, "/")
    import handler
    from deepgram import DeepgramClient, PrerecordedOptions
    # delete any stale result FIRST so a concurrent read is never ambiguous
    try:
        boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1")).delete_object(
            Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/_bridge_verify.json")
    except Exception:
        pass
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    out = []
    for lang, b64 in audio_map.items():
        p = tempfile.mktemp(suffix=".m4a")
        open(p, "wb").write(base64.b64decode(b64))
        try:
            ab = handler.prepare_audio_for_deepgram(p)
            resp = dg.listen.prerecorded.v("1").transcribe_file(
                {"buffer": ab, "mimetype": "audio/flac"},
                PrerecordedOptions(model="nova-3", language="multi", smart_format=True, punctuate=True))
            tx = handler._parse_deepgram_response(resp)
            script = handler._dominant_script(tx.get("words") or [])
            confused = handler._looks_confused(tx)
            treat = script
            probe = None
            if script == "Latin" and confused:
                is_ar, _ = handler._probe_confirms_arabic(p)
                probe = is_ar
                if is_ar:
                    treat = "Arabic"
            out.append({"lang": lang, "detected": tx.get("detected_language"),
                        "multi_script": script, "confused": confused,
                        "ar_probe": probe, "treat": treat,
                        "sample": (tx.get("text") or "")[:45]})
        except Exception as e:
            out.append({"lang": lang, "error": f"{type(e).__name__}: {e}"})
    for r in out:
        print(f"BRIDGE {r.get('lang')}: multi_script={r.get('multi_script')} "
              f"confused={r.get('confused')} ar_probe={r.get('ar_probe')} "
              f"treat={r.get('treat')} detected={r.get('detected')} err={r.get('error','')}")
    try:
        import json, boto3
        boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1")).put_object(
            Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/_bridge_verify.json",
            Body=json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json")
    except Exception:
        pass
    return out


@app.function(cpu=2, memory=4096, timeout=120)
def cert_bridge_read() -> list:
    import os, json, boto3, sys
    # SELF-TEST the DEPLOYED handler's signature (isolates "is the fix in the
    # image" from S3 staleness) — calls the image's _looks_confused directly.
    sys.path.insert(0, "/")
    try:
        import handler as _h
        _mock = {"detected_language": None, "words": [
            {"word": w, "language": "fr", "confidence": 0.9}
            for w in "Muawami innasi yas tazlimuna qabil najahi mubashara".split()]}
        print(f"SELFTEST deployed _looks_confused(romanized-ar, coherent-tags)="
              f"{_h._looks_confused(_mock)} (want True)")
    except Exception as _e:
        print(f"SELFTEST error {type(_e).__name__}: {_e}")
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    try:
        rows = json.loads(s3.get_object(Bucket=_CERT_BUCKET, Key=f"{_CERT_PREFIX}/_bridge_verify.json")["Body"].read())
    except Exception:
        print("BRIDGE_READ pending"); return []
    for r in rows:
        print(f"BRIDGE {r.get('lang')}: multi_script={r.get('multi_script')} confused={r.get('confused')} "
              f"ar_probe={r.get('ar_probe')} treat={r.get('treat')} detected={r.get('detected')} err={r.get('error','')}")
    return rows


@app.local_entrypoint()
def cert_bridge():
    import base64, os
    cert_dir = os.environ.get("CERT_AUDIO_DIR") or "/tmp/promptly_cert_audio"
    only = [s.strip() for s in os.environ.get("CERT_ONLY", "").split(",") if s.strip()]
    langs = only or ["ar", "ar_r140", "en", "es", "fr", "de", "id", "ru", "hi", "ja"]
    audio_map = {}
    for lang in langs:
        with open(os.path.join(cert_dir, f"{lang}.m4a"), "rb") as fh:
            audio_map[lang] = base64.b64encode(fh.read()).decode()
    call = cert_bridge_verify.spawn(audio_map)
    print(f"[cert_bridge] spawned → {call.object_id}; read via cert_bridge_read")


@app.local_entrypoint()
def cert_run():
    import base64, os
    cert_dir = os.environ.get("CERT_AUDIO_DIR") or "/tmp/promptly_cert_audio"
    # CERT_ONLY=de,ar re-runs a subset (single-lang avoids the concurrent-Gemini
    # 429 quota exhaustion that failed a lang under the full 10-way fan-out).
    only = [s.strip() for s in os.environ.get("CERT_ONLY", "").split(",") if s.strip()]
    langs = only or list(_CERT_LANG_META)
    audio_map = {}
    for lang in langs:
        fn = os.environ.get(f"CERT_AUDIO_{lang}") or f"{lang}.m4a"
        with open(os.path.join(cert_dir, fn), "rb") as fh:
            audio_map[lang] = base64.b64encode(fh.read()).decode()
    call = cert_run_all.spawn(audio_map)
    print(f"[cert_run] spawned cert_run_all({list(audio_map)}) → {call.object_id}; poll S3 {_CERT_PREFIX}/_summary.json")


# ── Forced-scene E2E proof for the cost-aware overlay-chunk render budget ─────
# (scene-timeout fix 4e4aec6). Ephemeral: `modal run modal_app.py::scene_timeout_proof`
# — no deploy, touches nothing live. Renders a scene-BEARING PromptlyOverlay long
# enough that the render exceeds the OLD flat 300s budget (a REAL reproduction —
# the verdict is judged from the ACTUAL measured render time, not an estimate),
# confirms it completes under the new scaled budget, and renders a plain
# scene-free overlay at the unchanged 300s.
@app.function(cpu=64, memory=131072, region="us", timeout=1800)
def cert_scene_timeout() -> dict:
    import subprocess, os, json, time, tempfile
    PUB = "/remotion/bundle/public"
    os.makedirs(PUB, exist_ok=True)
    still = os.path.join(PUB, "placeholder_scene.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x2a2a4e:s=900x900:d=1", "-frames:v", "1", still], check=True)

    def _input(n, with_scene):
        scene = {
            "fromFrame": 0, "durationInFrames": n,
            "background": {"kind": "gradient", "colors": ["#1a1a2e", "#0f3460"]},
            "subject": {"imageUrl": "placeholder_scene.png",
                        "generationPrompt": "placeholder proof still", "anchor": "center", "scale": 1.0},
            "textLayers": [{"content": "SCENE TIMEOUT PROOF", "anchor": "upper_third_safe"},
                           {"content": "cost aware budget", "anchor": "lower_third_safe"}],
            "motion": {"entrance": "rise", "easing": "spring", "motionBlur": True},
        }
        return {
            "sourceUrl": "placeholder_scene.png", "fps": 30, "width": 1080, "height": 1920,
            "totalDurationInFrames": n,
            "clips": [{"id": "c0", "startFromFrames": 0, "playbackRate": 1.0, "durationInFrames": n}],
            "transitions": [], "broll": [], "textOverlays": [], "motionGraphics": [],
            "generatedScenes": [scene] if with_scene else [],
            "caption": None, "tightCutOverlays": [], "outro": None,
        }

    def _render(n, with_scene, timeout):
        tag = "scene" if with_scene else "plain"
        inp = os.path.join(tempfile.gettempdir(), f"in_{tag}_{n}.json")
        out = os.path.join(tempfile.gettempdir(), f"out_{tag}_{n}.mov")
        with open(inp, "w") as fh:
            json.dump(_input(n, with_scene), fh)
        cmd = ["node", "/remotion/render-full.mjs", "--input", inp, "--output", out,
               "--public-dir", PUB, "--composition", "PromptlyOverlay", "--gl", "swangle",
               "--frame-range", f"0,{n - 1}", "--composition-start", "0", "--concurrency", "8"]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            el = time.time() - t0
            ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000
            return {"frames": n, "elapsed_s": round(el, 1), "completed": ok, "rc": r.returncode,
                    "out_mb": round(os.path.getsize(out) / 1e6, 2) if os.path.exists(out) else 0,
                    "err": "" if ok else (r.stderr or "")[-600:]}
        except subprocess.TimeoutExpired:
            return {"frames": n, "elapsed_s": round(time.time() - t0, 1), "completed": False,
                    "rc": "TIMEOUT", "err": f"TIMED OUT at {timeout}s (budget too small)"}

    # 1. CALIBRATION — per-scene-frame cost (180 frames dilutes Chrome startup)
    cal = _render(180, True, 900)
    per_frame = (cal["elapsed_s"] / 180.0) if cal["completed"] else None

    # 2. SIZE the span for a ~450s render — comfortably above the old 300s so the
    #    reproduction is real even if calibration slightly over/under-estimates.
    N = int(450.0 / per_frame) if (per_frame and per_frame > 0) else 900
    _new_budget = int(min(600, 300 + N * (6 - 1) * 0.4))   # the fix's computed budget

    # 3. FULL scene render under the NEW budget; 4. PLAIN at the unchanged 300s
    scene = _render(N, True, _new_budget + 30)
    plain = _render(N, False, 300)

    return {"calibration": cal, "per_scene_frame_s": round(per_frame, 3) if per_frame else None,
            "N_scene_frames": N, "old_flat_budget_s": 300, "new_scene_chunk_budget_s": _new_budget,
            "scene_render": scene, "plain_render": plain}


# ── Lumen scene-reel (Pass 2) — render the DESIGNED scenes into a reel so the ──
# actual animation state is auditable (frames extracted for the eye). Ephemeral:
# `modal run modal_app.py::scene_reel`. Nothing live, no deploy. Uses only the
# designed typo_stat scenes (pure typography — no generated asset needed), so it
# shows the smoothness machinery (value-landing + settle-pulse + continuous drift
# + camera sweep + CameraMotionBlur samples=6) honestly, at the real render path.
@app.function(cpu=64, memory=131072, region="us", timeout=1800, secrets=[modal.Secret.from_name("promptly-secrets")])
def cert_scene_reel(width: int = 1080, height: int = 1920) -> dict:
    import subprocess, os, json, time, tempfile, boto3
    PUB = "/remotion/bundle/public"
    os.makedirs(PUB, exist_ok=True)
    FPS, DUR = 30, 120  # 4s per scene

    def _typo(from_f, colors, stat, land):
        return {"fromFrame": from_f, "durationInFrames": DUR, "sceneType": "typo_stat",
                "landFrame": land,
                "background": {"kind": "gradient", "colors": colors},
                "subject": {"generationPrompt": "n/a for typo_stat", "anchor": "center"},
                "stat": stat, "textLayers": [],
                "motion": {"entrance": "rise", "easing": "spring", "motionBlur": True}}

    scenes = [
        _typo(0,   ["#0b1026", "#1b2a4a"], {"value": 92, "suffix": "%", "label": "FINISH RATE", "supporting_line": "before the breakthrough"}, 48),
        _typo(DUR, ["#1a0b26", "#3a1b4a"], {"value": 3.4, "suffix": "x", "label": "FASTER EDITS", "supporting_line": "vs. cutting by hand"}, 48),
        _typo(2 * DUR, ["#0b2620", "#123f34"], {"value": 10000, "prefix": "$", "label": "PER MONTH", "supporting_line": "the creator ceiling"}, 54),
    ]
    total = 3 * DUR
    inp = {"sourceUrl": "reel.png", "fps": FPS, "width": width, "height": height,
           "totalDurationInFrames": total,
           "clips": [{"id": "c0", "startFromFrames": 0, "playbackRate": 1.0, "durationInFrames": total}],
           "transitions": [], "broll": [], "textOverlays": [], "motionGraphics": [],
           "generatedScenes": scenes, "caption": None, "tightCutOverlays": [], "outro": None}
    # a dummy sourceUrl asset (overlay is transparent; scenes carry their own bg)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d=1",
                    "-frames:v", "1", os.path.join(PUB, "reel.png")], check=True)
    ip = os.path.join(tempfile.gettempdir(), "reel_in.json")
    ov = os.path.join(tempfile.gettempdir(), "reel_overlay.mov")
    with open(ip, "w") as fh:
        json.dump(inp, fh)
    t0 = time.time()
    r = subprocess.run(["node", "/remotion/render-full.mjs", "--input", ip, "--output", ov,
                        "--public-dir", PUB, "--composition", "PromptlyOverlay", "--gl", "swangle",
                        "--frame-range", f"0,{total - 1}", "--composition-start", "0", "--concurrency", "8"],
                       capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        return {"ok": False, "err": (r.stderr or "")[-800:]}
    # flatten alpha onto black -> viewable MP4
    mp4 = os.path.join(tempfile.gettempdir(), "scene_reel.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={width}x{height}:r={FPS}",
                    "-i", ov, "-filter_complex", "[0][1]overlay=shortest=1[v]", "-map", "[v]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", mp4], check=True)
    # extract key frames: count-up, the value-LAND, settle, mid-drift, label-in (scene-local + offset)
    key = {"s1_countup": 24, "s1_LAND": 48, "s1_settle": 58, "s1_drift": 108,
           "s2_LAND": DUR + 48, "s3_countup": 2 * DUR + 30, "s3_LAND": 2 * DUR + 54, "s3_drift": 2 * DUR + 108}
    s3 = boto3.client("s3", region_name="us-west-1")
    B, PFX = "thisismybucketagainwooo", f"lumen-scene-reel/{width}x{height}"
    frames = {}
    for name, fnum in key.items():
        pf = os.path.join(tempfile.gettempdir(), f"{name}.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vf", f"select=eq(n\\,{fnum})",
                        "-vframes", "1", pf], check=True)
        if os.path.exists(pf):
            s3.upload_file(pf, B, f"{PFX}/frames/{name}.png")
            frames[name] = f"{PFX}/frames/{name}.png"
    s3.upload_file(mp4, B, f"{PFX}/scene_reel.mp4")
    return {"ok": True, "render_s": round(time.time() - t0, 1), "aspect": f"{width}x{height}",
            "reel_key": f"{PFX}/scene_reel.mp4", "reel_mb": round(os.path.getsize(mp4) / 1e6, 2),
            "frame_keys": frames, "bucket": B}


@app.local_entrypoint()
def scene_reel():
    r = cert_scene_reel.remote()
    if not r.get("ok"):
        print("SCENE REEL FAILED:", r.get("err", "")[:500]); return
    print(f"\n=== LUMEN SCENE-REEL ({r['aspect']}) rendered in {r['render_s']}s -> {r['reel_mb']}MB ===")
    print(f"reel: s3://{r['bucket']}/{r['reel_key']}")
    print("frames:")
    for n, k in r["frame_keys"].items():
        print(f"  {n}: s3://{r['bucket']}/{k}")


@app.local_entrypoint()
def scene_timeout_proof():
    r = cert_scene_timeout.remote()
    sc, pl, cal = r["scene_render"], r["plain_render"], r["calibration"]
    print("\n============ FORCED-SCENE E2E PROOF (scene-timeout fix) ============")
    if not cal["completed"]:
        print(f"CALIBRATION FAILED — setup broken, cannot proof. err={cal.get('err','')[:300]}")
        return
    print(f"calibration: 180 scene frames in {cal['elapsed_s']}s -> {r['per_scene_frame_s']}s/scene-frame (CameraMotionBlur samples=6)")
    print(f"forced span: N={r['N_scene_frames']} scene frames  |  old flat budget=300s  |  new scaled budget={r['new_scene_chunk_budget_s']}s")
    repro = sc["elapsed_s"] > 300
    print(f"\nSCENE render : {sc['frames']}f in {sc['elapsed_s']}s  completed={sc['completed']} ({sc['out_mb']}MB)  rc={sc['rc']}")
    print(f"  REPRODUCTION: {sc['elapsed_s']}s {'>' if repro else '<='} 300s -> "
          + ("REAL (old flat-300 budget WOULD have timed out and stripped the scene)" if repro
             else "HOLLOW — render too cheap; NOT a valid reproduction, need a bigger span"))
    print(f"  new budget {r['new_scene_chunk_budget_s']}s -> {'ACCOMMODATES: scene chunk completes' if sc['completed'] else 'SCENE FAILED: '+sc.get('err','')[:200]}")
    plain_ok = pl["completed"] and pl["elapsed_s"] < 300
    print(f"\nPLAIN render : {pl['frames']}f in {pl['elapsed_s']}s  completed={pl['completed']} at unchanged 300s budget -> "
          + ("unaffected" if plain_ok else "CHECK: "+pl.get('err','')[:200]))
    proven = repro and sc["completed"] and plain_ok
    print(f"\n>>> E2E PROVEN: {'YES' if proven else 'NO'}  (repro={repro}, scene_completed={sc['completed']}, plain_unaffected={plain_ok})")
    if not repro:
        print("    verdict: NOT proven — the forced span didn't exceed 300s. Re-run with a larger N before claiming any proof.")
