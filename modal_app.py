import modal

# rebuild trigger v3

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("ubuntu:22.04", add_python="3.10")
    .run_commands(
        "echo 'build v7'",
        "apt-get update && apt-get install -y ca-certificates && update-ca-certificates",
    )
    .apt_install(
        "ca-certificates",
        "ffmpeg",
        "fontconfig",
        "fonts-noto-color-emoji",
        "wget",
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
        "wget -q https://github.com/samuelngs/apple-emoji-linux/releases/latest/download/AppleColorEmoji.ttf "
        "-O /usr/share/fonts/AppleColorEmoji.ttf || true"
    )
    .run_commands(
        "mkdir -p /etc/fonts/conf.d && "
        "echo '<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<!DOCTYPE fontconfig SYSTEM \"fonts.dtd\">"
        "<fontconfig>"
        "<alias><family>emoji</family><prefer>"
        "<family>Apple Color Emoji</family>"
        "<family>Noto Color Emoji</family>"
        "</prefer></alias>"
        "</fontconfig>' > /etc/fonts/conf.d/01-apple-emoji.conf"
    )
    .run_commands("fc-cache -f")
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
    )
    .run_commands("mkdir -p /assets/fonts && cp /usr/share/fonts/AppleColorEmoji.ttf /assets/fonts/ || true")
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
    timeout=600,
    scaledown_window=60,
    cpu=4,
    memory=8192,
)
@modal.concurrent(max_inputs=1)
@modal.fastapi_endpoint(method="POST")
def run_job(body: dict):
    import sys
    sys.path.insert(0, "/")
    from handler import handler as pipeline_handler
    result = pipeline_handler({"input": body})
    return result
