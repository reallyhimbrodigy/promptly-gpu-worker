import modal

# rebuild trigger v7 — A10G GPU + NVENC + 16 CPU + 32GB RAM (no Remotion)

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("nvidia/cuda:12.6.3-runtime-ubuntu22.04", add_python="3.10")
    .run_commands(
        "echo 'build v13 - A10G + NVENC + 16CPU + Pillow captions (no Remotion)'",
        "apt-get update && apt-get install -y ca-certificates && update-ca-certificates",
        # Remove CUDA stubs that can intercept dlopen before Modal's real driver libs
        "rm -rf /usr/local/cuda/lib64/stubs/libnvidia-encode* /usr/local/cuda/lib64/stubs/libcuda* 2>/dev/null || true",
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
    )
    .run_commands(
        "mkdir -p /opt/ffmpeg",
        # n7.1 GPL build — NVENC API 12.2 (driver ≥550, Modal has 580.95.05)
        # n8.1 required NVENC API 13.0 which caused EINVAL with CUDA 12.2 stubs
        "cd /opt/ffmpeg && wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz -O ffmpeg.tar.xz",
        "cd /opt/ffmpeg && tar -xJf ffmpeg.tar.xz --strip-components=1",
        "ln -sf /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg",
        "ln -sf /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe",
        "ffmpeg -version | head -1",
        "ffmpeg -encoders 2>/dev/null | grep nvenc || echo 'WARNING: nvenc not in build'",
        "ffmpeg -filters 2>/dev/null | grep subtitles || echo 'WARNING: subtitles filter not found'",
        "fc-cache -f",
    )
    .run_commands(
        # Download OpenCV DNN face detector model (much more accurate than Haar cascades)
        "mkdir -p /models/face_detector",
        "wget -q -O /models/face_detector/deploy.prototxt https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
        "wget -q -O /models/face_detector/res10_300x300_ssd_iter_140000.caffemodel https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
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
    .add_local_dir("src/assets/fonts", "/assets/fonts", copy=True)
    .run_commands(
        # Register Montserrat fonts system-wide for Pillow caption rendering
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
