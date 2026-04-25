import modal

# rebuild trigger v46 — Render speedup: skip runtime Chromium re-download + cut sub-clip count. (1) render-full.mjs no longer calls ensureBrowser when /usr/local/bin/chrome-headless-shell exists from the build-time symlink — saves the 86MB Chromium download (~5-8s) on every render. (2) densify_speed_curve params tightened: max_intermediates 150→30, min_step 0.08→0.20, per-ramp floor 12→6. Previous settings created 152 sub-clips from a 4-keypoint speed curve (sub-clip every ~300ms) which forced Remotion to mount/unmount OffthreadVideo on every transition for ~50s of source. New settings produce ~20-30 sub-clips for the same input, ~5x fewer composition transitions, while keeping per-sub-clip speed-delta under the human discrimination threshold (~5-10%).

# ── Image definition (replaces Dockerfile) ────────────────────────────────────
image = (
    modal.Image.from_registry("nvidia/cuda:12.6.3-runtime-ubuntu22.04", add_python="3.10")
    # CRITICAL: 'video' capability tells nvidia-container-toolkit to mount libnvidia-encode.so
    # Without this, NVENC silently fails and pipeline falls back to CPU encoding (10-15x slower)
    .env({"NVIDIA_DRIVER_CAPABILITIES": "all"})
    .run_commands(
        "echo 'build v24 - H100 + 64CPU + 128GB + Remotion 4.0.450 primary-render + genai SDK'",
        "apt-get update && apt-get install -y ca-certificates && update-ca-certificates",
        # Remove CUDA stubs AND compat libs that intercept dlopen before Modal's real driver libs
        "rm -rf /usr/local/cuda/lib64/stubs/libnvidia-encode* /usr/local/cuda/lib64/stubs/libcuda* /usr/local/cuda/compat/libcuda* /usr/local/cuda/lib64/libcuda.so* 2>/dev/null || true",
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
    .add_local_dir("src/assets/sounds", "/assets/sounds")
    .add_local_file("handler.py", "/handler.py")
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
    timeout=600,          # 10 min — target <60s with H100 + max cores
    scaledown_window=300, # keep warm 5 min — bursty traffic; 120s was killing containers between idle users (15-20s cold boot penalty)
    cpu=64,
    memory=131072,        # 128GB — headroom for parallel segment renders + Remotion Chrome tabs
    gpu="H100",           # H100 has no NVENC — encode is libx264 on 64 CPUs. GPU handles NVDEC + Chromium compositing via angle-egl.
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
# an H100; running it on the GPU class was costing us $3.95/hr while doing
# nothing GPU-shaped. This dedicated CPU-only class:
#   - Costs ~$35/mo always-warm (min_containers=1) vs $2844/mo for an H100
#   - Eliminates cold-start latency for prewarm itself (the request that
#     needs to be fastest to beat the user's send tap)
#   - Frees the GPU class to scale from zero on render-only demand
@app.cls(
    timeout=300,          # 5 min is plenty for an S3 download + Deepgram call
    scaledown_window=600, # stay warm a long time — cheap and helpful
    cpu=8,                # enough to run boto3 CRT multipart + Deepgram in parallel
    memory=4096,          # 4GB for in-flight download buffers + transcript JSON
    region="us-west",     # same region as the S3 bucket + render class
    volumes={"/prewarm": prewarm_volume},
    min_containers=1,     # always-warm — prewarm must be faster than the user's fingers
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
        Modal Volume and the download step is a no-op."""
        result = self._prewarm({"input": body})
        try:
            self._prewarm_volume.commit()
        except Exception as e:
            print(f"[prewarm] volume commit failed: {e}", flush=True)
        return result


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
