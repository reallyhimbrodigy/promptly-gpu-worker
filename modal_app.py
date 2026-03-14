import modal

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("nvidia/cuda:12.2.0-runtime-ubuntu22.04", add_python="3.10")
    .apt_install(
        "ffmpeg",
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
    .pip_install("numpy", "wheel")
    .pip_install("aubio", extra_options="--no-build-isolation")
    .pip_install(
        "requests",
        "anthropic",
        "google-generativeai",
        "deepgram-sdk",
        "httpx",
        "fastapi",
        "pydantic",
    )
    .add_local_dir("src/assets/sounds", "/assets/sounds")
    .add_local_dir("src/assets/fonts", "/assets/fonts")
    .add_local_dir("src/assets/music", "/assets/music")
    .add_local_file("handler.py", "/handler.py")
)

# ── Secrets ────────────────────────────────────────────────────────────────────
secrets = [
    modal.Secret.from_name("promptly-secrets"),
]

# ── App ────────────────────────────────────────────────────────────────────────
app = modal.App("promptly-gpu-worker", image=image, secrets=secrets)

# ── Web endpoint ───────────────────────────────────────────────────────────────
@app.function(
    gpu="A10G",
    timeout=600,
    scaledown_window=60,
)
@modal.concurrent(max_inputs=1)
@modal.fastapi_endpoint(method="POST")
def run_job(body: dict):
    import sys
    sys.path.insert(0, "/")
    from handler import handler as pipeline_handler
    result = pipeline_handler({"input": body})
    return result
