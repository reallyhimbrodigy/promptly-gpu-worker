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
    .run_commands(
        "mkdir -p /assets/emoji && "
        "base='https://raw.githubusercontent.com/zhdsmy/apple-emoji/main/assets/emoji' && "
        "for cp in 1f480 1f621 1f631 1f4b0 1f525 1f62d 1f92f 2764 1f64f 1f3b6 2705 274c 1f3a4 1f929 1f633 1f48b 26a1 1f6cf 1f1ee-1f1f1 1f3a8 1f54d; do "
        "  [ -f /assets/emoji/$cp.png ] || wget -q \"$base/$cp.png\" -O \"/assets/emoji/$cp.png\" || true; "
        "done && "
        "find /assets/emoji -maxdepth 1 -name '*.png' | wc -l"
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
        "Pillow",
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
