import modal

# rebuild trigger v6 — A10G GPU + 16 CPU + 32GB RAM + GPU Chrome

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("nvidia/cuda:12.2.0-runtime-ubuntu22.04", add_python="3.10")
    .run_commands(
        "echo 'build v12 - A10G + 16CPU + GPU Chrome + nonfree FFmpeg'",
        "apt-get update && apt-get install -y ca-certificates && update-ca-certificates",
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
        # EGL/GL libraries for GPU-accelerated Chrome rendering on A10G
        "libegl1",
        "libgl1",
        "libgles2",
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
        "mkdir -p /opt/ffmpeg",
        # GPL build includes h264_nvenc/hevc_nvenc via ffnvcodec headers (runtime needs NVIDIA drivers)
        "cd /opt/ffmpeg && wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz -O ffmpeg.tar.xz",
        "cd /opt/ffmpeg && tar -xJf ffmpeg.tar.xz --strip-components=1",
        "ln -sf /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg",
        "ln -sf /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe",
        "ffmpeg -version | head -1",
        "ffmpeg -filters 2>/dev/null | grep subtitles || echo 'WARNING: subtitles filter not found'",
        "fc-cache -f",
    )
    .run_commands(
        # Download OpenCV DNN face detector model (much more accurate than Haar cascades)
        "mkdir -p /models/face_detector",
        "wget -q -O /models/face_detector/deploy.prototxt https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
        "wget -q -O /models/face_detector/res10_300x300_ssd_iter_140000.caffemodel https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
    )
    .run_commands(
        # Install Node.js 20 LTS for Remotion caption rendering
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "node --version && npm --version",
    )
    .run_commands(
        # Install Remotion dependencies + bundle at build time for fast renders
        "mkdir -p /remotion",
    )
    .pip_install("numpy", "wheel")
    .pip_install("aubio", extra_options="--no-build-isolation")
    .pip_install(
        "certifi",
        "opencv-python-headless",
        "requests",
        "anthropic",
        "google-generativeai",
        "deepgram-sdk==3.4.0",
        "supabase",
        "httpx",
        "fastapi",
        "pydantic",
        "tqdm",
        "Pillow",
    )
    .add_local_dir("src/remotion", "/remotion", copy=True)
    .add_local_dir("src/assets/fonts", "/assets/fonts", copy=True)
    .run_commands(
        # Install Remotion npm deps, download Chromium, and pre-bundle at build time
        "cd /remotion && npm install 2>&1 | tail -5",
        "cd /remotion && npx remotion browser ensure 2>&1 | tail -3",
        "cd /remotion && node -e \"require('@remotion/renderer'); console.log('[remotion] renderer OK')\"",
        # Pre-bundle Remotion project → /remotion/bundle/ (saves 5-10s per render)
        "cd /remotion && node prebundle.mjs",
        # Register Montserrat fonts for Chromium rendering
        "cp /assets/fonts/*.ttf /usr/share/fonts/truetype/ && fc-cache -f",
    )
    .add_local_dir("src/assets/sounds", "/assets/sounds")
    .add_local_file("handler.py", "/handler.py")
    .add_local_file("caption_renderer.py", "/caption_renderer.py")
)

# ── Secrets ────────────────────────────────────────────────────────────────────
secrets = [
    modal.Secret.from_name("promptly-secrets"),
]

# ── App ────────────────────────────────────────────────────────────────────────
app = modal.App("promptly-gpu-worker", image=image, secrets=secrets)

# ── Web endpoint ───────────────────────────────────────────────────────────────
@app.function(
    timeout=300,          # 5 min — Gemini can take 30-50s + render time; 300s is safe ceiling
    scaledown_window=120, # keep warm 2 min for back-to-back requests (avoid cold start)
    cpu=16,
    memory=32768,
    gpu="A10G",
)
@modal.concurrent(max_inputs=1)
@modal.fastapi_endpoint(method="POST")
def run_job(body: dict):
    import sys
    sys.path.insert(0, "/")
    from handler import handler as pipeline_handler
    result = pipeline_handler({"input": body})
    return result
