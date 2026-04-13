# Modal worker entrypoint
import subprocess
import os
import sys
import ssl
import glob
import math
import requests
import tempfile
import time
import shutil
import json
import re
import concurrent.futures
import threading
import signal
from datetime import datetime
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

HANDLER_VERSION = "3.0.0"
GEMINI_MODEL = "gemini-3-flash-preview"

print(f"[startup] Python {sys.version}", flush=True)
print(f"[startup] handler version: {HANDLER_VERSION}", flush=True)
print(f"[startup] Gemini model: {GEMINI_MODEL}", flush=True)

try:
    from google import genai as genai_client_mod
    from google.genai import types as genai_types
    _genai_client = None  # lazily initialized with API key
    print("[startup] google-genai SDK OK", flush=True)
except Exception as e:
    print(f"[startup] google-genai SDK FAILED: {e}", flush=True)
    genai_client_mod = None
    genai_types = None

def _get_genai_client():
    """Get or create the Gemini API client (lazy init with API key from env)."""
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _genai_client = genai_client_mod.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=120_000),
        )
    return _genai_client

supabase = None
try:
    from supabase import create_client
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        print("[startup] supabase OK", flush=True)
    else:
        print("[startup] supabase unavailable: missing env", flush=True)
except Exception as e:
    print(f"[startup] supabase unavailable: {e}", flush=True)

# ── S3-compatible Supabase Storage client ────────────────────────────────
# Uses Supabase's S3 protocol for same-region transfers over AWS internal
# network (via Modal's S3 gateway endpoints). Falls back to HTTP if S3
# credentials are not configured.
_s3_client = None
_s3_project_ref = None
try:
    import boto3
    from botocore.config import Config as BotoConfig
    _s3_access_key = os.environ.get("SUPABASE_S3_ACCESS_KEY")
    _s3_secret_key = os.environ.get("SUPABASE_S3_SECRET_KEY")
    _s3_region = os.environ.get("SUPABASE_S3_REGION", "us-west-1")
    _supabase_url_raw = os.environ.get("SUPABASE_URL", "")
    # Extract project ref from https://XXXXXX.supabase.co
    import re as _re_s3
    _ref_match = _re_s3.match(r"https://([^.]+)\.supabase\.co", _supabase_url_raw)
    if _ref_match:
        _s3_project_ref = _ref_match.group(1)
    if _s3_access_key and _s3_secret_key and _s3_project_ref:
        _s3_endpoint = f"https://{_s3_project_ref}.storage.supabase.co/storage/v1/s3"
        _s3_client = boto3.client(
            "s3",
            endpoint_url=_s3_endpoint,
            region_name=_s3_region,
            aws_access_key_id=_s3_access_key,
            aws_secret_access_key=_s3_secret_key,
            config=BotoConfig(s3={"addressing_style": "path"}),
        )
        print(f"[startup] S3 storage OK (endpoint={_s3_endpoint}, region={_s3_region})", flush=True)
    else:
        _missing = []
        if not _s3_access_key: _missing.append("SUPABASE_S3_ACCESS_KEY")
        if not _s3_secret_key: _missing.append("SUPABASE_S3_SECRET_KEY")
        if not _s3_project_ref: _missing.append("SUPABASE_URL (invalid format)")
        print(f"[startup] S3 storage unavailable: missing {', '.join(_missing)} — will use HTTP", flush=True)
except ImportError:
    print("[startup] S3 storage unavailable: boto3 not installed — will use HTTP", flush=True)
except Exception as e:
    print(f"[startup] S3 storage init failed: {e} — will use HTTP", flush=True)


def _parse_supabase_storage_url(url):
    """Extract (bucket, key) from a Supabase storage URL.
    Handles all known Supabase storage URL formats:
      https://XXXX.supabase.co/storage/v1/object/public/BUCKET/KEY
      https://XXXX.supabase.co/storage/v1/object/sign/BUCKET/KEY?token=...
      https://XXXX.supabase.co/storage/v1/object/authenticated/BUCKET/KEY
      https://XXXX.supabase.co/storage/v1/upload/resumable/BUCKET/KEY?token=...
      https://XXXX.supabase.co/object/upload/sign/BUCKET/KEY?token=...
      https://XXXX.supabase.co/storage/v1/object/upload/sign/BUCKET/KEY?token=...
    Returns (bucket, key) or (None, None) if not a recognized Supabase storage URL.
    """
    import re as _re_parse
    # Try all known path patterns. The /storage/v1/ prefix may or may not be present.
    patterns = [
        r"/storage/v1/object/(?:public|sign|authenticated)/([^/]+)/(.+?)(?:\?|$)",
        r"/storage/v1/(?:object/)?upload/(?:sign|resumable)/([^/]+)/(.+?)(?:\?|$)",
        r"/object/upload/sign/([^/]+)/(.+?)(?:\?|$)",
        r"/object/(?:public|sign|authenticated)/([^/]+)/(.+?)(?:\?|$)",
    ]
    for pat in patterns:
        m = _re_parse.search(pat, url)
        if m:
            return m.group(1), m.group(2)
    return None, None

DeepgramClient = None
PrerecordedOptions = None
try:
    from deepgram import DeepgramClient, PrerecordedOptions
    print("[startup] deepgram OK", flush=True)
except ImportError:
    try:
        from deepgram.clients.prerecorded import PrerecordedOptions
        from deepgram import DeepgramClient
        print("[startup] deepgram OK (alt import)", flush=True)
    except ImportError as e:
        print(f"[startup] deepgram FAILED: {e}", flush=True)

try:
    rb_check = subprocess.run(["rubberband", "--version"], capture_output=True, text=True, timeout=5)
    rb_version = (rb_check.stdout or rb_check.stderr or "").strip().splitlines()
    print(f"[startup] rubberband OK: {rb_version[0] if rb_version else 'available'}", flush=True)
except Exception:
    print("[startup] WARNING: rubberband not found — speed curve will use fallback audio", flush=True)

_HAS_FFMPEG_RUBBERBAND = False
try:
    # Log which ffmpeg binary we're actually using
    _which_ff = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True, timeout=5)
    _ff_path = (_which_ff.stdout or "").strip()
    _ff_ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
    _ff_ver_line = (_ff_ver.stdout or "").split("\n")[0] if _ff_ver.stdout else "unknown"
    print(f"[startup] FFmpeg binary: {_ff_path} ({_ff_ver_line})", flush=True)

    ff_check = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=5)
    _ff_filters = ff_check.stdout or ""
    if "rubberband" in _ff_filters:
        _HAS_FFMPEG_RUBBERBAND = True
        print("[startup] FFmpeg rubberband filter: available", flush=True)
    else:
        print("[startup] WARNING: FFmpeg rubberband filter not available", flush=True)
        # Print FFmpeg configuration for debugging
        _config_line = [l for l in (_ff_ver.stdout or "").split("\n") if "configuration:" in l]
        if _config_line:
            print(f"[startup] FFmpeg config: {_config_line[0][:300]}", flush=True)
except Exception:
    pass

# Real-ESRGAN removed from pipeline — not needed for clean phone footage

print("[startup] all import checks done", flush=True)

# ── GPU / NVENC detection ─────────────────────────────────────────────────────
_HAS_NVENC = False
_HAS_HWACCEL = False  # NVDEC hardware decoding
try:
    # Print GPU info for diagnostics
    _smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=5,
    )
    if _smi.returncode == 0:
        print(f"[startup] GPU: {_smi.stdout.strip()}", flush=True)
    else:
        print(f"[startup] nvidia-smi failed: {_smi.stderr.strip()[:200]}", flush=True)

    # Remove CUDA stub/compat libraries that intercept dlopen before Modal's real drivers
    # The CUDA 12.6 base image ships libcuda.so.560.x in /usr/local/cuda — must be removed
    # so FFmpeg picks up the real Modal-mounted driver (580.x) from /usr/local/nvidia/
    for _stub_dir in ["/usr/local/cuda/lib64/stubs", "/usr/local/cuda/targets/x86_64-linux/lib/stubs",
                      "/usr/local/cuda/compat"]:
        if os.path.isdir(_stub_dir):
            for _sf in os.listdir(_stub_dir):
                if "encode" in _sf.lower() or "cuda.so" in _sf.lower():
                    try:
                        os.remove(os.path.join(_stub_dir, _sf))
                    except Exception:
                        pass
    # Also remove compat libcuda from the main CUDA lib dir
    for _cuda_dir in ["/usr/local/cuda/lib64", "/usr/local/cuda/targets/x86_64-linux/lib"]:
        if os.path.isdir(_cuda_dir):
            for _sf in os.listdir(_cuda_dir):
                if _sf.startswith("libcuda.so"):
                    try:
                        os.remove(os.path.join(_cuda_dir, _sf))
                    except Exception:
                        pass

    # Modal mounts NVIDIA drivers at runtime — real driver is in /usr/local/nvidia/
    # CRITICAL: NVIDIA dirs must come FIRST so the real driver (580.x) is found before any stale libs
    _nvidia_lib_dirs = []
    for _search_dir in ["/usr/local/nvidia/lib", "/usr/local/nvidia/lib64",
                        "/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/local/cuda/lib64"]:
        if os.path.isdir(_search_dir):
            _nvidia_lib_dirs.append(_search_dir)
    if _nvidia_lib_dirs:
        _existing_ldpath = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = ":".join(_nvidia_lib_dirs) + (":" + _existing_ldpath if _existing_ldpath else "")
        print(f"[startup] LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH'][:200]}", flush=True)

    # Create soname symlinks for NVIDIA libs (Modal mounts versioned .so but not symlinks)
    for _lib_dir in _nvidia_lib_dirs:
        try:
            for _f in os.listdir(_lib_dir):
                if _f.startswith("libnvidia-") and ".so." in _f and not _f.endswith(".so.1"):
                    _base = _f.split(".so.")[0]
                    _target = os.path.join(_lib_dir, _f)
                    for _suf in [".so.1", ".so"]:
                        _sym = os.path.join(_lib_dir, f"{_base}{_suf}")
                        if not os.path.exists(_sym):
                            try:
                                os.symlink(_target, _sym)
                            except Exception:
                                pass
                if _f.startswith("libcuda.so.") and not _f.endswith(".so.1"):
                    _target = os.path.join(_lib_dir, _f)
                    for _sym_name in ["libcuda.so.1", "libcuda.so"]:
                        _sym = os.path.join(_lib_dir, _sym_name)
                        if not os.path.exists(_sym):
                            try:
                                os.symlink(_target, _sym)
                            except Exception:
                                pass
        except Exception:
            pass
    subprocess.run(["ldconfig"], capture_output=True, timeout=5)

    # L40S has NVENC (8th gen Ada) — detect and enable automatically.
    # H100/A100 do NOT have NVENC (encode ASIC physically absent).
    _nvenc_check = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True, timeout=5,
    )
    if "h264_nvenc" in (_nvenc_check.stdout or ""):
        import tempfile as _tmpmod
        _nvenc_tmp = os.path.join(_tmpmod.gettempdir(), "_nvenc_test.mp4")
        _gpu_test = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=1920x1080:d=0.1:r=30",
             "-c:v", "h264_nvenc", "-preset", "p1", _nvenc_tmp],
            capture_output=True, text=True, timeout=10,
            env={**os.environ},
        )
        try:
            os.remove(_nvenc_tmp)
        except Exception:
            pass
        if _gpu_test.returncode == 0:
            _HAS_NVENC = True
            print("[startup] NVENC GPU encoder: AVAILABLE", flush=True)
        else:
            print(f"[startup] NVENC not available (H100/A100 lack encode ASIC) — using CPU encoder", flush=True)
    else:
        print("[startup] NVENC not in FFmpeg build — using CPU encoder", flush=True)

    # Test NVDEC hardware decoding (works on almost all NVIDIA GPUs even if NVENC fails)
    _hwaccel_test = subprocess.run(
        ["ffmpeg", "-y", "-hwaccel", "cuda", "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=10,
    )
    if _hwaccel_test.returncode == 0:
        _HAS_HWACCEL = True
        print("[startup] CUDA hwaccel decode: AVAILABLE", flush=True)
    else:
        print("[startup] CUDA hwaccel decode: not available", flush=True)
except Exception as _e:
    print(f"[startup] GPU check failed: {_e} — using CPU", flush=True)


def get_encode_args(quality="high", threads=0):
    """Return encoder args for FFmpeg. Uses NVENC when GPU is available.

    quality="high"     → final output (CQ 18 — maximum quality for social media)
    quality="lossless" → intermediate files (lossless preset)
    """
    if _HAS_NVENC:
        if quality == "lossless":
            return ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "lossless"]
        else:
            # p4 = high quality NVENC preset. H100 NVENC is so fast that p4 adds
            # negligible time vs p1 but produces significantly better quality.
            # CQ 18 = visually lossless on mobile. Higher bitrate ceiling (15M)
            # ensures complex scenes (fast motion, particle effects) don't starve.
            # H100 NVENC encodes 1080p @ 500+ fps — encoding is never the bottleneck.
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
                    "-rc", "vbr", "-cq", "18", "-b:v", "0",
                    "-maxrate", "15M", "-bufsize", "30M",
                    "-spatial-aq", "1", "-temporal-aq", "1",
                    "-b_ref_mode", "middle"]
    else:
        # H100 has no NVENC hardware — CPU encoding is the only option.
        # threads=0 lets x264 auto-detect (use all cores). Pass an explicit
        # value when running many ffmpeg processes in parallel — otherwise
        # each process tries to claim every core, producing massive
        # context-switch contention (60 processes × 80 threads each =
        # 4800 threads competing for 80 cores, render time blows up).
        # -fps_mode passthrough: honor filter graph PTS exactly. Without
        # this, libx264 forces CFR by duplicating/dropping frames to fit
        # the output frame rate, which re-introduces the quantization
        # drift the speed-warped setpts was supposed to eliminate.
        _x264_threads = f"threads={threads}"
        if quality == "lossless":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]
        else:
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-maxrate", "15M", "-bufsize", "30M",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]

# Module-level: tracks active Remotion chunk subprocesses for cleanup on timeout
_overlay_chunk_procs = []

_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937\U00010000-\U0010ffff"
    "\u2640-\u2642\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030]+",
    flags=re.UNICODE,
)
def get_trend_context():
    """Load the current weekly editing style guide from Supabase."""
    if supabase is None:
        print("[trend] No valid trend profile found", flush=True)
        return None
    try:
        result = supabase.table("trend_profiles") \
            .select("profile_json, sample_size") \
            .gt("valid_until", datetime.utcnow().isoformat()) \
            .order("valid_until", desc=True) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            profile = result.data[0]["profile_json"]
            sample_size = result.data[0].get("sample_size", 0)

            if isinstance(profile, dict) and profile.get("type") == "style_guide":
                style_guide = profile.get("style_guide", "")
                print(f"[trend] Loaded editing style guide: {sample_size} videos, {len(style_guide)} chars", flush=True)
                return {"type": "style_guide", "style_guide": style_guide, "sample_size": sample_size}
            else:
                print(f"[trend] Loaded trend profile (legacy stats): {sample_size} videos", flush=True)
                return profile
        else:
            print("[trend] No valid trend profile found", flush=True)
            return None
    except Exception as e:
        print(f"[trend] Error loading trend context: {e}", flush=True)
        return None


def format_trend_section(trend_context):
    """Format the trend context for injection into the Gemini prompt."""
    if not trend_context:
        return ""

    try:
        if isinstance(trend_context, dict) and trend_context.get("type") == "style_guide":
            style_guide = trend_context.get("style_guide", "")
            sample_size = trend_context.get("sample_size", 0)
            if not style_guide:
                return ""

            return f"""

=== WHAT'S WORKING ON TIKTOK RIGHT NOW ===

The following editing style guide was generated by watching {sample_size} of the highest-performing TikTok videos from this week — videos with 500K+ views that the algorithm is actively distributing. These are real patterns from real viral content, not theory.

Follow these patterns for speed ramping, pacing, and cuts only.

{style_guide}"""

        elif isinstance(trend_context, dict) and "numeric_patterns" in trend_context:
            sample_size = trend_context.get("sample_size", 0)
            return f"\n\n(Legacy trend data from {sample_size} videos available but in old format)\n"

        else:
            return ""

    except Exception as e:
        print(f"[trend] Error formatting trend section: {e}", flush=True)
        return ""

# Download arnndn noise-reduction model if not present (used by audio_denoise feature)
_RNNOISE_MODEL_PATH = "/usr/share/rnnoise/bd.rnnn"
SFX_SOUNDS_DIR    = os.path.join(os.path.dirname(__file__), "assets", "sounds")
CAPTION_FONT_DIR = "/usr/local/share/fonts/montserrat"


_fonts_registered = False
def ensure_caption_fonts_registered():
    """Register mounted caption fonts with fontconfig.
    Fonts are pre-registered at container build time (modal_app.py), so this
    is a fast no-op check in the common case. Only runs once per container.
    """
    global _fonts_registered
    if _fonts_registered:
        return
    _fonts_registered = True
    try:
        # Check if fonts are already registered (build-time registration)
        fc_check = subprocess.run(
            ["fc-list", ":family=Montserrat"], capture_output=True, text=True, timeout=5)
        if "Montserrat" in (fc_check.stdout or ""):
            print("[fonts] Montserrat already registered (build-time)", flush=True)
            return
        # Fallback: register at runtime
        os.makedirs(CAPTION_FONT_DIR, exist_ok=True)
        copied = 0
        for src in glob.glob("/assets/fonts/*.ttf"):
            dst = os.path.join(CAPTION_FONT_DIR, os.path.basename(src))
            shutil.copy2(src, dst)
            copied += 1
        subprocess.run(["fc-cache", "-f"], check=False, capture_output=True, text=True, timeout=20)
        print(f"[fonts] Registered {copied} caption fonts into {CAPTION_FONT_DIR}", flush=True)
    except Exception as e:
        print(f"[fonts] WARNING: failed to register caption fonts: {e}", flush=True)
if not os.path.exists(_RNNOISE_MODEL_PATH):
    try:
        os.makedirs(os.path.dirname(_RNNOISE_MODEL_PATH), exist_ok=True)
        import urllib.request
        urllib.request.urlretrieve(
            "https://github.com/GregorR/rnnoise-models/raw/master/beguiling-drafter-2018-08-30/bd.rnnn",
            _RNNOISE_MODEL_PATH
        )
        print(f"[startup] arnndn model downloaded → {_RNNOISE_MODEL_PATH}", flush=True)
    except Exception as e:
        print(f"[startup] arnndn model download failed (audio_denoise will be skipped): {e}", flush=True)
else:
    print(f"[startup] arnndn model present: {_RNNOISE_MODEL_PATH}", flush=True)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def detect_face_positions(video_path, sample_timestamps):
    """
    Sample frames at given timestamps and detect the dominant face position.
    Uses OpenCV's DNN-based face detector (ResNet SSD) which is far more
    reliable than Haar cascades — handles angled faces, glasses, hats,
    varying skin tones, and low light.
    Returns list of {"t", "cx", "cy", "found"} entries.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[reframe] Could not open video for face detection", flush=True)
        return []

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    center_x = frame_w // 2 if frame_w > 0 else 540
    center_y = frame_h // 2 if frame_h > 0 else 960

    # Load DNN face detector (ResNet-10 SSD, trained on WIDER FACE dataset)
    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    use_dnn = os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)

    if use_dnn:
        net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
        print("[reframe] Using DNN face detector (ResNet SSD)", flush=True)
    else:
        # Fallback to Haar cascade if model files not available
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        print("[reframe] WARNING: DNN model not found, falling back to Haar cascade", flush=True)

    # Track last known face position for temporal smoothing
    last_cx, last_cy = center_x, center_y
    CONFIDENCE_THRESHOLD = 0.5

    positions = []
    for t in sample_timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            positions.append({"t": float(t), "cx": last_cx, "cy": last_cy, "found": False})
            continue

        found = False
        best_cx, best_cy = center_x, center_y
        best_conf = 0.0

        if use_dnn:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)), 1.0, (300, 300),
                (104.0, 177.0, 123.0), swapRB=False, crop=False
            )
            net.setInput(blob)
            detections = net.forward()

            best_area = 0
            for det_i in range(detections.shape[2]):
                confidence = float(detections[0, 0, det_i, 2])
                if confidence < CONFIDENCE_THRESHOLD:
                    continue
                x1 = int(detections[0, 0, det_i, 3] * w)
                y1 = int(detections[0, 0, det_i, 4] * h)
                x2 = int(detections[0, 0, det_i, 5] * w)
                y2 = int(detections[0, 0, det_i, 6] * h)
                area = (x2 - x1) * (y2 - y1)
                # Pick the largest face with highest confidence
                if confidence > best_conf or (confidence > CONFIDENCE_THRESHOLD and area > best_area):
                    best_conf = confidence
                    best_area = area
                    best_cx = (x1 + x2) // 2
                    best_cy = (y1 + y2) // 2
                    found = True
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
            if len(faces) > 0:
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                best_cx = int(fx + fw // 2)
                best_cy = int(fy + fh // 2)
                found = True

        if found:
            last_cx, last_cy = best_cx, best_cy

        positions.append({
            "t": float(t),
            "cx": best_cx if found else last_cx,
            "cy": best_cy if found else last_cy,
            "found": found,
            "confidence": best_conf if found else 0.0,
        })

    cap.release()
    found_count = sum(1 for p in positions if p["found"])
    print(f"[reframe] Detected faces in {found_count}/{len(positions)} sampled frames", flush=True)
    return positions


def detect_face_positions_dense(video_path, every_n_frames=5, target_w=None, target_h=None):
    """
    Dense face detection using FFmpeg frame extraction + OpenCV DNN.
    FFmpeg extracts every Nth frame with GPU decode (NVDEC) — much faster
    than OpenCV's sequential read/grab loop which must decode all h264 frames.

    target_w/target_h: if set, scale coordinates to this resolution (e.g., when
    running on a low-res proxy but need coords in original source resolution).

    Returns list of {"t": float, "cx": float, "cy": float, "found": bool, "confidence": float}.
    """
    import cv2

    # Probe video metadata without decoding
    _probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True, timeout=5,
    )
    _streams = json.loads(_probe.stdout or "{}").get("streams", [])
    _vs = next((s for s in _streams if s.get("codec_type") == "video"), {})
    fps = float(eval(_vs.get("r_frame_rate", "30/1")))
    frame_count = int(_vs.get("nb_frames", 0)) or int(float(_vs.get("duration", "0")) * fps)
    frame_w = int(_vs.get("width", 0)) or 1080
    frame_h = int(_vs.get("height", 0)) or 1920

    # Output resolution for face coordinates
    _out_w = target_w or frame_w
    _out_h = target_h or frame_h

    # Extract at native resolution if source is already small (e.g., 240p proxy),
    # otherwise extract at 540p for speed
    _extract_h = min(540, frame_h)
    _scale = _out_h / _extract_h if _extract_h > 0 else 1.0
    _extract_w = round(frame_w * _extract_h / frame_h) if frame_h > 0 else round(_out_w * _extract_h / _out_h)
    center_x = _out_w // 2
    center_y = _out_h // 2

    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    if not (os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)):
        print("[dense-face] DNN model not found, cannot run dense detection", flush=True)
        return []

    net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    CONFIDENCE_THRESHOLD = 0.5

    _t_start = time.time()

    # Extract every Nth frame at reduced resolution using FFmpeg with GPU decode.
    # This is 5-10x faster than OpenCV's grab()/read() loop because:
    # 1. NVDEC hardware decode (vs CPU h264 decode)
    # 2. Only outputs frames we need (vs decoding all frames sequentially)
    # 3. Downscale happens on GPU or during decode (less memory bandwidth)
    _extract_dir = os.path.join(os.path.dirname(video_path) or "/tmp", "_face_frames")
    os.makedirs(_extract_dir, exist_ok=True)
    _hw_args = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
    _extract_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning"] + _hw_args + [
            "-i", video_path,
            "-vf", f"select=not(mod(n\\,{every_n_frames})),scale={_extract_w}:{_extract_h}",
            "-vsync", "0", "-q:v", "2",
            os.path.join(_extract_dir, "face_%04d.jpg"),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if _extract_cmd.returncode != 0:
        print(f"[dense-face] FFmpeg extraction failed, falling back to OpenCV: {_extract_cmd.stderr[-200:]}", flush=True)
        # Fallback: use basic OpenCV approach
        return _detect_face_positions_dense_fallback(video_path, every_n_frames)

    _extract_elapsed = time.time() - _t_start
    _frame_files = sorted(glob.glob(os.path.join(_extract_dir, "face_*.jpg")))
    if not _frame_files:
        print("[dense-face] No frames extracted", flush=True)
        return []

    # Run DNN on extracted frames
    last_cx, last_cy = center_x, center_y
    positions = []

    for _fi, _fpath in enumerate(_frame_files):
        frame_idx = _fi * every_n_frames
        t_sec = frame_idx / fps
        frame = cv2.imread(_fpath)
        if frame is None:
            continue

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0), swapRB=False, crop=False
        )
        net.setInput(blob)
        detections = net.forward()

        found = False
        best_cx, best_cy = center_x, center_y
        best_conf = 0.0
        best_area = 0

        for det_i in range(detections.shape[2]):
            confidence = float(detections[0, 0, det_i, 2])
            if confidence < CONFIDENCE_THRESHOLD:
                continue
            # Coordinates are in extract resolution — scale back to original
            x1 = int(detections[0, 0, det_i, 3] * w * _scale)
            y1 = int(detections[0, 0, det_i, 4] * h * _scale)
            x2 = int(detections[0, 0, det_i, 5] * w * _scale)
            y2 = int(detections[0, 0, det_i, 6] * h * _scale)
            area = (x2 - x1) * (y2 - y1)
            if confidence > best_conf or (confidence > CONFIDENCE_THRESHOLD and area > best_area):
                best_conf = confidence
                best_area = area
                best_cx = (x1 + x2) // 2
                best_cy = (y1 + y2) // 2
                found = True

        if found:
            last_cx, last_cy = best_cx, best_cy

        positions.append({
            "t": round(t_sec, 4),
            "cx": float(best_cx if found else last_cx),
            "cy": float(best_cy if found else last_cy),
            "found": found,
            "confidence": round(best_conf, 4) if found else 0.0,
        })

    # Cleanup extracted frames
    for _f in _frame_files:
        try:
            os.remove(_f)
        except OSError:
            pass
    try:
        os.rmdir(_extract_dir)
    except OSError:
        pass

    elapsed = time.time() - _t_start
    found_count = sum(1 for p in positions if p["found"])
    print(
        f"[dense-face] {found_count}/{len(positions)} detections in {elapsed:.2f}s "
        f"({frame_count} total frames, every {every_n_frames}th @ {fps:.1f}fps, extracted at {_extract_w}x{_extract_h})",
        flush=True,
    )
    return positions


def _detect_face_positions_dense_fallback(video_path, every_n_frames=5):
    """Fallback face detection using OpenCV sequential read (slower, no FFmpeg)."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1080)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
    center_x, center_y = frame_w // 2, frame_h // 2
    net = cv2.dnn.readNetFromCaffe(
        "/models/face_detector/deploy.prototxt",
        "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel",
    )
    last_cx, last_cy = center_x, center_y
    positions = []
    frame_idx = 0
    while True:
        if frame_idx % every_n_frames == 0:
            ret, frame = cap.read()
            if not ret:
                break
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=False, crop=False)
            net.setInput(blob)
            detections = net.forward()
            found, best_cx, best_cy, best_conf, best_area = False, center_x, center_y, 0.0, 0
            for di in range(detections.shape[2]):
                conf = float(detections[0, 0, di, 2])
                if conf < 0.5:
                    continue
                x1, y1, x2, y2 = int(detections[0,0,di,3]*w), int(detections[0,0,di,4]*h), int(detections[0,0,di,5]*w), int(detections[0,0,di,6]*h)
                area = (x2-x1)*(y2-y1)
                if conf > best_conf or area > best_area:
                    best_conf, best_area, best_cx, best_cy, found = conf, area, (x1+x2)//2, (y1+y2)//2, True
            if found:
                last_cx, last_cy = best_cx, best_cy
            positions.append({"t": round(frame_idx/fps, 4), "cx": float(best_cx if found else last_cx), "cy": float(best_cy if found else last_cy), "found": found, "confidence": round(best_conf, 4) if found else 0.0})
        else:
            if not cap.grab():
                break
        frame_idx += 1
    cap.release()
    return positions


def smooth_face_trajectory(detections, total_duration=0.0, alpha=0.15):
    """
    Apply exponential moving average to dense face detections for buttery
    smooth camera movement.  Gaps (found=False) coast on the last known
    smoothed position.

    Returns a new list with the same structure but smoothed cx/cy values.
    """
    if not detections:
        return []

    smoothed = []
    sx, sy = None, None

    for det in detections:
        cx = float(det.get("cx", 540.0))
        cy = float(det.get("cy", 960.0))
        found = det.get("found", False)

        if sx is None:
            # Initialise with first position
            sx, sy = cx, cy
        else:
            if found:
                sx = alpha * cx + (1.0 - alpha) * sx
                sy = alpha * cy + (1.0 - alpha) * sy
            # else: coast — sx/sy stay unchanged

        smoothed.append({
            "t": det["t"],
            "cx": round(sx, 2),
            "cy": round(sy, 2),
            "found": found,
            "confidence": det.get("confidence", 0.0),
        })

    return smoothed


def calculate_reframe_crop(face_positions, source_w, source_h, target_w=1080, target_h=1920):
    """
    Calculate a crop window that keeps the detected face near frame center.
    Returns crop positions in source-pixel coordinates, or None if no crop shift is needed.
    """
    if source_w == target_w and source_h == target_h:
        return None

    target_aspect = target_w / target_h
    source_aspect = source_w / source_h if source_h else target_aspect

    if source_aspect > target_aspect:
        crop_h = source_h
        crop_w = int(source_h * target_aspect)
    else:
        crop_w = source_w
        crop_h = int(source_w / target_aspect) if target_aspect else source_h

    crops = []
    for pos in face_positions:
        crop_x = int(pos["cx"] - crop_w // 2)
        crop_y = int(pos["cy"] - crop_h // 2)
        crop_x = max(0, min(crop_x, max(0, source_w - crop_w)))
        crop_y = max(0, min(crop_y, max(0, source_h - crop_h)))
        crops.append({
            "t": pos["t"],
            "crop_x": crop_x,
            "crop_y": crop_y,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "found": bool(pos.get("found")),
        })

    return crops

def normalize_analysis(parsed):
    if not parsed.get("speech"):
        parsed["speech"] = {"has_speech": False, "segments": [], "sentence_boundaries": []}
    if not parsed.get("safe_cut_points"):
        parsed["safe_cut_points"] = []
    if not parsed.get("peak_moments"):
        parsed["peak_moments"] = []
    if not parsed.get("highlights"):
        parsed["highlights"] = []
    if parsed.get("footage_assessment") and not parsed.get("video_profile"):
        parsed["video_profile"] = parsed["footage_assessment"]

    duration = float(parsed.get("duration") or 0)
    shots_raw = parsed.get("shots") or []
    shots = []
    for i, s in enumerate(shots_raw):
        shots.append({
            "start":         float(s.get("start") or 0),
            "end":           float(s.get("end") or duration),
            "visual":        s.get("visual") or "",
            "action":        s.get("action") or "",
            "energy":        float(s.get("energy") or 0.5),
            "editing_value": s.get("editing_value") or "",
            "delivery":      s.get("delivery") or "none",
            "description":   s.get("action") or s.get("visual") or f"Shot {i+1}",
            "score":         float(s.get("energy") or 0.5),
        })
    if not shots:
        shots = [{"start": 0, "end": duration, "description": "Full video", "score": 0.5,
                  "visual": "", "action": "", "energy": 0.5, "editing_value": "", "delivery": "none"}]

    raw_cb = parsed.get("color_baseline") or {}
    color_baseline = {
        "assessment":        raw_cb.get("assessment") or "",
        "brightness":        float(raw_cb["brightness"]) if isinstance(raw_cb.get("brightness"), (int, float)) else 1,
        "contrast":          float(raw_cb["contrast"]) if isinstance(raw_cb.get("contrast"), (int, float)) else 1,
        "saturation":        float(raw_cb["saturation"]) if isinstance(raw_cb.get("saturation"), (int, float)) else 1,
        "gamma":             float(raw_cb["gamma"]) if isinstance(raw_cb.get("gamma"), (int, float)) else 1,
        "color_temperature": raw_cb.get("color_temperature") if raw_cb.get("color_temperature") in ["warm", "cool", "neutral"] else "neutral",
    }
    raw_fl = parsed.get("frame_layout") or {}
    frame_layout = {
        "subject_position": raw_fl.get("subject_position") or "unknown",
        "existing_overlays": {
            "has_burned_captions": bool((raw_fl.get("existing_overlays") or {}).get("has_burned_captions")),
            "has_text_graphics":   bool((raw_fl.get("existing_overlays") or {}).get("has_text_graphics")),
            "overlay_locations":   (raw_fl.get("existing_overlays") or {}).get("overlay_locations") or "none detected",
        },
        "free_zones": raw_fl.get("free_zones") or "unknown",
    }

    # Hook, pacing, recommended_duration (new fields — backward compatible)
    raw_fa  = parsed.get("footage_assessment") or parsed.get("video_profile") or {}
    raw_hook = raw_fa.get("hook") or {}
    hook = {
        "timestamp":   float(raw_hook["timestamp"]) if isinstance(raw_hook.get("timestamp"), (int, float)) else 0.0,
        "description": str(raw_hook.get("description") or ""),
        "why":         str(raw_hook.get("why") or ""),
        "quality":     float(raw_hook["quality"]) if isinstance(raw_hook.get("quality"), (int, float)) else 0.5,
    } if raw_hook else None

    recommended_duration = None
    if isinstance(raw_fa.get("recommended_duration"), (int, float)):
        recommended_duration = int(raw_fa["recommended_duration"])

    pacing = str(raw_fa.get("pacing") or "").strip().lower()
    if pacing not in ("fast", "medium", "slow"):
        pacing = None

    raw_fq = parsed.get("footage_quality") or {}
    valid_noise       = {"none", "low", "medium", "high"}
    valid_sharpness   = {"soft", "normal", "sharp"}
    valid_highlight   = {"clipped", "bright", "normal", "dark"}
    valid_shadow      = {"crushed", "deep", "normal", "lifted"}
    valid_richness    = {"flat", "muted", "normal", "vivid"}
    valid_lighting    = {"natural_outdoor", "natural_indoor", "studio", "mixed", "unknown"}
    footage_quality = {
        "noise_level":       raw_fq.get("noise_level", "low") if raw_fq.get("noise_level") in valid_noise else "low",
        "source_sharpness":  raw_fq.get("source_sharpness", "normal") if raw_fq.get("source_sharpness") in valid_sharpness else "normal",
        "highlight_condition": raw_fq.get("highlight_condition", "normal") if raw_fq.get("highlight_condition") in valid_highlight else "normal",
        "shadow_condition":  raw_fq.get("shadow_condition", "normal") if raw_fq.get("shadow_condition") in valid_shadow else "normal",
        "color_richness":    raw_fq.get("color_richness", "normal") if raw_fq.get("color_richness") in valid_richness else "normal",
        "skin_tones_present": bool(raw_fq.get("skin_tones_present", True)),
        "lighting_type":     raw_fq.get("lighting_type", "unknown") if raw_fq.get("lighting_type") in valid_lighting else "unknown",
    }
    safe_cut_points = parsed.get("cut_points") or parsed.get("safe_cut_points") or []
    peak_moments = parsed.get("highlights") or parsed.get("peak_moments") or []
    vp = parsed.get("video_profile") or parsed.get("footage_assessment") or {}

    return {
        "duration":             duration,
        "shots":                shots,
        "speech":               parsed.get("speech") or {"has_speech": False, "segments": [], "sentence_boundaries": []},
        "audio":                parsed.get("audio") or {},
        "safe_cut_points":      safe_cut_points,
        "peak_moments":         peak_moments,
        "video_profile":        vp,
        "frame_layout":         frame_layout,
        "color_baseline":       color_baseline,
        "footage_quality":      footage_quality,
        "metadata":             parsed.get("metadata") or {},
        "visual_cuts":          [],
        "hook":                 hook,
        "recommended_duration": recommended_duration,
        "pacing":               pacing,
    }




# ─── BEAT DETECTION ──────────────────────────────────────────────────────────

def detect_beats(source_path):
    """Extract audio beat timestamps using aubio."""
    import aubio
    import numpy as np

    # Extract raw audio via ffmpeg → aubio
    cmd = [
        "ffmpeg", "-i", source_path,
        "-f", "f32le", "-ac", "1", "-ar", "44100", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = proc.stdout.read()
    proc.wait()
    if proc.returncode != 0:
        stderr_tail = (proc.stderr.read() or b"").decode("utf-8", errors="replace")[-300:]
        raise RuntimeError(f"FFmpeg audio extraction for beat detection failed: {stderr_tail}")

    samplerate = 44100
    hop_size   = 512
    win_size   = 1024
    samples    = np.frombuffer(raw, dtype="float32")
    if len(samples) == 0:
        raise RuntimeError(f"FFmpeg produced zero audio samples from {source_path}")

    tempo_detect = aubio.tempo("default", win_size, hop_size, samplerate)
    beats = []
    for i in range(0, len(samples) - hop_size, hop_size):
        chunk = samples[i:i + hop_size]
        if tempo_detect(chunk):
            beats.append(round(i / samplerate, 3))

    print(f"[beats] aubio detected {len(beats)} beats", flush=True)
    return beats


# ─── DEEPGRAM TRANSCRIPTION ───────────────────────────────────────────────────


def transcribe_audio(source_path):
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    try:
        dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
        with open(source_path, "rb") as f:
            audio_bytes = f.read()
        print(f"[deepgram] Sending {len(audio_bytes) / 1024:.0f}KB audio", flush=True)
        options = PrerecordedOptions(
            model="nova-3", detect_language=True,
            smart_format=True, utterances=True, punctuate=True, diarize=True,
        )
        resp = dg.listen.prerecorded.v("1").transcribe_file({"buffer": audio_bytes}, options)
        alt = resp.results.channels[0].alternatives[0]
        raw_words = alt.words or []
        words = [
            {
                "word":            w.word,
                "punctuated_word": getattr(w, "punctuated_word", w.word),
                "start":           float(w.start),
                "end":             float(w.end),
                "confidence":      float(getattr(w, "confidence", 1.0)),
                "speaker":         int(getattr(w, "speaker", 0)),
            }
            for w in raw_words
        ]

        # Utterances group words by speaker turn and are more reliable than
        # per-word speaker labels. Override per-word labels with utterance-level
        # speaker assignments when available.
        raw_utterances = getattr(resp.results, "utterances", None) or []
        if raw_utterances:
            utt_count = 0
            for utt in raw_utterances:
                utt_start = float(getattr(utt, "start", 0))
                utt_end = float(getattr(utt, "end", 0))
                utt_speaker = int(getattr(utt, "speaker", 0))
                for w in words:
                    if w["start"] >= utt_start - 0.05 and w["end"] <= utt_end + 0.05:
                        w["speaker"] = utt_speaker
                utt_count += 1
            print(f"[deepgram] Applied {utt_count} utterance-level speaker labels", flush=True)

        speaker_ids = set(w["speaker"] for w in words)
        if len(speaker_ids) > 1:
            print(f"[deepgram] Detected {len(speaker_ids)} speakers", flush=True)
        print(f"[deepgram] Transcribed {len(words)} words", flush=True)
        return {"text": alt.transcript or "", "words": words}
    except Exception as e:
        raise RuntimeError(f"Deepgram transcription failed: {e}") from e




# ─── TIGHTEN ──────────────────────────────────────────────────────────────────

ALWAYS_FILLER = {"um","uh","uhh","uhm","umm","erm","er","hmm","hm","mm","mmm","mhm","ah","ahh","huh"}
CONTEXT_FILLER = {"like","right","so","basically","literally","actually","honestly","obviously","just","really"}
MULTI_WORD_FILLER = [["you","know"],["i","mean"],["kind","of"],["sort","of"]]


def measure_source_loudness(source_path):
    """
    Measure the source audio's peak level, RMS, and noise floor using ffmpeg.
    Returns dict with 'peak_db', 'rms_db', 'noise_floor_db' (all negative floats).
    """
    # astats gives us peak, RMS; we sample the first 60s to keep it fast
    cmd = [
        "ffmpeg", "-i", source_path, "-t", "60",
        "-af", "astats=metadata=1:reset=0,ametadata=mode=print",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg loudness measurement failed: {(result.stderr or '')[-300:]}")
    stderr = result.stderr

    # Parse peak and RMS from astats output
    peak_matches = re.findall(r"lavfi\.astats\.Overall\.Peak_level=([-\d.]+)", stderr)
    rms_matches = re.findall(r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", stderr)
    noise_matches = re.findall(r"lavfi\.astats\.Overall\.Noise_floor=([-\d.]+)", stderr)
    if not peak_matches or not rms_matches:
        raise RuntimeError(f"FFmpeg astats returned no loudness data for {source_path}")

    peak_db = float(peak_matches[-1]) if peak_matches else -6.0
    rms_db = float(rms_matches[-1]) if rms_matches else -18.0
    # Noise floor: if astats reports it, use it; otherwise estimate from RMS - 24dB
    if noise_matches:
        noise_floor_db = float(noise_matches[-1])
    else:
        noise_floor_db = rms_db - 24.0

    # Clamp to reasonable ranges
    peak_db = max(-60.0, min(0.0, peak_db))
    rms_db = max(-60.0, min(0.0, rms_db))
    noise_floor_db = max(-70.0, min(-20.0, noise_floor_db))

    print(
        f"[loudness] peak={peak_db:.1f}dB rms={rms_db:.1f}dB noise_floor={noise_floor_db:.1f}dB",
        flush=True,
    )
    return {"peak_db": peak_db, "rms_db": rms_db, "noise_floor_db": noise_floor_db}


def auto_detect_hook(emphasis_moments, deepgram_words, source_beats, source_loudness, video_duration):
    """
    Score candidate moments and return the best hook segment.
    Uses emphasis type, audio energy proxy, speech rate changes, and position
    to pick the most compelling hook moment.
    Returns ({"source_start": float, "source_end": float}, score) or (None, 0).
    """
    if not emphasis_moments or not deepgram_words or video_duration <= 0:
        return None, 0

    # ── Weight constants ──────────────────────────────────────────────────
    W_EMPHASIS = 0.35
    W_ENERGY   = 0.25
    W_SPEECH   = 0.25
    W_POSITION = 0.15
    SCORE_THRESHOLD = 2.0  # minimum weighted score to be considered valid

    # ── Pre-compute words-per-second in 1s buckets for speech-rate signal ─
    wps_buckets = {}
    for w in deepgram_words:
        try:
            t = float(w.get("start") or 0)
        except (TypeError, ValueError):
            continue
        bucket = int(t)
        wps_buckets[bucket] = wps_buckets.get(bucket, 0) + 1

    # ── Pre-compute beat density per second (proxy for audio energy) ──────
    beat_density = {}
    if isinstance(source_beats, list):
        for bt in source_beats:
            try:
                bucket = int(float(bt))
                beat_density[bucket] = beat_density.get(bucket, 0) + 1
            except (TypeError, ValueError):
                continue

    max_bd = max(beat_density.values()) if beat_density else 1
    if max_bd == 0:
        max_bd = 1

    # ── Score each emphasis moment ────────────────────────────────────────
    _TYPE_SCORES = {
        "punchline":  10,
        "revelation": 8,
        "reaction":   6,
        "question":   5,
        "statement":  4,
        "transition": 2,
    }

    scored = []
    for em in emphasis_moments:
        em_t = float(em["t"])
        em_type = em.get("type", "statement")
        em_intensity = em.get("intensity", "medium")

        # 1) Emphasis type score (0-10)
        base_type = _TYPE_SCORES.get(em_type, 4)
        if em_intensity == "high":
            type_score = base_type
        else:
            type_score = base_type * 0.5

        # 2) Audio energy score (0-10): beat density around the moment
        bucket = int(em_t)
        nearby_beats = sum(beat_density.get(bucket + d, 0) for d in (-1, 0, 1))
        energy_score = min(10.0, (nearby_beats / max(max_bd, 1)) * 10.0)

        # 3) Speech rate change score (0-10)
        bucket_before_1 = wps_buckets.get(bucket - 2, 0) + wps_buckets.get(bucket - 1, 0)
        bucket_at = wps_buckets.get(bucket, 0) + wps_buckets.get(bucket + 1, 0)
        rate_before = bucket_before_1 / 2.0 if bucket_before_1 > 0 else 0
        rate_at = bucket_at / 2.0 if bucket_at > 0 else 0

        speech_score = 0.0
        if rate_before > 0:
            drop_ratio = 1.0 - (rate_at / rate_before)
            if drop_ratio > 0.4:
                speech_score = min(10.0, drop_ratio * 15.0)
            elif drop_ratio > 0.2:
                speech_score = min(5.0, drop_ratio * 10.0)

        # 4) Position penalty (0-10)
        rel_pos = em_t / video_duration
        if rel_pos < 0.15 or rel_pos > 0.85:
            position_score = 0.0
        elif 0.25 <= rel_pos <= 0.75:
            position_score = 10.0
        else:
            position_score = 5.0

        total = (
            W_EMPHASIS * type_score +
            W_ENERGY   * energy_score +
            W_SPEECH   * speech_score +
            W_POSITION * position_score
        )
        scored.append((em, total))

    if not scored:
        return None, 0

    scored.sort(key=lambda x: x[1], reverse=True)
    best_em, best_score = scored[0]

    if best_score < SCORE_THRESHOLD:
        print(f"[hook-auto] Best score {best_score:.2f} below threshold {SCORE_THRESHOLD} — no auto hook", flush=True)
        return None, 0

    em_t = float(best_em["t"])
    hook_start = max(0.0, em_t - 0.3)
    hook_end = min(video_duration, em_t + 2.0)

    # ── Snap to word boundaries ───────────────────────────────────────────
    best_word_start = hook_start
    best_word_end = hook_end
    for w in deepgram_words:
        try:
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
        except (TypeError, ValueError):
            continue
        if ws <= hook_start + 0.15 and ws >= hook_start - 0.5:
            best_word_start = ws
        if we >= hook_end - 0.3 and we <= hook_end + 0.8:
            best_word_end = we
            break

    hook_start = max(0.0, best_word_start)
    hook_end = min(video_duration, best_word_end)

    # Clamp duration to 0.5-3.0s range
    hook_dur = hook_end - hook_start
    if hook_dur < 0.5:
        hook_end = min(video_duration, hook_start + 0.8)
    elif hook_dur > 3.0:
        hook_end = hook_start + 2.5

    hook_dur = hook_end - hook_start
    if hook_dur < 0.5:
        return None, 0

    result = {
        "source_start": round(hook_start, 3),
        "source_end":   round(hook_end, 3),
    }
    print(f"[hook-auto] Best moment: {em_t:.2f}s ({best_em.get('type')}/{best_em.get('intensity')}) "
          f"score={best_score:.2f} → hook {result['source_start']:.3f}-{result['source_end']:.3f}", flush=True)
    return result, best_score


def extract_json(text):
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Empty Gemini response")
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"```json\s*\n?([\s\S]*?)\n?\s*```", raw, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    m = re.search(r"```\s*\n?([\s\S]*?)\n?\s*```", raw)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    first = raw.index("{") if "{" in raw else -1
    last  = raw.rindex("}") if "}" in raw else -1
    if first != -1 and last > first:
        try:
            return json.loads(raw[first:last+1])
        except Exception:
            pass
    raise ValueError("Could not extract valid JSON from Gemini response")


def build_gemini_edit_prompt(vibe, duration, trend_context=None):
    trend_block = ""
    if trend_context:
        trend_block = "\n\n" + format_trend_section(trend_context)

    prompt = f"""You are a professional short-form video editor. You are watching the source video right now. You can see every frame and hear every word.

The user wants: "{vibe}"

This video is {duration:.1f} seconds long. It will be posted on TikTok, Instagram Reels, or YouTube Shorts — vertical full-screen content where viewers decide in 2 seconds whether to keep watching or scroll past.

Watch the video. Then create an edit recipe that transforms this raw footage into something that feels professionally edited and matches the vibe the user described.

=== HOW TO THINK ABOUT THIS EDIT ===

What does the user actually want? They want to watch the finished video and feel like a professional editor understood their footage and made it look incredible. The edit should feel intentional — every cut, every speed change, every sound has a reason.

As you watch, pay attention to:
- Where the content changes (speaker to screen recording, topic shifts, visual changes)
- Where the energy peaks (strong statements, reveals, punchlines) and where it dips (filler, transitions between ideas, breaths)
- Where the viewer's attention would drift without intervention
- What's already baked into the footage (burned-in captions, existing text, graphics)

=== WHAT MAKES SHORT-FORM CONTENT FEEL EDITED ===

The opening is an audition. The first 2 seconds must give the viewer a reason to stay. A visual event, a sonic hit, tighter framing, text that creates curiosity — something that signals this isn't raw footage.

Pacing creates rhythm. For short-form content, the average clip should be 2-3 seconds. The Captions app and top TikTok editors cut every 2-3 seconds — this is the standard. Filler and setup should move even faster (1-2s). Key moments — reveals, punchlines, important statements — should breathe (3-4s max). The contrast between fast and slow is what makes pacing feel alive. When in doubt, cut shorter.

You are the editor. You decide what stays and what gets cut.

Your goal: make the final transcript as tight and to the point as possible without cutting actual valuable content. You understand the emotion and humor of what's being said — you know the difference between filler and content that matters. Every "um", every stutter, every false start, every meaningless pause gets cut. Every joke, every emotional beat, every setup that pays off later stays.

You are a professional short-form editor. You have the exact transcript with millisecond timestamps. Use them to place PRECISE cuts. Think like a human editor who can see the waveform and the video simultaneously.

DEAD AIR IN SPEECH CONTENT:
ALL silence is bad unless it's a deliberate comedic or dramatic pause that serves the story. You have millisecond-accurate word timestamps — use them. Find EVERY gap between words and mark it for removal. Professional short-form editors leave ZERO dead air. The video should feel like a continuous stream of speech with no wasted frames.

- Under 0.08 seconds between words — natural word spacing. KEEP.
- 0.08–0.3 seconds — these feel like pauses to the viewer. REMOVE unless the pause is clearly dramatic.
- Over 0.3 seconds — these are dead air. ALWAYS REMOVE using a start/end time range.
- Scan the ENTIRE transcript systematically. Do not skip any gaps. Every gap between every pair of adjacent words must be evaluated.

HOW TO MARK REMOVALS PRECISELY:
- Use word_index when removing a specific spoken word.
- Use start/end time ranges when removing silence, dead air, or an entire section.
- The pipeline will build clips automatically from the kept words, so your job is only to say what gets removed.

CONTINUOUS PHRASES:
Words within the same phrase that have small natural gaps (under 0.10s) should usually stay together. Do not remove words inside a flowing phrase unless they are filler, a stutter, or clearly unwanted.

FIRST CLIP:
- If the video starts with someone talking, do not remove anything before the first word.
- If the video starts with visuals, music, or action before speech begins, preserve that content unless it is clearly dead air.

DEAD AIR IN NON-SPEECH CONTENT:
Not every video is a talking head. For videos with music, product shots, tutorials, vlogs, or mixed content:
- Watch the video. Dead air is any moment where NOTHING interesting is happening — no movement, no action, no visual change, no music energy.
- A car detailing video has dead air when the camera is static and nothing is being wiped or polished. The satisfying wipe moments are NOT dead air — they are the content.
- A cooking video has dead air when the person is walking to the fridge. The chopping and plating are the content.
- A product review has dead air when the person pauses to think. The demonstration is the content.
- A music video or montage rarely has dead air — the rhythm and visuals carry the pacing.

Your job as the editor: keep what's interesting, cut what isn't. Use the word timestamps for speech precision. Use your visual judgment for non-speech decisions. Every millisecond in the final video should earn its place.

GENERAL RULES:
- Never remove only half of a word. If a spoken word should go, remove it by word_index.
- For non-speech sections, remove dead ranges at natural visual break points — scene changes, camera movements, action pauses.
- The source timeline only moves forward. Removals must stay chronological.

Sound design adds texture. A whoosh on a scene change, a boom when a statement lands, a click when something appears — these make cuts feel physical instead of digital. But not every cut needs a sound. Continuous speech flows best with silent hard cuts.

The ending matters. On these platforms, videos auto-loop. A clean ending that flows back into the opening earns replay credit. Avoid fade to black — it creates a flash before the loop restarts.{trend_block}

  HOOK CLIP:
  The hook is the single most important part of any short-form video. It plays FIRST before the full video.

  Pick the PUNCHLINE or REACTION — the moment of maximum emotional intensity. NOT the setup, NOT the buildup. The hook should be the payoff that makes the viewer think "WAIT WHAT" and need to see how it got there. Always pick the climax or reveal, never the question or context that leads to it.

  The hook MUST:
  - Be 1-3 seconds max
  - Start with speech (not silence) — the first word should land within 0.3s
  - Be the CLIMAX of the story, not the buildup
  - NOT make sense without the rest of the video — that's what keeps them watching

  If the video already opens with a strong hook (first 2s are immediately compelling), set hook_clip to null.

=== TOOLS ===

Word-level edit control:

  remove_words — this is how you remove content. Do NOT output cuts. The pipeline will build clips automatically from Deepgram's exact word timestamps.

  Each remove_words item can be one of:

    {{"word_index": <index>, "reason": "<stutter|false_start|filler>"}}
      Use this when removing a specific spoken word. This is the preferred way to remove stutters, repeated words, false starts, and filler words.

    {{"start": <seconds>, "end": <seconds>, "reason": "<dead_air|section_skip|non_speech_gap>"}}
      Use this when removing a silence range, a dead-air gap, or a whole non-speech section.

  Rules for remove_words:

  YOU are responsible for removing ALL disfluencies. The pipeline trusts your decisions completely. Do not leave any of these in the transcript:

  ALWAYS REMOVE (these are NEVER content):
  - Non-word fillers: "um", "uh", "er", "ah", "hmm", "uhh", "umm", "erm", "mhm", "hm", "mm", "mmm", "ahh", "huh" — every single one, no exceptions
  - Exact-word stutters: "I I", "the the", "and and" — where the same word is spoken twice consecutively, remove the first occurrence
  - False starts: "shou-" before "shouldn't", "I was go-" before "I was going to" — where a partial word/phrase is abandoned and restarted, remove the abandoned attempt
  - Phrasal restarts: "I said, who is — I said, who is he?" — where a multi-word phrase is started, abandoned, and restarted, remove the first attempt

  CONTEXT-DEPENDENT (you decide based on the sentence):
  - "like", "so", "basically", "you know", "I mean", "right", "literally", "actually", "honestly", "obviously", "just", "really", "kind of", "sort of"
  - Before removing any of these words, read the full sentence it appears in. Remove the word mentally and check if the sentence still makes grammatical sense and means the same thing. If removing the word breaks the sentence or changes its meaning, it is content and must stay. "I felt like I had been electrocuted" — remove "like" and you get "I felt I had been electrocuted" which changes the sentence structure. That "like" is a grammatical comparison, not filler. Only remove these words when they genuinely add nothing to the meaning.

  ALSO REMOVE:
  - Silence gaps longer than 0.5 seconds — mark with start/end time ranges. Gaps under 0.5s are auto-collapsed by the pipeline.
  - Genuine off-topic garbage that has nothing to do with the video's subject

  KEEP EVERYTHING ELSE. All actual spoken content stays. This includes:
  - Every sentence, question, answer, reaction, greeting, sign-off, intro, outro
  - Interviewer responses ("okay", "right", "interesting", "thanks so much")
  - Setup, context, transitions — these are CONTENT, not filler
  - The last word of any sentence — never cut mid-speech

  opening_zoom — "slow_in", "slow_out", or "none". A subtle push or pull to draw the viewer in.
  Put opening_zoom on the hook clip if hook_clip is set, otherwise on the first clip in the video.

Global parameters:

  SPEED RAMPING (only when vibe mentions "speed ramp", "speed ramping", or "CapCut style"):

  Speed ramping is storytelling through pacing. Speed up when the content is moving TOWARD something — setup, context, transitions between story beats. Slow down when the content ARRIVES — the reveal, the punchline, the reaction. The contrast between fast and slow is what makes each moment land. Every speed change must be motivated by the narrative.

  The slow section should begin 0.3–0.5 seconds BEFORE the key word or phrase, so the viewer feels the deceleration building into the moment. By the time the punchline word lands, the video is already in slow-mo and the moment has weight. Starting the slow-mo exactly on the word is too late — the viewer misses the buildup.

  Fast sections: 1.2x-1.4x. Slow sections: 0.67x-0.8x. Every section is either fast or slow — the video never plays at normal speed.

  The system linearly interpolates between adjacent keypoints. Two keypoints far apart produce a gradual drift. Two keypoints at the same speed produce a held section. Two keypoints close together at different speeds produce a deliberate ramp. You control the speed curve by combining these three building blocks.

  To hold a speed: place two keypoints at the same speed value, one at the start and one at the end of the section you want held constant.

  To change speed: place the end-of-hold keypoint and the new-speed keypoint 0.55–1.2 seconds apart. The gap between these two keypoints MUST be at least 0.55 seconds — the pipeline interpolates between them with easing, and gaps shorter than 0.55s produce audible audio artifacts instead of a smooth ramp. If the nearest word boundary is less than 0.55s away, move the target keypoint further out until the gap is at least 0.55s.

  Every speed change needs a ramp pair. Every held section needs matching start and end keypoints. The full curve alternates: hold fast → ramp down → hold slow → ramp up → hold fast. Each transition is a pair of close keypoints. Each held section is a pair of matching keypoints.

  Use exact word timestamps from the Deepgram list (3+ decimal places). Slow sections must land on spoken words. Speed range: 0.67x to 1.4x. Aim for 10-16 keypoints per 60 seconds (3-5 ramp pairs with held sections between them).

  If speed ramping is not requested in the vibe, set speed_curve to "none".

  caption_style — animated captions rendered via Remotion. Choose the style that best matches the vibe:
    none — no captions. Use ONLY when captions are already burned into the footage.
    volt — THE flagship premium style. Bold Montserrat, lowercase, white text with cyan/teal keyword highlights, spring animation, cascade layout (small context words + large keywords), strong shadow. Modern, clean, high-energy. DEFAULT CHOICE for most content.
    clarity — ultra-clean minimal. Nunito Bold (rounded sans-serif), lowercase, white text, centered on screen, 1-2 words at a time, very subtle shadow, no pill/glow. Soft, friendly, premium feel. Best for: calm, thoughtful, interviews, podcasts, ASMR, minimal aesthetic.
    impact — bold punchy Anton (condensed display), lowercase, white text with RED keyword highlights, heavy shadow, cascade layout. Attention-grabbing. Best for: motivational, business, high-energy, announcements, bold statements.
    ember — elegant serif (Playfair Display), lowercase, white text with warm gold keywords, medium shadow. Premium editorial feel. Best for: luxury, fashion, beauty, storytelling, documentary, elegant content.
    velocity — maximum energy Montserrat Black, UPPERCASE, white text with yellow keyword highlights + yellow glow, heavy shadow. Loud and bold. Best for: hype, fast-paced, comedy, gaming, sports, trend content.
    archive — condensed Oswald, UPPERCASE, off-white text with gold keyword accents, strong shadow. Documentary/cinematic feel. Best for: cinematic, dramatic, serious, documentary, historical, news.
    lumen — clean Inter Bold, lowercase, white text on semi-transparent dark pill, teal/green keywords, wave animation. Modern and readable. Best for: educational, tutorials, explainers, tech, lifestyle.
    rebel — bold Montserrat, lowercase, white text with lime/green keyword highlights + green glow. Edgy and youthful. Best for: creative, artistic, music, dance, nightlife, alternative content.

  STYLE SELECTION GUIDE based on vibe:
    - "professional", "clean", "business", "corporate" → volt or archive
    - "calm", "chill", "thoughtful", "serious", "interview", "podcast" → clarity or ember
    - "hype", "energy", "fast", "comedy", "trend", "viral" → velocity or rebel
    - "motivational", "grind", "hustle", "inspirational" → impact or velocity
    - "cinematic", "dramatic", "reveal", "suspense", "documentary" → archive or ember
    - "aesthetic", "lifestyle", "travel", "minimal" → clarity or ember
    - "creative", "artistic", "music", "dance" → rebel or lumen
    - "casual", "vlog", "tutorial", "simple", "educational" → lumen or volt
    - "tech", "startup", "product", "SaaS" → lumen or clarity
    - "luxury", "fashion", "beauty", "premium" → ember or archive
    - "gaming", "esports", "stream" → velocity or rebel
    - When unsure, DEFAULT to volt — it looks great on everything.

  caption_position — where captions appear on screen. Use "lower-third" (default) for talking head content. The pipeline automatically adjusts positioning based on face detection to avoid overlap.

  audio_denoise: true / false — AI noise removal for room tone, hiss, fan noise.

  outro: none, fade_black, fade_white — none is best for clean looping.

  aspect_ratio: always "9:16"

  thumbnail_timestamp — the SOURCE timestamp (in seconds) of the SINGLE best frame to use as the video's cover image. This is the most important visual decision in the entire edit. It's what makes someone scrolling stop and click. A bad thumbnail will tank the video no matter how good the edit is.

  CRITICAL INSIGHT — DO NOT PICK THE PUNCHLINE WORD ITSELF.
  A common mistake is to pick the timestamp where the most dramatic WORD is being spoken. This is almost always WRONG because:
    - Mid-syllable mouths are in awkward shapes (open mid-vowel, contorted mid-consonant)
    - Speaking causes head movement and motion blur
    - Eyes squint from vocal effort
    - The narratively-peak word is usually the visually-WORST moment

  INSTEAD, scan for the VISUAL peak, which almost always falls in one of these three zones:

  1. PRE-REVEAL ANTICIPATION (0.3 to 1.5 seconds BEFORE a dramatic word):
     The speaker is leaning into the camera, eyes WIDE, mouth set/closed, building tension. Just before they say the shocking thing. Their face shows the EMOTION without the speaking distortion. Best for reveals, punchlines, and shocking statements.

  2. POST-REVEAL REACTION (0.3 to 1.5 seconds AFTER a dramatic word):
     The speaker is REACTING to what they just said. Often the most extreme expression of the entire video — eyes huge, jaw set, head tilted in disbelief, scowl, smirk, raised eyebrows. The aftermath of the statement, not the statement itself.

  3. MID-EMOTION SILENT PAUSE:
     Between sentences when the speaker shows pure emotion (anger, disgust, shock, joy, contempt) with mouth closed or in a non-speaking expressive shape (gritted teeth, dropped jaw with no sound, set lips). These are gold.

  A GREAT thumbnail frame has ALL of these:
    ✓ Face is BIG in the frame (close-up framing — Ken Burns may have already zoomed in here)
    ✓ Eyes WIDE OPEN, looking at or near the camera lens
    ✓ Extreme facial expression — shock, anger, disgust, surprise, contempt, joy. NOT neutral, NOT "talking face"
    ✓ Mouth in an EXPRESSIVE shape: gritted teeth, jaw dropped (silent), smirk, scowl, lips pressed — NOT mid-syllable
    ✓ Head STILL (no motion blur from gesturing or moving)
    ✓ Face well-LIT (not in shadow)

  A BAD thumbnail frame:
    ✗ Mid-word with mouth in awkward syllable shape (vowel-O, consonant-clicks, etc.)
    ✗ Eyes half-closed mid-blink, or looking down/away
    ✗ Wide shot where the face is small
    ✗ Neutral "speaking" expression (not extreme)
    ✗ Mid-gesture motion blur from moving hands or head
    ✗ Face partially obscured (hand in front, glare, etc.)

  Pick the EXACT timestamp where the visual peak occurs. BE PRECISE — being 0.2s off can be the difference between a great frame and a mid-syllable mouth. Scrub the pre-reveal and post-reveal windows of the most emotional moments and pick the best face. The system will fine-tune within ±0.6s of your pick, so get within ~0.5s of the actual best frame.

  pacing — overall edit rhythm. Default to "fast" for short-form content under 60s. "fast" = cuts every 2-3s, energetic jump cuts, no dead air. "medium" = 3-4s per clip, balanced. "slow" = 4-6s per clip, deliberate. Most TikTok/Reels content should be "fast" — the Captions app averages 2-3 second segments. Only use "slow" for genuinely contemplative content.

Emphasis moments — THE MOST IMPORTANT PART OF YOUR EDIT. These are the 2-5 moments in the video that should HIT HARDEST. Every emphasis moment drives caption keyword highlighting, automatic zoom punches, and sound effects simultaneously. Think like a professional editor: which moments make the viewer feel something?

  emphasis_moments: [
    {{"t": <seconds>, "word_indices": [<n>, ...], "type": "<punchline|revelation|statement|reaction|question|transition>", "intensity": "<high|medium>", "duration": <seconds>}}
  ]

  - t: the source timestamp where the moment peaks (use word timestamps for precision)
  - word_indices: the 1-3 word indices that ARE the emphasis (these become the highlighted keywords in captions AND drive dramatic text overlays)
  - type: what kind of moment — this controls the visual effect:
    * "punchline" or "revelation" (high intensity) → dramatic stacked cascade text (word repeated 5x with decreasing opacity, like Captions AI "SKEPTIC" effect)
    * "statement" (high intensity) → full-screen impact text (huge bold text overlay, like "EASY EDITING")
    * "statement" (medium intensity) → blur card (blurred background with sharp text)
    * Other types → vignette pulse + impact flash
  - intensity: "high" = the biggest moment (gets cascade/impact text + cut-zoom + bass hit), "medium" = notable but subtler
  - duration: how long the emphasis visual should hold (1.5-3.0 seconds, default 2.5 for high, 1.5 for medium)

  IMPORTANT: Choose word_indices that point to a SINGLE powerful word (1-2 words max) for high-intensity moments. "SKEPTIC", "RESULT", "EDITING", "SAVED" — short, punchy words that look dramatic when displayed large. Do NOT pick long phrases.

  Every video MUST have at least 3 emphasis_moments. Most have 4-6. These moments are what separate a professional edit from a raw upload.
  Space ALL emphasis moments (high AND medium) at least 4 seconds apart. Each emphasis triggers a zoom punch — when two land within 3 seconds, the viewer sees rapid-fire zooming that looks broken, not dramatic. Check every emphasis moment's timestamp against the previous one before finalizing.

  caption_keywords — list of words that should be visually emphasized in captions (larger, colored). These are auto-derived from emphasis_moments word_indices, but you can add extra keywords here for words that should stand out even outside emphasis moments.

Text overlays:
  text_overlays — Short, bold text that gives the viewer instant context. Use ONE overlay maximum.
  This overlay sets the stakes in a few words — e.g. "My 6yo exposed my wife", "He said WHAT?!".
  The text overlay should appear in the FIRST SECONDS the viewer sees. If you set a hook_clip, the hook plays FIRST — so the text overlay should appear on the hook (use appear_at_clip: -1 to place it on the hook clip). If there is no hook_clip, use appear_at_clip: 0 to place it on the first clip.
  If the story doesn't need context-setting text, use an empty array.
  text — under 5 words, no emojis
  position — top or bottom ONLY for talking-head content (center blocks the speaker's face). Use center only if there is genuinely no face in the frame.
  appear_at_clip — -1 for hook clip (if hook_clip is set), 0 for first content clip, or any clip number
  style — title (72px), callout (56px), cta (64px)

Sound effects — audio accents that make the edit feel physical and professional. Every sound must be EARNED — placed at a moment that justifies it. The wrong sound at the wrong time makes the edit feel amateur. The right sound at the right time makes it feel like a Netflix trailer.

  === THE #1 RULE: MATCH THE EMOTION, NOT THE WORDS ===

  Every sound must match the speaker's ACTUAL EMOTION in that moment, not the literal words being said. The same word carries completely different emotions depending on context:
  - "She's crying" when the speaker caught his wife cheating = VINDICATION, not sadness. No sad_trombone.
  - "I killed it" = TRIUMPH, not death. Use boom, not something dark.
  - "That's crazy" = AMAZEMENT. Not literal insanity.
  - "I died" = slang for laughing hard. Not actual death.

  Before placing ANY sound, identify the speaker's emotion: Are they triumphant? Disappointed? Shocked? Amused? Furious? Satisfied? Then pick a sound that AMPLIFIES that exact emotion. If the emotion is complex or ambiguous, use NO sound — silence is always safe and often more powerful than the wrong sound.

  SILENCE is the most powerful sound effect. Use it when:
  - The speaker's delivery already carries all the energy
  - The moment is genuinely emotional or vulnerable
  - You're not sure the sound matches the emotion (when in doubt, leave it out)

  Available sounds and WHEN to use each:

  boom — deep cinematic impact. Use for the biggest moments in the video — jaw-drop statements, shocking reveals, mic-drop lines. Place on the single word that carries the most weight in the moment.

  hit — sharp dramatic impact. Use for strong statements that need punctuation but aren't THE biggest moment. A notch below boom in intensity.

  drum_roll — snare drum roll building to a cymbal crash. The crash lands on your trigger word; the system starts the file early automatically. Use for genuine dramatic buildup before a big reveal, announcement, or life-changing number. Not for regular transitions or mild emphasis.

  reverse — backward sweep sound. Use when the story literally reverses or rewinds, or for sudden stops where energy cuts dead.

  ching — cash register. Use ONLY when money, profit, sales, or financial success is literally mentioned. The trigger word must be the money-related word itself.

  ding — bright notification chime. Use ONLY when a DEVICE produces a notification — a phone ringing, a text arriving, an email pinging, a voicemail alert. The trigger word must be the device action word ("texted", "called", "voicemail", "notification"). A human delivering a message in person is NOT a device notification and should NEVER get a ding.

  pop — satisfying pop. Use ONLY when something visually pops up on screen — a text overlay appearing, a graphic appearing. Not for speech emphasis.

  click — mouse/button click. Use when something is selected, decided, or confirmed.

  camera_shutter — camera shutter click. Use ONLY when someone is visibly taking a photo on screen or literally describes taking a photo. Not for metaphorical usage like "picture this."

  sad_trombone — comedic failure sound. Use ONLY when the speaker is describing a lighthearted failure that THEY find funny. The speaker's tone must be playful or self-deprecating. NEVER use when the speaker is genuinely upset, angry, vindicated, or in pain. This sound trivializes the moment — only place it where trivializing is the intended comedic effect.

  typing — keyboard typing sounds. Use when someone is visibly typing on screen or literally describes typing/texting something.

  whoosh_slow — smooth atmospheric whoosh. Use on scene transitions or topic changes.

  transition_smooth — gentle transition sound. Use with smooth visual transitions.

  thunder — deep rolling thunder. Use for ominous, foreboding, or threatening moments where something dark is happening or about to happen.

  Transitions — the visual effect between two clips. Most cuts should be HARD CUTS (transition_out: "none") — they're fast, clean, and professional. Transitions are a tool, not decoration. Use them sparingly and with purpose.

  Available transition_out values and when to use each:

  none — hard cut. DEFAULT. Use for 90%+ of cuts. Continuous speech flows best with silent hard cuts. Never add a transition just because you can.

  fadewhite — brief white flash between clips. Use at major topic shifts or emotional resets. 1-2 per video maximum.

  fadeblack — fade through black. Use for somber or serious tone shifts.

  dissolve — cross-dissolve blend. Use for dreamy, reflective, or nostalgic transitions.

  whip_left — fast wipe with motion blur sweeping left. High-energy, punchy. Use for comedic cuts, rapid topic changes.

  whip_right — fast wipe with motion blur sweeping right. Same energy as whip_left but opposite direction. Alternate with whip_left if using multiple.

  smoothleft / smoothright / smoothup / smoothdown — smooth directional slides. More subtle than whips. Use for structured content moving through a list or sequence.

  wipeleft / wiperight / wipeup / wipedown — clean directional wipes without motion blur. More editorial, less energetic than whips. Good for interview-style content.

  flash — brief bright flash (more intense than fadewhite). Use for shock moments or dramatic reveals.

  glitch — pixelated digital glitch effect. Use for tech content, internet culture, or when something breaks in the story.

  zoomin — zoom-in transition between clips. Use for escalation or "zooming in" on a topic.

  Rules:
  - Default to "none" (hard cut) for every transition. Only add a transition when it EARNS its place.
  - Never use the same transition type more than 2-3 times in a single video.
  - Match transition energy to content energy: somber content gets dissolve/fadeblack, high-energy gets whip/flash.
  - Pair whoosh_slow sound effects with whip/wipe/smooth transitions. Hard cuts are SILENT.
  - transition_out goes on the clip BEFORE the transition (the outgoing clip).

  Rules:
  - BEFORE placing any sound, ask: "Would a professional editor add a sound HERE?" If you can't articulate WHY this moment needs THIS specific sound, leave it out.
  - Sound effects punctuate emphasis_moments. Place sounds where they amplify the moment.
  - Every sound effect MUST have a "word" field — the EXACT trigger word that justifies this sound (lowercase, no punctuation).
  - TIMING IS SAMPLE-ACCURATE. The "t" value MUST be the EXACT start time of the trigger word, in seconds with at least 3 decimal places (millisecond precision) — copy it directly from the Deepgram word timestamps provided. Do NOT round, do NOT estimate, do NOT pick a time "near" the word.
  - The downstream system snaps your sound to the exact start of the spoken word using the "word" field, so getting the word right matters more than getting "t" right — but BOTH must point to the same word.
  - Onset compensation is automatic: the system knows each SFX file's internal onset (where the actual hit/climax is) and schedules the file to start early so the perceived "moment" lands precisely on the word. You do NOT need to compensate — just place "t" on the word and the system handles the rest. This applies to build-up sounds too: drum_roll, reverse, sad_trombone, thunder, whoosh_slow all have their climax automatically aligned to the word.
  - There is NO upper cap on sound effects and NO per-type limit. Place as many as the edit truly justifies. Quality over quantity — every sound must be earned, but if 8 moments earn a sound, place 8 sounds.
  - Do not place 2 sounds on 1 moment. That will never work. If you want a layered impact, pick a single sound that already has the layers built in (drum_roll already builds to a crash; thunder already rumbles into a hit).
  - ding should ONLY be used when someone literally receives a text/call/message/notification.
  - whoosh_slow REQUIRES a wipe/fade/whip/smooth transition on the same clip. Never place it on a hard cut — there is no visual movement to sell the sound and it will play over silence.
  - transition_smooth follows the same rule as whoosh_slow — REQUIRES a wipe/fade/whip/smooth transition on the same clip.
  - When in doubt, leave the sound out. Silence is better than a wrong sound.

  sound_effects: [
    {{"t": <seconds, 3+ decimal places, EXACT word start from Deepgram>, "sound": "<boom|hit|drum_roll|reverse|ching|ding|pop|click|camera_shutter|sad_trombone|typing|whoosh_slow|transition_smooth|thunder>", "word": "<exact trigger word, lowercase>"}}
  ]

B-roll — stock footage cutaways from Pexels.com. Your keyword gets typed into the Pexels search bar and the top result plays in the video OVER the speaker's dialogue. The viewer hears the speaker's words while watching your clip. Good b-roll makes the viewer FEEL the words — the clip reinforces and amplifies what the speaker is saying.

  The VERB in the dialogue is the most important part of your keyword. The verb is what the viewer hears and what the clip must show. Start building your keyword from the verb in the speaker's dialogue, then add the subject and setting around it. The verb anchors the entire search — if the verb is wrong, the clip will clash with the dialogue and the video looks broken.

  B-roll should be VERY simple and general. One subject doing one thing — nothing more. Do not build complex scenes with multiple actions or props. Strip the keyword down to the core subject and the core verb from the dialogue. The simpler and more general the clip, the better it works over any dialogue. If the dialogue mentions a person, search for that type of person doing the ONE action the speaker described — nothing else added. Never search for abstract concepts or emotions — "frustration" "success" "happiness" return cheesy corporate stock. Use context words only to disambiguate — "calling" needs "smartphone ringing" to avoid bells or video calls.

  Each keyword MUST be at least 16 words long. Only add details that help Pexels find the right clip. No two keywords should return the same clip. Each clip should be visually distinct — different settings, different subjects, different types of shots.

  Only place b-roll on moments where the speaker describes a physical action or concrete scene. Stay on the speaker's face during emotional beats, opinions, punchlines, reveals, and reactions — during those moments the speaker's facial expression IS the content and cutting away destroys the impact. B-roll in the main body only, not during the hook.

  Select b-roll windows of roughly 4-8 words (1.5-3 seconds of dialogue). Shorter than 4 words feels like a flash. Longer than 10 words loses the speaker's presence for too long.

  Timing: b-roll appears the EXACT millisecond the first relevant word starts and disappears the EXACT millisecond the last relevant word ends. Use start_word_index and end_word_index from the Deepgram word list to define the window precisely. The pipeline computes exact timing from these indices — do not provide a duration, it is calculated automatically.
  Spacing: 3+ seconds of speaker face between clips. Coverage: ~40% of runtime. Place on held-speed sections, not ramps. Each clip visually distinct.

  broll_clips: [
    {{"keyword": "<minimum 16 words — clip must match what viewer hears at this moment>", "start_word_index": <index of first word the b-roll covers>, "end_word_index": <index of last word the b-roll covers>, "reason": "<quote the speaker's exact words>"}}
  ]

Visual effects — additional visual treatments for emphasis moments.

  visual_effects: [
    {{"type": "white_flash", "t": <source seconds>}}
  ]

  white_flash — a brief brightness spike at the peak of a high-intensity emphasis moment. Makes the moment hit harder visually. Maximum 1-2 per video.

  Rules:
  - Use sparingly — 0-2 per video maximum.
  - Only on "high" intensity emphasis moments.
  - The flash happens at the source timestamp, the pipeline handles time projection.

=== RESPONSE FORMAT ===

Output ONLY the JSON below — no commentary, no analysis, no explanation. Just the JSON block:

```json
{{
  "notes": "<50 words max>",
  "hook_clip": {{"source_start": <seconds>, "source_end": <seconds>}} or null,
  "thumbnail_timestamp": <seconds>,
  "caption_style": "<style>",
  "caption_position": "<position>",
  "caption_keywords": ["<word1>", "<word2>", ...],
  "audio_denoise": <true|false>,
  "outro": "<none|fade_black|fade_white>",
  "aspect_ratio": "9:16",
  "speed_curve": [{{"t": <seconds>, "speed": <multiplier>}}, ...] or "none",
  "pacing": "<fast|medium|slow>",
  "opening_zoom": "<slow_in|slow_out|none>",
  "emphasis_moments": [
    {{"t": <seconds>, "word_indices": [<n>, ...], "type": "<punchline|revelation|statement|reaction|question|transition>", "intensity": "<high|medium>", "duration": <seconds>}}
  ],
  "text_overlays": [
    {{"text": "<text>", "position": "<pos>", "appear_at_clip": <n>, "style": "<style>"}}
  ],
  "sound_effects": [
    {{"t": <seconds>, "sound": "<sound>", "word": "<trigger>"}}
  ],
  "broll_clips": [
    {{"keyword": "<minimum 16 words — clip must match what viewer hears at this moment>", "start_word_index": <index of first word>, "end_word_index": <index of last word>, "reason": "<quote the speaker's exact words>"}}
  ],
  "visual_effects": [
    {{"type": "white_flash", "t": <source seconds>}}
  ],
  "transitions": [
    {{"after_word_index": <n>, "type": "<fadewhite|fadeblack|dissolve|whip_left|whip_right|smoothleft|smoothright|smoothup|smoothdown|wipeleft|wiperight|wipeup|wipedown|flash|glitch|zoomin>"}}
  ],
  "remove_words": [
    {{"word_index": <n>, "reason": "<stutter|false_start|filler>"}} or
    {{"start": <n>, "end": <n>, "reason": "<dead_air|section_skip|non_speech_gap>"}}
  ]
}}
```"""

    return prompt


def infer_has_burned_captions(edit_plan, analysis_data=None, log_prefix=None):
    has_burned_captions = bool(
        ((analysis_data or {}).get("frame_layout") or {})
        .get("existing_overlays", {})
        .get("has_burned_captions")
    )
    if not has_burned_captions:
        notes = str((edit_plan or {}).get("notes") or "").lower()
        if "burned" in notes or "burned-in" in notes or "burn-in" in notes or "existing caption" in notes:
            has_burned_captions = True
            if log_prefix:
                print(f"{log_prefix} Detected burned-in captions from recipe notes", flush=True)
    if not has_burned_captions:
        caption_style = str((edit_plan or {}).get("caption_style") or "").lower()
        has_words = bool((edit_plan or {}).get("_deepgram_words"))
        if caption_style == "none" and has_words:
            has_burned_captions = True
            if log_prefix:
                print(f"{log_prefix} Inferred burned-in captions (caption_style=none but speech detected)", flush=True)
    return has_burned_captions


def build_analysis_from_gemini_recipe(edit_plan, duration):
    raw_frame_layout = edit_plan.get("frame_layout") or {}
    raw_existing = raw_frame_layout.get("existing_overlays") or {}
    raw_fq = edit_plan.get("footage_quality") or {}
    has_burned_captions = infer_has_burned_captions(
        edit_plan,
        analysis_data={"frame_layout": {"existing_overlays": raw_existing}},
    )

    parsed = {
        "duration": duration,
        "speech": {"has_speech": False, "speaker_style": "", "segments": [], "sentence_boundaries": []},
        "safe_cut_points": (
            [
                {"time": 0, "quality": 1.0, "why": "Video start"},
                {"time": round(duration * 1000) / 1000, "quality": 1.0, "why": "Video end"},
            ]
            if duration > 0 else []
        ),
        "video_profile": edit_plan.get("video_profile") or {},
        "frame_layout": {
            "subject_position": raw_frame_layout.get("subject_position") or "unknown",
            "existing_overlays": {
                "has_burned_captions": has_burned_captions,
                "has_text_graphics": bool(raw_existing.get("has_text_graphics")),
                "overlay_locations": raw_existing.get("overlay_locations") or ("captions visible in-frame" if has_burned_captions else "none detected"),
            },
            "free_zones": raw_frame_layout.get("free_zones") or "unknown",
        },
        "color_baseline": edit_plan.get("color_baseline") or {},
        "footage_quality": {
            **raw_fq,
            "has_burned_captions": has_burned_captions,
        },
        "audio": {"speech_source": "none"},
        "shots": [{
            "start": 0,
            "end": duration,
            "visual": "",
            "action": "Full video",
            "energy": 0.5,
            "editing_value": "usable",
            "delivery": "none",
        }],
    }
    analysis = normalize_analysis(parsed)
    analysis["visual_cuts"] = []
    analysis["beat_timestamps"] = []
    analysis["tightened_timeline"] = {}
    analysis["content_mode"] = "speech"
    return analysis


def generate_edit_gemini(video_path, vibe, duration, trend_context=None, deepgram_words=None, face_positions=None, gemini_file=None, cached_response=None, inline_video_bytes=None):
    # cached_response is visual pre-analysis from content-studio (shots, camera movement,
    # lighting, peak moments). NOT the edit recipe — the recipe requires Deepgram transcript
    # which only exists on Modal. We inject the analysis into the prompt for richer context.
    _pre_analysis = cached_response  # visual analysis dict or None

    # Full Gemini API call path (always runs — cached_response only augments the prompt)
    client = _get_genai_client()
    prompt = build_gemini_edit_prompt(
        vibe=vibe,
        duration=duration,
        trend_context=trend_context,
    )

    # Inject Deepgram word timestamps so Gemini can place cuts precisely
    if deepgram_words:
        readable_words = []
        for w in deepgram_words:
            readable_words.append(w.get("punctuated_word") or w.get("word") or "")
        readable_transcript = " ".join(readable_words)

        word_lines = []
        for idx, w in enumerate(deepgram_words):
            word_text = w.get("punctuated_word") or w.get("word") or ""
            start = float(w.get("start") or 0)
            end = float(w.get("end") or 0)
            word_lines.append(f"  [{idx}] {start:.2f}-{end:.2f}: {word_text}")

        transcript_block = "\n".join(word_lines)
        first_word_start = float(deepgram_words[0].get("start", 0))
        prompt += f"""

=== FULL TRANSCRIPT ===

Read this first to understand the full story before making any editing decisions. Identify the narrative structure — what is setup, what is filler, what is the buildup, and where are the punchlines or reveals. For speed ramping, use this understanding: the parts you'd skim if reading are filler (speed up), the parts that make you react are punchlines (slow down), and the parts that build tension should be fast — tension comes from momentum, not from slowing down.

{readable_transcript}

=== WORD-BY-WORD TIMESTAMPS ===

The following is the complete word-by-word transcript with millisecond-accurate timestamps from speech recognition. Use these timestamps to place your cuts PRECISELY in the silence gaps between words.

{transcript_block}

RULES FOR USING THESE TIMESTAMPS:
- word_index refers to the numbered list above. Use those exact indices in remove_words when removing specific spoken words.
- Your source_start and source_end values MUST land in the gaps BETWEEN words, not inside a word.
- A gap is the time between one word's end timestamp and the next word's start timestamp.
- For example, if "problem." ends at 5.62 and "With" starts at 5.76, the silence gap is 5.62-5.76. Place source_end at 5.62 and source_start at 5.76 (or anywhere in between).
- NEVER place a source_start or source_end between a word's start and end timestamps — that cuts the word in half.
- The first word starts at {first_word_start:.2f}s. If this is a talking head video, set your first clip's source_start to {first_word_start:.2f} so the video starts on the first word with zero dead air.
- If the video has intentional visual content before the first word (action, scenery, product shots), start source_start at 0.0 to preserve that content.
"""
        print(f"[generate-edit] Injected {len(deepgram_words)} Deepgram word timestamps into Gemini prompt", flush=True)

    if face_positions:
        found_positions = [p for p in face_positions if p.get("found")]
        if found_positions:
            avg_cx = sum(float(p["cx"]) for p in found_positions) / len(found_positions)
            if abs(avg_cx - 540) > 100:
                prompt += (
                    f"\nNOTE: The subject's face is off-center (average X position: {int(avg_cx)} out of 1080). "
                    "Do NOT use zoom on this video — it will crop poorly.\n"
                )
                print(f"[generate-edit] Injected off-center face note into Gemini prompt (avg_x={avg_cx:.1f})", flush=True)

    # Inject pre-analysis from content-studio if available (richer visual context)
    if _pre_analysis and isinstance(_pre_analysis, dict):
        _pa_parts = []
        if _pre_analysis.get("peak_moments"):
            _pa_parts.append(f"Peak moments: {json.dumps(_pre_analysis['peak_moments'])}")
        if _pre_analysis.get("safe_cut_points"):
            _pa_parts.append(f"Safe cut points: {json.dumps(_pre_analysis['safe_cut_points'])}")
        if _pre_analysis.get("video_profile"):
            _pa_parts.append(f"Video profile: {json.dumps(_pre_analysis['video_profile'])}")
        # Shot breakdown intentionally excluded — narrative "action" descriptions
        # from content-studio leak into Gemini's b-roll keyword generation,
        # overriding the stock-footage-title instructions.
        if _pa_parts:
            prompt += "\n\n=== PRE-ANALYZED VIDEO DATA ===\n" + "\n".join(_pa_parts) + "\n"
            print(f"[generate-edit] Injected pre-analysis context ({len(_pa_parts)} sections)", flush=True)

    if trend_context:
        print(f"[generate-edit] Trend context included: {trend_context.get('sample_size', '?')} videos", flush=True)
    else:
        print("[generate-edit] No trend context available", flush=True)

    # Build video content part — inline bytes (fast, no upload/poll) or file reference (legacy)
    if inline_video_bytes:
        _video_part = genai_types.Part.from_bytes(data=inline_video_bytes, mime_type="video/mp4")
        print(f"[generate-edit] Using inline video ({len(inline_video_bytes)/1024/1024:.1f}MB, no upload)", flush=True)
    elif gemini_file is not None:
        _video_part = gemini_file
        print(f"[generate-edit] Using pre-uploaded Gemini file: {gemini_file.uri}", flush=True)
    else:
        raise RuntimeError("No video data provided — need either inline_video_bytes or gemini_file")

    print(f"[generate-edit] Calling Gemini model={GEMINI_MODEL} (thinking=LOW)...", flush=True)
    t = time.time()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_video_part, prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.6,
            # Edit plans serialize to 2-5KB JSON. 4096 tokens is comfortably above the
            # observed maximum and reduces tokenizer overhead vs the previous 32768
            # over-allocation. Gemini will return finish_reason=MAX_TOKENS if exceeded
            # — handler logs that and we can bump back up if it ever triggers.
            max_output_tokens=4096,
            thinking_config=genai_types.ThinkingConfig(thinking_level="LOW"),
            media_resolution="MEDIA_RESOLUTION_LOW",
        ),
    )
    print(f"[generate-edit] Gemini complete in {time.time()-t:.1f}s", flush=True)

    response_text = str(getattr(response, "text", "") or "").strip()
    try:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            print(f"[generate-edit] Gemini finish_reason={finish_reason}", flush=True)
            fr_str = str(finish_reason).upper()
            if "MAX" in fr_str:
                print("[generate-edit] WARNING: Gemini response TRUNCATED — increase max_output_tokens", flush=True)
            elif "SAFETY" in fr_str:
                print("[generate-edit] WARNING: Gemini response blocked by safety filter", flush=True)
    except Exception:
        pass
    if "```json" not in response_text and "{" not in response_text:
        print(
            f"[generate-edit] ERROR: No JSON found in response. Response length: {len(response_text)} chars",
            flush=True,
        )
        print(f"[generate-edit] Response tail: ...{response_text[-200:]}", flush=True)
    if not response_text:
        raise RuntimeError("Empty Gemini response")

    print(f"[generate-edit] RAW RESPONSE:\n{response_text}\n[generate-edit] END RESPONSE", flush=True)

    edit_plan = extract_json(response_text)

    # Post-processing
    edit_plan["_deepgram_words"] = list(deepgram_words or [])
    analysis = build_analysis_from_gemini_recipe(edit_plan, duration=duration)
    has_burned_captions = infer_has_burned_captions(edit_plan, analysis, log_prefix="[generate-edit]")

    video_duration = float(analysis.get("duration") or 0)
    _dg_words = edit_plan.get("_deepgram_words", [])
    raw_remove_words = edit_plan.get("remove_words")
    raw_cuts = edit_plan.get("cuts") or edit_plan.get("clips")

    validated_cuts = []
    if isinstance(raw_remove_words, list) and not _dg_words:
        # No speech detected — skip word-based editing, create single full-video clip
        print("[generate-edit] No words available — skipping word-based cuts, using full video as single clip", flush=True)
        edit_plan["caption_style"] = "none"
        validated_cuts = [{"source_start": 0.0, "source_end": round(duration, 3)}]
    elif isinstance(raw_remove_words, list):
        if not _dg_words:
            raise ValueError("Deepgram words missing — remove_words architecture requires word timestamps")
        print(f"[DIAG] Full transcript ({len(_dg_words)} words):", flush=True)
        for i, w in enumerate(_dg_words):
            spk = w.get('speaker', '?')
            print(
                f"[DIAG]   [{i}] {float(w.get('start') or 0):.3f}-{float(w.get('end') or 0):.3f} "
                f"(spk{spk}): {w.get('punctuated_word') or w.get('word')}",
                flush=True,
            )
        normalized_remove_words = []
        for item in raw_remove_words:
            if not isinstance(item, dict):
                continue
            if "word_index" in item:
                try:
                    idx = int(item["word_index"])
                except Exception:
                    continue
                if 0 <= idx < len(_dg_words):
                    normalized_remove_words.append({
                        "word_index": idx,
                        "reason": str(item.get("reason") or "remove"),
                    })
                    w = _dg_words[idx]
                    word_text = w.get("punctuated_word") or w.get("word") or ""
                    print(
                        f"[remove] Removing word [{idx}] '{word_text}' ({item.get('reason', 'unknown')})",
                        flush=True,
                    )
                else:
                    print(
                        f"[remove] WARNING: word_index {idx} out of bounds (max {len(_dg_words)-1})",
                        flush=True,
                    )
            elif "start" in item and "end" in item:
                try:
                    rw_s = max(0.0, float(item["start"]))
                    rw_e = max(0.0, float(item["end"]))
                except Exception:
                    continue
                if rw_e > rw_s:
                    if video_duration > 0:
                        rw_e = min(rw_e, video_duration)
                    if rw_e <= rw_s:
                        continue
                    normalized_remove_words.append({
                        "start": round(rw_s, 3),
                        "end": round(rw_e, 3),
                        "reason": str(item.get("reason") or "remove"),
                    })
                    print(
                        f"[remove] Removing range {rw_s:.2f}-{rw_e:.2f} ({item.get('reason', 'unknown')})",
                        flush=True,
                    )

        edit_plan["remove_words"] = normalized_remove_words
        # Adapt tightening threshold to speech rate AND pacing.
        # Lower gap = more aggressive silence removal = tighter jump cuts.
        # Captions app aggressively removes ALL dead air — we match that.
        _pacing = str(edit_plan.get("pacing") or "fast").lower()
        if _pacing == "fast":
            _speech_gap = 0.06  # ultra-tight — gaps become noticeable at 0.75x slow-mo
        elif _pacing == "medium":
            _speech_gap = 0.10
        else:
            _speech_gap = 0.13  # slow pacing — more breathing room
        if len(_dg_words) >= 5:
            _first_t = float(_dg_words[0].get("start", 0))
            _last_t = float(_dg_words[-1].get("end", 0))
            _speech_dur = _last_t - _first_t
            if _speech_dur > 0:
                _wpm = len(_dg_words) / (_speech_dur / 60.0)
                if _wpm > 180:
                    _speech_gap += 0.05  # very fast talker — widen slightly to preserve phrasing
                elif _wpm > 150:
                    _speech_gap += 0.03  # fast talker
                elif _wpm < 100:
                    _speech_gap = max(0.08, _speech_gap - 0.03)  # slow talker — even tighter
                print(f"[tighten] Speech rate: {_wpm:.0f} wpm, pacing={_pacing} → gap threshold: {_speech_gap*1000:.0f}ms", flush=True)
        print(
            f"[generate-edit] Building clips: {len(_dg_words)} words, "
            f"{len(normalized_remove_words)} Gemini removals + deterministic tightening",
            flush=True,
        )
        validated_cuts, _removed_word_indices = build_clips_from_words(_dg_words, normalized_remove_words, max_silence_gap=_speech_gap, video_duration=video_duration)
        edit_plan["_removed_word_indices"] = _removed_word_indices
        for i, clip in enumerate(validated_cuts):
            clip_start = float(clip["source_start"])
            clip_end = float(clip["source_end"])
            # Find words inside this clip using padded boundaries
            clip_words = []
            for w in _dg_words:
                ws = float(w.get("start") or 0)
                we = float(w.get("end") or 0)
                if ws >= clip_start - 0.02 and we <= clip_end + 0.02:
                    clip_words.append(w.get("punctuated_word") or w.get("word") or "")
            first_word = clip_words[0] if clip_words else ""
            last_word = clip_words[-1] if clip_words else ""
            print(
                f"[clips] Clip {i}: {clip_start:.3f}-{clip_end:.3f} "
                f"({len(clip_words)} words) '{first_word}' ... '{last_word}'",
                flush=True,
            )
        if not validated_cuts:
            raise ValueError("Gemini response removed all words — no clips remain")
    elif isinstance(raw_cuts, list):
        print("[generate-edit] WARNING: Gemini returned cuts instead of remove_words — using legacy path", flush=True)
        for clip in raw_cuts:
            clip.pop("freeze_frame", None)
            clip.pop("motion_blur_transition", None)
            clip.pop("speed_ramp", None)
            clip.pop("motion_blur_transition", None)
            clip.pop("speed_segments", None)

        for i, cut in enumerate(raw_cuts):
            src_start = float(cut.get("source_start") or 0)
            src_end = float(cut.get("source_end") or 0)
            if src_start >= src_end:
                raise ValueError(f"Cut {i}: source_start ({src_start}) >= source_end ({src_end})")
            if src_start < 0:
                raise ValueError(f"Cut {i}: source_start is negative")
            if video_duration > 0 and src_end > video_duration + 0.5:
                raise ValueError(f"Cut {i}: source_end ({src_end}) exceeds video duration ({video_duration})")
            validated_cuts.append({**cut, "source_start": src_start, "source_end": src_end, "clip": i + 1})

        validated_cuts.sort(key=lambda c: float(c["source_start"]))
        for i in range(1, len(validated_cuts)):
            prev_end = validated_cuts[i - 1]["source_end"]
            curr_start = validated_cuts[i]["source_start"]
            if curr_start < prev_end:
                print(f"[generate-edit] Fixing clip {i} overlap: source_start {curr_start} -> {prev_end}", flush=True)
                validated_cuts[i]["source_start"] = prev_end

        # Remove clips that ended up with zero or negative duration after overlap fix
        validated_cuts = [
            c for c in validated_cuts
            if float(c["source_end"]) - float(c["source_start"]) > 0.01
        ]

        for i in range(1, len(validated_cuts)):
            prev_end = validated_cuts[i - 1]["source_end"]
            curr_start = validated_cuts[i]["source_start"]
            gap = curr_start - prev_end
            if 0 < gap <= 0.05:
                print(f"[generate-edit] Closing {gap:.3f}s micro-gap between clip {i-1} and clip {i}", flush=True)
                validated_cuts[i - 1]["source_end"] = curr_start
            elif 0.05 < gap <= 2.0:
                print(f"[generate-edit] Intentional cut: {gap:.3f}s removed between clip {i-1} and clip {i}", flush=True)
            elif gap > 2.0:
                print(f"[generate-edit] Section skip: {gap:.3f}s removed between clip {i-1} and clip {i}", flush=True)
    else:
        if not _dg_words:
            # No speech, no cuts — create single full-video clip
            print("[generate-edit] No words and no cuts from Gemini — using full video as single clip", flush=True)
            edit_plan["caption_style"] = "none"
            validated_cuts = [{"source_start": 0.0, "source_end": round(duration, 3)}]
        else:
            raise ValueError("Gemini response missing both remove_words and cuts")

    # Verify no large gaps in output (monitoring only — not auto-removing)
    for _gi in range(1, len(validated_cuts)):
        _prev_end = float(validated_cuts[_gi - 1].get("source_end", 0))
        _curr_start = float(validated_cuts[_gi].get("source_start", 0))
        _gap = _curr_start - _prev_end
        if _gap > 0.5:
            print(f"[gap-check] WARNING: {_gap:.2f}s gap between clip {_gi-1} and clip {_gi} (source {_prev_end:.2f}s-{_curr_start:.2f}s)", flush=True)

    # Apply transitions from Gemini's transitions array onto clips.
    # Each transition has after_word_index — find the clip whose source range
    # contains that word's timestamp and set transition_out on it.
    raw_transitions = edit_plan.get("transitions") or []
    if raw_transitions and _dg_words:
        _valid_tr_types = {
            "none", "fade", "fadeblack", "fadewhite", "dissolve",
            "wipeleft", "wiperight", "wipeup", "wipedown",
            "smoothleft", "smoothright", "smoothup", "smoothdown",
            "whip_left", "whip_right", "flash", "glitch", "zoomin",
        }
        # Build set of removed word indices to handle transitions on removed words
        _tr_removed = set()
        for rw in (edit_plan.get("remove_words") or []):
            if "word_index" in rw:
                _tr_removed.add(int(rw["word_index"]))
        for tr in raw_transitions:
            if not isinstance(tr, dict):
                continue
            tr_type = str(tr.get("type") or "none").lower()
            if tr_type not in _valid_tr_types or tr_type == "none":
                continue
            awi = tr.get("after_word_index")
            if awi is None or not isinstance(awi, (int, float)):
                continue
            awi = int(awi)
            if awi < 0 or awi >= len(_dg_words):
                print(f"[generate-edit] Transition '{tr_type}' skipped — word index {awi} out of bounds", flush=True)
                continue
            # If referenced word was removed, find the nearest kept word before it
            if awi in _tr_removed:
                _found = False
                for _wi in range(awi - 1, -1, -1):
                    if _wi not in _tr_removed:
                        awi = _wi
                        _found = True
                        break
                if not _found:
                    print(f"[generate-edit] Transition '{tr_type}' skipped — no kept word before index {tr.get('after_word_index')}", flush=True)
                    continue
            word_end = float(_dg_words[awi].get("end") or 0)
            # Find the clip that contains this word (with 50ms tolerance)
            _applied = False
            for ci, clip in enumerate(validated_cuts):
                cs = float(clip["source_start"])
                ce = float(clip["source_end"])
                if cs - 0.05 <= word_end <= ce + 0.05 and ci < len(validated_cuts) - 1:
                    clip["transition_out"] = tr_type
                    print(f"[generate-edit] Transition '{tr_type}' applied to clip {ci} (after word {awi})", flush=True)
                    _applied = True
                    break
            if not _applied:
                print(f"[generate-edit] Transition '{tr_type}' at word {awi} ({word_end:.3f}s) — no matching clip found", flush=True)

    # Transition count/variety is Gemini's decision — the prompt teaches restraint.

    edit_plan.setdefault("caption_style", "none")
    edit_plan.setdefault("caption_position", "lower-third")
    edit_plan.setdefault("caption_keywords", [])
    edit_plan.setdefault("audio_denoise", False)
    edit_plan.setdefault("beat_sync", False)
    edit_plan.setdefault("outro", "none")
    edit_plan.setdefault("aspect_ratio", "original")
    edit_plan.setdefault("video_profile", {})
    edit_plan.setdefault("frame_layout", {})
    edit_plan.setdefault("text_overlays", [])
    edit_plan.setdefault("vignette", "none")
    edit_plan.setdefault("sharpening", False)
    edit_plan.setdefault("grain", "none")
    edit_plan.setdefault("denoise", False)
    edit_plan.setdefault("cinematic_bars", False)
    edit_plan.setdefault("shadow_lift", False)
    edit_plan.setdefault("highlight_rolloff", False)
    edit_plan.setdefault("vibrance", False)
    edit_plan.setdefault("teal_orange", "none")
    for _ov in (edit_plan.get("text_overlays") or []):
        if "text" in _ov:
            _ov["text"] = _EMOJI_RE.sub("", str(_ov["text"])).strip()
    edit_plan.setdefault("sound_effects", [])
    edit_plan.setdefault("emphasis_moments", [])
    edit_plan.setdefault("visual_effects", [])

    # ── B-roll clips validation ───────────────────────────────────────────
    # Type/sanity checks only — no value clamps. Gemini owns every creative
    # decision (duration, count, placement). We only filter entries that
    # would crash the renderer or are physically impossible (negative time,
    # zero duration, NaN, past end of video, malformed JSON types).
    raw_broll = edit_plan.get("broll_clips") or []
    validated_broll = []
    _broll_dg_words = edit_plan.get("_deepgram_words") or []
    for _br in raw_broll:
        if not isinstance(_br, dict):
            continue
        _br_kw = str(_br.get("keyword") or "").strip()
        if not _br_kw:
            continue
        # Word-index timing — compute exact start/end from Deepgram words
        try:
            _sw = int(_br["start_word_index"])
            _ew = int(_br["end_word_index"])
        except (TypeError, ValueError, KeyError):
            continue
        if _sw < 0 or _ew < _sw or _sw >= len(_broll_dg_words):
            continue
        _ew = min(_ew, len(_broll_dg_words) - 1)
        _br_ts = float(_broll_dg_words[_sw].get("start") or 0)
        _br_end = float(_broll_dg_words[_ew].get("end") or 0)
        _br_dur = _br_end - _br_ts
        if _br_dur <= 0:
            continue
        print(f"[broll] Word-index timing: [{_sw}]-[{_ew}] → {_br_ts:.3f}s-{_br_end:.3f}s ({_br_dur:.2f}s)", flush=True)
        if not (math.isfinite(_br_ts) and math.isfinite(_br_dur)):
            continue
        if _br_ts < 0 or _br_dur <= 0:
            continue
        if video_duration > 0 and _br_ts >= video_duration:
            continue
        validated_broll.append({
            "keyword": _br_kw,
            "timestamp": _br_ts,
            "duration": _br_dur,
            "reason": str(_br.get("reason") or "").strip(),
        })
    edit_plan["broll_clips"] = validated_broll
    if validated_broll:
        print(f"[broll] Gemini requested {len(validated_broll)} B-roll clip(s)", flush=True)
        for _vb in validated_broll:
            _r = _vb.get("reason") or "(no reason given)"
            print(f"[broll]   → '{_vb['keyword']}' @ {_vb['timestamp']:.2f}s for {_vb['duration']:.2f}s — {_r}", flush=True)

    # ── Visual effects validation ─────────────────────────────────────────
    raw_vfx = edit_plan.get("visual_effects") or []
    validated_vfx = []
    valid_vfx_types = {"white_flash"}
    for _vf in raw_vfx:
        if not isinstance(_vf, dict):
            continue
        _vf_type = str(_vf.get("type") or "").strip()
        if _vf_type in valid_vfx_types:
            validated_vfx.append(_vf)
    edit_plan["visual_effects"] = validated_vfx
    if validated_vfx:
        print(f"[fx] Gemini requested {len(validated_vfx)} visual effect(s)", flush=True)

    valid_caption_styles = {"none", "volt", "clarity", "impact", "ember", "velocity", "archive", "lumen", "rebel"}
    if str(edit_plan.get("caption_style") or "").lower() not in valid_caption_styles:
        edit_plan["caption_style"] = "volt"  # default to Volt — the flagship Captions AI style
    else:
        edit_plan["caption_style"] = str(edit_plan.get("caption_style") or "none").lower()

    valid_zoom_modes = {"none", "slow_in", "slow_out", "punch_in", "punch_out", "cut_zoom"}
    opening_zoom = str(edit_plan.get("opening_zoom") or "none").lower()
    if opening_zoom not in valid_zoom_modes:
        opening_zoom = "none"
    edit_plan["opening_zoom"] = opening_zoom

    raw_curve = edit_plan.get("speed_curve", "none")
    if raw_curve == "none" or raw_curve is None or not isinstance(raw_curve, list):
        speed_curve = None
    else:
        speed_curve = []
        for kp in raw_curve:
            if isinstance(kp, dict) and "t" in kp and ("speed" in kp or "s" in kp):
                try:
                    t = max(0.0, float(kp["t"]))
                    s = max(0.25, min(2.0, float(kp.get("speed") or kp.get("s"))))
                    speed_curve.append({"t": t, "speed": s})
                except Exception:
                    continue
        if len(speed_curve) < 2:
            speed_curve = None
        else:
            speed_curve.sort(key=lambda x: x["t"])

            # Gemini already has word-level timestamps at 3-decimal
            # precision and places keypoints directly on them. Any
            # rounding error is ≤1 frame (33ms) — imperceptible in a
            # speed ramp. The old snapping code corrected this tiny
            # error but caused a catastrophic bug: when a snap-back
            # keypoint fell in a dead-air gap (removed silence between
            # clips), it got pulled onto its partner's timestamp and
            # the ramp pair collapsed into a single keypoint. The
            # densifier then saw a long gap and filled it with a
            # gradual 10-second drift instead of a sharp snap. Gemini
            # is the expert — trust its timestamps exactly.

        if speed_curve and len(speed_curve) >= 2:
            # MIN_RAMP_SECS spreading was removed. It existed to prevent
            # jarring abrupt speed changes under hold-and-snap semantics
            # (where a 0.7→1.3 jump over 0.3s was an instant snap). With
            # linear interpolation, the same keypoints become a smooth
            # 0.3s glide which sounds fine. The spreading was also moving
            # keypoints away from word boundaries, defeating the snap-to-
            # word fix.

            # Densify with linear interpolation. BUDGETED allocation: a
            # global cap of 50 intermediate keypoints distributed across
            # ramps proportional to each ramp's speed delta. This bounds
            # total sub-clip count regardless of how many keypoints
            # Gemini sends, making render time predictable. Steeper ramps
            # get more sub-steps where smoothness matters most.
            _gemini_kp_count = len(speed_curve)
            speed_curve = densify_speed_curve(speed_curve, max_intermediates=150, min_step=0.08)
            if len(speed_curve) > _gemini_kp_count:
                print(
                    f"[speed-curve] Densified {_gemini_kp_count} Gemini keypoints → "
                    f"{len(speed_curve)} interpolated keypoints (smooth ramping)",
                    flush=True,
                )

            speeds = [kp["speed"] for kp in speed_curve]
            print(
                f"[generate-edit] Speed curve: {len(speed_curve)} keypoints, range "
                f"{min(speeds):.2f}x - {max(speeds):.2f}x",
                flush=True,
            )
    edit_plan["_parsed_speed_curve"] = speed_curve

    thumbnail_timestamp = None
    try:
        if edit_plan.get("thumbnail_timestamp") is not None:
            thumbnail_timestamp = max(0.0, float(edit_plan.get("thumbnail_timestamp")))
            if video_duration > 0:
                thumbnail_timestamp = min(thumbnail_timestamp, video_duration)
    except Exception:
        thumbnail_timestamp = None
    edit_plan["thumbnail_timestamp"] = thumbnail_timestamp

    hook_clip = None
    raw_hook = edit_plan.get("hook_clip")
    if isinstance(raw_hook, dict):
        try:
            hook_start = max(0.0, float(raw_hook.get("source_start")))
            hook_end = max(0.0, float(raw_hook.get("source_end")))
            if video_duration > 0:
                hook_end = min(hook_end, video_duration)
            hook_dur = hook_end - hook_start
            if 0.5 <= hook_dur <= 5.0:
                hook_clip = {
                    "source_start": round(hook_start, 3),
                    "source_end": round(hook_end, 3),
                }
            else:
                print(f"[generate-edit] Hook clip duration {hook_dur:.2f}s out of range — skipping", flush=True)
        except Exception:
            hook_clip = None
    if hook_clip:
        _hs = float(hook_clip["source_start"])
        _he = float(hook_clip["source_end"])
        print(f"[hook] Hook timestamps: {_hs:.2f}-{_he:.2f} ({_he - _hs:.2f}s)", flush=True)
    edit_plan["hook_clip"] = hook_clip
    edit_plan["cuts"] = list(validated_cuts)

    # ── Parse emphasis moments ─────────────────────────────────────────────
    raw_emphasis = edit_plan.get("emphasis_moments", [])
    emphasis_moments = []
    for em in raw_emphasis:
        if isinstance(em, dict) and "t" in em:
            try:
                t = float(em["t"])
                if t < 0 or (video_duration > 0 and t > video_duration):
                    continue
                word_indices = em.get("word_indices", [])
                if not isinstance(word_indices, list):
                    word_indices = []
                intensity = str(em.get("intensity") or "medium").lower()
                if intensity not in ("high", "medium"):
                    intensity = "medium"
                em_type = str(em.get("type") or "statement").lower()
                _valid_em_types = {"punchline", "statement", "question", "reaction", "transition", "revelation"}
                if em_type not in _valid_em_types:
                    em_type = "statement"
                _valid_indices = [int(i) for i in word_indices if isinstance(i, (int, float))]
                if not _valid_indices:
                    continue
                # Extract the actual emphasized word(s) from Deepgram transcript
                _em_word_parts = []
                for idx in _valid_indices:
                    if _dg_words and 0 <= idx < len(_dg_words):
                        w = str(_dg_words[idx].get("punctuated_word") or _dg_words[idx].get("word") or "").strip()
                        if w:
                            _em_word_parts.append(w)
                _em_word = " ".join(_em_word_parts) if _em_word_parts else ""
                _em_duration = float(em.get("duration") or (2.5 if intensity == "high" else 1.5))
                emphasis_moments.append({
                    "t": t,
                    "word_indices": _valid_indices,
                    "type": em_type,
                    "intensity": intensity,
                    "word": _em_word,
                    "duration": _em_duration,
                })
            except Exception:
                continue
    if emphasis_moments:
        emphasis_moments.sort(key=lambda x: x["t"])
        print(f"[generate-edit] Emphasis moments: {len(emphasis_moments)}", flush=True)
        for em in emphasis_moments:
            print(f"[generate-edit]   {em['t']:.1f}s: {em['type']} ({em['intensity']})", flush=True)
    edit_plan["_emphasis_moments"] = emphasis_moments

    # Auto-derive caption_keywords from emphasis_moments if not provided
    if not edit_plan.get("caption_keywords") and emphasis_moments and _dg_words:
        # Build set of explicitly removed word indices to avoid deriving keywords from them
        _removed_word_indices = set()
        for rw in (edit_plan.get("remove_words") or []):
            if "word_index" in rw:
                _removed_word_indices.add(int(rw["word_index"]))
        _KEYWORD_STOPWORDS = {"the", "and", "for", "but", "get", "got", "was", "are", "this", "that", "with", "from", "have", "has", "had", "not", "been", "were", "will", "can", "did", "does", "its", "they", "them", "then", "than", "what", "when", "where", "which", "who", "whom", "how", "all", "each", "every", "both", "few", "more", "most", "some", "such", "only", "very", "just", "also", "into", "over", "like", "about", "know", "think", "said", "says", "going", "really", "actually"}
        auto_keywords = set()
        for em in emphasis_moments:
            for idx in em.get("word_indices", []):
                if 0 <= idx < len(_dg_words) and idx not in _removed_word_indices:
                    kw = re.sub(r"[.,!?;:'\"\\]", "", str(_dg_words[idx].get("word") or "").lower())
                    if len(kw) >= 4 and kw not in _KEYWORD_STOPWORDS:
                        auto_keywords.add(kw)
        if auto_keywords:
            edit_plan["caption_keywords"] = list(auto_keywords)
            print(f"[generate-edit] Auto-derived {len(auto_keywords)} caption keywords from emphasis moments: {auto_keywords}", flush=True)

    # ── Parse sound effects ──────────────────────────────────────────────
    raw_sfx = edit_plan.get("sound_effects", [])
    sound_effects = []
    valid_sounds = set(_SFX_CATEGORIES.keys())
    for sfx in raw_sfx:
        if isinstance(sfx, dict) and "t" in sfx and "sound" in sfx:
            try:
                t = float(sfx["t"])
            except Exception:
                continue
            sound = str(sfx["sound"]).lower()
            # Resolve aliases (including legacy names like thud→hit, swoosh→whoosh_slow, etc.)
            sound = _SFX_ALIASES.get(sound, sound)
            if sound in valid_sounds and t >= 0 and (video_duration <= 0 or t <= video_duration):
                word = str(sfx.get("word") or "").strip().lower()
                sound_effects.append({"t": t, "sound": sound, "word": word})

    # Sound effects are taken EXACTLY as Gemini provided them. No caps,
    # no spacing filter, no auto-placement, no dedup. The Gemini prompt is
    # the single source of truth for SFX placement rules — if a placement
    # is wrong, the fix is the prompt.
    if sound_effects:
        sound_effects.sort(key=lambda x: x["t"])
        print(f"[generate-edit] Sound effects: {len(sound_effects)} placements", flush=True)
        for sfx in sound_effects:
            print(f"[generate-edit]   {sfx['t']:.1f}s: {sfx['sound']}", flush=True)
    edit_plan["sound_effects"] = sound_effects
    edit_plan["_parsed_sound_effects"] = sound_effects

    for bool_field in ("sharpening", "denoise", "shadow_lift", "highlight_rolloff", "vibrance",
                       "cinematic_bars", "audio_denoise", "beat_sync"):
        v = edit_plan.get(bool_field)
        if isinstance(v, str):
            edit_plan[bool_field] = v.strip().lower() in ("true", "1", "yes")
        else:
            edit_plan[bool_field] = bool(v)

    valid_grain = {"none", "subtle", "medium", "heavy"}
    valid_vignette = {"none", "light", "medium", "strong"}
    valid_transitions = {
        "none", "fade", "fadeblack", "fadewhite", "dissolve",
        "wipeleft", "wiperight", "wipeup", "wipedown",
        "smoothleft", "smoothright", "smoothup", "smoothdown",
        "whip_left", "whip_right", "flash", "glitch", "zoomin",
    }
    if edit_plan.get("grain") not in valid_grain:
        edit_plan["grain"] = "none"
    if edit_plan.get("vignette") not in valid_vignette:
        edit_plan["vignette"] = "none"

    for overlay in edit_plan.get("text_overlays", []):
        overlay["sfx_style"] = "none"

    final_cuts = []
    for clip_entry in validated_cuts:
        transition = str(clip_entry.get("transition_out") or "").lower()
        if transition not in valid_transitions:
            print(f"[generate-edit] Unknown transition '{clip_entry.get('transition_out')}' -> 'none'", flush=True)
            transition = "none"
        speed = max(0.25, min(4.0, float(clip_entry.get("speed") or 1.0)))
        clip_entry["transition_sound"] = "none"
        clip_entry["sfx_style"] = "none"
        final_cuts.append({
            "source_start": clip_entry["source_start"],
            "source_end": clip_entry["source_end"],
            "transition_out": transition,
            "transition_sound": "none",
            "sfx_style": "none",
            "zoom": clip_entry.get("zoom") or "none",
            "cut_zoom": bool(clip_entry.get("cut_zoom")),
            "speed": speed,
        })

    if final_cuts and opening_zoom != "none":
        target_idx = 0
        raw_hook = edit_plan.get("hook_clip")
        if isinstance(raw_hook, dict):
            hs = float(raw_hook.get("source_start") or 0.0)
            he = float(raw_hook.get("source_end") or 0.0)
            for i, cut in enumerate(final_cuts):
                if float(cut["source_start"]) <= hs + 0.1 and float(cut["source_end"]) >= he - 0.1:
                    target_idx = i
                    break
        final_cuts[target_idx]["zoom"] = opening_zoom
        print(f"[generate-edit] Assigned opening_zoom={opening_zoom} to clip {target_idx}", flush=True)

    # ── Map emphasis_moments to cut_zoom on the containing clip ──────────
    # cut_zoom is the renderer's interpretation of "this is a high-intensity
    # moment" — same as how SFX onset compensation interprets "place sound
    # at word X". It is NOT auto-placement of new content; it implements the
    # render decision implied by Gemini's emphasis_moments declaration.
    # Apply cut_zoom to clips containing high-intensity emphasis moments.
    # Gemini owns the spacing of emphasis moments — the prompt teaches it
    # to space them appropriately. No debounce needed.
    for em in emphasis_moments:
        em_t = em["t"]
        for clip in final_cuts:
            cs = float(clip["source_start"])
            ce = float(clip["source_end"])
            if cs <= em_t <= ce:
                if em["intensity"] == "high" and str(clip.get("zoom") or "none") == "none":
                    clip["zoom"] = "cut_zoom"
                    clip["cut_zoom"] = True
                    print(f"[emphasis] Applied cut_zoom to clip {cs:.1f}-{ce:.1f}s ({em['type']})", flush=True)
                break

    # Color grading is Gemini's decision — the prompt teaches it that phone
    # cameras auto-white-balance and grading talking-head content usually
    # makes it worse. If Gemini still picks a grade, trust the choice.
    edit_plan["cuts"] = final_cuts
    edit_plan.pop("teal_orange", None)
    edit_plan.pop("beat_sync", None)
    edit_plan.pop("video_profile", None)
    edit_plan.pop("frame_layout", None)
    if "clips" in edit_plan:
        del edit_plan["clips"]
    edit_plan.pop("remove_words", None)
    edit_plan.pop("target_duration", None)

    total_clip_duration = sum(max(0, c["source_end"] - c["source_start"]) for c in final_cuts)
    if video_duration > 0 and total_clip_duration / video_duration < 0.3:
        print(
            f"[generate-edit] WARNING: Gemini's clips only cover {(total_clip_duration / video_duration)*100:.0f}% "
            f"of the video ({total_clip_duration:.1f}s of {video_duration:.1f}s)",
            flush=True,
        )

    edit_plan["analysis_data"] = analysis

    print(
        f"[generate-edit] Recipe: {len(final_cuts)} clips, "
        f"{len(edit_plan.get('sound_effects', []))} sfx, "
        f"intent={edit_plan.get('color_intent', 'none')}, "
        f"captions={edit_plan.get('caption_style', 'none')}",
        flush=True,
    )

    return edit_plan


# ─── SFX HELPERS ─────────────────────────────────────────────────────────────

# LUFS-based SFX normalization — eliminates per-sound manual volume tuning.
# Instead of 29 hand-tuned volumes, we:
#   1. Measure each SFX file's RMS loudness once (cached)
#   2. Assign each sound to a MIX CATEGORY (3 levels, not 29)
#   3. Compute gain adjustment to hit the category's target level
#
# Mix categories (relative to voice at 0 dB):
#   "quiet"  — ambient/atmospheric sounds, sit well below voice (-20 dB)
#   "medium" — transitions, risers, UI sounds (-14 dB below voice)
#   "loud"   — impacts, punchy sounds (-10 dB below voice)
#
# Reference: ITU-R BS.1770-4 / EBU R128 for loudness normalization principles.

# Target mix levels as linear amplitude (10^(dB/20)):
# quiet=-20dB → 0.10, medium=-14dB → 0.20, loud=-10dB → 0.316
_SFX_CATEGORY_LEVELS = {
    "quiet":  0.10,
    "medium": 0.20,
    "loud":   0.316,
}

# Sound → category mapping. Adding a new SFX only requires placing it in
# one of 3 categories — no per-file volume calibration needed.
_SFX_CATEGORIES = {
    "boom": "loud",
    "camera_shutter": "medium",
    "ching": "loud",
    "click": "medium",
    "ding": "medium",
    "drum_roll": "medium",
    "hit": "loud",
    "pop": "medium",
    "reverse": "quiet",
    "sad_trombone": "medium",
    "transition_smooth": "quiet",
    "typing": "quiet",
    "whoosh_slow": "quiet",
    "thunder": "medium",
}

# Sound → onset offset (seconds). The "onset" is the time within the file
# at which the meaningful moment of the sound occurs (the impact, the climax,
# the perceived "hit"). When mixing, we schedule each SFX to start at
# (placement_time - onset) so the perceived moment lands EXACTLY on the word.
#
# For impact sounds (boom, hit, ching, ding, click, pop, camera_shutter), the
# onset is the peak amplitude.
#
# For build-up sounds (drum_roll, reverse, sad_trombone, thunder, whoosh_slow,
# transition_smooth), the onset is the climactic moment — the build PRECEDES
# the trigger word and the climax lands on it.
#
# Measured by decoding each file to PCM and finding the peak amplitude sample.
_SFX_ONSET_OFFSETS = {
    # Short impacts — offset to ATTACK (first audible transient on the word)
    "hit":               0.000,
    "ching":             0.000,
    "ding":              0.000,
    "click":             0.052,
    "pop":               0.013,
    "camera_shutter":    0.012,
    # Cinematic impacts — offset to PEAK (crash/hit lands on the word, buildup precedes)
    "boom":              0.440,
    "thunder":           0.734,
    # Build-up sounds — offset to CLIMAX (the payoff moment lands on the word)
    "drum_roll":         1.657,
    "reverse":           1.372,
    "sad_trombone":      1.290,
    # Atmospheric — offset to ONSET (first audible whoosh on the word)
    "transition_smooth": 0.089,
    "whoosh_slow":       0.034,
    # Continuous — no offset
    "typing":            0.000,
}

# RMS measurement cache — populated lazily, avoids re-measuring same file
_SFX_RMS_CACHE = {}
_SFX_TARGET_RMS = -18.0  # dBFS — reference level all SFX are normalized to


def _measure_sfx_rms(sfx_path):
    """Measure RMS loudness of an SFX file using ffmpeg astats. Cached."""
    if sfx_path in _SFX_RMS_CACHE:
        return _SFX_RMS_CACHE[sfx_path]
    cmd = [
        "ffmpeg", "-i", sfx_path, "-af",
        "astats=metadata=1:reset=0,ametadata=mode=print",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg SFX RMS measurement failed for {sfx_path}: {(result.stderr or '')[-300:]}")
    rms_matches = re.findall(
        r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", result.stderr
    )
    if not rms_matches:
        raise RuntimeError(f"FFmpeg astats returned no RMS data for {sfx_path}")
    rms_db = float(rms_matches[-1])
    rms_db = max(-60.0, min(0.0, rms_db))
    _SFX_RMS_CACHE[sfx_path] = rms_db
    return rms_db

_SFX_ALIASES = {
    "whoosh": "whoosh_slow",
    "swoosh": "whoosh_slow",
    "impact": "hit",
    "drop": "boom",
    "bass_drop": "boom",
    "bass": "boom",
    "slam": "hit",
    "thud": "hit",
    "stinger": "hit",
    "cash": "ching",
    "money": "ching",
    "cash_register": "ching",
    "ka_ching": "ching",
    "coin": "ching",
    "chime": "ding",
    "alert": "ding",
    "notification": "ding",
    "bell": "ding",
    "unlock": "ding",
    "reveal": "ding",
    "flash": "pop",
    "snap": "click",
    "button": "click",
    "press": "click",
    "bounce": "pop",
    "boing": "pop",
    "fail": "sad_trombone",
    "wah": "sad_trombone",
    "horn": "pop",
    "scratch": "reverse",
    "vinyl_scratch": "reverse",
    "record_stop": "reverse",
    "glitch": "reverse",
    "riser": "drum_roll",
    "riser_short": "drum_roll",
    "buildup": "drum_roll",
    "tension": "drum_roll",
    "swipe": "transition_smooth",
    "slide": "transition_smooth",
    "whoosh_fast": "transition_smooth",
    "wind": "whoosh_slow",
    "breeze": "whoosh_slow",
    "fire": "boom",
    "static": "reverse",
    "heartbeat": "boom",
    "page_turn": "click",
    "switch": "click",
    "shutter": "camera_shutter",
    "camera": "camera_shutter",
}


def normalize_sfx_style(style):
    key = str(style or "").strip().lower()
    if not key or key == "none":
        return "none"
    return _SFX_ALIASES.get(key, key)


def get_sfx_path(sound_name):
    normalized = normalize_sfx_style(sound_name)
    if normalized == "none":
        return None
    candidate = os.path.join(SFX_SOUNDS_DIR, f"{normalized}.mp3")
    if os.path.exists(candidate):
        return candidate
    print(f"[sfx] Sound file not found: {candidate}", flush=True)
    return None


def get_sfx_volume(sound_name, timestamp, speech_segments, is_text_overlay=False):
    """
    Compute SFX mix volume using LUFS-based normalization.

    Instead of hand-tuned per-sound volumes, we:
    1. Look up the sound's mix category (quiet/medium/loud)
    2. Measure the file's actual RMS (cached)
    3. Compute gain to normalize to reference level
    4. Apply category mix level
    5. Duck 6dB during speech (broadcast standard for under-bed audio)
    """
    normalized = normalize_sfx_style(sound_name)
    category = _SFX_CATEGORIES.get(normalized, "medium")
    category_level = _SFX_CATEGORY_LEVELS[category]

    # Measure actual file loudness and compute normalization gain
    sfx_path = get_sfx_path(sound_name)
    if sfx_path:
        measured_rms = _measure_sfx_rms(sfx_path)
        # Gain to bring SFX to reference level: 10^((target - measured) / 20)
        gain_db = _SFX_TARGET_RMS - measured_rms
        norm_gain = 10 ** (gain_db / 20.0)
    else:
        norm_gain = 1.0

    base = category_level * norm_gain

    # Duck during speech: -6dB (factor 0.5) per broadcast practice
    # Text overlays duck slightly less since they're meant to sync with text
    segs = speech_segments or []
    during_speech = any(
        float(seg.get("start") or 0) <= timestamp <= float(seg.get("end") or 0)
        for seg in segs
    )
    duck = 0.63 if (during_speech and is_text_overlay) else (0.50 if during_speech else 1.0)
    vol = base * duck
    return round(max(0.01, min(0.5, vol)), 3)


# ─── FFMPEG RENDER ────────────────────────────────────────────────────────────

def export_additional_format(output_path, aspect_ratio, dest_path):
    """Crop 9:16 output to '1:1' (1080x1080) or '16:9' (1920x1080)."""
    if aspect_ratio == "1:1":
        vf = "crop=1080:1080:0:(ih-1080)/2"
    elif aspect_ratio == "16:9":
        vf = "crop=1080:607:0:(ih-607)/2,scale=1920:1080"
    else:
        raise ValueError(f"Unsupported aspect_ratio: {aspect_ratio}")
    run_ffmpeg([
        "-y", "-i", output_path,
        "-vf", vf,
    ] + get_encode_args("high") + [
        "-c:a", "copy",
        "-movflags", "+faststart",
        dest_path,
    ])


def select_best_thumbnail_frame(video_path, seed_ts, work_dir):
    """Pick the visually best frame for a thumbnail by scanning a window around
    Gemini's recommended `seed_ts` and scoring each candidate on multiple
    objective visual quality metrics.

    NO post-processing whatsoever — the winning frame is extracted at full
    resolution from the video and saved as a high-quality JPEG, exactly as
    it appears in the rendered output.

    Scoring metrics (weights sum to 1.0):
      - Face DNN confidence (25%)            — is there a clearly detectable face?
      - Face area (capped) (10%)             — is the face large enough to fill?
      - Face centeredness (10%)              — is the face well-positioned?
      - Sharpness on face region (25%)       — Laplacian variance, penalizes motion blur
      - Brightness sweet-spot (15%)          — penalizes under/over-exposed faces
      - Eye openness (15%)                   — Haar cascade, 2 eyes detected = blinks penalized

    For videos with no detectable face (b-roll, landscape), falls back to
    sharpness + brightness only on the full frame.

    Returns (bytes, 'image/jpeg').
    """
    import cv2
    import numpy as np

    # ── Load detectors ──────────────────────────────────────────────────
    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    _face_net = None
    if os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL):
        try:
            _face_net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
        except Exception as _e:
            print(f"[thumbnail] WARNING: face DNN load failed: {_e}", flush=True)

    _eye_cascade = None
    try:
        _eye_xml = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
        if os.path.exists(_eye_xml):
            _eye_cascade = cv2.CascadeClassifier(_eye_xml)
            if _eye_cascade.empty():
                _eye_cascade = None
    except Exception:
        _eye_cascade = None

    # ── Probe video duration ────────────────────────────────────────────
    _probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True, timeout=5,
    )
    try:
        _streams = json.loads(_probe.stdout or "{}").get("streams", [])
        _vs = next((s for s in _streams if s.get("codec_type") == "video"), {})
        _duration = float(_vs.get("duration") or 0.0)
        if _duration <= 0:
            _duration = float(_vs.get("nb_frames", 0)) / float(eval(_vs.get("r_frame_rate", "30/1")))
    except Exception:
        _duration = 60.0

    # ── Compute scan window ─────────────────────────────────────────────
    # TIGHT window of ±0.6s around Gemini's seed. The user explicitly wants
    # the dramatic moment Gemini identified, not "any clean face frame nearby".
    # ±0.6s × 15 fps = ~18 candidates. That's enough density to skip a blink
    # frame or motion blur, but narrow enough that the picker can't drift to
    # a totally different sentence (which is what happened with ±2s — the
    # picker chose 32.41s "And" instead of 33.91s "Stelius?").
    _window = 0.6
    _window_start = max(0.05, seed_ts - _window)
    _window_end = min(max(0.1, _duration - 0.05), seed_ts + _window)
    if _window_end <= _window_start:
        _window_start = max(0.05, seed_ts - 0.3)
        _window_end = min(_duration - 0.05, seed_ts + 0.3)
    _window_dur = _window_end - _window_start
    _candidate_fps = 15.0  # 15 candidates per second within the narrow window

    # ── Extract candidates in ONE ffmpeg call ───────────────────────────
    # Use a moderate scoring resolution (540 wide for 9:16 = 540x960). This
    # gives the DNN plenty of pixels to detect faces accurately, the eye
    # cascade enough resolution for blink detection, and Laplacian a real
    # signal — while keeping decode + scoring under ~2 seconds total.
    _cand_dir = os.path.join(work_dir, "_thumb_candidates")
    os.makedirs(_cand_dir, exist_ok=True)
    # Clear any stale frames from prior jobs
    for _stale in glob.glob(os.path.join(_cand_dir, "*.jpg")):
        try:
            os.unlink(_stale)
        except Exception:
            pass

    _t_extract = time.time()
    _extract_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning",
         "-ss", f"{_window_start:.3f}",
         "-t", f"{_window_dur:.3f}",
         "-i", video_path,
         "-vf", f"fps={_candidate_fps},scale=540:-2",
         "-q:v", "3",
         os.path.join(_cand_dir, "cand_%04d.jpg")],
        capture_output=True, text=True, timeout=15,
    )
    if _extract_cmd.returncode != 0:
        raise RuntimeError(f"[thumbnail] candidate extraction failed: {(_extract_cmd.stderr or '')[-300:]}")
    _t_extract = time.time() - _t_extract

    _cand_files = sorted(glob.glob(os.path.join(_cand_dir, "cand_*.jpg")))
    if not _cand_files:
        raise RuntimeError("[thumbnail] no candidate frames extracted")

    # ── Pass 1: Collect raw metrics for every candidate ─────────────────
    # We do TWO passes: first collect raw values, then normalize relatively.
    # Relative normalization means the SHARPEST frame in the window wins, the
    # LARGEST face wins, etc. — instead of a "good enough" threshold that
    # produces ties at 1.0 and arbitrary tiebreaking.
    _t_score = time.time()
    _raw = []  # list of dicts with raw per-candidate metrics

    for _ci, _cpath in enumerate(_cand_files):
        _cand_ts = _window_start + (_ci / _candidate_fps)

        _frame = cv2.imread(_cpath)
        if _frame is None:
            continue
        _h, _w = _frame.shape[:2]

        # Face detection
        _face_conf = 0.0
        _face_bbox = None
        if _face_net is not None:
            _blob = cv2.dnn.blobFromImage(
                cv2.resize(_frame, (300, 300)), 1.0, (300, 300),
                (104.0, 177.0, 123.0), swapRB=False, crop=False,
            )
            _face_net.setInput(_blob)
            _detections = _face_net.forward()
            for _di in range(_detections.shape[2]):
                _conf = float(_detections[0, 0, _di, 2])
                if _conf < 0.5:
                    continue
                _x1 = int(_detections[0, 0, _di, 3] * _w)
                _y1 = int(_detections[0, 0, _di, 4] * _h)
                _x2 = int(_detections[0, 0, _di, 5] * _w)
                _y2 = int(_detections[0, 0, _di, 6] * _h)
                _x1, _y1 = max(0, _x1), max(0, _y1)
                _x2, _y2 = min(_w, _x2), min(_h, _y2)
                if _x2 <= _x1 or _y2 <= _y1:
                    continue
                _area = (_x2 - _x1) * (_y2 - _y1)
                if _face_bbox is None or _area > ((_face_bbox[2] - _face_bbox[0]) * (_face_bbox[3] - _face_bbox[1])):
                    _face_conf = _conf
                    _face_bbox = (_x1, _y1, _x2, _y2)

        if _face_bbox is not None:
            _fx1, _fy1, _fx2, _fy2 = _face_bbox
            _face_region = _frame[_fy1:_fy2, _fx1:_fx2]
            _face_gray = cv2.cvtColor(_face_region, cv2.COLOR_BGR2GRAY)

            _face_area = (_fx2 - _fx1) * (_fy2 - _fy1)
            _frame_area = _w * _h
            _area_ratio = _face_area / _frame_area

            _face_cx = (_fx1 + _fx2) / 2
            _face_cy = (_fy1 + _fy2) / 2
            _frame_cx = _w / 2
            _frame_cy = _h / 2
            _max_dist = ((_w / 2) ** 2 + (_h / 2) ** 2) ** 0.5
            _dist = ((_face_cx - _frame_cx) ** 2 + (_face_cy - _frame_cy) ** 2) ** 0.5
            _center_score = max(0.0, 1.0 - (_dist / _max_dist))

            _lap_var = float(cv2.Laplacian(_face_gray, cv2.CV_64F).var())
            _mean_lum = float(_face_gray.mean())

            # Eye detection: 2 eyes = open, 1 = partial, 0 = blink
            _eye_score = 0.7  # neutral default if cascade unavailable
            if _eye_cascade is not None and _face_gray.size > 0:
                _eyes = _eye_cascade.detectMultiScale(
                    _face_gray, scaleFactor=1.1, minNeighbors=5,
                    minSize=(int((_fx2 - _fx1) * 0.1), int((_fy2 - _fy1) * 0.05)),
                )
                _n_eyes = len(_eyes)
                if _n_eyes >= 2:
                    _eye_score = 1.0
                elif _n_eyes == 1:
                    _eye_score = 0.55
                else:
                    _eye_score = 0.15

            _raw.append({
                "ts": _cand_ts,
                "has_face": True,
                "face_conf": _face_conf,
                "area_ratio": _area_ratio,
                "center": _center_score,
                "lap_var": _lap_var,
                "mean_lum": _mean_lum,
                "eye_score": _eye_score,
            })
        else:
            _gray = cv2.cvtColor(_frame, cv2.COLOR_BGR2GRAY)
            _lap_var = float(cv2.Laplacian(_gray, cv2.CV_64F).var())
            _mean_lum = float(_gray.mean())
            _raw.append({
                "ts": _cand_ts,
                "has_face": False,
                "lap_var": _lap_var,
                "mean_lum": _mean_lum,
            })

    if not _raw:
        raise RuntimeError("[thumbnail] no scorable candidates")

    # ── Pass 2: Normalize relatively + score ────────────────────────────
    # Sharpness and face area are normalized against the BEST candidate in
    # the window so the sharpest/largest-face frame gets 1.0 and others get
    # proportional credit. This eliminates the "many candidates tie at 1.0"
    # problem caused by absolute thresholds.
    _face_candidates = [r for r in _raw if r["has_face"]]
    _max_lap = max((r["lap_var"] for r in _raw), default=1.0) or 1.0
    _max_area = max((r["area_ratio"] for r in _face_candidates), default=0.15) or 0.15

    def _brightness_score(_lum):
        # Tighter sweet-spot: peak at 130, falls off symmetrically
        if _lum < 40 or _lum > 220:
            return 0.0
        if 110 <= _lum <= 160:
            return 1.0
        if _lum < 110:
            return max(0.0, (_lum - 40) / 70)
        return max(0.0, (220 - _lum) / 60)

    _scored = []  # list of (score, ts, breakdown)
    for _r in _raw:
        if _r["has_face"]:
            _conf_score = (_r["face_conf"] - 0.5) / 0.5  # [0.5,1] → [0,1]
            _area_score = min(_r["area_ratio"] / _max_area, 1.0)
            _sharp_score = min(_r["lap_var"] / _max_lap, 1.0)
            _bright_score = _brightness_score(_r["mean_lum"])

            # Seed proximity is HEAVILY weighted: Gemini chose this exact
            # timestamp for narrative reasons. We only deviate to skip frames
            # with objective failure modes (blinks, motion blur, bad lighting).
            # Distance from seed in seconds → score in [0, 1].
            _seed_dist = abs(_r["ts"] - seed_ts)
            _proximity = max(0.0, 1.0 - _seed_dist / _window)

            _total = (
                0.10 * _conf_score
                + 0.10 * _area_score
                + 0.05 * _r["center"]
                + 0.20 * _sharp_score
                + 0.10 * _bright_score
                + 0.20 * _r["eye_score"]
                + 0.25 * _proximity
            )
            _breakdown = {
                "has_face": True,
                "conf": _conf_score, "area": _area_score, "center": _r["center"],
                "sharp": _sharp_score, "bright": _bright_score, "eye": _r["eye_score"],
                "proximity": _proximity,
                "lap_var": _r["lap_var"], "mean_lum": _r["mean_lum"],
                "face_conf": _r["face_conf"],
            }
        else:
            # No face — use sharpness + brightness on full frame.
            # Capped at 0.5 so any face-frame still wins when available.
            _sharp_score = min(_r["lap_var"] / _max_lap, 1.0)
            _bright_score = _brightness_score(_r["mean_lum"])
            _total = 0.5 * (0.6 * _sharp_score + 0.4 * _bright_score)
            _breakdown = {
                "has_face": False, "sharp": _sharp_score, "bright": _bright_score,
                "lap_var": _r["lap_var"], "mean_lum": _r["mean_lum"],
            }
        _scored.append((_total, _r["ts"], _breakdown))

    _t_score = time.time() - _t_score

    # Sort by score descending, pick winner
    _scored.sort(key=lambda r: -r[0])
    _winner_score, _winner_ts, _winner_breakdown = _scored[0]

    # Cleanup candidate frames
    for _f in _cand_files:
        try:
            os.unlink(_f)
        except Exception:
            pass
    try:
        os.rmdir(_cand_dir)
    except Exception:
        pass

    # ── Re-extract winning frame at FULL resolution ─────────────────────
    # The candidate scoring used 540p; the actual thumbnail must be the full
    # 1080x1920 frame from the video. NO post-processing applied.
    _final_path = os.path.join(work_dir, "thumbnail_final.jpg")
    _t_final = time.time()
    _final_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning",
         "-ss", f"{_winner_ts:.3f}",
         "-i", video_path,
         "-frames:v", "1",
         "-q:v", "2",  # JPEG quality scale 2 = ~95%
         _final_path],
        capture_output=True, text=True, timeout=10,
    )
    _t_final = time.time() - _t_final
    if _final_cmd.returncode != 0 or not os.path.exists(_final_path):
        raise RuntimeError(f"[thumbnail] final frame extract failed: {(_final_cmd.stderr or '')[-300:]}")

    with open(_final_path, "rb") as f:
        _data = f.read()
    try:
        os.unlink(_final_path)
    except Exception:
        pass

    _has_face = _winner_breakdown.get("has_face", False)
    print(
        f"[thumbnail] Selected best frame at {_winner_ts:.3f}s "
        f"(seed={seed_ts:.2f}s, window=±{_window:.1f}s, {len(_scored)} candidates) "
        f"score={_winner_score:.3f} face={_has_face} "
        f"extract={_t_extract:.2f}s score={_t_score:.2f}s final={_t_final:.2f}s",
        flush=True,
    )
    if _has_face:
        print(
            f"[thumbnail]   metrics: conf={_winner_breakdown['conf']:.2f} "
            f"area={_winner_breakdown['area']:.2f} center={_winner_breakdown['center']:.2f} "
            f"sharp={_winner_breakdown['sharp']:.2f}(lap={_winner_breakdown['lap_var']:.0f}) "
            f"bright={_winner_breakdown['bright']:.2f}(lum={_winner_breakdown['mean_lum']:.0f}) "
            f"eye={_winner_breakdown['eye']:.2f} "
            f"prox={_winner_breakdown['proximity']:.2f}",
            flush=True,
        )
        # Log top 3 candidates for debugging — helps diagnose unexpected picks
        for _idx, (_s, _ts, _b) in enumerate(_scored[:3]):
            if _b.get("has_face"):
                print(
                    f"[thumbnail]   #{_idx+1} t={_ts:.3f}s score={_s:.3f} "
                    f"sharp={_b['sharp']:.2f} bright={_b['bright']:.2f} "
                    f"eye={_b['eye']:.2f} prox={_b['proximity']:.2f}",
                    flush=True,
                )

    return _data, "image/jpeg"


def fetch_broll_clip(keyword, duration_needed, work_dir, dialogue_reason=""):
    """Search Pexels for a portrait video clip. Returns local path or None."""
    pexels_key = os.environ.get("PEXELS_API_KEY")
    if not pexels_key:
        print(f"[broll] PEXELS_API_KEY not set — skipping '{keyword}'", flush=True)
        return None

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": pexels_key},
        params={
            "query": keyword,
            "per_page": 15,
            "orientation": "portrait",
            "size": "large",
        },
        timeout=25,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos") or []

    if not videos:
        print(f"[broll] No Pexels results for '{keyword}'", flush=True)
        return None

    print(f"[broll] Pexels returned {len(videos)} results for '{keyword}'", flush=True)

    # Extract key words from the keyword for tag/URL matching
    _kw_words = set(keyword.lower().split())
    _stop_words = {"a", "an", "the", "in", "on", "of", "with", "and", "to", "for", "up", "at", "by", "from", "into", "is", "it", "close"}
    _kw_match_words = _kw_words - _stop_words

    # Score all candidates
    _candidates = []
    for vid_idx, video in enumerate(videos):
        vid_dur = float(video.get("duration") or 0)
        vid_id = video.get("id", "unknown")
        video_files = video.get("video_files") or []

        portrait_files = []
        for f in video_files:
            h = f.get("height") or 0
            w = f.get("width") or 0
            link = f.get("link") or ""
            file_type = f.get("file_type") or ""

            if h <= w:
                continue
            if not link:
                continue
            if h < 720:
                continue
            if file_type and "image" in file_type.lower():
                continue
            if file_type and "video" not in file_type.lower() and file_type != "":
                continue

            portrait_files.append({"link": link, "height": h, "width": w, "file_type": file_type})

        if not portrait_files:
            continue

        portrait_files.sort(key=lambda x: abs(x["height"] - 1920))
        best_file = portrait_files[0]

        score = 0
        if vid_dur >= duration_needed:
            score += 10
        elif vid_dur >= duration_needed * 0.7:
            score += 5
        if best_file["height"] >= 1920:
            score += 5
        elif best_file["height"] >= 1080:
            score += 3
        score += max(0, 10 - vid_idx)

        # URL slug relevance — Pexels encodes descriptive words in the page URL
        _vid_url = str(video.get("url") or "").lower()
        _vid_url_words = set(re.split(r'[-/]', _vid_url.split("pexels.com/")[-1] if "pexels.com/" in _vid_url else ""))
        # Also check tags (usually empty on Pexels, but check anyway)
        _vid_tags = set()
        for _tag_obj in (video.get("tags") or []):
            if isinstance(_tag_obj, dict):
                _vid_tags.update(_tag_obj.get("name", "").lower().split())
            elif isinstance(_tag_obj, str):
                _vid_tags.update(_tag_obj.lower().split())
        _all_vid_words = _vid_tags | _vid_url_words
        if _all_vid_words and _kw_match_words:
            _tag_matches = len(_kw_match_words & _all_vid_words)
            score += _tag_matches * 3

        # Get poster thumbnail URL for visual scoring
        _poster_url = str(video.get("image") or "")

        _candidates.append({
            "video_id": vid_id,
            "video_idx": vid_idx,
            "duration": vid_dur,
            "file": best_file,
            "score": score,
            "poster_url": _poster_url,
            "url_words": _all_vid_words,
        })

    # Visual scoring: fetch poster thumbnails for top candidates and use
    # Gemini to pick the best match. This is a single tiny API call with
    # ~3 small JPEG thumbnails — completes in <1s, no video downloads.
    if _candidates and _kw_match_words:
        _candidates.sort(key=lambda x: x["score"], reverse=True)
        _top_n = _candidates[:5]  # top 5 candidates
        _poster_images = {}

        # Fetch poster thumbnails in parallel (~5KB each, <200ms total)
        def _fetch_poster(idx_url):
            _idx, _url = idx_url
            if not _url:
                return _idx, None
            try:
                _r = requests.get(_url, timeout=5)
                if _r.status_code == 200 and len(_r.content) > 500:
                    return _idx, _r.content
            except Exception:
                pass
            return _idx, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as _poster_pool:
            _poster_futs = [_poster_pool.submit(_fetch_poster, (i, c["poster_url"])) for i, c in enumerate(_top_n)]
            for _fut in concurrent.futures.as_completed(_poster_futs, timeout=5):
                try:
                    _pi, _pdata = _fut.result()
                    if _pdata:
                        _poster_images[_pi] = _pdata
                except Exception:
                    pass

        # Use Gemini to pick the best thumbnail match (single fast call)
        if _poster_images and len(_poster_images) >= 2:
            try:
                _pick_client = _get_genai_client()
                _dialogue_ctx = f' The speaker says: "{dialogue_reason}".' if dialogue_reason else ""
                _parts = [f'This clip plays over a talking-head video while the viewer hears the dialogue.{_dialogue_ctx} Which image best matches what the viewer should see for "{keyword}"? Reply with ONLY the number (1-{len(_poster_images)}).']
                _poster_idx_map = {}
                _num = 1
                for _pi in sorted(_poster_images.keys()):
                    _img_bytes = _poster_images[_pi]
                    _parts.append(f"\nImage {_num}:")
                    _parts.append(genai_types.Part.from_bytes(data=_img_bytes, mime_type="image/jpeg"))
                    _poster_idx_map[_num] = _pi
                    _num += 1

                _pick_t0 = time.time()
                _pick_resp = _pick_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[_parts],
                    config=genai_types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=8,
                    ),
                )
                _pick_elapsed = time.time() - _pick_t0
                _pick_text = str(getattr(_pick_resp, "text", "") or "").strip()
                # Extract the number from response
                _pick_num = None
                for _ch in _pick_text:
                    if _ch.isdigit():
                        _pick_num = int(_ch)
                        break
                if _pick_num and _pick_num in _poster_idx_map:
                    _winner_idx = _poster_idx_map[_pick_num]
                    _top_n[_winner_idx]["score"] += 50  # massive boost for visual match
                    print(f"[broll] Gemini visual pick: #{_pick_num} (candidate {_winner_idx}) in {_pick_elapsed:.1f}s for '{keyword}'", flush=True)
                else:
                    print(f"[broll] Gemini visual pick: unclear response '{_pick_text}' in {_pick_elapsed:.1f}s", flush=True)
            except Exception as _pick_err:
                print(f"[broll] Gemini visual pick failed: {_pick_err}", flush=True)

        # Put scored candidates back
        _candidates = _top_n + _candidates[5:]

    # Pick the best candidate
    best_match = None
    best_score = -1
    for _c in _candidates:
        if _c["score"] > best_score:
            best_match = _c
            best_score = _c["score"]

    if not best_match:
        print(f"[broll] No portrait video files found across {len(videos)} results for '{keyword}' — SKIPPING", flush=True)
        return None

    chosen_file = best_match["file"]
    chosen_url = chosen_file["link"]
    if not chosen_url:
        print(f"[broll] No usable file for '{keyword}'", flush=True)
        return None

    print(
        f"[broll] Selected '{keyword}': pexels_id={best_match['video_id']}, "
        f"result #{best_match['video_idx']+1}/{len(videos)}, "
        f"{chosen_file['width']}x{chosen_file['height']}, "
        f"type={chosen_file['file_type']}, "
        f"duration={best_match['duration']:.1f}s, "
        f"score={best_match['score']}",
        flush=True,
    )

    safe_kw = re.sub(r"[^a-z0-9]", "_", keyword.lower())[:30]
    dest = os.path.join(work_dir, f"broll_{safe_kw}.mp4")

    dl = requests.get(chosen_url, stream=True, timeout=30)
    dl.raise_for_status()

    content_type = dl.headers.get("content-type", "")
    if "image" in content_type.lower():
        print(f"[broll] REJECTED '{keyword}': download returned image content-type ({content_type})", flush=True)
        return None

    _MAX_BROLL_BYTES = 25 * 1024 * 1024  # 25MB cap — prevents 100MB+ 4K downloads
    with open(dest, "wb") as f:
        total_bytes = 0
        for chunk in dl.iter_content(65536):
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes > _MAX_BROLL_BYTES:
                break

    if total_bytes > _MAX_BROLL_BYTES:
        print(f"[broll] SKIPPED '{keyword}': file too large ({total_bytes / 1024 / 1024:.1f}MB > 25MB cap)", flush=True)
        try:
            os.remove(dest)
        except OSError:
            pass
        return None

    print(f"[broll] Downloaded '{keyword}': {total_bytes / 1024:.0f}KB -> {dest}", flush=True)

    # ── Validate downloaded clip ──────────────────────────────────────────
    probe_data = _probe_full(dest)

    video_stream = None
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        print(f"[broll] REJECTED '{keyword}': no video stream found", flush=True)
        os.remove(dest)
        return None

    stream_w = int(video_stream.get("width", 0) or 0)
    stream_h = int(video_stream.get("height", 0) or 0)
    codec_name = video_stream.get("codec_name", "unknown")
    fmt_duration = float(probe_data.get("format", {}).get("duration", 0) or 0)

    if fmt_duration < 1.0:
        print(f"[broll] REJECTED '{keyword}': too short ({fmt_duration:.1f}s)", flush=True)
        os.remove(dest)
        return None

    # Skip frame decode + motion check — Pexels videos are trusted, and these checks
    # cost ~1s each (2 FFmpeg decodes per clip). Metadata validation is sufficient.

    if stream_h <= stream_w:
        print(f"[broll] REJECTED '{keyword}': landscape orientation ({stream_w}x{stream_h})", flush=True)
        os.remove(dest)
        return None

    print(
        f"[broll] VALIDATED '{keyword}': {stream_w}x{stream_h} ({codec_name}), "
        f"{fmt_duration:.1f}s",
        flush=True,
    )
    return dest


def get_video_duration(path):
    """Get duration of a video file in seconds."""
    return probe_duration(path) or 0.0


_KB_DIRECTIONS = [
    "zoom_in", "zoom_out", "pan_right", "pan_left",
    "zoom_in_pan_right", "zoom_in_pan_left",
    "zoom_out_pan_right", "zoom_out_pan_left",
    "pan_up", "pan_down",
]


def _kb_crop_exprs(direction, kb_smooth, extra_px_w, extra_px_h):
    """Return (crop_x, crop_y) FFmpeg expressions for a Ken Burns direction.

    All expressions use escaped commas (\\,) for FFmpeg filter_complex safety.
    """
    # Center offsets for zoom-only directions
    _half_w = extra_px_w / 2
    _half_h = extra_px_h / 2

    if direction == "zoom_in":
        cx = f"'max(0\\,min({_half_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_out":
        cx = f"'max(0\\,min({_half_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,(ih-1920)/2)'"
    elif direction == "pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,(ih-1920)/2)'"
    elif direction == "pan_up":
        cx = f"'max(0\\,(iw-1080)/2)'"
        cy = f"'max(0\\,min({extra_px_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "pan_down":
        cx = f"'max(0\\,(iw-1080)/2)'"
        cy = f"'max(0\\,min({extra_px_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_in_pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_in_pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_out_pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "zoom_out_pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    else:
        # Fallback: gentle zoom in
        cx = f"'max(0\\,min({_half_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    return cx, cy

TRANSITION_DURATION_DEFAULT = 0.3

def get_transition_duration(pacing=None):
    """Adaptive transition duration based on video pacing.
    Fast pacing = snappy transitions (0.2s), slow = smoother (0.4s)."""
    if pacing == "fast":
        return 0.2
    elif pacing == "slow":
        return 0.4
    return TRANSITION_DURATION_DEFAULT


# ── Probe cache — eliminates redundant ffprobe calls on the same file ─────────
# One comprehensive ffprobe call returns streams + format; subsequent queries
# for duration, sample_rate, resolution, etc. pull from the cached result.
_probe_cache = {}  # path → {"streams": [...], "format": {...}}


def _probe_full(file_path):
    """Run a single comprehensive ffprobe and cache the result."""
    if file_path in _probe_cache:
        return _probe_cache[file_path]
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", file_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {file_path}: {(result.stderr or '')[-300:]}")
    try:
        data = json.loads(result.stdout or "{}")
    except Exception as e:
        raise RuntimeError(f"ffprobe returned invalid JSON for {file_path}: {e}") from e
    if not data.get("streams") and not data.get("format"):
        raise RuntimeError(f"ffprobe returned empty data for {file_path}")
    _probe_cache[file_path] = data
    return data


def probe_cache_clear(file_path=None):
    """Clear cache for a specific file (after re-encode) or all files."""
    if file_path:
        _probe_cache.pop(file_path, None)
    else:
        _probe_cache.clear()


def probe_duration(file_path):
    data = _probe_full(file_path)
    # Try format duration first, then video stream duration
    try:
        d = float((data.get("format") or {}).get("duration") or 0)
        if d > 0:
            return d
    except Exception:
        pass
    for s in (data.get("streams") or []):
        try:
            d = float(s.get("duration") or 0)
            if d > 0:
                return d
        except Exception:
            continue
    return None


def probe_audio_sample_rate(file_path):
    data = _probe_full(file_path)
    for s in (data.get("streams") or []):
        if s.get("codec_type") == "audio":
            try:
                sr = int(s.get("sample_rate") or 0)
                return sr if sr > 0 else None
            except Exception:
                pass
    return None


def validate_output(path, step_name, min_size_bytes=100000):
    """Check that output file exists and is not empty/corrupt. Returns True if valid."""
    if not os.path.exists(path):
        print(f"[{step_name}] OUTPUT MISSING: {path} does not exist", flush=True)
        return False
    size = os.path.getsize(path)
    if size < min_size_bytes:
        print(f"[{step_name}] OUTPUT TOO SMALL: {path} is {size} bytes (expected >{min_size_bytes})", flush=True)
        return False
    dur = probe_duration(path)
    if not dur or dur < 1.0:
        print(f"[{step_name}] OUTPUT INVALID: duration={dur}s", flush=True)
        return False
    print(f"[{step_name}] Output valid: {size / 1024 / 1024:.1f}MB, {dur:.1f}s", flush=True)
    return True


def probe_resolution(file_path):
    data = _probe_full(file_path)
    for s in (data.get("streams") or []):
        if s.get("codec_type") == "video":
            return {"width": s.get("width") or 1080, "height": s.get("height") or 1920}
    return {"width": 1080, "height": 1920}


def run_ffmpeg(args):
    print(f"[ffmpeg] Running: ffmpeg {' '.join(str(a) for a in args[:10])}...", flush=True)
    t = time.time()
    result = subprocess.run(
        ["ffmpeg", "-v", "warning", "-stats", "-threads", "0", "-benchmark"] + [str(a) for a in args],
        capture_output=True, text=True, timeout=300,
    )
    elapsed = time.time() - t
    if result.returncode != 0:
        print(f"[ffmpeg] FAILED after {elapsed:.1f}s (exit code {result.returncode})", flush=True)
        _stderr = result.stderr or ""
        # Extract error/warning lines (skip progress and build config)
        _err_lines = [ln for ln in _stderr.split("\n")
                      if any(k in ln.lower() for k in ("error", "invalid", "failed", "cannot", "no such", "warning"))]
        if _err_lines:
            print(f"[ffmpeg] errors/warnings:\n" + "\n".join(_err_lines[:30]), flush=True)
        print(f"[ffmpeg] stderr (last 1500):\n{_stderr[-1500:]}", flush=True)
        raise RuntimeError(f"FFmpeg failed: {_stderr[-500:]}")
    # Print benchmark/stats lines from stderr for timing diagnostics
    _stderr = result.stderr or ""
    for _line in _stderr.split("\n"):
        _ll = _line.strip()
        if _ll and ("bench" in _ll.lower() or "speed=" in _ll or "time=" in _ll):
            print(f"[ffmpeg] {_ll}", flush=True)
    print(f"[ffmpeg] Completed in {elapsed:.1f}s", flush=True)
    return result


def analyze_source_video(source_path):
    """Analyze source video and return metadata + scale/crop filter for the main render.

    Instead of re-encoding the entire source into a normalized intermediate,
    this returns the FFmpeg filter string that each segment's v_chain should
    prepend to fold scale/crop/fps conversion into the single render pass.
    Saves an entire encode/decode cycle (3-10s depending on source length).

    Returns dict with keys:
        source_path: str — unchanged original path
        width: int, height: int — original dimensions
        fps: float — original fps
        normalize_vf: str or None — filter to prepend (None if already 1080x1920@30fps)
    """
    info = _probe_full(source_path)
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("No video stream found in source")

    w = int(video.get("width") or 0)
    h = int(video.get("height") or 0)
    if w > h:
        print(f"[analyze] Landscape input ({w}x{h}) — will center-crop to 9:16 in render", flush=True)

    fps_str = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0

    r_fps_str = video.get("r_frame_rate") or "30/1"
    try:
        rn, rd = r_fps_str.split("/")
        r_fps = float(rn) / float(rd)
    except Exception:
        r_fps = fps

    is_vfr = abs(fps - r_fps) > 0.5
    needs_scale_crop = (w != 1080 or h != 1920)

    if not needs_scale_crop:
        # fps/VFR conversion is handled by fps=30 filter in render v_chain — no normalize_vf needed
        if abs(fps - 30) > 1 or is_vfr:
            print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps (VFR={is_vfr}) — fps=30 filter handles it", flush=True)
        else:
            print(f"[analyze] Source is already {w}x{h} @ {fps:.2f}fps — no normalize needed", flush=True)
        return {"source_path": source_path, "width": w, "height": h, "fps": fps, "normalize_vf": None,
                "crop_x": 0, "crop_y": 0, "crop_w": 1080, "crop_h": 1920}

    print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps — will normalize in render pass", flush=True)

    # Build the scale/crop filter that will be prepended to each segment's v_chain.
    # Also store transform params so face positions can be mapped to 1080x1920 space.
    #
    # Two coordinate systems:
    #   - "raw": the original source frame pixels
    #   - "output": 1080x1920 after normalize_vf
    #
    # For reframe (face-aware crop): crop in raw space, then scale to 1080x1920
    #   → transform: new_cx = (raw_cx - crop_x) * (1080 / crop_w)
    #
    # For center crop (scale first, then crop): scale to fit, crop center
    #   → transform: new_cx = raw_cx * scale - crop_offset_in_scaled_space

    normalize_vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    # Default transform: identity (raw == output)
    _face_transform = {"mode": "identity"}

    if w != 1080 or h != 1920:
        # Compute what "force_original_aspect_ratio=increase" does:
        # Scale so the SMALLER dimension fills the target → then crop the overflow
        scale_x = 1080.0 / w
        scale_y = 1920.0 / h
        scale = max(scale_x, scale_y)  # increase = use the larger scale factor
        scaled_w = round(w * scale)
        scaled_h = round(h * scale)
        # Default center crop offset (in post-scale space)
        _center_crop_x = (scaled_w - 1080) // 2
        _center_crop_y = (scaled_h - 1920) // 2

        # Default transform for center-crop path
        _face_transform = {
            "mode": "scale_then_crop",
            "scale": scale,
            "crop_x": _center_crop_x,
            "crop_y": _center_crop_y,
        }

        source_duration = probe_duration(source_path) or 0.0
        _sample_ts = [round(source_duration * f, 3) for f in (0.2, 0.5, 0.8)] if source_duration > 1 else []
        _sparse_faces = detect_face_positions(source_path, _sample_ts) if _sample_ts else []
        reframe_crops = calculate_reframe_crop(_sparse_faces, w, h)
        if reframe_crops:
            avg_crops = [c for c in reframe_crops if c.get("found")] or reframe_crops
            avg_x = int(sum(c["crop_x"] for c in avg_crops) / len(avg_crops))
            avg_y = int(sum(c["crop_y"] for c in avg_crops) / len(avg_crops))
            crop_w = int(reframe_crops[0]["crop_w"])
            crop_h = int(reframe_crops[0]["crop_h"])
            normalize_vf = f"crop={crop_w}:{crop_h}:{avg_x}:{avg_y},scale=1080:1920,setsar=1"
            _face_transform = {
                "mode": "crop_then_scale",
                "crop_x": avg_x, "crop_y": avg_y,
                "crop_w": crop_w, "crop_h": crop_h,
            }
            print(f"[reframe] Static reframe: crop={crop_w}x{crop_h}@({avg_x},{avg_y})", flush=True)
        else:
            print("[reframe] No face found — using center crop", flush=True)

    return {
        "source_path": source_path, "width": w, "height": h, "fps": fps,
        "normalize_vf": normalize_vf,
        "face_transform": _face_transform,
    }




def get_atempo_filter(speed):
    """Build an atempo filter chain for arbitrary positive speed values."""
    safe = max(0.01, float(speed) or 1.0)
    parts = []
    remaining = safe
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def get_pitch_preserving_speed_filter(speed: float) -> str:
    """Return FFmpeg audio filter for speed change WITHOUT pitch shift.

    Preferred: rubberband (best quality, preserves formants).
    Fallback: atempo chain (always available, good quality).
    Returns empty string if speed is ~1.0x (no filter needed).
    """
    if abs(speed - 1.0) < 0.001:
        return ""
    if _HAS_FFMPEG_RUBBERBAND:
        return f"rubberband=tempo={speed:.4f}:pitch=1.0"
    return get_atempo_filter(speed)


def densify_speed_curve(speed_curve, max_intermediates=50, min_step=0.10):
    """Insert linearly-interpolated intermediate keypoints between Gemini's
    keypoints so the speed curve becomes a perceptually smooth ramp instead
    of discrete jumps.

    BUDGETED proportional allocation: a global cap of max_intermediates
    intermediate keypoints is distributed across all the ramps in
    proportion to each ramp's speed delta. Steeper ramps get more sub-steps
    (where smoothness matters most), gentler ramps get fewer. Hold sections
    get zero. This guarantees the total sub-clip count is bounded
    independently of how many keypoints Gemini sends, so render time is
    predictable.

    With a budget of 50 across typical 6-9 keypoint Gemini curves, the
    max per-step speed delta lands around 0.05 — at or just under the
    human tempo discrimination threshold. Steep ramps where smoothness
    matters most get the densest allocation; gentle ramps barely need any.

    min_step (100ms) clamps the minimum sub-clip duration so the splitter's
    micro-clip merger doesn't drop sub-clips smaller than 3 frames.

    Returns a new list with the original keypoints plus inserted intermediates.
    """
    if not speed_curve or len(speed_curve) < 2:
        return list(speed_curve or [])

    # First pass: compute each ramp's speed_delta and gap so we can
    # allocate the intermediate budget proportionally.
    ramps = []
    total_delta = 0.0
    for i in range(len(speed_curve) - 1):
        t_a = float(speed_curve[i]["t"])
        s_a = float(speed_curve[i]["speed"])
        t_b = float(speed_curve[i + 1]["t"])
        s_b = float(speed_curve[i + 1]["speed"])
        gap = t_b - t_a
        speed_delta = abs(s_b - s_a)
        is_hold = speed_delta < 0.01
        ramps.append({
            "i": i, "t_a": t_a, "s_a": s_a, "t_b": t_b, "s_b": s_b,
            "gap": gap, "delta": speed_delta, "is_hold": is_hold,
            "n_steps": 1,  # default: no intermediates (just the endpoint)
        })
        if not is_hold:
            total_delta += speed_delta

    # Second pass: allocate budget proportional to each ramp's delta.
    # Each ramp's n_steps is the number of equal sub-slices it gets
    # divided into (so n_steps - 1 intermediate keypoints inserted).
    if total_delta > 0:
        for r in ramps:
            if r["is_hold"]:
                continue
            # Ramp's share of the budget, proportional to its speed delta
            share = (r["delta"] / total_delta) * max_intermediates
            # n_steps = share + 1 (since we add (n_steps - 1) intermediates)
            n_steps = max(12, round(share) + 1)
            # Clamp by min_step so we don't create micro-clips smaller than min_step
            n_steps_time = max(12, int(r["gap"] / min_step))
            r["n_steps"] = min(n_steps, n_steps_time)

    # Third pass: emit the densified curve using smoothstep (ease-in-out)
    # interpolation. Linear interpolation has instant acceleration at ramp
    # boundaries which sounds/looks abrupt. Smoothstep (3t²-2t³) eases in
    # and out so the speed change is gentle at both ends of every ramp.
    densified = [dict(speed_curve[0])]
    for r in ramps:
        n_steps = r["n_steps"]
        if n_steps >= 2:
            for k in range(1, n_steps):
                frac = k / n_steps
                # Smoothstep: 3t² - 2t³ (ease-in-out)
                smooth_frac = frac * frac * (3.0 - 2.0 * frac)
                t_new = r["t_a"] + frac * r["gap"]  # time stays linear
                s_new = r["s_a"] + (r["s_b"] - r["s_a"]) * smooth_frac
                densified.append({"t": round(t_new, 3), "speed": round(s_new, 4)})
        densified.append(dict(speed_curve[r["i"] + 1]))

    return densified


def get_speed_for_timestamp(t, speed_curve):
    """Return the speed in effect at time t.

    Speed keypoints are HOLD-and-snap: a keypoint at time T with speed S
    means "from T onward, play at speed S, until the next keypoint takes
    effect." This matches the Gemini prompt's stated intent ("place each
    keypoint at the MOMENT the speed should change") and the user's
    mental model of speed ramping.

    Previously this function smoothstep-interpolated between adjacent
    keypoints, which produced speed values in the MIDDLE of a ramp that
    averaged toward 1.0 — meaning a clip whose start time fell between
    two keypoints would play at near-normal speed regardless of what
    Gemini set on either side.
    """
    if not speed_curve or speed_curve == "none":
        return 1.0
    if not isinstance(speed_curve, list) or len(speed_curve) == 0:
        return 1.0
    if t < float(speed_curve[0]["t"]):
        return float(speed_curve[0]["speed"])
    # Walk forward and return the speed of the most recent keypoint at or
    # before t. Keypoints are sorted by time at parse time.
    current = float(speed_curve[0]["speed"])
    for kp in speed_curve:
        if float(kp["t"]) <= t:
            current = float(kp["speed"])
        else:
            break
    return current


def project_words_to_output(transcript, cuts, effective_durations, speed_curve=None, transition_duration=None, clip_time_maps=None, removed_word_indices=None, fps=30.0):
    """Project word timestamps from source to output timeline using canonical time maps.

    If removed_word_indices is provided, words at those indices are excluded.
    This is the SAME source of truth used by build_clips_from_words, so the
    caption projection cannot emit fragments of removed words.
    """
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    _removed = removed_word_indices if isinstance(removed_word_indices, (set, frozenset)) else set(removed_word_indices or [])
    clip_ranges = get_output_clip_ranges(cuts, effective_durations, transition_duration=transition_duration)
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        tm = clip_time_maps[i] if clip_time_maps and i < len(clip_time_maps) else None
        for word_idx, w in enumerate(words):
            if word_idx in _removed:
                continue
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            if we <= c_start or ws >= c_end:
                continue
            clamped_s = max(ws, c_start)
            clamped_e = min(we, c_end)
            if tm:
                local_s = _time_map_lookup(tm, clamped_s - c_start)
                local_e = _time_map_lookup(tm, clamped_e - c_start)
            else:
                speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
                local_s = (clamped_s - c_start) / speed
                local_e = (clamped_e - c_start) / speed
            projected.append({
                "start": round((output_cursor + local_s)*1000)/1000,
                "end":   round((output_cursor + local_e)*1000)/1000,
                "word":  w.get("punctuated_word") or w.get("word") or "",
                "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                "speaker": int(w.get("speaker", 0) or 0),
                "_source_start": max(ws, c_start),
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        # Snap cursor to frame boundaries so word timestamps live on the
        # SAME quantized timeline as Remotion's frame ranges and FFmpeg's
        # segment durations. Without this, raw float accumulation drifts
        # from the integer-frame accumulation over 100+ segments.
        output_cursor = round((output_cursor + dur) * fps) / fps

    projected = [w for w in projected if w["end"] > w["start"]]
    return projected

def prepare_remotion_input(
    words, caption_style, output_res, caption_keywords, work_dir,
    total_duration=0.0, fps=30, cuts=None, emphasis_moments=None, vibe="",
):
    """Build Remotion input JSON for caption overlay rendering. Returns input_json_path."""
    w = output_res.get("width") or 1080
    h = output_res.get("height") or 1920

    cut_points = []
    if cuts:
        cursor = 0.0
        for c in cuts:
            dur = float(c.get("_effective_duration") or c.get("duration") or 0)
            if cursor > 0:
                cut_points.append({
                    "time": round(cursor, 3),
                    "transition": str(c.get("transition_out") or "none"),
                    "duration": round(dur, 3),
                })
            cursor += dur

    em_list = []
    if emphasis_moments:
        for em in emphasis_moments:
            _em_entry = {
                "t": float(em.get("t") or 0),
                "type": str(em.get("type") or "statement"),
                "intensity": str(em.get("intensity") or "medium"),
            }
            if em.get("word"):
                _em_entry["word"] = re.sub(r"[.,!?;:'\"\\]", "", str(em["word"])).strip()
            if em.get("duration"):
                _em_entry["duration"] = float(em["duration"])
            em_list.append(_em_entry)

    input_data = {
        "words": words or [],
        "captionStyle": caption_style,
        "keywords": caption_keywords or [],
        "effects": [],
        "cuts": cut_points,
        "emphasisMoments": em_list,
        "textOverlays": [],  # populated by caller if text overlays exist
        "width": w,
        "height": h,
        "fps": fps,
        "duration": total_duration,
        "fontDir": "/assets/fonts",
        "vibe": vibe,
    }

    input_json_path = os.path.join(work_dir, "remotion_input.json")
    with open(input_json_path, "w") as f:
        json.dump(input_data, f)

    return input_json_path


def render_remotion_pool(input_json_path, segments, num_workers, concurrency_per_worker, gl_mode="angle-egl"):
    """Render N segments using a POOL of long-lived Node workers.

    Each worker runs render-batch.mjs which spawns ONE Chrome browser and renders
    multiple segments using `puppeteerInstance` (shared browser across renderFrames
    calls). This pays Chrome boot N_workers times instead of len(segments) times.

    Per-segment timing showed Chrome boot is ~3-4s per segment (dominates short ramp
    sub-clips). With 47 segments, the old per-segment approach paid ~150-180s of
    cumulative boot work / 10 parallelism = ~15-18s wall on boots alone.

    With this pool: 10 workers × ~3s boot in parallel = ~3s wall on boots. The frame
    rendering itself runs at the same per-segment throughput because each worker
    has its own dedicated Chrome process (multi-process Chrome parallelizes better
    than multi-tab — proven by the failed single-process attempt in commit 15896b0).

    Args:
        input_json_path: shared input JSON for all segments
        segments: list of dicts in original order: [{"frameStart": int, "frameEnd": int,
                  "outputDir": str, "_orig_idx": int}, ...]
        num_workers: how many parallel Node processes (~10, matching the old semaphore)
        concurrency_per_worker: tabs per Chrome browser (~4)
        gl_mode: chromium GL backend

    Returns: list aligned with `segments` (by _orig_idx): [(start_num, count, digits), ...]
    """
    remotion_dir = "/remotion"
    render_batch = os.path.join(remotion_dir, "render-batch.mjs")
    if not os.path.exists(render_batch):
        raise RuntimeError(f"[remotion] render-batch.mjs not found at {render_batch}")

    n_segs = len(segments)
    if n_segs == 0:
        return []

    # Round-robin distribute segments into worker batches. Round-robin ensures
    # long and short segments are interleaved across workers (the segment list
    # has long base clips first then short ramp pieces, so contiguous batching
    # would give one worker all the long ones).
    n_workers = min(num_workers, n_segs)
    batches = [[] for _ in range(n_workers)]
    for i, seg in enumerate(segments):
        batches[i % n_workers].append(seg)

    # Pre-create output dirs (each segment has its own, preserving the existing
    # ffmpeg per-segment dir contract — no shared-dir I/O contention).
    for seg in segments:
        os.makedirs(seg["outputDir"], exist_ok=True)

    # Write per-batch segments.json files
    work_dir = os.path.dirname(input_json_path)
    batch_specs = []
    for batch_idx, batch in enumerate(batches):
        if not batch:
            continue
        batch_path = os.path.join(work_dir, f"remotion_batch_{batch_idx:02d}.json")
        # render-batch.mjs expects only frameStart/frameEnd/outputDir
        with open(batch_path, "w") as f:
            json.dump([{"frameStart": s["frameStart"],
                        "frameEnd":   s["frameEnd"],
                        "outputDir":  s["outputDir"]} for s in batch], f)
        batch_specs.append((batch_idx, batch, batch_path))

    print(f"[remotion-pool] Launching {len(batch_specs)} workers ({concurrency_per_worker} tabs each) "
          f"for {n_segs} segments", flush=True)

    # Launch all worker processes in parallel
    procs = []
    for batch_idx, batch, batch_path in batch_specs:
        cmd = [
            "node", render_batch,
            "--input", input_json_path,
            "--segments", batch_path,
            "--concurrency", str(concurrency_per_worker),
            "--gl", gl_mode,
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=remotion_dir, start_new_session=True,
        )
        _overlay_chunk_procs.append(proc)
        procs.append((batch_idx, batch, proc))

    # Wait for all workers in parallel and collect output
    _total_frames = sum(s["frameEnd"] - s["frameStart"] + 1 for s in segments)
    _timeout = max(180, _total_frames * 0.3)
    failures = []
    for batch_idx, batch, proc in procs:
        try:
            stdout, stderr = proc.communicate(timeout=_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            failures.append(f"worker {batch_idx} timed out after {_timeout:.0f}s")
            continue
        if proc.returncode != 0:
            _err = (stdout or "") + "\n" + (stderr or "")
            failures.append(f"worker {batch_idx} failed (rc={proc.returncode}): {_err[-500:]}")
            continue
        # Print only the final summary line from each worker
        if stdout:
            for _line in stdout.strip().split("\n"):
                if "All " in _line and "rendered in" in _line:
                    print(f"[remotion-pool] worker {batch_idx}: {_line.strip()}", flush=True)

    if failures:
        raise RuntimeError("[remotion-pool] " + " | ".join(failures))

    # Collect per-segment PNG metadata (start_num, count, digits) in original order
    results = [None] * n_segs
    for seg in segments:
        _odir = seg["outputDir"]
        _orig_idx = seg["_orig_idx"]
        _pngs = sorted(glob.glob(os.path.join(_odir, "element-*.png")))
        if not _pngs:
            raise RuntimeError(f"[remotion-pool] No PNGs found in {_odir} (frames {seg['frameStart']}-{seg['frameEnd']})")
        _first = os.path.basename(_pngs[0])
        _num_part = _first.split("-")[1].split(".")[0]
        results[_orig_idx] = (int(_num_part), len(_pngs), len(_num_part))
    return results


def get_output_clip_ranges(cuts, effective_durations, transition_duration=None):
    """
    Return list of {"start": float, "end": float} for each clip's position
    in the output timeline.

    The actual ffmpeg pipeline concatenates segments with `-f concat -c copy`
    (stream copy), which does NOT cross-fade. Transitions are decomposed into
    per-segment fade-in/fade-out *within* each segment — they consume time
    inside the segment but the segment's total playback duration is unchanged.
    Therefore the cursor must advance by the FULL effective duration with no
    overlap subtraction. Subtracting overlap was the bug that caused captions
    and SFX to drift earlier by (n_transitions × transition_duration).

    The transition_duration parameter is kept for API compatibility but is
    intentionally unused.
    """
    _ = transition_duration  # intentionally unused — see docstring
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = cursor
        end   = cursor + dur
        ranges.append({"start": start, "end": end})
        cursor = end
    return ranges


FILLER_WORDS = {"uh", "um", "uh,", "um,", "hmm", "hmm,", "uhh", "umm", "er", "ah"}


def _is_stutter(current_word, next_word):
    """Detect clear false-start patterns that should be removed."""
    if not next_word:
        return False

    curr = str(current_word or "").strip().lower().rstrip(".,!?;:'\"")
    nxt = str(next_word or "").strip().lower().rstrip(".,!?;:'\"")

    if not curr or not nxt:
        return False

    # Exact repetition: "I I", "the the"
    if curr == nxt:
        return True

    # Prefix/false start: "shou" before "shouldn't", "wh" before "what"
    if len(curr) >= 2 and nxt.startswith(curr) and len(nxt) > len(curr):
        return True

    # Contraction false start: "do" before "don't"
    if curr + "n't" == nxt or curr + "nt" == nxt:
        return True

    # Hyphenated/truncated word (Deepgram sometimes returns "wh-" or "th-")
    if curr.endswith("-") and len(curr) >= 2:
        return True

    return False


def build_clips_from_words(deepgram_words, remove_words, max_silence_gap=0.15, video_duration=0.0):
    """
    Deterministic, CapCut-quality clip builder.

    Pipeline:
      1. Apply Gemini's remove_words (word indices + time ranges)
      2. Deterministic filler removal (ALWAYS_FILLER, CONTEXT_FILLER, MULTI_WORD_FILLER)
      3. Stutter/repeat detection and removal
      4. Build clips from kept words, collapsing dead air
      5. Add audio padding so cuts never clip consonants
      6. Merge micro-clips (< 120ms) into neighbors
      7. Fix overlaps between adjacent clips
      8. Final safety: expand any boundary that lands mid-word

    video_duration (when > 0) clamps every word's end timestamp so that
    no clip ever requests source frames past the actual end of the video.
    Without this, ffmpeg silently produces a shorter segment than predicted
    when the last word's Deepgram-reported end exceeds the actual video
    length, causing a downstream timeline mismatch.
    """
    if not deepgram_words:
        return []

    _vd = float(video_duration or 0.0)

    # ── Step 0: Prepare sorted word list with metadata ────────────────────
    def _clamp_end(_v):
        if _vd > 0 and _v > _vd:
            return _vd
        return _v

    sorted_words = sorted(
        [
            {
                **w,
                "_word_index": i,
                "_start": float(w.get("start") or 0.0),
                "_end": _clamp_end(float(w.get("end") or 0.0)),
                "_text": str(w.get("punctuated_word") or w.get("word") or "").strip(),
                "_clean": re.sub(r"[^a-z']", "", str(w.get("word") or w.get("punctuated_word") or "").strip().lower()),
            }
            for i, w in enumerate(deepgram_words)
        ],
        key=lambda w: w["_start"],
    )
    # Drop any word whose start is past video_duration entirely (rare edge case)
    if _vd > 0:
        sorted_words = [w for w in sorted_words if w["_start"] < _vd and w["_end"] > w["_start"]]

    removed_indices = set()

    # ── Step 1: Apply Gemini's remove_words ───────────────────────────────
    # Gemini's word removal decisions are trusted. No code-side validation
    # or rejection of filler calls — if Gemini says a word is filler, it is.
    # If filler detection is wrong, the fix is the prompt, not code heuristics.
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item:
            try:
                idx = int(item["word_index"])
            except Exception:
                continue
            if not (0 <= idx < len(sorted_words)):
                continue
            removed_indices.add(idx)

    # ── Step 1b: Time-range removals (section_skip / dead_air / non_speech_gap) ──
    # Gemini can also send {"start": X, "end": Y, "reason": "..."} entries.
    # Originally these were silently ignored (only word_index removed words),
    # but the prompt advertises section_skip and Gemini relies on it.
    #
    # SAFETY: only remove words whose ENTIRE acoustic span [start, end] is
    # FULLY CONTAINED inside the requested range. A word that partially
    # overlaps the boundary is kept. This is the protection that the original
    # silent-ignore was trying to provide — Gemini's slightly-off timestamps
    # cannot accidentally clip content at the edges.
    _range_removed_count = 0
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item:
            continue  # already handled in Step 1
        if "start" not in item or "end" not in item:
            continue
        try:
            _r_start = float(item["start"])
            _r_end = float(item["end"])
        except Exception:
            continue
        if _r_end <= _r_start:
            continue
        _reason = str(item.get("reason") or "range_remove")
        for _w in sorted_words:
            if _w["_word_index"] in removed_indices:
                continue
            # Strict containment: word must be entirely inside the range
            if _w["_start"] >= _r_start and _w["_end"] <= _r_end:
                removed_indices.add(_w["_word_index"])
                _range_removed_count += 1
                print(
                    f"[tighten] Word '{_w['_text']}' at {_w['_start']:.3f}s removed "
                    f"(inside {_reason} range {_r_start:.3f}-{_r_end:.3f}s)",
                    flush=True,
                )
    if _range_removed_count:
        print(f"[tighten] Range removals removed {_range_removed_count} word(s)", flush=True)

    gemini_removed = set(removed_indices)

    # ── Step 2: Deterministic filler word removal ─────────────────────────
    # Build a list of non-Gemini-removed words for context-aware filler detection
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    for idx_in_remaining, w in enumerate(remaining):
        clean = w["_clean"]

        # Always-filler: remove unconditionally — these are never content words
        # ("um", "uh", "er", "ah", "hmm", etc.)
        # Context-dependent fillers ("like", "so", "basically", "you know") are
        # left to Gemini which understands sentence meaning and can decide whether
        # the word is filler or actual content.
        if clean in ALWAYS_FILLER:
            removed_indices.add(w["_word_index"])
            print(
                f"[tighten] Filler '{w['_text']}' at {w['_start']:.3f}s removed (always-filler)",
                flush=True,
            )
            continue

    # ── Step 3: Stutter/repeat detection ──────────────────────────────────
    # Re-build remaining list after filler removal
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    for idx_in_remaining, w in enumerate(remaining):
        if w["_word_index"] in removed_indices:
            continue
        next_w = remaining[idx_in_remaining + 1] if idx_in_remaining + 1 < len(remaining) else None
        if next_w and _is_stutter(w["_clean"], next_w["_clean"]):
            # Different speakers repeating the same word is conversation, not a stutter.
            w_speaker = w.get("speaker", w.get("_speaker"))
            next_speaker = next_w.get("speaker", next_w.get("_speaker"))
            if w_speaker is not None and next_speaker is not None and w_speaker != next_speaker:
                print(
                    f"[tighten] Skipping cross-speaker repeat '{w['_text']}' (speaker {w_speaker}) → "
                    f"'{next_w['_text']}' (speaker {next_speaker})",
                    flush=True,
                )
                continue
            removed_indices.add(w["_word_index"])
            print(
                f"[tighten] Stutter '{w['_text']}' before '{next_w['_text']}' at {w['_start']:.3f}s removed",
                flush=True,
            )

    # ── Step 3b: Phrasal restart detection (N-gram lookahead) ─────────────
    # Catches 2- and 3-word phrasal restarts where the speaker abandons a
    # phrase mid-thought and restarts it. Example:
    #   [141] who  [142] is  [143] I  [144] said  [145] who  [146] is  [147] he?
    # "who is" at 141-142 was abandoned and restarted at 145-146.
    #
    # CRITICAL DISCRIMINATOR: a true restart abandons the first phrase mid-
    # thought. A parallel structure ("what are you gonna do? what are you
    # gonna learn?") COMPLETES the first sentence with sentence-ending
    # punctuation (?, ., !) before the next begins. We reject any match
    # where any word in the gap between the first and second occurrence has
    # sentence-ending punctuation — that signals the first sentence finished.
    #
    # Constraints (tight to avoid false positives):
    #   - phrase length 2 or 3 words
    #   - lookahead window: next 3 word positions only
    #   - time gap between phrases: ≤1.5s
    #   - same speaker
    #   - NO sentence-ending punctuation in the gap words
    _SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]
    _restart_removed = set()
    for idx_in_remaining, w in enumerate(remaining):
        if w["_word_index"] in _restart_removed:
            continue
        for phrase_len in (4, 3, 2):  # try longest first to avoid orphan words
            if idx_in_remaining + phrase_len > len(remaining):
                continue
            phrase_words = remaining[idx_in_remaining : idx_in_remaining + phrase_len]
            if any(pw["_word_index"] in _restart_removed for pw in phrase_words):
                continue
            phrase_text = tuple(pw["_clean"] for pw in phrase_words)
            if not all(phrase_text):
                continue
            # If the LAST word of the candidate phrase already has sentence-
            # ending punctuation, the phrase is a complete thought — not an
            # abandoned restart. Skip.
            _last_phrase_punct = str(phrase_words[-1].get("punctuated_word") or phrase_words[-1].get("_text") or "")
            if _SENTENCE_END_RE.search(_last_phrase_punct):
                continue
            phrase_speaker = phrase_words[0].get("speaker", phrase_words[0].get("_speaker"))
            _matched = False
            # TIGHT lookahead: only check the next 3 positions, not 5
            for scan_idx in range(idx_in_remaining + phrase_len, min(idx_in_remaining + phrase_len + 3, len(remaining))):
                if scan_idx + phrase_len > len(remaining):
                    break
                cand_words = remaining[scan_idx : scan_idx + phrase_len]
                if any(cw["_word_index"] in _restart_removed for cw in cand_words):
                    continue
                cand_text = tuple(cw["_clean"] for cw in cand_words)
                if cand_text != phrase_text:
                    continue
                cand_speaker = cand_words[0].get("speaker", cand_words[0].get("_speaker"))
                if phrase_speaker is not None and cand_speaker is not None and phrase_speaker != cand_speaker:
                    continue
                # TIGHT time gap: ≤1.5s (true restarts are quick)
                _time_gap = cand_words[0]["_start"] - phrase_words[-1]["_end"]
                if _time_gap > 1.5 or _time_gap < 0:
                    continue
                # CRITICAL: reject if any word in the gap has sentence-ending
                # punctuation. That means the first sentence completed and
                # this is parallel structure, not a restart.
                _gap_words = remaining[idx_in_remaining + phrase_len : scan_idx]
                _sentence_completed = False
                for _gw in _gap_words:
                    _gw_punct = str(_gw.get("punctuated_word") or _gw.get("_text") or "")
                    if _SENTENCE_END_RE.search(_gw_punct):
                        _sentence_completed = True
                        break
                if _sentence_completed:
                    continue
                # Validated restart — remove the FIRST occurrence (false start)
                for pw in phrase_words:
                    _restart_removed.add(pw["_word_index"])
                # Also remove orphan fillers in the gap between false start and
                # restart. Example: "calling me, like, calling me" — once the
                # first "calling me" is removed, "like" becomes an orphan
                # discourse marker dangling between "started" and "calling me".
                # Its grammatical role was to bridge the false start to its
                # restart; with the false start gone, it serves no purpose.
                # We do NOT apply the pause-bracket validator here because the
                # word is provably orphaned by structural evidence (between a
                # confirmed false start and its restart). Meaningful conjunctions
                # like "but", "and", "however" are not in either filler set,
                # so they're kept.
                for _gw in _gap_words:
                    _gw_clean = _gw["_clean"]
                    if _gw_clean in ALWAYS_FILLER or _gw_clean in CONTEXT_FILLER:
                        _restart_removed.add(_gw["_word_index"])
                        print(
                            f"[tighten] Orphan filler '{_gw['_text']}' at "
                            f"{_gw['_start']:.3f}s removed "
                            f"(gap between false start and restart)",
                            flush=True,
                        )
                print(
                    f"[tighten] Phrasal restart '{' '.join(phrase_text)}' at "
                    f"{phrase_words[0]['_start']:.3f}s removed "
                    f"(repeats at {cand_words[0]['_start']:.3f}s, gap={_time_gap*1000:.0f}ms)",
                    flush=True,
                )
                _matched = True
                break
            if _matched:
                break  # don't also try shorter phrase length at this position
    removed_indices |= _restart_removed

    deterministic_removed = removed_indices - gemini_removed

    # ── Step 4: Build clips from kept words ───────────────────────────────
    kept_words = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    if not kept_words:
        return []

    # The split threshold: if the gap between two kept words exceeds this,
    # we create a new clip. This collapses dead air while preserving natural
    # sentence rhythm.
    NATURAL_PAUSE = max_silence_gap  # 150ms — preserves natural breath pauses, splits on real dead air

    clips = []
    current_words = [kept_words[0]]

    for prev, curr in zip(kept_words, kept_words[1:]):
        gap = curr["_start"] - prev["_end"]

        # If any removed word exists between these two kept words, we MUST
        # split here. Otherwise the clip's audio range spans the removed
        # word and its audio bleeds through (e.g. "shou-" before "shouldn't").
        # This also fixes captions: the removed word's timestamps fall
        # outside all clips, so project_words_to_output naturally skips it.
        removed_between = any(
            idx in removed_indices
            for idx in range(prev["_word_index"] + 1, curr["_word_index"])
        )

        if gap > NATURAL_PAUSE or removed_between:
            clips.append(current_words)
            current_words = [curr]
        else:
            current_words.append(curr)

    if current_words:
        clips.append(current_words)

    # ── Step 5: Build raw clips at exact word boundaries ──────────────────
    # No padding. Cuts land at Deepgram's word.start and word.end exactly.
    # The render pipeline (PCM-audio segments + AAC-once final encode) is
    # sample-accurate, so the boundary in the rendered video matches the
    # boundary we ask for here. Previously we added 15ms / 60ms padding to
    # mask AAC priming-delay artifacts (~21ms per segment) that bled into
    # boundaries when AAC segments were stream-copy concatenated. With PCM
    # intermediates that mechanism no longer exists, so the padding is gone.
    raw_clips = []
    for word_group in clips:
        first_start = word_group[0]["_start"]
        last_end = word_group[-1]["_end"]

        raw_clips.append({
            "raw_start": first_start,
            "raw_end": last_end,
            "padded_start": first_start,
            "padded_end": last_end,
            "first_word": word_group[0]["_text"],
            "last_word": word_group[-1]["_text"],
            "word_count": len(word_group),
        })

    # ── Step 6: Merge micro-clips into neighbors ──────────────────────────
    # Any clip shorter than 120ms is too small to be a standalone segment.
    # Merge it into the nearest neighbor — but ONLY if no removed words
    # exist in the gap, otherwise we'd re-introduce audio bleed.
    MIN_CLIP_DURATION = 0.120
    merged = []
    for clip in raw_clips:
        dur = clip["padded_end"] - clip["padded_start"]
        if dur < MIN_CLIP_DURATION and merged:
            gap_start = merged[-1]["raw_end"]
            gap_end = clip["raw_start"]
            has_removed_in_gap = any(
                w["_word_index"] in removed_indices
                and w["_end"] > gap_start and w["_start"] < gap_end
                for w in sorted_words
            )
            if has_removed_in_gap:
                # Can't merge — removed word in the gap. Keep as separate clip.
                merged.append(clip)
            else:
                merged[-1]["padded_end"] = clip["padded_end"]
                merged[-1]["raw_end"] = clip["raw_end"]
                merged[-1]["last_word"] = clip["last_word"]
                merged[-1]["word_count"] += clip["word_count"]
        else:
            merged.append(clip)
    raw_clips = merged

    # ── Step 7: Fix overlaps — earlier clip wins ──────────────────────────
    for i in range(1, len(raw_clips)):
        if raw_clips[i]["padded_start"] < raw_clips[i - 1]["padded_end"]:
            # Place the boundary at the midpoint of the gap between the
            # last word of clip i-1 and the first word of clip i
            mid = (raw_clips[i - 1]["raw_end"] + raw_clips[i]["raw_start"]) / 2
            raw_clips[i - 1]["padded_end"] = round(mid * 1000) / 1000
            raw_clips[i]["padded_start"] = round(mid * 1000) / 1000

    # ── Build final clip dicts ────────────────────────────────────────────
    final_clips = []
    for rc in raw_clips:
        s = round(rc["padded_start"] * 1000) / 1000
        e = round(rc["padded_end"] * 1000) / 1000
        # Final clamp: padding may have pushed end past video_duration
        if _vd > 0 and e > _vd:
            e = round(_vd * 1000) / 1000
        if e - s < 0.05:
            continue
        final_clips.append({
            "source_start": s,
            "source_end": e,
            "transition_out": "none",
            "transition_sound": "none",
            "sfx_style": "none",
            "zoom": "none",
            "cut_zoom": False,
            "speed": 1.0,
            "freeze_frame": False,
        })

    # ── Summary ───────────────────────────────────────────────────────────
    total_kept = len(kept_words)
    total_words = len(sorted_words)
    total_gemini = len(gemini_removed)
    total_det = len(deterministic_removed)
    total_source = sum(c["source_end"] - c["source_start"] for c in final_clips)

    # Log every removed word so we can audit exactly what was cut
    all_removed = sorted(removed_indices)
    if all_removed:
        print(f"[tighten] REMOVED WORDS ({len(all_removed)}):", flush=True)
        for idx in all_removed:
            w = sorted_words[idx]
            source = "gemini" if idx in gemini_removed else "deterministic"
            print(f"[tighten]   [{idx}] '{w['_text']}' @ {w['_start']:.3f}s ({source})", flush=True)

    print(
        f"[tighten] {total_words} words → {total_kept} kept, "
        f"{total_gemini} Gemini removals + {total_det} deterministic removals, "
        f"{len(final_clips)} clips, {total_source:.2f}s output",
        flush=True,
    )

    # Return clips AND the set of removed word indices so downstream consumers
    # (caption projection, SFX word-snapping) can use the SAME source of truth
    # as the cut builder. Without this, the caption projection iterates the
    # full Deepgram transcript and emits fragments of removed words.
    return final_clips, set(removed_indices)


def build_clip_time_map(clip_start, clip_end, clip_speed, speed_curve, fps=30):
    """Build a canonical per-frame time map for one clip.

    This is the SINGLE SOURCE OF TRUTH for the time mapping. All systems
    (FFmpeg setpts, caption projection, SFX/B-roll projection) derive their
    timing from this same table, eliminating drift between systems.

    Uses trapezoidal integration at 1 sample per frame for sub-frame accuracy.

    Returns dict with:
        output_times: list of output times (seconds) at each source frame boundary [0..n_frames]
        effective_duration: total output duration (= output_times[-1])
        avg_speed: average speed (for audio, which must be constant)
        n_frames: number of source frames
        source_dur: source duration in seconds
    """
    source_dur = clip_end - clip_start
    if source_dur <= 0.001:
        return {"output_times": [0.0, max(source_dur, 0.001)], "effective_duration": max(source_dur, 0.001),
                "avg_speed": clip_speed, "n_frames": 1, "source_dur": source_dur}

    has_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
    n_frames = max(1, round(source_dur * fps))

    # Use the speed at clip start — after splitting at keypoints, each sub-clip
    # starts at a keypoint, so this IS the speed Gemini intended for this section.
    # No averaging, no integration. 1.3x means 1.3x, 0.75x means 0.75x.
    curve_speed = max(0.25, min(2.0, get_speed_for_timestamp(clip_start, speed_curve))) if has_curve else 1.0
    speed = max(0.25, min(4.0, clip_speed * curve_speed))

    # Compute effective_duration from the frame-quantized source duration,
    # not the raw float. FFmpeg outputs exactly n_frames frames (each segment
    # is decoded to n_frames source frames, then setpts relabels them).
    # The actual encoded duration is n_frames / (fps * speed). Using
    # source_dur / speed instead diverges by up to 16ms per segment, which
    # accumulates to ~1s over 70+ micro-segments — causing b-roll to appear
    # late and enable gates to misalign (flashing).
    eff_dur = n_frames / (fps * speed)

    # Build simple linear output_times for consistency with _time_map_lookup
    dt = n_frames / fps  # frame-quantized source duration
    output_times = [k * (dt / n_frames) / speed for k in range(n_frames + 1)]

    return {
        "output_times": output_times,
        "effective_duration": eff_dur,
        "avg_speed": speed,
        "n_frames": n_frames,
        "source_dur": source_dur,
    }


def split_clips_at_speed_keypoints(cuts, speed_curve):
    """Split clips at speed curve keypoints so each sub-clip has near-constant speed.

    This is the root fix for audio/video sync: when each sub-clip has <5% speed variation,
    constant-average audio matches the video perfectly. The parallel architecture is preserved.

    Returns expanded list of cuts with sub-clips replacing originals.
    """
    if not speed_curve or speed_curve == "none" or not isinstance(speed_curve, list):
        return list(cuts)

    # Split at every keypoint in the speed curve. The speed curve has
    # already been densified at parse time (densify_speed_curve) — Gemini's
    # original keypoints + linearly-interpolated intermediates at ~250ms
    # intervals — so this loop produces enough sub-clips for smooth ramping.
    all_split_times = sorted(set(float(kp["t"]) for kp in speed_curve))
    expanded = []

    for cut in cuts:
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])

        # Find split points that fall strictly inside this clip
        interior = [t for t in all_split_times if src_start + 0.05 < t < src_end - 0.05]

        if not interior:
            expanded.append(dict(cut))
            continue

        boundaries = [src_start] + interior + [src_end]

        for si in range(len(boundaries) - 1):
            sub_start = boundaries[si]
            sub_end = boundaries[si + 1]

            if sub_end - sub_start < 0.001:
                continue  # skip zero-length clips (floating point edge case)

            sub_cut = dict(cut)
            sub_cut["source_start"] = round(sub_start, 3)
            sub_cut["source_end"] = round(sub_end, 3)

            # Only last sub-clip keeps transition_out
            if si < len(boundaries) - 2:
                sub_cut["transition_out"] = "none"

            expanded.append(sub_cut)

    if expanded:
        n_split = len(expanded) - len(cuts)
        if n_split > 0:
            print(f"[speed-split] Split {len(cuts)} clips into {len(expanded)} sub-clips ({len(all_split_times)} split points)", flush=True)

    return expanded


def _time_map_lookup(tm, source_offset):
    """Look up output time from a clip time map given a source offset (seconds from clip start).
    Uses constant avg_speed to exactly match FFmpeg's setpts=(1/avg_speed)*PTS."""
    if source_offset <= 0:
        return 0.0
    avg_speed = tm["avg_speed"]
    return source_offset / avg_speed if avg_speed > 0 else source_offset


def build_setpts_from_time_map(tm, log=False):
    """Generate constant-speed FFmpeg setpts expression from a canonical time map.

    Uses the integrated average speed from the time map. After splitting clips at
    speed keypoints, each sub-clip has near-constant speed, so the constant average
    is accurate. Audio uses the same avg_speed, guaranteeing perfect sync.

    Returns (setpts_value, effective_dur, avg_speed).
    """
    eff_dur = tm["effective_duration"]
    avg_speed = tm["avg_speed"]
    n_frames = tm["n_frames"]

    if n_frames <= 1:
        return None, eff_dur, avg_speed

    # Skip setpts if speed is ~1.0
    if abs(avg_speed - 1.0) < 0.005:
        return None, eff_dur, avg_speed

    # Full float precision (10 decimals) so the audio asetrate and the
    # video setpts agree on the playback rate to sub-microsecond accuracy.
    # Previously :.4f rounded both values independently in opposite
    # directions, producing different effective playback rates that drifted
    # by ~1-10ms per minute of segment.
    setpts_val = f"{1.0/avg_speed:.10f}*PTS"
    if log:
        print(f"[speed] Setpts: avg={avg_speed:.3f}x, eff={eff_dur:.3f}s", flush=True)

    return setpts_val, eff_dur, avg_speed


def project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve=None, clip_time_maps=None):
    """Map a source-timeline timestamp to the output-timeline timestamp.
    Uses canonical time maps for exact alignment with FFmpeg.

    clip_time_maps is REQUIRED — it contains the combined clip_speed *
    curve_speed used by FFmpeg's setpts. Without it, the projection
    would use cut["speed"] (always 1.0 when speed_curve is active),
    ignoring the speed curve entirely and placing b-roll/SFX late.

    When a hook clip duplicates a source range at the start of the timeline,
    multiple cuts can contain the same source timestamp. We prefer the LAST
    (narrative) match so that b-roll, SFX, and emphasis moments land at the
    correct narrative position rather than the hook preview position."""
    if not clip_time_maps:
        raise ValueError("project_source_time_to_output requires clip_time_maps")
    best_output_t = None
    for i, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])

        if src_start <= source_t <= src_end:
            source_offset = source_t - src_start
            local_offset = _time_map_lookup(clip_time_maps[i], source_offset)
            best_output_t = float(clip_ranges[i]["start"]) + local_offset

    if best_output_t is not None:
        return best_output_t

    for i, cut in enumerate(cuts):
        if source_t < float(cut["source_start"]):
            return float(clip_ranges[i]["start"])

    if clip_ranges:
        return float(clip_ranges[-1]["end"]) - 0.1
    return None


def project_source_time_to_final_output(source_t, cuts, effective_durations, speed_curve=None, clip_time_maps=None):
    """Map a source timestamp to the final output timeline after cut compression."""
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    return project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve, clip_time_maps=clip_time_maps)


def build_variable_speed_setpts(clip_start, clip_end, clip_speed, speed_curve, log=False, fps=30):
    """Build speed expression from canonical time map. Wrapper for backward compatibility."""
    tm = build_clip_time_map(clip_start, clip_end, clip_speed, speed_curve, fps=fps)
    setpts_val, eff_dur, avg_speed = build_setpts_from_time_map(tm, log=log)
    return setpts_val, eff_dur, avg_speed


def compute_effective_durations(cuts, speed_curve=None, fps=30):
    """Compute output duration for each clip using canonical time maps."""
    durations = []
    for cut in (cuts or []):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        tm = build_clip_time_map(src_start, src_end, clip_speed, speed_curve, fps=fps)
        durations.append(tm["effective_duration"])
    return durations


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None,
                      broll_clips=None, broll_fetch_futures=None, face_future=None):
    speed_curve = edit_plan.get("_parsed_speed_curve")
    _normalize_vf = edit_plan.get("_normalize_vf")  # scale/crop filter (None if native 1080x1920)
    # Adaptive transition duration based on Gemini pacing assessment
    TRANSITION_DURATION = get_transition_duration(edit_plan.get("pacing"))
    print(f"[render] transition_duration={TRANSITION_DURATION:.2f}s (pacing={edit_plan.get('pacing')})", flush=True)
    original_cuts = list(cuts)
    render_cuts = list(cuts)
    hook_clip = edit_plan.get("hook_clip")
    if isinstance(hook_clip, dict):
        # Hook clips ALWAYS get tight zoom (slow_in) — this is the "grab attention"
        # moment. Research: tight framing + immediate speech = >65% 3-second retention.
        hook_zoom = "slow_in"
        edit_plan["_hook_zoom"] = hook_zoom

        _hook_start = float(hook_clip.get("source_start") or 0.0)
        _hook_end = float(hook_clip.get("source_end") or 0.0)

        # Build hook from NARRATIVE clips that overlap the hook's source range.
        # This guarantees the hook is identical to the narrative: word removals,
        # speed ramping, captions, and effects are all baked in. The old approach
        # rendered one raw-source segment covering the full hook range, which
        # included false starts and dead air that had been removed from the
        # narrative clips.
        _hook_clips = []
        for _nc in render_cuts:
            _nc_start = float(_nc["source_start"])
            _nc_end = float(_nc["source_end"])
            # Check overlap with hook range
            _overlap_start = max(_nc_start, _hook_start)
            _overlap_end = min(_nc_end, _hook_end)
            if _overlap_end - _overlap_start > 0.05:
                _hc = dict(_nc)
                _hc["source_start"] = _overlap_start
                _hc["source_end"] = _overlap_end
                _hc["zoom"] = hook_zoom
                _hc["transition_out"] = "none"
                _hc["freeze_frame"] = False
                _hc["_is_hook"] = True
                _hook_clips.append(_hc)

        if _hook_clips:
            _hook_dur = sum(float(h["source_end"]) - float(h["source_start"]) for h in _hook_clips)
            print(f"[hook] Built hook from {len(_hook_clips)} narrative clip(s) covering {_hook_dur:.2f}s", flush=True)
            render_cuts = _hook_clips + render_cuts
        else:
            print(f"[hook] No narrative clips overlap hook range {_hook_start:.3f}-{_hook_end:.3f} — skipping hook", flush=True)

    # Tag each cut with its pre-split index so text overlays can map back
    # Hook clip(s) get _original_idx = -1; content clips get 0, 1, 2, ...
    _content_idx = 0
    for _rc in render_cuts:
        if _rc.get("_is_hook"):
            _rc["_original_idx"] = -1
        else:
            _rc["_original_idx"] = _content_idx
            _content_idx += 1

    # Clips will be split at speed curve keypoints after this initial setup,
    # ensuring each sub-clip has near-constant speed for audio/video sync.

    n = len(render_cuts)
    source_res = probe_resolution(source_path)
    # Skip keyframe forcing — trim filter works on decoded frames, always frame-accurate
    render_source = source_path
    # Diagnostic probe uses cached data — no extra ffprobe call
    _cached = _probe_full(render_source)
    _vs = next((s for s in (_cached.get("streams") or []) if s.get("codec_type") == "video"), {})
    print(f"[DIAG] Render source: codec={_vs.get('codec_name')} pix_fmt={_vs.get('pix_fmt')} fps={_vs.get('r_frame_rate')}", flush=True)
    # Detect source fps once and propagate as the unified frame rate for the
    # entire render. This eliminates the audio/video/caption drift caused by
    # forcing a 30fps grid on a 29.97fps source. Every fps consumer (the
    # video filter chain's fps= filter, build_clip_time_map, the PNG overlay
    # framerate, and Remotion's caption rendering) uses the SAME value, so
    # there is exactly one timeline and they cannot drift relative to each
    # other.
    _src_fps_str = _vs.get("r_frame_rate") or "30/1"
    try:
        if "/" in _src_fps_str:
            _num, _den = _src_fps_str.split("/")
            source_fps = float(_num) / float(_den)
        else:
            source_fps = float(_src_fps_str)
    except Exception:
        source_fps = 30.0
    if source_fps <= 0 or source_fps > 240:
        source_fps = 30.0
    print(f"[render] Unified source fps: {source_fps:.4f} (raw: {_src_fps_str})", flush=True)
    has_burned_captions = infer_has_burned_captions(
        edit_plan,
        edit_plan.get("analysis_data") or {},
        log_prefix="[render]",
    )

    # Per-segment inputs with -ss/-t pre-seeking to avoid buffering the entire
    # source video in memory (15 [0:v]trim= refs would force FFmpeg to keep all
    # decoded frames until every trim filter has consumed them → OOM on 8GB).
    input_args = []
    sample_rate = probe_audio_sample_rate(source_path) or 48000

    # Shift speed ramps that span removed-content gaps into the tail of the
    # preceding clip. When Gemini places a slow-down ramp (e.g., 1.3→0.75)
    # across dead air, the entire ramp is invisible. The viewer hears a hard
    # step at the clip boundary. Fix: for speed DECREASES across gaps, move
    # the ramp into the last ~0.4s of the preceding clip. The deceleration
    # plays on the final spoken words before the cut — exactly what a human
    # editor would do. Speed INCREASES across gaps need no fix (a hard
    # speed-up at a visual cut is natural).
    if speed_curve and isinstance(speed_curve, list) and len(speed_curve) >= 2 and len(render_cuts) >= 2:
        _ramps_shifted = 0
        for _bi in range(1, len(render_cuts)):
            _prev_start = float(render_cuts[_bi - 1]["source_start"])
            _prev_end = float(render_cuts[_bi - 1]["source_end"])
            _curr_start = float(render_cuts[_bi]["source_start"])
            _gap = _curr_start - _prev_end
            if _gap < 0.05:
                continue
            _speed_at_prev_end = get_speed_for_timestamp(_prev_end, speed_curve)
            _speed_at_curr_start = get_speed_for_timestamp(_curr_start, speed_curve)
            _delta = _speed_at_curr_start - _speed_at_prev_end
            if _delta >= -0.03:
                continue  # speed increase or negligible — skip
            # Speed decrease across gap: shift ramp into preceding clip tail
            _prev_dur = _prev_end - _prev_start
            _ramp_dur = min(0.4, _prev_dur * 0.3)
            if _ramp_dur < 0.08:
                continue  # clip too short for a ramp
            _ramp_start = round(_prev_end - _ramp_dur, 3)
            _target_speed = _speed_at_curr_start
            # Remove existing densified keypoints in the ramp zone so we
            # don't create duplicates or conflicts
            speed_curve = [kp for kp in speed_curve
                           if not (_ramp_start < float(kp["t"]) <= _prev_end)]
            # Insert smoothstep-eased ramp (8 steps)
            _n_steps = 8
            for _si in range(_n_steps + 1):
                _frac = _si / _n_steps
                _smooth = _frac * _frac * (3.0 - 2.0 * _frac)
                _t = _ramp_start + _frac * _ramp_dur
                _s = _speed_at_prev_end + (_target_speed - _speed_at_prev_end) * _smooth
                speed_curve.append({"t": round(_t, 3), "speed": round(_s, 4)})
            _ramps_shifted += 1
        if _ramps_shifted > 0:
            speed_curve.sort(key=lambda x: float(x["t"]))
            print(f"[speed-curve] Shifted {_ramps_shifted} ramp(s) into preceding clip tails ({len(speed_curve)} keypoints)", flush=True)

    # Inject b-roll source timestamps as speed curve keypoints so the splitter
    # creates a segment boundary exactly where each b-roll starts. This ensures
    # b-roll always begins at local_start≈0 (segment beginning), avoiding the
    # FFmpeg overlay bug where PTS-offset b-roll silently fails to render when
    # the offset is >2s into a segment.
    _broll_clips_for_split = edit_plan.get("broll_clips") or []
    if _broll_clips_for_split and speed_curve and isinstance(speed_curve, list):
        _broll_splits_added = 0
        _existing_times = set(float(kp["t"]) for kp in speed_curve)
        for _bc in _broll_clips_for_split:
            _bts = float(_bc.get("timestamp") or 0)
            if _bts > 0 and _bts not in _existing_times:
                _speed_at_bts = get_speed_for_timestamp(_bts, speed_curve)
                speed_curve.append({"t": round(_bts, 3), "speed": round(_speed_at_bts, 4)})
                _existing_times.add(_bts)
                _broll_splits_added += 1
        if _broll_splits_added > 0:
            speed_curve.sort(key=lambda x: float(x["t"]))
            print(f"[speed-curve] Added {_broll_splits_added} b-roll split point(s) ({len(speed_curve)} keypoints)", flush=True)

    # Split clips at speed curve keypoints so each sub-clip has near-constant speed.
    # This is the root fix for audio/video sync — constant-average audio matches video.
    render_cuts = split_clips_at_speed_keypoints(render_cuts, speed_curve)
    n = len(render_cuts)

    # ── Auto-transition assignment (MOVED UPSTREAM) ─────────────────────
    # ROOT FIX: this loop mutates render_cuts[i]["transition_out"] in place.
    # Previously it ran AFTER caption/emphasis projection, so those consumers
    # saw a render_cuts state where transition_out was still "none", but the
    # SFX projection and the actual rendered video saw the post-mutation
    # state where transitions exist. The result was a growing drift between
    # captions and the rendered video equal to (n_transitions * 0.20s).
    #
    # Solution: mutate FIRST, then every downstream consumer sees the same
    # final render_cuts. There is no longer a "before" and "after" state.
    # Auto-transitions are visual breaks between Gemini's narrative clips,
    # not between speed-curve sub-clips. After densification, render_cuts
    # contains many sub-clips per Gemini clip — each sub-clip carries the
    # parent's _original_idx. A "real" clip boundary is a transition from
    # one _original_idx to another. We only consider those positions as
    # candidates for auto-transitions.
    _auto_transitions_added = 0
    _em_all_for_auto = edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or []
    _SUBTLE_TRANSITIONS_AUTO = ["dissolve", "smoothleft", "smoothright", "fade"]
    _real_boundary_idx = 0  # counts only real clip boundaries, for the % 3 pattern
    for _ci in range(1, n):
        _prev_oi = render_cuts[_ci - 1].get("_original_idx", -2)
        _curr_oi = render_cuts[_ci].get("_original_idx", -2)
        if _prev_oi == _curr_oi:
            continue  # sub-clip split inside the same Gemini clip — not a real boundary
        _real_boundary_idx += 1
        _existing = str(render_cuts[_ci - 1].get("transition_out") or "none").lower()
        if _existing != "none" or render_cuts[_ci - 1].get("_is_hook"):
            continue
        _cut_source_end = float(render_cuts[_ci - 1].get("source_end") or 0)
        _near_emphasis = any(abs(float(em.get("t") or 0) - _cut_source_end) < 1.5 for em in _em_all_for_auto)
        # Hard cap of 4 auto-transitions per video — visual variety
        # without becoming busy. Applies to both the emphasis-driven
        # path and the every-3rd-cut pattern.
        if _auto_transitions_added >= 4:
            continue
        if _near_emphasis or (_real_boundary_idx % 3 == 0):
            _auto_t = _SUBTLE_TRANSITIONS_AUTO[_auto_transitions_added % len(_SUBTLE_TRANSITIONS_AUTO)]
            render_cuts[_ci - 1]["transition_out"] = _auto_t
            _auto_transitions_added += 1
    if _auto_transitions_added:
        print(f"[transitions] Auto-assigned {_auto_transitions_added} subtle transition(s)", flush=True)

    # Build canonical time maps — the SINGLE SOURCE OF TRUTH for all timing.
    # Every system (FFmpeg setpts, caption projection, B-roll, SFX) uses these.
    _clip_time_maps = []
    for _rc in render_cuts:
        _tm = build_clip_time_map(
            float(_rc["source_start"]), float(_rc["source_end"]),
            max(0.25, min(4.0, float(_rc.get("speed") or 1.0))), speed_curve,
            fps=source_fps,
        )
        _clip_time_maps.append(_tm)
    # Use raw effective durations — no frame-boundary rounding. With 80+
    # micro-segments from speed curve densification, rounding each duration
    # to 1/30s accumulated ~1.2s of cumulative error by segment 69, causing
    # b-roll overlays to appear ~1.4s late in the rendered video.
    effective_durations = [tm["effective_duration"] for tm in _clip_time_maps]
    # Store render's split cuts and effective_durations so B-roll/SFX projection
    # uses the same timeline as the actual render (not the pre-split approximation)
    edit_plan["_render_cuts"] = render_cuts
    edit_plan["_render_effective_durations"] = effective_durations
    edit_plan["_render_clip_time_maps"] = _clip_time_maps

    _caption_pngs = []
    caption_style = str(edit_plan.get("caption_style") or "none").lower()
    _all_caption_styles = {"volt", "clarity", "impact", "ember", "velocity",
                           "archive", "lumen", "rebel"}

    # Project words to output timeline for captions
    _projected_words = []
    if caption_style != "none" and caption_style in _all_caption_styles and transcript.get("words"):
        _projected_words = project_words_to_output(
            transcript, render_cuts, effective_durations,
            speed_curve=speed_curve,
            transition_duration=TRANSITION_DURATION,
            clip_time_maps=_clip_time_maps,
            removed_word_indices=edit_plan.get("_removed_word_indices") or set(),
            fps=source_fps,
        )
        if _projected_words:
            # Clean curly braces
            for _wd in _projected_words:
                for _k in ("word", "punctuated_word"):
                    if _k in _wd and ("{" in str(_wd[_k]) or "}" in str(_wd[_k])):
                        _wd[_k] = str(_wd[_k]).replace("{", "").replace("}", "")
            # Deduplicate consecutive stutters
            if len(_projected_words) > 1:
                _deduped = [_projected_words[0]]
                for _wi in range(1, len(_projected_words)):
                    _p = re.sub(r"[.,!?;:'\"\\]", "", str(_projected_words[_wi - 1].get("word") or "").lower().strip())
                    _c = re.sub(r"[.,!?;:'\"\\]", "", str(_projected_words[_wi].get("word") or "").lower().strip())
                    if _c and _c == _p:
                        _deduped[-1]["end"] = _projected_words[_wi]["end"]
                        continue
                    _deduped.append(_projected_words[_wi])
                _projected_words = _deduped

    _cap_kw = edit_plan.get("caption_keywords") or []
    # Compute total render duration from per-segment frame counts (not raw sum
    # of effective_durations) so Remotion's durationInFrames exactly matches
    # the total frames requested in _seg_frame_ranges. Without this, rounding
    # each segment's frame count independently can accumulate to more frames
    # than round(total_duration * fps), causing frame range overflow.
    _total_seg_frames = sum(max(1, round(ed * source_fps)) for ed in effective_durations)
    _total_render_dur = _total_seg_frames / source_fps
    _vibe = str(edit_plan.get("_user_vibe") or edit_plan.get("notes") or "")
    _emphasis_moments_raw = edit_plan.get("emphasis_moments") or []

    # Project emphasis moment timestamps from source time → output timeline
    # (Gemini gives source timestamps, but Remotion overlay uses output timeline)
    _clip_ranges_for_em = get_output_clip_ranges(render_cuts, effective_durations, transition_duration=TRANSITION_DURATION)
    _emphasis_moments = []
    for _em in _emphasis_moments_raw:
        _em_copy = dict(_em)
        _src_t = float(_em.get("t") or 0)
        _out_t = project_source_time_to_output(_src_t, render_cuts, _clip_ranges_for_em, speed_curve, clip_time_maps=_clip_time_maps)
        if _out_t is not None:
            _em_copy["t"] = _out_t
            _emphasis_moments.append(_em_copy)
            print(f"[emphasis] Projected {_src_t:.2f}s → {_out_t:.2f}s ({_em.get('type')}/{_em.get('intensity')})", flush=True)

    # Build cut info with effective durations for Remotion effect timing
    _cuts_for_remotion = []
    for _ci, _rc in enumerate(render_cuts):
        _rc_copy = dict(_rc)
        _rc_copy["_effective_duration"] = effective_durations[_ci] if _ci < len(effective_durations) else 0
        _cuts_for_remotion.append(_rc_copy)

    # Prepare Remotion input JSON (shared by all per-segment Remotion renders)
    _remotion_input_json = None
    _captions_enabled = bool(_projected_words and caption_style)
    if _captions_enabled:
        _remotion_input_json = prepare_remotion_input(
            _projected_words, caption_style,
            {"width": 1080, "height": 1920},
            _cap_kw, work_dir,
            total_duration=_total_render_dur, fps=source_fps,
            cuts=_cuts_for_remotion,
            emphasis_moments=_emphasis_moments,
            vibe=_vibe,
        )
        # Inject text overlays into Remotion input so they render as part of
        # the caption PNG sequence — continuous across segments, no flashing.
        text_overlays = edit_plan.get("text_overlays") or []
        if text_overlays and _remotion_input_json:
            # Compute output-time window for each text overlay
            _seg_starts_ov = []
            _cursor_ov = 0.0
            for _si_ov in range(n):
                _seg_starts_ov.append(_cursor_ov)
                _cursor_ov += effective_durations[_si_ov]
            _orig_idx_to_range_ov = {}
            _hook_ci_range_ov = None
            for _ci_ov, _rc_ov in enumerate(render_cuts):
                _oi_ov = _rc_ov.get("_original_idx")
                if _oi_ov is not None and _oi_ov >= 0:
                    if _oi_ov not in _orig_idx_to_range_ov:
                        _orig_idx_to_range_ov[_oi_ov] = (_ci_ov, _ci_ov)
                    else:
                        _orig_idx_to_range_ov[_oi_ov] = (_orig_idx_to_range_ov[_oi_ov][0], _ci_ov)
                elif _oi_ov == -1:
                    if _hook_ci_range_ov is None:
                        _hook_ci_range_ov = (_ci_ov, _ci_ov)
                    else:
                        _hook_ci_range_ov = (_hook_ci_range_ov[0], _ci_ov)
            _remotion_text_overlays = []
            for _ov in text_overlays:
                _gem_idx = int(_ov.get("appear_at_clip") or 0)
                if _gem_idx == -1:
                    _f, _l = _hook_ci_range_ov if _hook_ci_range_ov else (0, 0)
                elif _gem_idx in _orig_idx_to_range_ov:
                    _f, _l = _orig_idx_to_range_ov[_gem_idx]
                else:
                    _valid = sorted(_orig_idx_to_range_ov.keys()) if _orig_idx_to_range_ov else [0]
                    _closest = min(_valid, key=lambda x: abs(x - _gem_idx))
                    _f, _l = _orig_idx_to_range_ov.get(_closest, (0, 0))
                _f = max(0, min(_f, n - 1))
                _l = max(0, min(_l, n - 1))
                _ov_text = _EMOJI_RE.sub("", str(_ov.get("text") or "")).strip()
                if not _ov_text:
                    continue
                _ov_start = _seg_starts_ov[_f]
                _ov_end = _seg_starts_ov[_l] + effective_durations[_l]
                _remotion_text_overlays.append({
                    "text": _ov_text,
                    "start": round(_ov_start, 3),
                    "end": round(_ov_end, 3),
                    "position": str(_ov.get("position") or "top"),
                    "style": str(_ov.get("style") or "callout"),
                })
            if _remotion_text_overlays:
                # Re-write the Remotion JSON with text overlays included
                with open(_remotion_input_json, "r") as _rjf:
                    _rj_data = json.load(_rjf)
                _rj_data["textOverlays"] = _remotion_text_overlays
                with open(_remotion_input_json, "w") as _rjf:
                    json.dump(_rj_data, _rjf)
                print(f"[remotion] Injected {len(_remotion_text_overlays)} text overlay(s) into Remotion input", flush=True)
        print(f"[remotion] Prepared input JSON: {caption_style} ({len(_projected_words)} words), "
              f"{len(_emphasis_moments)} emphasis — will render per-segment", flush=True)
    else:
        print(f"[captions] No captions (style={caption_style}, words={len(_projected_words)})", flush=True)

    for i, cut in enumerate(render_cuts):
        src_dur = round((float(cut["source_end"]) - float(cut["source_start"])) * 1000) / 1000
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        _, _eff, _avg = build_variable_speed_setpts(
            float(cut["source_start"]), float(cut["source_end"]), clip_speed, speed_curve,
            fps=source_fps,
        )
        eff_dur = effective_durations[i]
        print(
            f"[ffmpeg] Segment {i}: {cut['source_start']:.3f}s->{cut['source_end']:.3f}s "
            f"(dur={src_dur:.3f}s, eff={eff_dur:.3f}s @ avg_speed={_avg:.2f}x)",
            flush=True,
        )

    video_filters = []
    audio_filters = []
    # Per-segment data for parallel rendering
    _seg_v_chains = []
    _seg_a_chains = []
    _seg_input_args_list = []
    _seg_speeds = []  # avg speed per segment (for caption PNG framerate matching)

    # Collect face detection results (may still be running from mega-parallel phase).
    # By collecting here (after Remotion launch), face detection runs in parallel with
    # both Remotion AND the Remotion prep — saving ~5s vs collecting before render_multi_clip.
    if face_future is not None:
        _face_t0 = time.time()
        try:
            _face_raw, _face_dense_raw = face_future.result(timeout=60)
        except Exception as _face_err:
            print(f"[faces] Face detection failed: {_face_err} — using defaults", flush=True)
            _face_raw, _face_dense_raw = [], []
        _face_wait = time.time() - _face_t0
        if _face_wait > 0.5:
            print(f"[faces] Waited {_face_wait:.1f}s for face detection (overlapped with Remotion)", flush=True)

        # Transform face positions from raw source → 1080x1920 if needed
        _ft = edit_plan.get("_face_transform") or {}
        _ft_mode = _ft.get("mode", "identity")
        if _ft_mode != "identity" and (_face_raw or _face_dense_raw):
            if _ft_mode == "crop_then_scale":
                _cx_off, _cy_off = _ft["crop_x"], _ft["crop_y"]
                _sx = 1080.0 / _ft["crop_w"] if _ft["crop_w"] > 0 else 1.0
                _sy = 1920.0 / _ft["crop_h"] if _ft["crop_h"] > 0 else 1.0
                _face_raw = [dict(fp, cx=round((fp["cx"] - _cx_off) * _sx, 2), cy=round((fp["cy"] - _cy_off) * _sy, 2)) for fp in _face_raw]
                _face_dense_raw = [dict(fp, cx=round((fp["cx"] - _cx_off) * _sx, 2), cy=round((fp["cy"] - _cy_off) * _sy, 2)) for fp in _face_dense_raw]
            elif _ft_mode == "scale_then_crop":
                _scale, _cx_off, _cy_off = _ft["scale"], _ft["crop_x"], _ft["crop_y"]
                _face_raw = [dict(fp, cx=round(fp["cx"] * _scale - _cx_off, 2), cy=round(fp["cy"] * _scale - _cy_off, 2)) for fp in _face_raw]
                _face_dense_raw = [dict(fp, cx=round(fp["cx"] * _scale - _cx_off, 2), cy=round(fp["cy"] * _scale - _cy_off, 2)) for fp in _face_dense_raw]
            print(f"[faces] Transformed {len(_face_raw)} + {len(_face_dense_raw)} points → 1080x1920 ({_ft_mode})", flush=True)

        edit_plan["_face_positions"] = _face_raw
        edit_plan["_dense_face_trajectory"] = _face_dense_raw

    face_positions = edit_plan.get("_face_positions") or []
    dense_face_trajectory = edit_plan.get("_dense_face_trajectory") or []
    _has_dense_trajectory = len(dense_face_trajectory) > 0
    n_segment_inputs = len(render_cuts)  # each segment gets its own input

    # Precompute per-original-cut metadata so sub-clips from the same
    # parent cut share continuous zoom (no per-subclip reset).
    # _orig_cut_info[orig_idx] = {"total_source_dur": float, "source_start": float}
    # _subclip_frame_offset[i] = frame offset of sub-clip i within its parent cut
    _orig_cut_info = {}
    for _oi, _oc in enumerate(render_cuts):
        _oidx = _oc.get("_original_idx", _oi)
        _oc_dur = float(_oc["source_end"]) - float(_oc["source_start"])
        if _oidx not in _orig_cut_info:
            _orig_cut_info[_oidx] = {"total_source_dur": 0.0, "source_start": float(_oc["source_start"])}
        _orig_cut_info[_oidx]["total_source_dur"] += _oc_dur

    _subclip_frame_offset = []
    _orig_frame_cursor = {}
    for _oi, _oc in enumerate(render_cuts):
        _oidx = _oc.get("_original_idx", _oi)
        _offset = _orig_frame_cursor.get(_oidx, 0)
        _subclip_frame_offset.append(_offset)
        _oc_dur = float(_oc["source_end"]) - float(_oc["source_start"])
        _orig_frame_cursor[_oidx] = _offset + max(1, round(_oc_dur * source_fps))

    for i, cut in enumerate(render_cuts):
        start = float(cut["source_start"])
        end = float(cut["source_end"])
        seg_dur = end - start
        # Each segment is a separate input with pre-seeking.
        # IMPORTANT: NVDEC hwaccel is NOT used here. We have ~30-60 parallel
        # ffmpeg processes, and each NVDEC context init takes ~500-1000ms
        # plus the H100's NVDEC engines serialize when contended. With 37
        # processes contending, NVDEC becomes the bottleneck (~36s render
        # time observed). CPU decode of small H.264 slices (1-3s each) is
        # fast — 80 CPU cores eat that easily in parallel — and avoids the
        # GPU contention entirely.
        _seg_input = (
            ["-ss", f"{start:.3f}", "-t", f"{seg_dur:.3f}",
             "-analyzeduration", "1000000", "-probesize", "1000000",
             "-i", render_source]
        )
        input_args += _seg_input
        _seg_input_args_list.append(list(_seg_input))
        speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))

        # Build variable-speed setpts expression — speed curve flows continuously
        # across the timeline, independent of clip boundaries
        setpts_val, _, avg_speed = build_variable_speed_setpts(start, end, speed, speed_curve, log=True, fps=source_fps)
        combined_speed = avg_speed  # for audio (constant) and logging
        zoom = str(cut.get("zoom") or "none")
        if has_burned_captions and zoom in ["punch_in", "punch_out"]:
            zoom = "slow_in" if zoom == "punch_in" else "slow_out"
        # Always-on Ken Burns: no clip is ever truly static.
        # Matches Captions app where every talking-head shot has subtle movement.
        if zoom == "none" and not cut.get("_is_hook"):
            zoom = "slow_in"

        eff_dur = effective_durations[i]
        fps = source_fps
        # Use the ORIGINAL cut's total source duration for zoom, not the
        # sub-clip's. After speed-curve splitting, sub-clips are 20-250ms.
        # Using the sub-clip's frame count would complete a full Ken Burns
        # zoom in 30ms, then reset on the next sub-clip — causing rapid
        # zoom flickering. The original cut's duration gives a smooth,
        # continuous zoom across all its sub-clips.
        _orig_idx = cut.get("_original_idx", i)
        _orig_info = _orig_cut_info.get(_orig_idx)
        _orig_total_dur = _orig_info["total_source_dur"] if _orig_info else (float(cut["source_end"]) - float(cut["source_start"]))
        total_frames = max(1, round(_orig_total_dur * source_fps))
        # Frame offset: where this sub-clip starts within the original cut's
        # zoom expression. Zoom uses (n + offset) so it's continuous.
        _zoom_frame_offset = _subclip_frame_offset[i]
        MIN_ZOOM_FRAMES = max(1, round(3.0 * source_fps))  # ~3 seconds, scaled to source fps
        if zoom != "none" and total_frames < MIN_ZOOM_FRAMES:
            zoom_scale_factor = total_frames / MIN_ZOOM_FRAMES
            total_frames_for_zoom = MIN_ZOOM_FRAMES
        else:
            zoom_scale_factor = 1.0
            total_frames_for_zoom = total_frames
        # 2-camera simulation: alternate between wide (100%) and tight (115%) per cut.
        # Tight cuts get a static 15% zoom (instant crop, face-centered) + subtle drift.
        # Wide cuts get subtle 4-5% Ken Burns drift. Research: 115% is standard reframe.
        # Use _original_idx so sub-clips from the same parent cut share the same camera angle.
        _is_tight_cut = (_orig_idx % 2 == 1) and zoom not in ("cut_zoom",) and not cut.get("_is_hook")
        _base_zoom_max = 1.14 if has_burned_captions else 1.14  # 14% drift — visible Ken Burns for Captions-level energy

        # ── Face-tracked zoom ──────────────────────────────────────────
        # Find the closest face detection to this clip's midpoint.
        # ALL zoom types target the face — never zoom into dead space.
        zoom_filter = None
        closest_face = None
        if zoom != "none" and face_positions:
            clip_mid = (start + end) / 2.0
            closest_face = min(face_positions, key=lambda p: abs(float(p.get("t") or 0.0) - clip_mid))
            _face_dt = abs(float(closest_face.get("t") or 0.0) - clip_mid)
            if not closest_face.get("found") or _face_dt > 5.0:
                closest_face = None

        # Adaptive zoom_max: scale based on face detection confidence
        if closest_face:
            _face_conf = float(closest_face.get("confidence", 0.5))
            zoom_max = 1.0 + (_base_zoom_max - 1.0) * max(0.5, min(1.0, _face_conf))
        else:
            # No face detected: aggressive zooms (cut_zoom, punch_in) look bad
            # when targeting dead center — downgrade to gentle slow_in or skip
            if zoom in ("cut_zoom", "punch_in"):
                zoom = "slow_in"
                print(f"[zoom] clip {i}: downgraded {cut.get('zoom')} → slow_in (no face detected)", flush=True)
            zoom_max = 1.0 + (_base_zoom_max - 1.0) * 0.35

        # 2-camera: tight cuts get base 118% zoom (static crop) + drift on top.
        # 18% creates a visually OBVIOUS framing change between wide/tight shots.
        # Research: Captions app alternates between full frame and 115-120% tight.
        _tight_base = 0.0
        if _is_tight_cut and closest_face:
            _tight_base = 0.28  # 28% base zoom for tight framing — dramatic wide/tight alternation like Captions AI

        # Compute face offset for crop targeting — interpolate between two nearest
        # face positions for smooth continuous pan across the clip
        face_cx = 540.0
        face_cy = 960.0
        face_cx_end = 540.0
        face_cy_end = 960.0
        _has_face_interp = False

        # ── Dense trajectory keyframes for this clip ──────────────────────
        # Extract keyframes from the smoothed dense trajectory that fall within
        # this clip's source time range.  Used for piecewise-linear FFmpeg
        # expressions that smoothly pan the crop across the clip.
        _clip_dense_kf = []  # list of (frame_number, offset_x, offset_y)
        _use_dense_pan = False
        if _has_dense_trajectory and closest_face:
            _kf_raw = []
            for dp in dense_face_trajectory:
                dp_t = dp["t"]
                if dp_t < start - 0.5 or dp_t > end + 0.5:
                    continue
                clip_local_t = max(0.0, dp_t - start)
                frame_n = round(clip_local_t * fps)
                ox = clamp(dp["cx"] - 540.0, -240.0, 240.0)
                oy = clamp(dp["cy"] - 960.0, -320.0, 320.0)
                _kf_raw.append((frame_n, ox, oy))

            if len(_kf_raw) >= 2:
                # Compress: only keep keyframes where position changes by >5px
                _clip_dense_kf = [_kf_raw[0]]
                for kf in _kf_raw[1:]:
                    last = _clip_dense_kf[-1]
                    if abs(kf[1] - last[1]) > 5.0 or abs(kf[2] - last[2]) > 5.0:
                        _clip_dense_kf.append(kf)
                # Always include the last keyframe
                if _clip_dense_kf[-1] != _kf_raw[-1]:
                    _clip_dense_kf.append(_kf_raw[-1])
                _use_dense_pan = len(_clip_dense_kf) >= 2

        if closest_face:
            face_cx = float(closest_face.get("cx") or 540.0)
            face_cy = float(closest_face.get("cy") or 960.0)
            face_cx_end = face_cx
            face_cy_end = face_cy
            # Find next face position after clip midpoint for interpolation
            if face_positions:
                clip_mid = (start + end) / 2.0
                _sorted_fp = sorted(
                    [fp for fp in face_positions if fp.get("found")],
                    key=lambda p: float(p.get("t") or 0.0),
                )
                _before = None
                _after = None
                for fp in _sorted_fp:
                    ft = float(fp.get("t") or 0.0)
                    if ft <= clip_mid:
                        _before = fp
                    elif _after is None:
                        _after = fp
                if _before and _after:
                    face_cx = float(_before.get("cx") or 540.0)
                    face_cy = float(_before.get("cy") or 960.0)
                    face_cx_end = float(_after.get("cx") or 540.0)
                    face_cy_end = float(_after.get("cy") or 960.0)
                    _has_face_interp = True

        offset_x_start = clamp(face_cx - 540.0, -240.0, 240.0)
        offset_y_start = clamp(face_cy - 960.0, -320.0, 320.0)
        offset_x_end = clamp(face_cx_end - 540.0, -240.0, 240.0)
        offset_y_end = clamp(face_cy_end - 960.0, -320.0, 320.0)
        # Legacy single offset for non-interpolated paths
        offset_x = offset_x_start
        offset_y = offset_y_start

        # ── Multi-camera simulation ──────────────────────────────────────
        # Rotate through virtual "camera angles" on consecutive talking-head
        # clips. Each angle varies crop offset + subtle color tint, creating
        # the illusion of a multi-camera shoot from a single source.
        # Camera presets simulate multi-camera by varying crop offset + subtle tint.
        # Shifts are now larger (8-10% of frame) so the alternation is VISIBLE.
        _CAMERA_PRESETS = [
            {"name": "center",  "ox_shift": 0.0,    "oy_shift": 0.0,    "zoom_add": 0.0,   "tint": ""},
            {"name": "close",   "ox_shift": 0.0,    "oy_shift": -0.015,  "zoom_add": 0.06,  "tint": "colorbalance=rs=0.02:gs=0.01:bs=-0.01"},
            {"name": "left",    "ox_shift": -0.035,  "oy_shift": 0.0,    "zoom_add": 0.03,  "tint": "colorbalance=rs=-0.01:gs=0.00:bs=0.01"},
            {"name": "right",   "ox_shift": 0.035,   "oy_shift": 0.0,    "zoom_add": 0.03,  "tint": "colorbalance=rs=0.01:gs=0.01:bs=-0.01"},
        ]
        cam_preset = None
        if not cut.get("_is_hook") and zoom != "cut_zoom":
            _content_i = cut.get("_original_idx", i)
            if _content_i >= 0:
                cam_preset = _CAMERA_PRESETS[_content_i % len(_CAMERA_PRESETS)]
                if cam_preset["ox_shift"] != 0.0:
                    offset_x_start += cam_preset["ox_shift"] * 1080
                    offset_x_end += cam_preset["ox_shift"] * 1080
                    offset_x_start = clamp(offset_x_start, -120.0, 120.0)
                    offset_x_end = clamp(offset_x_end, -120.0, 120.0)
                    offset_x = offset_x_start
                if cam_preset["oy_shift"] != 0.0:
                    offset_y_start += cam_preset["oy_shift"] * 1920
                    offset_y_end += cam_preset["oy_shift"] * 1920
                    offset_y_start = clamp(offset_y_start, -160.0, 160.0)
                    offset_y_end = clamp(offset_y_end, -160.0, 160.0)
                    offset_y = offset_y_start
                if cam_preset["zoom_add"] > 0 and zoom in ("slow_in", "slow_out", "none"):
                    zoom_max += cam_preset["zoom_add"]

        if closest_face:
            _interp_tag = f" (dense:{len(_clip_dense_kf)}kf)" if _use_dense_pan else (" (interpolated)" if _has_face_interp else "")
            _cam_tag = f" cam={cam_preset['name']}" if cam_preset else ""
            print(f"[zoom] clip {i}: {zoom} → face at ({face_cx:.0f}, {face_cy:.0f}){_interp_tag}{_cam_tag}", flush=True)
        elif zoom != "none":
            print(f"[zoom] clip {i}: {zoom} → no face detected, using center", flush=True)

        def _face_crop(scale_expr, tf_val, reverse=False):
            """Build a scale+crop filter that targets the detected face.
            When dense trajectory keyframes are available, generates a piecewise-
            linear FFmpeg expression for smooth per-frame face panning.
            Falls back to simple start/end interpolation otherwise.
            reverse=True: start at face, drift to center (for slow_out).
            """
            # Use (n+offset) so sub-clips from the same parent cut have
            # continuous zoom/pan instead of resetting at each sub-clip boundary.
            _nvar = f"(n+{_zoom_frame_offset})" if _zoom_frame_offset > 0 else "n"
            _t = f"min({_nvar}/{tf_val}\\,1.0)"
            progress = f"(1.0-{_t})" if reverse else _t

            if _use_dense_pan and len(_clip_dense_kf) >= 2:
                # Build piecewise-linear FFmpeg expression from dense keyframes.
                # Each segment: if(between(n,F1,F2), lerp(ox1,ox2,(n-F1)/(F2-F1)), ...)
                # Camera presets shift applied on top.
                _cam_ox_shift = (cam_preset["ox_shift"] * 1080) if cam_preset and cam_preset.get("ox_shift") else 0.0
                _cam_oy_shift = (cam_preset["oy_shift"] * 1920) if cam_preset and cam_preset.get("oy_shift") else 0.0

                def _build_dense_expr(coord_idx):
                    """coord_idx: 1=ox, 2=oy"""
                    shift = _cam_ox_shift if coord_idx == 1 else _cam_oy_shift
                    lo_clamp = -240.0 if coord_idx == 1 else -320.0
                    hi_clamp = 240.0 if coord_idx == 1 else 320.0
                    segments = []
                    for si in range(len(_clip_dense_kf) - 1):
                        f1 = _clip_dense_kf[si][0]
                        f2 = _clip_dense_kf[si + 1][0]
                        v1 = clamp(_clip_dense_kf[si][coord_idx] + shift, lo_clamp, hi_clamp)
                        v2 = clamp(_clip_dense_kf[si + 1][coord_idx] + shift, lo_clamp, hi_clamp)
                        if f2 <= f1:
                            continue
                        frac = f"(n-{f1})/({f2 - f1})"
                        lerp = f"({v1:.1f}+({v2:.1f}-{v1:.1f})*{frac})"
                        segments.append(f"if(between(n\\,{f1}\\,{f2})\\,{lerp}")
                    if not segments:
                        # Fallback: constant at first keyframe value
                        v = clamp(_clip_dense_kf[0][coord_idx] + shift, lo_clamp, hi_clamp)
                        return f"{v:.1f}"
                    # Last segment is the default (holds last value)
                    last_v = clamp(_clip_dense_kf[-1][coord_idx] + shift, lo_clamp, hi_clamp)
                    expr = f"{last_v:.1f}"
                    for seg in reversed(segments):
                        expr = f"{seg}\\,{expr})"
                    return expr

                _dense_ox = _build_dense_expr(1)
                _dense_oy = _build_dense_expr(2)
                crop_x = f"max(0\\,min((iw-1080)/2+({_dense_ox})*{progress}\\,iw-1080))"
                crop_y = f"max(0\\,min((ih-1920)/2+({_dense_oy})*{progress}\\,ih-1920))"
            else:
                # Legacy: simple start/end interpolation
                _ox = f"({offset_x_start:.1f}+({offset_x_end:.1f}-{offset_x_start:.1f})*{_t})"
                _oy = f"({offset_y_start:.1f}+({offset_y_end:.1f}-{offset_y_start:.1f})*{_t})"
                crop_x = f"max(0\\,min((iw-1080)/2+{_ox}*{progress}\\,iw-1080))"
                crop_y = f"max(0\\,min((ih-1920)/2+{_oy}*{progress}\\,ih-1920))"
            return f"{scale_expr}:eval=frame:flags=bicubic,crop=1080:1920:x='{crop_x}':y='{crop_y}'"

        # All zoom expressions use _nvar so sub-clips from the same parent
        # cut produce a continuous zoom instead of resetting at each boundary.
        _nvar = f"(n+{_zoom_frame_offset})" if _zoom_frame_offset > 0 else "n"

        if zoom == "slow_in":
            tf = max(1, total_frames_for_zoom) if zoom_scale_factor < 1.0 else max(1, total_frames)
            zoom_range = (zoom_max - 1.0) * zoom_scale_factor
            # Smoothstep easing for buttery smooth zoom
            _si_p = f"min({_nvar}/{tf}\\,1.0)"
            _si_smooth = f"({_si_p}*{_si_p}*(3-2*{_si_p}))"
            # _tight_base adds static 15% zoom for tight-framing cuts (2-camera sim)
            _total_base = _tight_base
            scale_expr = (
                f"scale=w='trunc(iw*({1.0 + _total_base:.4f}+{zoom_range:.4f}*{_si_smooth})/2)*2'"
                f":h='trunc(ih*({1.0 + _total_base:.4f}+{zoom_range:.4f}*{_si_smooth})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf)
        elif zoom == "slow_out":
            tf = max(1, total_frames_for_zoom) if zoom_scale_factor < 1.0 else max(1, total_frames)
            zoom_range = (zoom_max - 1.0) * zoom_scale_factor
            # Smoothstep easing: 3t²-2t³ for natural deceleration (clamped to [0,1])
            smooth = f"(min({_nvar}/{tf}\\,1))*(min({_nvar}/{tf}\\,1))*(3-2*(min({_nvar}/{tf}\\,1)))"
            scale_expr = (
                f"scale=w='trunc(iw*({1.0 + zoom_range:.4f}-{zoom_range:.4f}*{smooth})/2)*2'"
                f":h='trunc(ih*({1.0 + zoom_range:.4f}-{zoom_range:.4f}*{smooth})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf, reverse=True)
        elif zoom == "punch_in":
            punch_range = 0.18 * zoom_scale_factor  # aggressive punch for Captions-level impact
            tf = max(1, total_frames_for_zoom)
            # Smoothstep ease for natural feel
            _pi_p = f"min({_nvar}/{tf}\\,1.0)"
            _pi_ease = f"({_pi_p}*{_pi_p}*(3-2*{_pi_p}))"
            scale_expr = (
                f"scale=w='trunc(iw*(1.0+{punch_range:.4f}*{_pi_ease})/2)*2'"
                f":h='trunc(ih*(1.0+{punch_range:.4f}*{_pi_ease})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf)
        elif zoom == "punch_out":
            punch_range = 0.18 * zoom_scale_factor  # aggressive punch for Captions-level impact
            tf = max(1, total_frames_for_zoom)
            _po_p = f"min({_nvar}/{tf}\\,1.0)"
            _po_ease = f"({_po_p}*{_po_p}*(3-2*{_po_p}))"
            scale_expr = (
                f"scale=w='trunc(iw*({1.0 + punch_range:.4f}-{punch_range:.4f}*{_po_ease})/2)*2'"
                f":h='trunc(ih*({1.0 + punch_range:.4f}-{punch_range:.4f}*{_po_ease})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf, reverse=True)
        elif zoom == "cut_zoom":
            # Rapid punch-in zoom: 100% → 118% over 4 frames, hold for clip.
            # 115-118% is industry standard (CapCut, Captions, Opus Clip).
            # 4 frames at 30fps = 0.13s — fast enough to feel instant, smooth enough
            # to avoid jarring single-frame snaps.
            cz_target = 0.18  # 18% zoom = 118% scale
            cz_frames = 4     # rapid snap (4 frames ≈ 0.13s)
            cz_p = f"min({_nvar}/{cz_frames}\\,1.0)"
            cz_ease = f"({cz_p}*{cz_p}*(3-2*{cz_p}))"
            scale_expr = (
                f"scale=w='trunc(iw*(1.0+{cz_target:.4f}*{cz_ease})/2)*2'"
                f":h='trunc(ih*(1.0+{cz_target:.4f}*{cz_ease})/2)*2'"
            )
            cz_crop_x = f"max(0\\,min((iw-1080)/2+{offset_x:.1f}*{cz_ease}\\,iw-1080))"
            cz_crop_y = f"max(0\\,min((ih-1920)/2+{offset_y:.1f}*{cz_ease}\\,ih-1920))"
            zoom_filter = f"{scale_expr}:eval=frame:flags=bicubic,crop=1080:1920:x='{cz_crop_x}':y='{cz_crop_y}'"
            print(f"[zoom] clip {i}: cut_zoom → 100%→118% punch-in, face-tracked", flush=True)

        vignette = str(edit_plan.get("vignette") or "none").lower()
        vignette_filter = None
        if vignette == "light":    vignette_filter = "vignette=angle=PI/4"
        elif vignette == "medium": vignette_filter = "vignette=angle=PI/5"
        elif vignette == "strong": vignette_filter = "vignette=angle=PI/6"

        outro_filter = None
        outro = edit_plan.get("outro") or "none"
        if i == n-1 and outro != "none":
            fade_color = "white" if outro == "fade_white" else "black"
            fade_start = max(0, eff_dur - 1.0)
            outro_filter = f"fade=t=out:st={fade_start:.3f}:d=1.0:color={fade_color}"

        # Video: each segment has its own pre-seeked input (no trim needed)
        # Scale/crop filter folded in from normalize — eliminates separate encode pass
        # fps=30 BEFORE setpts so timebase is guaranteed 1/30 and N=frame number.
        # The piecewise setpts expression uses N to look up the canonical time map.
        v_chain = []
        if _normalize_vf:
            v_chain.append(_normalize_vf)
        v_chain.append("setpts=PTS-STARTPTS")
        if setpts_val:
            v_chain.append(f"setpts={setpts_val}")
        # NO fps= filter. Previously fps=30 quantized the video stream's
        # duration to 1/30s frame boundaries, while audio's asetrate/aresample
        # produced sample-accurate output. Per segment, video and audio
        # diverged by up to ±16.67ms (half a frame), and across N segments
        # the cumulative drift reached ~100ms — exactly the user's complaint.
        #
        # Without fps=, setpts only RELABELS frame timestamps without
        # dropping or duplicating frames. Output frame count = source frame
        # count. Output stream duration = source_dur / avg_speed (matches
        # audio sample-accurately). The output is VFR (variable frame rate)
        # which all modern players (TikTok, Instagram, browsers) handle
        # natively. The encoder needs -fps_mode passthrough to honor the
        # filter graph timestamps instead of forcing CFR.
        if zoom_filter:
            v_chain.append(zoom_filter)
        # Per-clip camera tint (multi-camera color variation)
        if cam_preset and cam_preset.get("tint"):
            v_chain.append(cam_preset["tint"])

        # ── Emotion-adaptive per-clip color grading ──────────────────────
        # Derive emotional tone from emphasis moments overlapping this clip.
        # Subtle color shift per emotion type creates subconscious mood shifts.
        _EMOTION_GRADES = {
            "punchline":   "eq=brightness=0.02:saturation=1.06",   # warm pop
            "revelation":  "eq=brightness=-0.01:saturation=0.96",  # cooler, slightly desaturated
            "statement":   "",                                      # neutral (no shift)
            "reaction":    "eq=saturation=1.08:contrast=1.03",     # vivid
            "question":    "eq=brightness=0.01:saturation=0.98",   # slightly muted
            "transition":  "",                                      # neutral
        }
        if not cut.get("_is_hook"):
            _em_all = edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or []
            _clip_em = [em for em in _em_all if start <= float(em.get("t") or 0) <= end]
            if _clip_em:
                _dom_type = max(_clip_em, key=lambda e: 1 if e.get("intensity") == "high" else 0).get("type", "")
                _em_grade = _EMOTION_GRADES.get(_dom_type, "")
                if _em_grade:
                    v_chain.append(_em_grade)

        if vignette_filter:
            v_chain.append(vignette_filter)

        freeze_frame = bool(cut.get("freeze_frame"))
        if freeze_frame and eff_dur > 0.5:
            freeze_frames = 9
            v_chain.append(f"tpad=stop={freeze_frames}:stop_mode=clone")
            print(f"[render] clip {i}: freeze_frame=true (+{freeze_frames} frames @ end)", flush=True)

        if outro_filter:
            v_chain.append(outro_filter)

        # format=yuv420p LAST — after all color grading for maximum fidelity
        v_chain.append("format=yuv420p")
        video_filters.append(f"[{i}:v]{','.join(v_chain)}[v{i}]")
        _seg_v_chains.append(list(v_chain))
        _seg_speeds.append(combined_speed)

        # Audio: each segment has its own pre-seeked input (no atrim needed)
        a_chain = ["asetpts=PTS-STARTPTS"]
        _has_active_speed_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
        if abs(combined_speed - 1.0) > 0.001:
            if _has_active_speed_curve:
                # Speed ramping is active — pitch shift is intentional (the effect).
                # Full float precision (10 decimals) so audio playback rate
                # agrees with the video setpts rate to sub-microsecond accuracy.
                a_chain.append(f"asetrate={sample_rate}*{combined_speed:.10f}")
                a_chain.append(f"aresample={sample_rate}")
            else:
                # Normal clip speed — use pitch-preserving filter
                _pp_filter = get_pitch_preserving_speed_filter(combined_speed)
                if _pp_filter:
                    a_chain.append(_pp_filter)
        if i == n-1 and outro != "none":
            fade_start = max(0, eff_dur - 1.0)
            a_chain.append(f"afade=t=out:st={fade_start:.3f}:d=1.0")
        audio_filters.append(f"[{i}:a]{','.join(a_chain)}[a{i}]")
        _seg_a_chains.append(list(a_chain))


    # ══════════════════════════════════════════════════════════════════════════
    # PARALLEL SEGMENT RENDERING
    # Each segment runs as an independent FFmpeg process for maximum CPU
    # utilization. Then concat (stream copy) + audio post-processing.
    # ══════════════════════════════════════════════════════════════════════════

    # ── Compute per-segment transition fades ────────────────────────────
    # Decompose xfade transitions into per-segment fade-in/fade-out so each
    # segment can be rendered independently without cross-segment dependencies.
    _FADE_COLOR_MAP = {
        "fadewhite": "white", "flash": "white",
        "fadeblack": "black", "fade": "black",
        "dissolve": "black", "glitch": "black",
        "wipeleft": "black", "wiperight": "black",
        "smoothleft": "black", "smoothright": "black",
        "whip_left": "black", "whip_right": "black",
    }
    _seg_fade_in = [None] * n   # {"duration": float, "color": str} or None
    _seg_fade_out = [None] * n
    for _ti in range(1, n):
        _tr = str(render_cuts[_ti - 1].get("transition_out") or "none").lower()
        if _tr == "none" or _tr == "clean_cut" or _tr == "":
            continue
        _td = TRANSITION_DURATION
        _prev_dur = effective_durations[_ti - 1] if _ti - 1 < len(effective_durations) else 1.0
        _curr_dur = effective_durations[_ti] if _ti < len(effective_durations) else 1.0
        if _prev_dur < _td + 0.1 or _curr_dur < _td + 0.1:
            continue
        _color = _FADE_COLOR_MAP.get(_tr, "black")
        _seg_fade_out[_ti - 1] = {"duration": _td, "color": _color}
        _seg_fade_in[_ti] = {"duration": _td, "color": _color}

    # ── SFX collection (for audio post-processing pass) ─────────────────
    sfx_input_args = []
    sfx_filter_strs = []
    sfx_audio_labels = []
    sfx_timestamps = []
    _sfx_extra_idx = 0

    _speech_segs = speech_segments or (edit_plan.get("analysis_data") or {}).get("speech", {}).get("segments") or []
    _base_cuts = original_cuts
    _base_effective_durations = compute_effective_durations(_base_cuts, speed_curve) if _base_cuts else []

    _running_sfx = _base_effective_durations[0] if _base_effective_durations else 0.0
    _transition_times = []
    for _i in range(max(0, len(_base_cuts) - 1)):
        _transition = str(_base_cuts[_i].get("transition_out") or "none").lower()
        _td = TRANSITION_DURATION if _transition not in ("none", "clean_cut", "") else 0.0
        # Anchor at the actual transition moment — onset compensation below
        # will pull the file start earlier so the climax lands on it.
        _event_time = max(0.0, _running_sfx)
        _transition_times.append(_event_time)
        _running_sfx = _running_sfx + _base_effective_durations[_i + 1] - _td

    for _i in range(max(0, len(_base_cuts) - 1)):
        _sound_style = normalize_sfx_style(_base_cuts[_i].get("transition_sound") or _base_cuts[_i].get("sfx_style") or "none")
        if _sound_style == "none":
            continue
        _sound_path = get_sfx_path(_sound_style)
        if not _sound_path:
            continue
        _onset = _SFX_ONSET_OFFSETS.get(_sound_style, 0.0)
        _event_time = max(0.0, _transition_times[_i] - _onset)
        _offset_ms = max(0, round(_event_time * 1000))
        _vol = get_sfx_volume(_sound_style, _event_time, _speech_segs, is_text_overlay=False)
        sfx_input_args += ["-i", _sound_path]
        sfx_audio_labels.append(f"[snd{_i}]")
        sfx_filter_strs.append(f"[{_sfx_extra_idx + 1}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}[snd{_i}]")
        sfx_timestamps.append(_event_time)
        print(f"[sfx] transition {_i}: {_sound_style} vol={_vol:.3f} at {_event_time:.3f}s", flush=True)
        _sfx_extra_idx += 1

    _clip_ranges_sfx = get_output_clip_ranges(_base_cuts, _base_effective_durations, transition_duration=TRANSITION_DURATION) if _base_cuts else []
    for _i, _overlay in enumerate(edit_plan.get("text_overlays") or []):
        _clip_idx = int(_overlay.get("appear_at_clip") or 0)
        if _clip_idx < 0 or _clip_idx >= len(_clip_ranges_sfx):
            continue
        _sfx_style = normalize_sfx_style(_overlay.get("sfx_style") or "none")
        if _sfx_style == "none":
            continue
        _sound_path = get_sfx_path(_sfx_style)
        if not _sound_path:
            continue
        _onset = _SFX_ONSET_OFFSETS.get(_sfx_style, 0.0)
        _ts = max(0.0, float(_clip_ranges_sfx[_clip_idx].get("start") or 0) + 0.02 - _onset)
        _offset_ms = round(_ts * 1000)
        _vol = get_sfx_volume(_sfx_style, _ts, _speech_segs, is_text_overlay=True)
        sfx_input_args += ["-i", _sound_path]
        sfx_audio_labels.append(f"[txtsnd{_i}]")
        sfx_filter_strs.append(f"[{_sfx_extra_idx + 1}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}[txtsnd{_i}]")
        sfx_timestamps.append(_ts)
        print(f"[sfx] text_overlay {_i}: {_sfx_style} vol={_vol:.3f} at {_ts:.3f}s", flush=True)
        _sfx_extra_idx += 1

    # Use the SAME rounded effective_durations as the render — no recomputing.
    _full_ranges = get_output_clip_ranges(render_cuts, effective_durations, transition_duration=TRANSITION_DURATION) if render_cuts else []
    parsed_sfx = edit_plan.get("_parsed_sound_effects", [])
    for _i, _sfx in enumerate(parsed_sfx):
        _sound_style = normalize_sfx_style(_sfx.get("sound") or "none")
        if _sound_style == "none":
            continue
        _sound_path = get_sfx_path(_sound_style)
        if not _sound_path:
            continue
        _source_t = float(_sfx.get("t") or 0.0)
        _projected_t = project_source_time_to_output(_source_t, render_cuts, _full_ranges, speed_curve, clip_time_maps=_clip_time_maps)
        if _projected_t is None:
            continue
        # Onset compensation: subtract the SFX file's internal onset so the
        # perceived "moment" of the sound lands EXACTLY on the trigger word.
        # For build-up sounds (drum_roll etc.), this means the build precedes
        # the word and the climax lands on it.
        _onset = _SFX_ONSET_OFFSETS.get(_sound_style, 0.0)
        _ts = max(0.0, _projected_t - _onset)
        _offset_ms = round(_ts * 1000)
        _vol = get_sfx_volume(_sound_style, _ts, _speech_segs, is_text_overlay=False)
        sfx_input_args += ["-i", _sound_path]
        sfx_audio_labels.append(f"[timesfx{_i}]")
        sfx_filter_strs.append(f"[{_sfx_extra_idx + 1}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}[timesfx{_i}]")
        sfx_timestamps.append(_ts)
        print(f"[sfx] sound_effect: {_sound_style} vol={_vol:.3f} source={_source_t:.3f}s → projected={_projected_t:.3f}s → onset_comp(-{_onset:.3f}s)={_ts:.3f}s", flush=True)
        _sfx_extra_idx += 1

    # ── Collect B-roll files and build TIMELINE-LEVEL overlay list ──────
    # B-roll is a timeline overlay, NOT a per-segment overlay. Each entry
    # has an output-time start/end. The per-segment renderer slices the
    # overlay against its own output-time window — a 3s b-roll that
    # crosses a sub-clip boundary naturally splits across multiple
    # segments with the correct seek_point offset for each. No trimming,
    # no min duration, no fit-to-segment math. Gemini's intent is honored
    # exactly.
    #
    # Compute segment output-time boundaries unconditionally so they're
    # available to _run_one_segment whether or not b-roll exists.
    _seg_starts = []
    _cursor_ss = 0.0
    for _si in range(n):
        _seg_starts.append(_cursor_ss)
        _cursor_ss += effective_durations[_si]
    _seg_total_dur = _cursor_ss

    _broll_overlays = []  # list of {path, out_start, out_end, seek_point, ken_burns_dir, keyword}
    if broll_fetch_futures:
        _broll_sc = edit_plan.get("_parsed_speed_curve")
        _broll_files = {}
        for _fut in concurrent.futures.as_completed(broll_fetch_futures, timeout=30):
            _idx = broll_fetch_futures[_fut]
            try:
                _path = _fut.result()
                if _path:
                    _broll_files[_idx] = _path
            except Exception as _be_err:
                print(f"[broll] Fetch error for clip {_idx}: {_be_err}", flush=True)

        if _broll_files and broll_clips:
            for _bi, _bc in enumerate(broll_clips):
                if _bi not in _broll_files:
                    continue
                _local_path = _broll_files[_bi]
                _src_ts = float(_bc.get("timestamp") or 0)
                _src_dur = float(_bc.get("duration") or 0)
                if _src_dur <= 0:
                    continue
                _src_end = _src_ts + _src_dur

                # Project BOTH start and end through the speed curve independently.
                # Source duration ≠ output duration when speed ramping is active.
                # A 1.76s source window at 1.25x becomes 1.41s in output.
                _out_start = project_source_time_to_final_output(
                    _src_ts, render_cuts, effective_durations, _broll_sc,
                    clip_time_maps=_clip_time_maps,
                )
                _out_end = project_source_time_to_final_output(
                    _src_end, render_cuts, effective_durations, _broll_sc,
                    clip_time_maps=_clip_time_maps,
                )
                if _out_start is None or _out_start >= _seg_total_dur:
                    print(f"[broll] '{_bc.get('keyword')}' projected output start invalid — skipping", flush=True)
                    continue
                if _out_end is None or _out_end <= _out_start:
                    # End projection failed — fall back to projecting duration at avg speed
                    _out_end = _out_start + _src_dur
                    print(f"[broll] '{_bc.get('keyword')}' end projection failed, using source duration", flush=True)

                effective_duration = _out_end - _out_start
                broll_file_duration = get_video_duration(_local_path)
                if broll_file_duration > 0 and effective_duration > broll_file_duration:
                    effective_duration = broll_file_duration
                    _out_end = _out_start + effective_duration
                _max_remaining = _seg_total_dur - _out_start
                if effective_duration > _max_remaining:
                    effective_duration = _max_remaining
                    _out_end = _out_start + effective_duration
                if effective_duration <= 0:
                    continue

                # Pick a seek_point within the source clip that gives a
                # visually interesting middle slice rather than the first
                # frame (which is often a fade-in or static intro).
                seek_point = 0.0
                if broll_file_duration > effective_duration + 1.0:
                    seek_point = min(
                        broll_file_duration * 0.25,
                        max(0.0, broll_file_duration - effective_duration - 0.5)
                    )

                _kb_dir = _KB_DIRECTIONS[len(_broll_overlays) % len(_KB_DIRECTIONS)]
                _broll_overlays.append({
                    "path": _local_path,
                    "out_start": _out_start,
                    "out_end": _out_end,
                    "seek_point": seek_point,
                    "ken_burns_dir": _kb_dir,
                    "keyword": _bc.get("keyword", ""),
                })
                # Record output-time range so the thumbnail scorer can
                # avoid b-roll regions (we want speaker frames, not stock).
                edit_plan.setdefault("_broll_output_ranges", []).append(
                    (_out_start, _out_end)
                )
                _kw = _bc.get("keyword", "")
                _reason = _bc.get("reason") or ""
                _reason_str = f" — {_reason}" if _reason else ""
                print(f"[broll] '{_kw}' out=[{_out_start:.2f}s..{_out_end:.2f}s] dur={effective_duration:.2f}s seek={seek_point:.2f}s kb={_kb_dir}{_reason_str}", flush=True)

            if _broll_overlays:
                print(f"[broll] Built {len(_broll_overlays)} timeline overlay(s) — will slice across segments as needed", flush=True)

    # ── Compute frame ranges per segment (for per-segment Remotion renders) ──
    # Frame count uses effective_duration (output time after speed scaling).
    # Remotion renders captions on the OUTPUT timeline — each PNG corresponds
    # to an output timestamp. FFmpeg's overlay matches PNGs to video frames
    # by PTS (timestamp), not frame number, so the different frame counts
    # (source vs effective) don't matter. eof_action=repeat on the overlay
    # bridges any PTS gap at the segment boundary where the video has a few
    # more frames than PNGs.
    _seg_frame_ranges = []
    _frame_cursor = 0
    for _si in range(n):
        _frame_count = max(1, round(effective_durations[_si] * source_fps))
        _seg_frame_ranges.append((_frame_cursor, _frame_cursor + _frame_count - 1))
        _frame_cursor += _frame_count

    # Text overlays are rendered by Remotion as part of the caption PNG
    # sequence (injected into the Remotion input JSON above).

    # ── Build and run parallel segment FFmpeg processes ──────────────────
    _par_t0 = time.time()
    # Per-segment thread budget: divide cores evenly across the parallel
    # ffmpeg processes. Without this, each process used threads=0 ("all
    # cores") and 60 processes oversubscribed the machine 60x, blowing
    # up render time. Minimum 1 thread, maximum 4 (libx264 ultrafast
    # parallelizes well up to ~4 threads, beyond which gains diminish).
    _seg_count_for_threads = len(render_cuts)
    _seg_threads = max(1, min(4, (os.cpu_count() or 16) // max(1, _seg_count_for_threads)))
    _encode_args = get_encode_args("high", threads=_seg_threads) + ["-pix_fmt", "yuv420p"]
    print(f"[render] Per-segment threads: {_seg_threads} ({_seg_count_for_threads} segments × {_seg_threads} threads ≤ {os.cpu_count()} cores)", flush=True)
    _seg_dir = os.path.join(work_dir, "segments")
    os.makedirs(_seg_dir, exist_ok=True)

    # Pool-based Remotion render: 10 long-lived workers, each handling ~N segments
    # by reusing a single Chrome browser via puppeteerInstance. Renders ALL segment
    # PNGs upfront (blocking), then FFmpeg gets all CPU cores without contention.
    _cpu_count = os.cpu_count() or 64
    _physical_cores = max(_cpu_count // 2, 1)
    _pool_workers = min(10, n)
    _pool_tabs_per_worker = max(2, _physical_cores // _pool_workers)
    _gl_mode = "angle-egl" if _HAS_HWACCEL else "swiftshader"

    _seg_overlay_meta = [None] * n
    _seg_overlay_dirs = [None] * n
    if _captions_enabled and _remotion_input_json:
        _pool_t0 = time.time()
        _pool_segments = []
        for _si in range(n):
            _fs, _fe = _seg_frame_ranges[_si]
            _odir = os.path.join(_seg_dir, f"overlay_seg_{_si:03d}")
            _seg_overlay_dirs[_si] = _odir
            _pool_segments.append({
                "frameStart": _fs,
                "frameEnd": _fe,
                "outputDir": _odir,
                "_orig_idx": _si,
            })
        _meta_list = render_remotion_pool(
            _remotion_input_json, _pool_segments,
            num_workers=_pool_workers,
            concurrency_per_worker=_pool_tabs_per_worker,
            gl_mode=_gl_mode,
        )
        for _si, _meta in enumerate(_meta_list):
            _seg_overlay_meta[_si] = _meta
        print(f"[remotion-pool] Pool render complete in {time.time() - _pool_t0:.2f}s "
              f"({_pool_workers} workers × {_pool_tabs_per_worker} tabs)", flush=True)

    # Timing instrumentation: capture per-segment phase timings so we can
    # see where the render time is actually going (Remotion wait vs Remotion
    # render vs ffmpeg invocation). The data goes into _seg_timings as
    # (seg_idx, start_offset, remotion_wait, remotion_run, ffmpeg_run, total).
    _seg_timings = []
    _seg_timings_lock = threading.Lock()

    def _run_one_segment(seg_idx):
        """Run FFmpeg for one segment. Remotion PNGs already rendered upfront. Returns output path."""
        _t_start = time.time()
        _t_start_offset = _t_start - _par_t0
        _t_remotion_wait = 0.0
        _t_remotion_run = 0.0
        _t_ffmpeg_run = 0.0

        _seg_out = os.path.join(_seg_dir, f"seg_{seg_idx:03d}.mkv")
        _eff_dur = effective_durations[seg_idx]

        _seg_overlay_dir = _seg_overlay_dirs[seg_idx]
        _seg_png_start_num = 0
        _seg_png_digits = 6
        if _seg_overlay_dir and _seg_overlay_meta[seg_idx] is not None:
            _seg_png_start_num, _seg_png_count, _seg_png_digits = _seg_overlay_meta[seg_idx]

        # Phase 2: FFmpeg encode
        # Video filter chain (already built, just change input ref to [0:v])
        _vc = list(_seg_v_chains[seg_idx])
        # Add transition fades (before format=yuv420p which is always last)
        _fade_v = []
        if _seg_fade_in[seg_idx]:
            _fi = _seg_fade_in[seg_idx]
            _fade_v.append(f"fade=t=in:st=0:d={_fi['duration']:.3f}:color={_fi['color']}")
        if _seg_fade_out[seg_idx]:
            _fo = _seg_fade_out[seg_idx]
            _fo_st = max(0, _eff_dur - _fo["duration"])
            _fade_v.append(f"fade=t=out:st={_fo_st:.3f}:d={_fo['duration']:.3f}:color={_fo['color']}")
        if _fade_v:
            # Insert before format=yuv420p (last element)
            _vc = _vc[:-1] + _fade_v + [_vc[-1]]

        _filter_parts = []
        _video_label = "[vout]"
        _filter_parts.append(f"[0:v]{','.join(_vc)}{_video_label}")

        # Audio chain
        _ac = list(_seg_a_chains[seg_idx])
        if _seg_fade_in[seg_idx]:
            _td = _seg_fade_in[seg_idx]["duration"]
            _ac.append(f"afade=t=in:st=0:d={_td:.3f}")
        if _seg_fade_out[seg_idx]:
            _td = _seg_fade_out[seg_idx]["duration"]
            _fo_st = max(0, _eff_dur - _td)
            _ac.append(f"afade=t=out:st={_fo_st:.3f}:d={_td:.3f}")
        _filter_parts.append(f"[0:a]{','.join(_ac)}[aout]")

        # Extra inputs (B-roll, then caption overlay)
        # ORDER MATTERS: b-roll composites FIRST (replaces video), then
        # captions render ON TOP so they're always visible even during
        # b-roll cutaways. Text overlays are part of the caption PNGs
        # (rendered by Remotion), so they also stay on top.
        _extra_inputs = []
        _extra_idx = 1

        # B-roll overlays for this segment (applied FIRST, underneath captions).
        #
        # B-roll lives on the GLOBAL output timeline. Each overlay has an
        # absolute output-time window [out_start, out_end]. For this
        # segment we compute the intersection between that window and the
        # segment's own output-time window [seg_out_start, seg_out_end].
        _seg_out_start = _seg_starts[seg_idx]
        _seg_out_end = _seg_out_start + _eff_dur
        _BROLL_MIN_DUR = 1.5 / source_fps  # minimum 1.5 frames — shorter slices produce zero frames and flash
        _bi_emitted = 0
        for _br in _broll_overlays:
            _ov_start = _br["out_start"]
            _ov_end = _br["out_end"]
            _slice_start = max(_ov_start, _seg_out_start)
            _slice_end = min(_ov_end, _seg_out_end)
            if _slice_end - _slice_start <= _BROLL_MIN_DUR:
                continue
            _slice_dur = _slice_end - _slice_start
            _local_start = _slice_start - _seg_out_start
            _slice_seek = _br["seek_point"] + (_slice_start - _ov_start)

            # No Ken Burns on b-roll. Pexels clips have their own camera
            # movement baked in. Ken Burns added a frame-dependent smoothstep
            # crop that recalculated per-segment, causing crop coordinate
            # discontinuities at every segment boundary (visible as flashing
            # with 80+ micro-segments from speed curve densification).
            # Simple center-crop to 1080x1920 is clean and consistent.
            _extra_inputs += ["-i", _br["path"]]
            _bv = f"bv{_bi_emitted}"
            # Offset the b-roll's PTS by _local_start so its timestamps
            # align with the main video's timeline at the overlay point.
            # Without this, the b-roll starts at PTS=0 but the overlay's
            # enable gate doesn't open until t=_local_start. FFmpeg's
            # overlay consumes b-roll frames trying to sync to the main
            # video's PTS, exhausting the b-roll before the gate opens.
            # eof_action=repeat then freezes the last frame.
            _broll_pts_offset = f"+{_local_start:.3f}" if _local_start >= 0.01 else ""
            _filter_parts.append(
                f"[{_extra_idx}:v]trim=start={_slice_seek:.3f}:duration={_slice_dur:.3f},"
                f"setpts=PTS-STARTPTS,"
                f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop=1080:1920,"
                f"setsar=1,eq=saturation=0.92:contrast=1.02,"
                f"setpts=PTS-STARTPTS{_broll_pts_offset}[{_bv}]"
            )
            # B-roll split points guarantee local_start≈0 for most slices.
            # When b-roll covers the full segment (local_start < 0.01), use
            # a simple overlay with no enable gate — the b-roll plays from
            # start to end, and eof_action=repeat holds the last frame if
            # the trim is fractionally short. No enable gate means no
            # timing-dependent glitches on micro-segments.
            # When b-roll starts mid-segment (rare after split points),
            # use enable gate + PTS offset as before.
            if _local_start < 0.01 and abs(_slice_dur - _eff_dur) < 0.02:
                # B-roll covers full segment — no enable gate needed
                _filter_parts.append(
                    f"{_video_label}[{_bv}]overlay=0:0:eof_action=repeat[bov{_bi_emitted}]"
                )
            else:
                _filter_parts.append(
                    f"{_video_label}[{_bv}]overlay=0:0:eof_action=repeat:enable='between(t,{_local_start:.3f},{_local_start + _slice_dur:.3f})'[bov{_bi_emitted}]"
                )
            _video_label = f"[bov{_bi_emitted}]"
            _extra_idx += 1
            _bi_emitted += 1

        # Caption + text overlay PNGs (applied LAST, always on top of everything).
        # PNGs are presented at source_fps (matching Remotion's render rate).
        # eof_action=repeat keeps the last caption frame visible at segment
        # boundaries where VFR PTS discontinuities could otherwise cause a
        # 1-frame gap. Repeating the last frame is invisible because caption
        # content doesn't change within a single sub-clip.
        if _seg_overlay_dir:
            _png_pattern = os.path.join(_seg_overlay_dir, f"element-%0{_seg_png_digits}d.png")
            _extra_inputs += [
                "-f", "image2", "-framerate", f"{source_fps:.5f}",
                "-start_number", str(_seg_png_start_num),
                "-i", _png_pattern,
            ]
            _filter_parts.append(f"{_video_label}[{_extra_idx}:v]overlay=eof_action=repeat[vcap]")
            _video_label = "[vcap]"
            _extra_idx += 1

        _fc = ";".join(_filter_parts)
        # Audio encoded as PCM (not AAC) to eliminate per-segment AAC priming
        # delay (~21ms per segment) that previously bled into clip boundaries
        # when stream-copy concatenated. PCM has no priming, no codec state,
        # and is sample-accurate at every boundary. The final output pass
        # re-encodes audio to AAC once, applying its single priming delay
        # only at the file start (handled correctly by the MP4 edit list).
        _cmd = (
            ["ffmpeg", "-y", "-v", "warning", "-threads", str(_seg_threads)]
            + list(_seg_input_args_list[seg_idx])
            + _extra_inputs
            + ["-filter_complex", _fc, "-map", _video_label, "-map", "[aout]"]
            + list(_encode_args)
            + ["-c:a", "pcm_s16le", "-ar", "48000"]
            + [_seg_out]
        )
        _t_ff = time.time()
        _r = subprocess.run(_cmd, capture_output=True, text=True, timeout=120)
        _t_ffmpeg_run = time.time() - _t_ff
        if _r.returncode != 0:
            raise RuntimeError(f"Segment {seg_idx} FFmpeg failed: {_r.stderr[-500:]}")
        _t_total = time.time() - _t_start
        with _seg_timings_lock:
            _seg_timings.append((seg_idx, _t_start_offset, _t_remotion_wait,
                                 _t_remotion_run, _t_ffmpeg_run, _t_total))
        return _seg_out

    # Launch all segments in parallel. With speed_curve densification we
    # routinely have 60+ sub-clips. Each ffmpeg invocation has ~500ms of
    # fixed startup overhead (process spawn + NVDEC init + libx264 init)
    # that dominates the actual encode time for short sub-clips, so we
    # need maximum parallelism to amortize that cost. Capping workers
    # makes render time WORSE because it forces sub-clips to queue into
    # sequential batches each paying their own startup cost.
    _max_workers = min(n, os.cpu_count() or 16)
    print(f"[render] Parallel: {n} segments, {_max_workers} workers, {os.cpu_count()} cores", flush=True)
    _seg_paths = [None] * n
    with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as _seg_pool:
        _seg_futures = {_seg_pool.submit(_run_one_segment, _si): _si for _si in range(n)}
        for _fut in concurrent.futures.as_completed(_seg_futures):
            _si = _seg_futures[_fut]
            _seg_paths[_si] = _fut.result()
    _par_elapsed = time.time() - _par_t0
    print(f"[render] All {n} segments rendered in {_par_elapsed:.1f}s (parallel)", flush=True)

    # ── Per-segment timing report ────────────────────────────────────────
    # Diagnostic instrumentation: shows where each segment's time went so
    # we can identify the actual bottleneck (Remotion wait? Remotion run?
    # FFmpeg subprocess?). Sorted by total time descending so the slowest
    # are at the top. Remove once perf is satisfactory.
    if _seg_timings:
        _seg_timings.sort(key=lambda r: -r[5])
        _wait_total = sum(r[2] for r in _seg_timings)
        _rem_total  = sum(r[3] for r in _seg_timings)
        _ff_total   = sum(r[4] for r in _seg_timings)
        _all_total  = sum(r[5] for r in _seg_timings)
        print(f"[seg-timing] phases summed across all segments: rem_wait={_wait_total:.1f}s rem_run={_rem_total:.1f}s ffmpeg={_ff_total:.1f}s total={_all_total:.1f}s", flush=True)
        print(f"[seg-timing] top 10 slowest segments (idx | start_offset | rem_wait | rem_run | ffmpeg | total):", flush=True)
        for r in _seg_timings[:10]:
            _idx, _so, _rw, _rr, _fr, _tot = r
            print(f"[seg-timing]   seg {_idx:3d}  start@{_so:5.2f}s  wait={_rw:5.2f}s  rem={_rr:5.2f}s  ff={_fr:5.2f}s  total={_tot:5.2f}s", flush=True)

    # ── Build concat list (consumed directly by audio_post via concat demuxer) ─
    # Previously this was a separate ffmpeg invocation that wrote concat_raw.mkv
    # then audio_post read it back — ~1.6s of pure overhead. The concat demuxer
    # handles the same job inline as audio_post's input, eliminating the
    # intermediate file and the second ffmpeg process. The segments are all
    # encoded with identical codec/timebase (libx264 + PCM @ 48kHz) so concat
    # demuxer compatibility is unchanged from the standalone concat call.
    _concat_list_path = os.path.join(work_dir, "concat_list.txt")
    with open(_concat_list_path, "w") as _clf:
        for _sp in _seg_paths:
            _clf.write(f"file '{_sp}'\n")

    # ── Audio post-processing pass (video stream copy) ──────────────────
    # SFX mixing, audio ducking, denoise, EQ, compress, loudnorm
    _audio_t0 = time.time()

    audio_denoise = bool(edit_plan.get("audio_denoise"))
    _src_loudness = edit_plan.get("_source_loudness") or {}
    _src_rms = _src_loudness.get("rms_db", -18.0)
    _src_peak = _src_loudness.get("peak_db", -6.0)
    _src_nf = _src_loudness.get("noise_floor_db", -45.0)
    if audio_denoise:
        _nr = 6 if _src_nf > -40 else (10 if _src_nf > -50 else 14)
        denoise_part = f"afftdn=nr={_nr}:nf={int(_src_nf)}:tn=1,"
    else:
        denoise_part = ""
    _fast_thresh = max(-28, min(-16, _src_rms - 4))
    _level_thresh = max(-22, min(-10, _src_rms + 2))
    _makeup = max(1, min(4, round(-_src_rms / 6)))
    print(
        f"[audio] Adaptive chain: rms={_src_rms:.0f}dB peak={_src_peak:.0f}dB "
        f"fast_thresh={_fast_thresh:.0f}dB level_thresh={_level_thresh:.0f}dB makeup={_makeup}dB",
        flush=True,
    )
    # No apad/atrim — let the audio be exactly the length the filters
    # naturally produce. Forcing a target duration was cutting off the
    # last word's natural decay.
    audio_chain = (
        f"{denoise_part}highpass=f=75,"
        f"equalizer=f=200:t=q:w=1.5:g=-1.5,"
        f"equalizer=f=3000:t=q:w=1.2:g=1.5,"
        f"acompressor=threshold={_fast_thresh}dB:ratio=3:attack=3:release=40:detection=peak"
        f":link=maximum:knee=3:mix=0.6,"
        f"lowpass=f=14000,"
        f"acompressor=threshold={_level_thresh}dB:ratio=1.8:attack=15:release=80:makeup={_makeup},"
        f"loudnorm=I=-14:TP=-1:LRA=11"
    )

    _audio_filter_parts = []
    _audio_out = "[audio_base]"
    _audio_filter_parts.append(f"[0:a]asetpts=PTS-STARTPTS{_audio_out}")

    if sfx_audio_labels and sfx_timestamps:
        _duck_parts = []
        for _dt in sorted(set(sfx_timestamps)):
            _dip_start = max(0, _dt - 0.05)
            _dip_end = _dt + 0.25
            _duck_parts.append(
                f"if(between(t,{_dip_start:.3f},{_dip_end:.3f}),"
                f"0.45+0.55*max(0,min(abs(t-{_dt:.3f})/0.15,1)),"
                f"1)"
            )
        if _duck_parts:
            _duck_expr = "*".join(_duck_parts[:20])
            _audio_filter_parts.append(f"{_audio_out}volume='{_duck_expr}':eval=frame[audio_ducked]")
            _audio_out = "[audio_ducked]"
            print(f"[sfx] Audio ducking: {len(_duck_parts)} dip point(s)", flush=True)

        _n_sfx = len(sfx_audio_labels) + 1
        _sfx_labels_str = _audio_out + "".join(sfx_audio_labels)
        _audio_filter_parts.append(
            f"{_sfx_labels_str}amix=inputs={_n_sfx}:duration=first:dropout_transition=0:normalize=0[audio_sfx_mixed]"
        )
        _audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio", flush=True)

    _audio_filter_parts.append(f"{_audio_out}{audio_chain}[final_audio]")
    _audio_fc = ";".join(sfx_filter_strs + _audio_filter_parts)

    # No -shortest: let video and audio be their natural lengths so the
    # tail of the last word is not silently truncated when the audio
    # happens to be slightly longer than the video timeline.
    _final_cmd = (
        ["ffmpeg", "-y", "-v", "warning", "-threads", "0",
         "-f", "concat", "-safe", "0", "-i", _concat_list_path]
        + sfx_input_args
        + ["-filter_complex", _audio_fc,
           "-map", "0:v", "-c:v", "copy",
           "-map", "[final_audio]", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart"]
        + [output_path]
    )
    _final_r = subprocess.run(_final_cmd, capture_output=True, text=True, timeout=120)
    if _final_r.returncode != 0:
        raise RuntimeError(f"Audio post-processing failed: {_final_r.stderr[-500:]}")
    _audio_elapsed = time.time() - _audio_t0
    print(f"[render] Audio post-processing in {_audio_elapsed:.1f}s (concat demuxer inline)", flush=True)
    print(f"[render] Total render: parallel={_par_elapsed:.1f}s + audio={_audio_elapsed:.1f}s", flush=True)



# ─── MAIN HANDLER ─────────────────────────────────────────────────────────────

def classify_error(e):
    """
    Convert a pipeline exception into a user-facing message.
    Returns a string safe to display directly to the user.
    """
    msg = str(e)

    # File / input problems — user can fix these
    if "No video stream found" in msg:
        return "We couldn't read your video file. Please make sure it's a standard video format (MP4, MOV, or similar)."
    if "Landscape video" in msg:
        return "Promptly works with vertical videos (9:16). Please upload a portrait-orientation clip."

    # Edit generation — no cuts produced
    if "missing cuts array" in msg:
        return "We couldn't generate an edit for this video. Try a different vibe or a longer clip."

    # Analysis problems
    if "Gemini file upload timed out" in msg:
        return "Your video took too long to upload for analysis. Please try again."
    if "Failed to parse Gemini" in msg or "parse Gemini" in msg:
        return "We had trouble analyzing your video. Please try again."

    # Edit recipe problems
    if "Empty Gemini response" in msg or "valid JSON from Gemini" in msg:
        return "We had trouble generating your edit. Please try again."
    if "source_start" in msg or "source_end" in msg or "chronological" in msg:
        return "We had trouble generating your edit. Please try again."

    # Render problems
    if "FFmpeg failed" in msg or "Pre-split mismatch" in msg:
        return "We had trouble rendering your video. Please try again."

    # Config / internal — user can't fix, keep it vague
    return "Something went wrong. Please try again."


def send_progress(job_id, step, pct, message, app_url):
    """
    POST progress update to the JS server. Fire-and-forget in background thread.
    Never blocks the main pipeline — progress updates are best-effort only.
    """
    if not app_url:
        return
    import threading
    def _fire():
        try:
            requests.post(
                f"{app_url}/api/modal-progress",
                json={"job_id": job_id, "step": step, "pct": pct, "message": message},
                timeout=3,
            )
        except Exception:
            pass
    threading.Thread(target=_fire, daemon=True).start()


def handler(job):
    input_data = job["input"]
    work_dir = None
    try:
        app_url = os.environ.get("APP_URL", "").rstrip("/")

        required = ["job_id","video_url","vibe","user_id","upload_url"]
        missing = [f for f in required if not input_data.get(f)]
        if missing:
            return {"error": f"Missing required input fields: {', '.join(missing)}"}

        job_id    = input_data["job_id"]
        video_url = input_data["video_url"]
        vibe      = input_data["vibe"]
        upload_url = input_data["upload_url"]

        work_dir    = tempfile.mkdtemp(prefix=f"promptly-{job_id}-")
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id}: \"{vibe}\"", flush=True)
        print(f"{'='*80}", flush=True)
        _pipeline_start = time.time()
        _timings = {}
        ensure_caption_fonts_registered()

        # Step 1 — Download (S3 internal network if available, HTTP fallback)
        send_progress(job_id, "download", 5, "Got your video, loading it in...", app_url)
        t = time.time()
        print("[pipeline] step=download", flush=True)
        _dl_method = "http"
        if _s3_client:
            _dl_bucket, _dl_key = _parse_supabase_storage_url(video_url)
            if _dl_bucket and _dl_key:
                try:
                    _s3_client.download_file(_dl_bucket, _dl_key, source_path)
                    _dl_method = "s3"
                except Exception as _s3_err:
                    print(f"[pipeline] S3 download failed ({_s3_err}), falling back to HTTP", flush=True)
                    _dl_method = "http"
        if _dl_method == "http":
            r = requests.get(video_url, stream=True, timeout=120)
            r.raise_for_status()
            with open(source_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=4194304):
                    f.write(chunk)
        size_mb = os.path.getsize(source_path) / (1024*1024)
        _timings["download"] = time.time() - t
        print(f"[pipeline] download complete: {size_mb:.1f}MB in {_timings['download']:.1f}s ({_dl_method})", flush=True)

        # Step 2 — ALL initialization in ONE mega-parallel phase
        # Normalize, transcribe, Gemini upload, loudness, beats, edit recipe, face detect
        # all run concurrently. Edit recipe starts as soon as transcript + upload finish
        # (doesn't wait for normalize). Face detect starts when normalize finishes.
        send_progress(job_id, "normalize", 12, "Getting everything set up...", app_url)
        t = time.time()
        print("[pipeline] step=mega-parallel (normalize + transcribe + upload + edit + faces)", flush=True)

        # Quick probe of raw source for duration (needed for face detect timestamps)
        # Uses cached probe — same data reused by analyze_source_video, probe_resolution, etc.
        source_duration = probe_duration(source_path) or 0
        sample_timestamps = [round(i * 4.0, 3) for i in range(int(source_duration / 4.0) + 1)] if source_duration > 0 else []

        # Initialize Gemini client early so we can pre-upload
        _get_genai_client()  # ensures client is ready for upload + generate

        # All 5 operations run in parallel — Deepgram, Gemini upload, loudness,
        # and beats all read from the RAW source (audio is identical pre/post normalize).
        # Unix file semantics keep the raw file accessible even after normalize unlinks it.
        _raw_source = source_path  # raw path — analyze_source_video reads but doesn't modify

        def _do_normalize():
            return analyze_source_video(_raw_source)

        def _do_transcribe():
            audio_path = os.path.join(work_dir, "audio_for_words.ogg")
            _audio_ext = subprocess.run(
                ["ffmpeg", "-threads", "0", "-y", "-i", _raw_source,
                 "-vn", "-c:a", "libopus", "-b:a", "32k", "-ar", "16000", "-ac", "1", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            if _audio_ext.returncode != 0:
                raise RuntimeError(f"FFmpeg audio extraction failed: {(_audio_ext.stderr or '')[-300:]}")
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
                raise RuntimeError(f"FFmpeg produced empty/missing audio file: {audio_path}")
            result = transcribe_audio(audio_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return result

        def _do_gemini_proxy():
            """Encode 240p proxy and return bytes for inline Gemini API call.
            Skips the file upload + poll cycle (~6s) by sending bytes directly."""
            try:
                _proxy_t = time.time()
                _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
                _proxy_venc = (["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "35"]
                               if _HAS_NVENC else
                               ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"])
                _hw_dec = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
                _proxy_cmd = subprocess.run(
                    ["ffmpeg", "-y", "-threads", "0"] + _hw_dec + ["-i", _raw_source,
                     "-vf", "scale=240:-2,fps=10"] + _proxy_venc + [
                     "-c:a", "aac", "-b:a", "32k", "-ac", "1",
                     _proxy_path],
                    capture_output=True, text=True, timeout=30,
                )
                if _proxy_cmd.returncode != 0 or not os.path.exists(_proxy_path):
                    raise RuntimeError(f"Gemini proxy encode failed: {(_proxy_cmd.stderr or '')[-300:]}")
                with open(_proxy_path, "rb") as f:
                    _proxy_bytes = f.read()
                _proxy_mb = len(_proxy_bytes) / (1024 * 1024)
                print(f"[pipeline] Gemini proxy: 240p@10fps {_proxy_mb:.1f}MB in {time.time()-_proxy_t:.1f}s (inline, no upload)", flush=True)
                return _proxy_bytes
            except Exception as e:
                raise RuntimeError(f"Gemini proxy encode failed: {e}") from e

        def _do_loudness():
            return measure_source_loudness(_raw_source)

        def _do_beats():
            return detect_beats(_raw_source)

        # ── ALL initialization + Gemini edit in ONE parallel phase ────────────
        # Gemini starts as soon as transcript + upload + trend context are ready.
        # Everything runs concurrently — no sequential network calls on main thread.
        # If cached_analysis is provided (pre-computed by content-studio), skip the
        # entire Gemini chain (proxy encode + upload + poll + API call = ~19s savings).

        _cached_analysis = input_data.get("cached_analysis")

        # Shared futures — edit recipe and face detect wait on their deps internally
        future_normalize = None
        future_transcribe = None
        future_gemini_proxy = None
        future_trend = None  # trend context fetched in parallel

        def _do_trend_context():
            tc = get_trend_context()
            if not tc:
                print("[trend] WARNING: Style guide not available — Gemini will edit without reference video patterns", flush=True)
            return tc

        def _do_edit_recipe_overlapped():
            """Start Gemini as soon as transcript + proxy + trend are ready."""
            _transcript = future_transcribe.result()
            _proxy_bytes = future_gemini_proxy.result()
            _trend = future_trend.result()
            _dg_words = _transcript.get("words", [])
            if len(_dg_words) == 0:
                print("[pipeline] WARNING: Deepgram returned 0 words — proceeding without speech (no captions, time-based cuts only)", flush=True)
            send_progress(job_id, "edit_recipe", 52, "Putting your edit together...", app_url)
            print(f"[pipeline] Gemini edit starting (transcript ready: {len(_dg_words)} words)", flush=True)
            return generate_edit_gemini(
                video_path=_raw_source,
                vibe=vibe,
                duration=source_duration,
                trend_context=_trend,
                deepgram_words=_dg_words,
                face_positions=None,
                inline_video_bytes=_proxy_bytes,
                cached_response=_cached_analysis,
            )

        def _do_face_detect_overlapped():
            """Run face detection on 240p proxy (much faster than 1080p source).
            Waits for proxy encode (~1.5s), then decodes 240p instead of 1080p (~20x fewer pixels)."""
            send_progress(job_id, "analysis", 20, "Watching your footage...", app_url)
            # Wait for proxy to be encoded (runs in parallel, typically ~1.5s)
            future_gemini_proxy.result()
            _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
            if os.path.exists(_proxy_path):
                # Proxy is 10fps — every 7th frame ≈ 1.4fps detection (similar to every 20th @ 30fps)
                dense = detect_face_positions_dense(
                    _proxy_path, every_n_frames=7,
                    target_w=1080, target_h=1920,
                )
            else:
                # Fallback to source if proxy somehow doesn't exist
                dense = detect_face_positions_dense(_raw_source, every_n_frames=20)
            if dense:
                smoothed = smooth_face_trajectory(dense, total_duration=source_duration)
                print(f"[dense-face] Smoothed trajectory: {len(smoothed)} keyframes", flush=True)
                return dense, smoothed
            return [], []

        # Manual pool management — do NOT use `with` block because it calls
        # shutdown(wait=True) on exit, which would block on future_faces and defeat
        # the deferred face collection optimization (face detection should overlap with Remotion).
        mega_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        future_normalize = mega_pool.submit(_do_normalize)
        future_transcribe = mega_pool.submit(_do_transcribe)
        future_gemini_proxy = mega_pool.submit(_do_gemini_proxy)
        future_trend = mega_pool.submit(_do_trend_context)
        future_loudness = mega_pool.submit(_do_loudness)
        future_beats = mega_pool.submit(_do_beats)
        # Edit recipe waits on transcript + upload internally
        future_edit = mega_pool.submit(_do_edit_recipe_overlapped)
        # Face detection runs directly on raw source (no normalize dependency)
        future_faces = mega_pool.submit(_do_face_detect_overlapped)

        # Collect results — get edit_plan FIRST so we can start B-roll fetch early
        _mega_t0 = time.time()
        edit_plan = future_edit.result()  # critical path — longest wait (Gemini)
        print(f"[TIMING] edit_plan ready in {time.time() - _mega_t0:.1f}s (critical path)", flush=True)

        # Start B-roll fetch IMMEDIATELY while other futures may still be running
        _broll_fetch_pool = None
        _broll_fetch_futures = {}
        broll_clips = edit_plan.get("broll_clips") or []
        if broll_clips:
            print(f"[broll] Starting parallel fetch of {len(broll_clips)} B-roll clip(s) (overlapping with face detect)...", flush=True)
            _broll_fetch_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
            for _bi, _bc in enumerate(broll_clips):
                _fut = _broll_fetch_pool.submit(
                    fetch_broll_clip,
                    _bc["keyword"],
                    float(_bc.get("duration") or 2.0),
                    work_dir,
                    dialogue_reason=str(_bc.get("reason") or ""),
                )
                _broll_fetch_futures[_fut] = _bi

        # Collect fast futures (all should be done already — they finish before Gemini).
        # Face detection is collected LATER inside render_multi_clip so Remotion can
        # launch immediately without waiting for face detection to finish.
        _collect_t0 = time.time()
        source_info = future_normalize.result()
        source_path = source_info["source_path"]
        _normalize_vf = source_info.get("normalize_vf")
        transcript = future_transcribe.result()
        source_loudness = future_loudness.result()
        source_beats = future_beats.result()
        # NOTE: future_faces NOT collected here — passed to render_multi_clip for parallel collection
        _collect_elapsed = time.time() - _collect_t0
        if _collect_elapsed > 0.5:
            print(f"[TIMING] Fast futures collected in {_collect_elapsed:.1f}s", flush=True)
        # Shut down mega_pool WITHOUT waiting for future_faces (it's still running)
        mega_pool.shutdown(wait=False)

        # Source res is what it is — normalize filter will handle conversion in render
        source_res = {"width": source_info["width"], "height": source_info["height"]}
        print(f"[DIAG] Source: {source_res['width']}x{source_res['height']} @ {source_info['fps']:.1f}fps, normalize_vf={'yes' if _normalize_vf else 'no'}", flush=True)

        # Store face transform info for render_multi_clip to use when it collects face_future
        _ft = source_info.get("face_transform", {})
        edit_plan["_face_transform"] = _ft

        _timings["normalize_transcribe_upload"] = time.time() - t
        _dg_words = transcript.get("words", [])
        if len(_dg_words) == 0:
            # Force captions off — no words to display
            edit_plan["caption_style"] = "none"
            print(f"[pipeline] All init complete: 0 words (no speech detected), edit recipe ready ({_timings['normalize_transcribe_upload']:.1f}s)", flush=True)
        else:
            print(f"[pipeline] All init complete: {len(_dg_words)} words, edit recipe ready ({_timings['normalize_transcribe_upload']:.1f}s)", flush=True)

        print(f"[edit] User vibe: \"{vibe}\"", flush=True)

        if _normalize_vf:
            print(f"[reframe] Smart reframe active via normalize_vf (folded into render pass)", flush=True)
        else:
            print("[reframe] Source is native 9:16 — no reframe needed", flush=True)

        edit_plan["_user_vibe"] = vibe
        edit_plan["_source_path"] = source_path
        edit_plan["_normalize_vf"] = _normalize_vf
        edit_plan["_face_positions"] = []  # populated by render_multi_clip from face_future
        edit_plan["_dense_face_trajectory"] = []  # populated by render_multi_clip from face_future
        edit_plan["_source_loudness"] = source_loudness
        edit_plan["_source_beats"] = source_beats
        _timings["edit_recipe_faces"] = 0
        print(f"[pipeline] Pipeline init phase complete", flush=True)

        # ── Auto-hook detection: validate/override Gemini's hook_clip ─────
        try:
            _ahook_emphasis = edit_plan.get("_emphasis_moments") or []
            _ahook_dg_words = edit_plan.get("_deepgram_words") or []
            _ahook_duration = float(edit_plan.get("analysis_data", {}).get("duration") or source_duration or 0)
            auto_hook, auto_hook_score = auto_detect_hook(
                emphasis_moments=_ahook_emphasis,
                deepgram_words=_ahook_dg_words,
                source_beats=source_beats,
                source_loudness=source_loudness,
                video_duration=_ahook_duration,
            )
            gemini_hook = edit_plan.get("hook_clip")
            if auto_hook:
                if not isinstance(gemini_hook, dict):
                    # Gemini didn't provide a hook — use auto-detected
                    edit_plan["hook_clip"] = auto_hook
                    print(f"[hook] Gemini picked None, auto-detected "
                          f"{auto_hook['source_start']:.2f}-{auto_hook['source_end']:.2f} "
                          f"(score {auto_hook_score:.2f}), using auto", flush=True)
                else:
                    # Gemini provided a hook — score it and compare
                    gemini_t = (float(gemini_hook["source_start"]) + float(gemini_hook["source_end"])) / 2.0
                    gemini_moment_score = 0.0
                    # Find the emphasis moment closest to Gemini's hook and get its score
                    _best_gem_dist = float("inf")
                    for _em in _ahook_emphasis:
                        _d = abs(float(_em["t"]) - gemini_t)
                        if _d < _best_gem_dist:
                            _best_gem_dist = _d
                            # Re-score this moment using the same logic
                            _gem_bucket = int(float(_em["t"]))
                            _gem_type_scores = {"punchline": 10, "revelation": 8, "reaction": 6, "question": 5, "statement": 4, "transition": 2}
                            _gem_base = _gem_type_scores.get(_em.get("type", "statement"), 4)
                            gemini_moment_score = _gem_base * (1.0 if _em.get("intensity") == "high" else 0.5) * 0.35
                            # Add position component
                            if _ahook_duration > 0:
                                _gem_rel = float(_em["t"]) / _ahook_duration
                                if 0.25 <= _gem_rel <= 0.75:
                                    gemini_moment_score += 10.0 * 0.15
                                elif 0.15 <= _gem_rel <= 0.85:
                                    gemini_moment_score += 5.0 * 0.15

                    # Always trust Gemini's hook selection — it understands content semantics
                    # (e.g., "who the fuck is Stelius?" is a better hook than a setup line)
                    print(f"[hook] Gemini picked {gemini_hook['source_start']:.2f}-{gemini_hook['source_end']:.2f}, "
                          f"auto-detected {auto_hook['source_start']:.2f}-{auto_hook['source_end']:.2f} "
                          f"(score {auto_hook_score:.2f} vs {gemini_moment_score:.2f}), using Gemini", flush=True)
            else:
                _gh = gemini_hook if isinstance(gemini_hook, dict) else None
                _gh_str = f"{_gh['source_start']:.2f}-{_gh['source_end']:.2f}" if _gh else "None"
                print(f"[hook] Gemini picked {_gh_str}, auto-detected None, using Gemini", flush=True)
        except Exception as _hook_err:
            print(f"[hook-auto] Auto-hook detection failed ({_hook_err}) — keeping Gemini's choice", flush=True)
        analysis = edit_plan.get("analysis_data") or {}

        # B-roll fetch already started inside mega-parallel phase (right after edit_plan ready)

        print("[pipeline] step=parallel_render", flush=True)
        send_progress(job_id, "render", 62, "Rendering — almost there...", app_url)
        t = time.time()
        render_multi_clip(
            source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
            broll_clips=broll_clips, broll_fetch_futures=_broll_fetch_futures,
            face_future=future_faces,
        )
        if _broll_fetch_pool:
            _broll_fetch_pool.shutdown(wait=False)
        edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        _timings["render"] = render_elapsed
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        _enc_label = "NVENC" if _HAS_NVENC else "libx264/ultrafast threads=auto"
        print(f"[render] Encoding: {_enc_label}", flush=True)
        speed_curve = edit_plan.get("_parsed_speed_curve")
        # Validate render output — single ffprobe for file check + duration extraction
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100000:
            raise RuntimeError(f"Main render produced invalid output: {output_path}")
        _rv, _ra = 0.0, 0.0
        try:
            probe_cache_clear(output_path)  # freshly rendered — clear stale cache
            _cp = _probe_full(output_path)
            for _s in (_cp.get("streams") or []):
                if _s.get("codec_type") == "video" and _s.get("duration"):
                    _rv = float(_s["duration"])
                elif _s.get("codec_type") == "audio" and _s.get("duration"):
                    _ra = float(_s["duration"])
        except Exception:
            pass
        if _rv < 1.0:
            raise RuntimeError(f"Main render output too short: video={_rv:.1f}s")
        print(f"[render] Output valid: {os.path.getsize(output_path)/1024/1024:.1f}MB, video={_rv:.1f}s audio={_ra:.1f}s", flush=True)

        cuts = edit_plan.get("_render_cuts") or edit_plan.get("cuts") or []
        effective_durations = edit_plan.get("_render_effective_durations") or compute_effective_durations(cuts, speed_curve)
        final_dur = _rv

        # B-roll is now integrated into the first FFmpeg pass (no second encode needed)
        _timings["broll"] = 0.0

        # ── Parallel group 2: cover frame + upload ────────────────────────────────
        t = time.time()
        thumbnail_source_ts = edit_plan.get("thumbnail_timestamp")
        if thumbnail_source_ts is None:
            thumbnail_source_ts = (source_duration / 3.0) if source_duration > 0 else 1.0
        speed_curve = edit_plan.get("_parsed_speed_curve")
        cover_frame_ts = project_source_time_to_final_output(
            float(thumbnail_source_ts),
            cuts,
            effective_durations,
            speed_curve,
            clip_time_maps=edit_plan.get("_render_clip_time_maps"),
        )
        if cover_frame_ts is None:
            cover_frame_ts = min(1.0, max(0.1, final_dur - 0.1))
        cover_frame_b64  = None
        cover_frame_mime = "image/jpeg"

        if not validate_output(output_path, "final"):
            raise RuntimeError(f"Final output is invalid: {output_path}")
        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        send_progress(job_id, "upload", 90, "Just about done...", app_url)
        print(f"[pipeline] output: {output_size_mb:.1f}MB, {final_dur:.1f}s — parallel upload + cover frame", flush=True)

        def _upload_main():
            print("[pipeline] step=upload", flush=True)
            _ul_method = "http"
            if _s3_client:
                _ul_bucket, _ul_key = _parse_supabase_storage_url(upload_url)
                if _ul_bucket and _ul_key:
                    try:
                        _s3_client.upload_file(
                            output_path, _ul_bucket, _ul_key,
                            ExtraArgs={"ContentType": "video/mp4"},
                        )
                        _ul_method = "s3"
                    except Exception as _s3_err:
                        print(f"[pipeline] S3 upload failed ({_s3_err}), falling back to HTTP", flush=True)
                        _ul_method = "http"
            if _ul_method == "http":
                with open(output_path, "rb") as f:
                    resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                    resp.raise_for_status()
            print(f"[pipeline] upload complete ({_ul_method})", flush=True)

        def _extract_and_upload_cover():
            # Pick the visually best frame from the FINAL RENDERED OUTPUT around
            # Gemini's projected timestamp. The output has captions burned in,
            # speed warps applied, and zoom effects — exactly what makes a great
            # social-media thumbnail. NO additional post-processing.
            #
            # If Gemini's seed lands inside a b-roll segment, shift it to the
            # nearest moment showing the speaker (not the b-roll content).
            _thumb_seed = float(cover_frame_ts)
            _broll_ranges = edit_plan.get("_broll_output_ranges") or []
            for _br_start, _br_end in _broll_ranges:
                if _br_start <= _thumb_seed <= _br_end:
                    # Shift to whichever side of the b-roll is closer
                    _dist_before = _thumb_seed - _br_start
                    _dist_after = _br_end - _thumb_seed
                    if _dist_before <= _dist_after:
                        _thumb_seed = max(0.1, _br_start - 0.3)
                    else:
                        _thumb_seed = min(final_dur - 0.1, _br_end + 0.3)
                    print(
                        f"[thumbnail] Seed was inside b-roll [{_br_start:.2f}, {_br_end:.2f}], "
                        f"shifted to {_thumb_seed:.2f}s",
                        flush=True,
                    )
                    break
            try:
                data, mime = select_best_thumbnail_frame(
                    output_path, _thumb_seed, work_dir,
                )
            except Exception as _thumb_err:
                # Last-resort fallback: extract a single frame at the seed timestamp
                # without any scoring. Should be very rare (only triggers on cv2/ffprobe
                # failures, not on bad-quality frames).
                print(f"[thumbnail] WARNING: scorer failed ({_thumb_err}) — using seed frame", flush=True)
                _fallback_path = os.path.join(work_dir, "thumbnail_fallback.jpg")
                _r = subprocess.run(
                    ["ffmpeg", "-y", "-v", "warning",
                     "-ss", f"{_thumb_seed:.3f}", "-i", output_path,
                     "-frames:v", "1", "-q:v", "2", _fallback_path],
                    capture_output=True, text=True, timeout=10,
                )
                if _r.returncode != 0 or not os.path.exists(_fallback_path):
                    raise RuntimeError(f"Thumbnail fallback failed: {(_r.stderr or '')[-300:]}")
                with open(_fallback_path, "rb") as f:
                    data = f.read()
                try:
                    os.unlink(_fallback_path)
                except Exception:
                    pass
                mime = "image/jpeg"
            if data:
                print(
                    f"[pipeline] cover frame at {cover_frame_ts:.2f}s "
                    f"(AI-selected from source {float(thumbnail_source_ts):.2f}s, {len(data)//1024}KB)",
                    flush=True,
                )
                # Upload thumbnail in parallel with main video upload
                upload_url_thumb = input_data.get("upload_url_thumb")
                if upload_url_thumb:
                    _thumb_uploaded = False
                    if _s3_client:
                        _tb, _tk = _parse_supabase_storage_url(upload_url_thumb)
                        if _tb and _tk:
                            try:
                                import io as _io_thumb
                                _s3_client.upload_fileobj(
                                    _io_thumb.BytesIO(data), _tb, _tk,
                                    ExtraArgs={"ContentType": mime},
                                )
                                print("[pipeline] thumbnail uploaded (s3)", flush=True)
                                _thumb_uploaded = True
                            except Exception as _s3_thumb_err:
                                print(f"[pipeline] S3 thumbnail upload failed ({_s3_thumb_err}), falling back to HTTP", flush=True)
                    if not _thumb_uploaded:
                        try:
                            thumb_resp = requests.put(
                                upload_url_thumb, data=data,
                                headers={"Content-Type": mime}, timeout=30,
                            )
                            thumb_resp.raise_for_status()
                            print("[pipeline] thumbnail uploaded (http)", flush=True)
                        except Exception as thumb_err:
                            print(f"[pipeline] thumbnail upload failed (non-fatal): {thumb_err}", flush=True)
                else:
                    print("[pipeline] thumbnail: no upload_url_thumb provided by frontend", flush=True)
            return data, mime

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as post_executor:
            f_upload = post_executor.submit(_upload_main)
            f_cover  = post_executor.submit(_extract_and_upload_cover)
            f_upload.result()
            cover_bytes, _ = f_cover.result()

        if cover_bytes:
            import base64
            cover_frame_b64 = base64.b64encode(cover_bytes).decode()

        # Step 13.5 — Additional format exports (parallelized)
        export_formats   = input_data.get("export_formats") or []
        exported_formats = []

        def _export_and_upload(fmt):
            ar  = str(fmt.get("aspect_ratio") or "").strip()
            url = str(fmt.get("upload_url") or "").strip()
            if not ar or not url:
                return None
            fmt_path = os.path.join(work_dir, f"output_{ar.replace(':','x')}.mp4")
            export_additional_format(output_path, ar, fmt_path)
            _fmt_uploaded = False
            if _s3_client:
                _fb, _fk = _parse_supabase_storage_url(url)
                if _fb and _fk:
                    try:
                        _s3_client.upload_file(fmt_path, _fb, _fk, ExtraArgs={"ContentType": "video/mp4"})
                        _fmt_uploaded = True
                    except Exception:
                        pass
            if not _fmt_uploaded:
                with open(fmt_path, "rb") as f:
                    fmt_resp = requests.put(url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                    fmt_resp.raise_for_status()
            fmt_size = os.path.getsize(fmt_path) / (1024 * 1024)
            print(f"[pipeline] exported {ar} ({fmt_size:.1f}MB) -> uploaded", flush=True)
            return {"aspect_ratio": ar, "size_mb": round(fmt_size, 1)}

        if export_formats:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(export_formats))) as fmt_executor:
                fmt_futures = {fmt_executor.submit(_export_and_upload, fmt): fmt for fmt in export_formats}
                for future in concurrent.futures.as_completed(fmt_futures):
                    try:
                        result = future.result()
                        if result:
                            exported_formats.append(result)
                    except Exception as fmt_err:
                        print(f"[pipeline] format export failed (non-fatal): {fmt_err}", flush=True)

        _timings["upload_export"] = time.time() - t
        _timings["total"] = time.time() - _pipeline_start

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id} COMPLETE — {_timings['total']:.1f}s total", flush=True)
        print(f"  download:    {_timings.get('download', 0):.1f}s", flush=True)
        print(f"  norm+tx+up:  {_timings.get('normalize_transcribe_upload', 0):.1f}s", flush=True)
        print(f"  edit+faces:  {_timings.get('edit_recipe_faces', 0):.1f}s", flush=True)
        print(f"  render:      {_timings.get('render', 0):.1f}s", flush=True)
        print(f"  broll:       {_timings.get('broll', 0):.1f}s", flush=True)
        print(f"  upload+exp:  {_timings.get('upload_export', 0):.1f}s", flush=True)
        print(f"{'='*80}\n", flush=True)

        send_progress(job_id, "complete", 100, "Your video is ready!", app_url)

        result_payload = {
            "status": "success",
            "job_id": job_id,
            "render_time": round(render_elapsed, 1),
            "pipeline_time": round(_timings.get("total", 0), 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": {k: v for k, v in edit_plan.items() if k != "analysis_data" and not k.startswith("_")},
            "cover_frame_timestamp": round(cover_frame_ts, 3),
            "thumbnail_timestamp": round(float(thumbnail_source_ts), 3),
        }
        if cover_frame_b64:
            result_payload["cover_frame_b64"]  = cover_frame_b64
            result_payload["cover_frame_mime"] = "image/jpeg"
        if exported_formats:
            result_payload["exported_formats"] = exported_formats
        return result_payload

    except Exception as e:
        import traceback
        traceback.print_exc()
        user_message = classify_error(e)
        return {"error": user_message, "error_detail": str(e)}

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


# Modal entrypoint — handler() is called directly by modal_app.py
# To test locally: python3 handler.py
if __name__ == "__main__":
    print("[handler] Running in local test mode", flush=True)
