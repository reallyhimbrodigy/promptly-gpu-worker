# Modal worker entrypoint
import subprocess
import os
import sys
import ssl
import glob
import requests
import tempfile
import time
import shutil
import json
import re
import concurrent.futures
from datetime import datetime
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

HANDLER_VERSION = "3.0.0"
GEMINI_MODEL = "gemini-2.5-flash"

print(f"[startup] Python {sys.version}", flush=True)
print(f"[startup] handler version: {HANDLER_VERSION}", flush=True)
print(f"[startup] Gemini model: {GEMINI_MODEL}", flush=True)

try:
    import google.generativeai as genai
    print("[startup] google.generativeai OK", flush=True)
except Exception as e:
    print(f"[startup] google.generativeai FAILED: {e}", flush=True)

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
_HAS_DRAWTEXT = False
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
    if "drawtext" in _ff_filters:
        _HAS_DRAWTEXT = True
        print("[startup] FFmpeg drawtext filter: available", flush=True)
    else:
        print("[startup] WARNING: FFmpeg drawtext filter NOT available — text overlays will be skipped", flush=True)
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

    _nvenc_check = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True, timeout=5,
    )
    if "h264_nvenc" in (_nvenc_check.stdout or ""):
        # Verify actual GPU access with a tiny encode to a real file
        # Using -f null can fail on some driver versions; write to a temp file instead
        import tempfile as _tmpmod
        _nvenc_tmp = os.path.join(_tmpmod.gettempdir(), "_nvenc_test.mp4")
        _gpu_test = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1:r=30",
             "-c:v", "h264_nvenc", "-gpu", "0", "-preset", "p1", _nvenc_tmp],
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
            _full_err = (_gpu_test.stderr or "")
            # Print last 800 chars to capture the full error chain
            print(f"[startup] NVENC test failed — using CPU encoder", flush=True)
            print(f"[startup] NVENC error: {_full_err[-800:]}", flush=True)
            _encode_libs = []
            for _ld in _nvidia_lib_dirs:
                try:
                    _encode_libs.extend(f for f in os.listdir(_ld) if "encode" in f.lower() or "cuda.so" in f.lower())
                except Exception:
                    pass
            print(f"[startup] Encode libs found: {sorted(set(_encode_libs))}", flush=True)
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


def get_encode_args(quality="high"):
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
        if quality == "lossless":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "0"]
        else:
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-maxrate", "15M", "-bufsize", "30M"]

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

Follow these patterns closely. The example edits show exactly how speed ramping, cuts, and pacing should be applied. Match the techniques you see in these examples — they are the standard.

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
OVERLAY_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Montserrat-Black.ttf")
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


def sample_background_brightness(video_path, timestamp, y_fraction=0.13):
    """Sample average brightness at a vertical region of a frame.

    Used to choose text overlay colors that contrast with the actual
    background. Returns 0-255 (0=black, 255=white). Defaults to 128
    if frame sampling fails.
    """
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 128
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return 128
    h, w = frame.shape[:2]
    y_px = int(y_fraction * h)
    y_start = max(0, y_px - 60)
    y_end = min(h, y_px + 60)
    strip = frame[y_start:y_end, :]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    avg = float(gray.mean())
    print(f"[overlay] Background brightness at y={y_fraction:.2f} t={timestamp:.2f}s: {avg:.0f}/255", flush=True)
    return avg


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


def detect_face_positions_dense(video_path, every_n_frames=5):
    """
    Dense face detection: read every Nth frame sequentially (no seeking) for
    smooth face tracking.  At every_n_frames=5 on 30fps video this gives 6fps
    detection — roughly 360 detections for a 60s clip at ~3ms each (<3s total).

    Returns list of {"t": float, "cx": float, "cy": float, "found": bool, "confidence": float}.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[dense-face] Could not open video for dense face detection", flush=True)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    center_x = frame_w // 2 if frame_w > 0 else 540
    center_y = frame_h // 2 if frame_h > 0 else 960

    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    if not (os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)):
        print("[dense-face] DNN model not found, cannot run dense detection", flush=True)
        return []

    net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    CONFIDENCE_THRESHOLD = 0.5

    last_cx, last_cy = center_x, center_y
    positions = []
    frame_idx = 0
    _t_start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if frame_idx % every_n_frames == 0:
            t_sec = frame_idx / fps
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
                x1 = int(detections[0, 0, det_i, 3] * w)
                y1 = int(detections[0, 0, det_i, 4] * h)
                x2 = int(detections[0, 0, det_i, 5] * w)
                y2 = int(detections[0, 0, det_i, 6] * h)
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

        frame_idx += 1

    cap.release()
    elapsed = time.time() - _t_start
    found_count = sum(1 for p in positions if p["found"])
    print(
        f"[dense-face] {found_count}/{len(positions)} detections in {elapsed:.2f}s "
        f"({frame_count} total frames, every {every_n_frames}th @ {fps:.1f}fps)",
        flush=True,
    )
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


def get_face_position_at_time(face_trajectory, t):
    """
    Binary-search the smoothed trajectory for time *t* and linearly interpolate
    between the two nearest entries.

    Returns (cx, cy, found, confidence).
    """
    if not face_trajectory:
        return (540.0, 960.0, False, 0.0)

    # Binary search for right-insertion point
    lo, hi = 0, len(face_trajectory)
    while lo < hi:
        mid = (lo + hi) // 2
        if face_trajectory[mid]["t"] < t:
            lo = mid + 1
        else:
            hi = mid
    # lo = index of first entry with t >= query t
    if lo == 0:
        e = face_trajectory[0]
        return (e["cx"], e["cy"], e["found"], e.get("confidence", 0.0))
    if lo >= len(face_trajectory):
        e = face_trajectory[-1]
        return (e["cx"], e["cy"], e["found"], e.get("confidence", 0.0))

    a = face_trajectory[lo - 1]
    b = face_trajectory[lo]
    dt = b["t"] - a["t"]
    if dt <= 0:
        return (b["cx"], b["cy"], b["found"], b.get("confidence", 0.0))

    frac = (t - a["t"]) / dt
    frac = max(0.0, min(1.0, frac))
    cx = a["cx"] + (b["cx"] - a["cx"]) * frac
    cy = a["cy"] + (b["cy"] - a["cy"]) * frac
    conf = a.get("confidence", 0.0) + (b.get("confidence", 0.0) - a.get("confidence", 0.0)) * frac
    found = a["found"] or b["found"]
    return (round(cx, 2), round(cy, 2), found, round(conf, 4))


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


def build_dynamic_crop_expr(smoothed_positions, source_w, source_h, target_w=1080, target_h=1920):
    """
    Build a dynamic FFmpeg crop expression that follows the face over time.
    Uses piecewise linear interpolation between keyframes in FFmpeg expression syntax.

    Returns (crop_w, crop_h, x_expr, y_expr) or None if source is already 9:16.
    The expressions use FFmpeg's 't' variable (time in seconds).
    """
    if source_w == target_w and source_h == target_h:
        return None
    if not smoothed_positions or len(smoothed_positions) < 2:
        return None

    target_aspect = target_w / target_h
    source_aspect = source_w / source_h if source_h else target_aspect

    if source_aspect > target_aspect:
        crop_h = source_h
        crop_w = int(source_h * target_aspect)
    else:
        crop_w = source_w
        crop_h = int(source_w / target_aspect) if target_aspect else source_h

    max_x = max(0, source_w - crop_w)
    max_y = max(0, source_h - crop_h)

    # Convert face positions to crop positions, clamped
    keyframes = []
    for pos in smoothed_positions:
        cx = int(pos["cx"] - crop_w // 2)
        cy = int(pos["cy"] - crop_h // 2)
        cx = max(0, min(cx, max_x))
        cy = max(0, min(cy, max_y))
        keyframes.append((float(pos["t"]), cx, cy))

    # Subsample: only keep keyframes where position changes significantly
    # This reduces expression length from hundreds to ~20-50 keyframes
    MIN_MOVE_PX = 8  # ignore movements smaller than 8px
    reduced = [keyframes[0]]
    for kf in keyframes[1:]:
        prev = reduced[-1]
        dx = abs(kf[1] - prev[1])
        dy = abs(kf[2] - prev[2])
        if dx > MIN_MOVE_PX or dy > MIN_MOVE_PX:
            reduced.append(kf)
    # Always include the last keyframe
    if reduced[-1] != keyframes[-1]:
        reduced.append(keyframes[-1])
    keyframes = reduced

    if len(keyframes) < 2:
        # Static — no movement
        return (crop_w, crop_h, str(keyframes[0][1]), str(keyframes[0][2]))

    # Build piecewise linear FFmpeg expression
    # Pattern: if(lt(t,t1), lerp(v0,v1,(t-t0)/(t1-t0)), if(lt(t,t2), lerp(...), vN))
    def _build_expr(keyframes, val_idx):
        """Build nested if expression for x (val_idx=1) or y (val_idx=2)."""
        n = len(keyframes)
        if n == 1:
            return str(keyframes[0][val_idx])

        # Build from the last segment backwards (innermost = last value)
        expr = str(keyframes[-1][val_idx])
        for i in range(n - 2, -1, -1):
            t0, v0 = keyframes[i][0], keyframes[i][val_idx]
            t1, v1 = keyframes[i + 1][0], keyframes[i + 1][val_idx]
            dt = t1 - t0
            if dt <= 0 or v0 == v1:
                # No movement in this segment — just use the value
                segment = str(v0)
            else:
                # lerp: v0 + (v1-v0) * (t-t0)/(t1-t0)
                segment = f"{v0}+{v1-v0}*(t-{t0:.3f})/{dt:.3f}"
            expr = f"if(lt(t,{t1:.3f}),{segment},{expr})"
        return expr

    x_expr = _build_expr(keyframes, 1)
    y_expr = _build_expr(keyframes, 2)

    print(
        f"[reframe] Dynamic crop: {len(keyframes)} keyframes, "
        f"expr_len={len(x_expr)+len(y_expr)} chars",
        flush=True,
    )

    return (crop_w, crop_h, x_expr, y_expr)

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
    """Extract audio beat timestamps using FFmpeg + aubio if available, fallback to energy-based."""
    try:
        import aubio
        import numpy as np

        # Extract raw audio via ffmpeg → aubio
        cmd = [
            "ffmpeg", "-i", source_path,
            "-f", "f32le", "-ac", "1", "-ar", "44100", "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw = proc.stdout.read()
        proc.wait()

        samplerate = 44100
        hop_size   = 512
        win_size   = 1024
        samples    = np.frombuffer(raw, dtype="float32")

        tempo_detect = aubio.tempo("default", win_size, hop_size, samplerate)
        beats = []
        for i in range(0, len(samples) - hop_size, hop_size):
            chunk = samples[i:i + hop_size]
            if tempo_detect(chunk):
                beats.append(round(i / samplerate, 3))

        print(f"[beats] aubio detected {len(beats)} beats", flush=True)
        return beats

    except Exception as aubio_err:
        print(f"[beats] aubio unavailable ({aubio_err}), falling back to energy-based detection", flush=True)

    # Fallback: energy-based transient detection via FFmpeg silencedetect + astats
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", source_path,
             "-af", "aresample=22050,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=60
        )
        rms_vals = []
        times    = []
        for line in result.stderr.splitlines():
            m = re.search(r"pts_time:([\d.]+)", line)
            if m:
                times.append(float(m.group(1)))
            m2 = re.search(r"RMS_level=([\d.\-]+)", line)
            if m2:
                rms_vals.append(float(m2.group(1)))

        if len(rms_vals) > 4:
            avg = sum(rms_vals) / len(rms_vals)
            beats = []
            min_gap = 0.3
            last_beat = -1.0
            for i, (t, r) in enumerate(zip(times, rms_vals)):
                if r > avg * 1.4 and (t - last_beat) > min_gap:
                    beats.append(round(t, 3))
                    last_beat = t
            print(f"[beats] energy fallback detected {len(beats)} transients", flush=True)
            return beats
    except Exception as e:
        print(f"[beats] energy fallback failed: {e}", flush=True)

    return []


def detect_scene_cuts(video_path, threshold=3):
    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf", f"scdet=threshold={threshold}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120
    )
    cuts = []
    for m in re.finditer(r"lavfi\.scd\.time:\s*([\d.]+)", result.stderr):
        t = float(m.group(1))
        if t > 0.5:
            cuts.append(round(t * 1000) / 1000)
    print(f"[scdet] Detected {len(cuts)} visual cuts: {cuts}", flush=True)
    return cuts


# ─── DEEPGRAM TRANSCRIPTION ───────────────────────────────────────────────────

def build_speech_from_deepgram(words, duration):
    if not words:
        if duration > 0:
            return {
                "speech": {"has_speech": False, "speaker_style": "", "segments": [], "sentence_boundaries": []},
                "safe_cut_points": [{"time": 0, "quality": 1, "why": "Video start"}, {"time": round(duration * 1000) / 1000, "quality": 1, "why": "Video end"}],
            }
        return {"speech": {"has_speech": False, "speaker_style": "", "segments": [], "sentence_boundaries": []}, "safe_cut_points": []}

    segments = []
    boundaries = []
    seg_start = words[0]["start"]
    seg_words = []

    for i, w in enumerate(words):
        seg_words.append(w)
        pw = w.get("punctuated_word") or w.get("word") or ""
        is_sentence_end = bool(re.search(r"[.!?]$", pw))
        has_long_pause = (i < len(words) - 1) and (words[i + 1]["start"] - w["end"] > 0.3)
        is_last_word = (i == len(words) - 1)

        if is_sentence_end or has_long_pause or is_last_word:
            seg_text = " ".join(sw.get("punctuated_word") or sw.get("word") or "" for sw in seg_words)
            seg_end = round(w["end"] * 1000) / 1000
            segments.append({
                "start": round(seg_start * 1000) / 1000,
                "end": seg_end,
                "text": seg_text,
                "emotion": "informative",
                "energy_level": 0.7,
                "notes": "",
            })
            if i < len(words) - 1:
                next_word = words[i + 1]
                pause_after = round((next_word["start"] - w["end"]) * 1000) / 1000
                boundaries.append({"time": seg_end, "pause_after": max(0, pause_after), "context": ""})
                seg_start = next_word["start"]
                seg_words = []

    safe_cut_points = [{"time": 0, "quality": 1, "why": "Video start"}]
    for b in boundaries:
        safe_cut_points.append({
            "time":    b["time"],
            "quality": 0.9 if b["pause_after"] > 0.3 else 0.8,
            "why":     "sentence end, breath gap" if b["pause_after"] > 0.3 else "sentence end",
        })
    if duration:
        safe_cut_points.append({"time": round(duration * 1000) / 1000, "quality": 1, "why": "Video end"})

    return {
        "speech": {"has_speech": True, "speaker_style": "", "segments": segments, "sentence_boundaries": boundaries},
        "safe_cut_points": safe_cut_points,
    }


def transcribe_audio(source_path):
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    try:
        dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
        with open(source_path, "rb") as f:
            audio_bytes = f.read()
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
        print(f"[pipeline] transcription failed: {e}", flush=True)
        return {"text": "", "words": []}




# ─── TIGHTEN ──────────────────────────────────────────────────────────────────

ALWAYS_FILLER = {"um","uh","uhh","uhm","umm","erm","er","hmm","hm","mm","mmm","mhm","ah","ahh","huh"}
CONTEXT_FILLER = {"like","right","so","basically","literally","actually","honestly","obviously","just","really"}
MULTI_WORD_FILLER = [["you","know"],["i","mean"],["kind","of"],["sort","of"]]


def normalize_token(raw):
    return re.sub(r"[^a-z]", "", str(raw or "").lower().replace("'","").replace('"',""))


def detect_filler_words(words):
    fillers = []
    i = 0
    while i < len(words):
        w = words[i]
        text = normalize_token(w.get("word") or w.get("punctuated_word") or "")
        gap_before = (w["start"] - words[i-1]["end"]) if i > 0 else 999
        gap_after  = (words[i+1]["start"] - w["end"]) if i < len(words)-1 else 999

        if text in ALWAYS_FILLER:
            fillers.append({"start": w["start"], "end": w["end"], "word": w.get("word", text), "reason": "always-filler"})
            i += 1
            continue

        matched_multi = False
        for phrase in MULTI_WORD_FILLER:
            if i + len(phrase) > len(words):
                continue
            if all(normalize_token(words[i+j].get("word") or words[i+j].get("punctuated_word") or "") == phrase[j] for j in range(len(phrase))):
                phrase_start = words[i]["start"]
                phrase_end   = words[i+len(phrase)-1]["end"]
                pg_before = (phrase_start - words[i-1]["end"]) if i > 0 else 999
                pg_after  = (words[i+len(phrase)]["start"] - phrase_end) if i+len(phrase) < len(words) else 999
                if pg_before >= 0.08 and pg_after >= 0.08:
                    fillers.append({"start": phrase_start, "end": phrase_end, "word": " ".join(phrase), "reason": "multi-word-filler"})
                    i += len(phrase)
                    matched_multi = True
                break
        if matched_multi:
            continue

        if text in CONTEXT_FILLER and gap_before >= 0.08 and gap_after >= 0.08:
            fillers.append({"start": w["start"], "end": w["end"], "word": w.get("word", text), "reason": "context-filler"})
        i += 1
    return fillers


def detect_silence_regions(source_path, silence_db=-40, min_silence_duration=0.2):
    """
    Use ffmpeg silencedetect to find actual silent regions in the audio.
    Returns list of {"start": float, "end": float} dicts.
    silence_db: threshold in dB below which audio is considered silent
    min_silence_duration: minimum duration in seconds to count as silence
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-f", "lavfi",
            "-i", f"amovie={source_path},silencedetect=noise={silence_db}dB:d={min_silence_duration}",
            "-show_entries", "frame_tags=lavfi.silence_start,lavfi.silence_end",
            "-of", "csv=p=0"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        regions = []
        current_start = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if "silence_start" in part:
                    try:
                        current_start = float(part.split("=")[-1])
                    except ValueError:
                        pass
                elif "silence_end" in part and current_start is not None:
                    try:
                        end = float(part.split("=")[-1])
                        regions.append({"start": current_start, "end": end})
                        current_start = None
                    except ValueError:
                        pass
        # Handle unclosed silence at end of file
        if current_start is not None:
            regions.append({"start": current_start, "end": 999999})
        return regions
    except Exception as e:
        print(f"[silence_detect] failed: {e}", flush=True)
        return []


def measure_source_loudness(source_path):
    """
    Measure the source audio's peak level, RMS, and noise floor using ffmpeg.
    Returns dict with 'peak_db', 'rms_db', 'noise_floor_db' (all negative floats).
    Falls back to safe defaults if measurement fails.
    """
    defaults = {"peak_db": -6.0, "rms_db": -18.0, "noise_floor_db": -45.0}
    try:
        # astats gives us peak, RMS; we sample the first 60s to keep it fast
        cmd = [
            "ffmpeg", "-i", source_path, "-t", "60",
            "-af", "astats=metadata=1:reset=0,ametadata=mode=print",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stderr = result.stderr

        # Parse peak and RMS from astats output
        peak_matches = re.findall(r"lavfi\.astats\.Overall\.Peak_level=([-\d.]+)", stderr)
        rms_matches = re.findall(r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", stderr)
        noise_matches = re.findall(r"lavfi\.astats\.Overall\.Noise_floor=([-\d.]+)", stderr)

        peak_db = float(peak_matches[-1]) if peak_matches else defaults["peak_db"]
        rms_db = float(rms_matches[-1]) if rms_matches else defaults["rms_db"]
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
    except Exception as e:
        print(f"[loudness] measurement failed ({e}) — using defaults", flush=True)
        return defaults


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


def tighten_transcript(words, scene_cuts=None, shots=None, original_duration=0, source_path=None, noise_floor_db=None):
    scene_cuts = scene_cuts or []
    min_segment = 0.3
    breath_pad = 0.08  # Leave natural breath on each side of a silence region

    if not words:
        if original_duration > 0:
            return {"segments": [{"start": 0, "end": round(original_duration*1000)/1000}], "removedSeconds": 0, "timeline_map": [], "tightened_duration": original_duration}
        return {"segments": [], "removedSeconds": 0, "timeline_map": [], "tightened_duration": 0}

    fillers = detect_filler_words(words)
    filler_keys = {f"{round(f['start']*1000)/1000}-{round(f['end']*1000)/1000}" for f in fillers}
    keep_words = [w for w in words if f"{round(w['start']*1000)/1000}-{round(w['end']*1000)/1000}" not in filler_keys]
    if not keep_words:
        return {"segments": [], "removedSeconds": 0, "timeline_map": [], "tightened_duration": 0}

    first = 0
    last = keep_words[-1]["end"] + 0.15
    if original_duration > 0:
        last = min(last, original_duration)

    # Use actual silence detection if source_path available
    # Adaptive threshold: set silence detection ~5dB above measured noise floor
    # so we catch dead air without cutting into quiet speech
    _silence_db = -40  # default
    if noise_floor_db is not None:
        _silence_db = max(-55, min(-25, noise_floor_db + 5))
        print(f"[tighten] adaptive silence threshold: {_silence_db:.0f}dB (noise_floor={noise_floor_db:.0f}dB)", flush=True)
    silence_regions = []
    if source_path and os.path.exists(source_path):
        silence_regions = detect_silence_regions(source_path, silence_db=_silence_db, min_silence_duration=0.2)
        print(f"[tighten] silence detection found {len(silence_regions)} silent regions", flush=True)

    if silence_regions:
        # Build remove_ranges from actual silence, trimmed by breath_pad on each side
        dead_air_cuts = []
        for region in silence_regions:
            rs = region["start"] + breath_pad
            re_ = region["end"] - breath_pad
            if re_ > rs + 0.05:
                # Don't cut near scene changes
                near_scene = any(abs(c - region["start"]) < 0.1 or abs(c - region["end"]) < 0.1 for c in scene_cuts)
                if not near_scene:
                    dead_air_cuts.append({"start": rs, "end": re_})
        filler_cuts = [{"start": max(0, f["start"]-0.02), "end": f["end"]+0.02} for f in fillers]
        remove_ranges = sorted(filler_cuts + dead_air_cuts, key=lambda r: r["start"])
    else:
        # Fallback to gap-based detection if silence detection unavailable
        max_gap = 0.25
        trim_to = 0.05
        dead_air_cuts = []
        for i in range(1, len(keep_words)):
            prev_end = keep_words[i-1]["end"]
            curr_start = keep_words[i]["start"]
            gap = curr_start - prev_end
            if gap <= max_gap:
                continue
            near_scene = any(abs(c - prev_end) < 0.05 or abs(c - curr_start) < 0.05 for c in scene_cuts)
            if near_scene:
                continue
            remove_start = prev_end + trim_to
            remove_end = curr_start
            if remove_end > remove_start:
                dead_air_cuts.append({"start": remove_start, "end": remove_end})
        first_word_start = keep_words[0]["start"]
        leading_cuts = []
        if first_word_start > trim_to:
            leading_cuts.append({"start": 0, "end": first_word_start - trim_to})
        filler_cuts = [{"start": max(0, f["start"]-0.02), "end": f["end"]+0.02} for f in fillers]
        remove_ranges = sorted(leading_cuts + filler_cuts + dead_air_cuts, key=lambda r: r["start"])

    segments = []
    cursor = first
    for r in remove_ranges:
        rs = max(first, r["start"])
        re_ = min(last, r["end"])
        if re_ <= rs:
            continue
        if rs > cursor:
            segments.append({"start": round(cursor*1000)/1000, "end": round(rs*1000)/1000})
        cursor = max(cursor, re_)
    if cursor < last:
        segments.append({"start": round(cursor*1000)/1000, "end": round(last*1000)/1000})

    merged = []
    for seg in segments:
        if seg["end"] - seg["start"] < min_segment and merged:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    tightened_duration = sum(s["end"] - s["start"] for s in merged)
    removed = max(0, round(((last - first) - tightened_duration) * 1000) / 1000)
    print(f"[tighten] {len(words)} words -> {len(merged)} segments, removed {removed:.1f}s", flush=True)
    return {"segments": merged, "removedSeconds": removed, "timeline_map": [], "tightened_duration": round(tightened_duration*1000)/1000}


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


def format_transcript_for_prompt(transcript):
    words = (transcript or {}).get("words") or []
    if not words:
        return "  none"

    groups = []
    current = []
    for i, w in enumerate(words):
        current.append(w)
        token = str(w.get("punctuated_word") or w.get("word") or "").strip()
        next_w = words[i + 1] if i + 1 < len(words) else None
        pause = (float(next_w.get("start") or 0) - float(w.get("end") or 0)) if next_w else 1.0
        if re.search(r"[.!?]$", token) or pause > 0.35 or len(current) >= 14 or not next_w:
            start = float(current[0].get("start") or 0)
            end = float(current[-1].get("end") or start)
            text = " ".join(str(x.get("punctuated_word") or x.get("word") or "").strip() for x in current).strip()
            groups.append(f"  [{start:.2f}s - {end:.2f}s] {text}")
            current = []
    return "\n".join(groups) if groups else "  none"


def format_tightened_segments_for_prompt(tightened_segments):
    if not tightened_segments:
        return "  none"
    return "\n".join(
        f"  {float(seg.get('start') or 0):.2f}s - {float(seg.get('end') or 0):.2f}s"
        for seg in tightened_segments
    )


def format_timestamps_for_prompt(values, empty_label="none"):
    vals = [float(v) for v in (values or []) if v is not None]
    if not vals:
        return f"  {empty_label}"
    return "  " + ", ".join(f"{v:.2f}s" for v in vals[:120])


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

You are a professional short-form editor. You have the exact transcript with millisecond timestamps. Use them to place PRECISE cuts. Think like a human editor who can see the waveform and the video simultaneously.

DEAD AIR IN SPEECH CONTENT:
Look at the gaps between words in the transcript:
- Under 0.08 seconds between words — natural word spacing. KEEP. This is how speech flows.
- 0.3 seconds or more between words — this is dead air. REMOVE that gap using a remove_words time range with start/end. The Captions app removes ALL gaps this long. We must too.
- Gaps between 0.08 and 0.3 seconds — the pipeline auto-collapses these. Do NOT mark them.
- Filler words (uh, um, hmm, er, ah) — the pipeline auto-removes these. Do NOT mark them.
- Stutters and false starts — the pipeline auto-removes these. Do NOT mark them.

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

Sound design adds texture. A whoosh on a scene change, a bass_drop when a statement lands, a click when something appears — these make cuts feel physical instead of digital. But not every cut needs a sound. Continuous speech flows best with silent hard cuts.

The ending matters. On these platforms, videos auto-loop. A clean ending that flows back into the opening earns replay credit. Avoid fade to black — it creates a flash before the loop restarts.{trend_block}

  HOOK CLIP:
  The hook is the single most important part of any short-form video. Research shows >65% 3-second retention = 4-7x more impressions on TikTok/Reels.

  Use a hook clip when:
  1. The first 2-3 seconds of the video are NOT immediately compelling (slow start, setup, dead air)
  2. There IS a compelling moment later in the video (punchline, reveal, reaction, shocking statement)

  If BOTH are true: pick the single most captivating 1-2 second moment — the punchline, reveal, or reaction that makes someone stop scrolling. Set hook_clip source_start/source_end to that moment. This plays FIRST as a teaser, then the full video plays from the beginning.

  The hook clip MUST:
  - Be 1-2 seconds max
  - Start with speech (not silence) — the first word should land within 0.3s
  - Be something that makes the viewer think "WHAT?" or "HOW?" without context
  - NOT make sense without the rest of the video — that's what keeps them watching

  If the video already opens with a strong hook (provocative question, action, bold statement in the first 2s), set hook_clip to null.

=== TOOLS ===

Word-level edit control:

  remove_words — this is how you remove content. Do NOT output cuts. The pipeline will build clips automatically from Deepgram's exact word timestamps.

  Each remove_words item can be one of:

    {{"word_index": <index>, "reason": "<stutter|false_start|filler>"}}
      Use this when removing a specific spoken word. This is the preferred way to remove stutters, repeated words, false starts, and filler words.

    {{"start": <seconds>, "end": <seconds>, "reason": "<dead_air|section_skip|non_speech_gap>"}}
      Use this when removing a silence range, a dead-air gap, or a whole non-speech section.

  Rules for remove_words:

  The pipeline already handles these AUTOMATICALLY — do NOT mark them:
  - "uh", "um", "er", "ah", "hmm", "uhh", "umm", "mhm" and similar non-word fillers
  - Stutters where a word is repeated exactly ("I I", "the the")
  - False starts where a partial word precedes the full word ("shou-" before "shouldn't")
  These are removed deterministically by the pipeline. You do not need to include them.

  YOUR JOB — context-dependent filler words:
  The pipeline cannot tell if "like", "so", "basically", "you know", "I mean", "right",
  "literally", "actually", "honestly", "obviously", "just", "really", "kind of", "sort of"
  are filler or content. YOU decide based on the sentence:
    - "I was like walking down the street" → "like" is FILLER, remove it
    - "I like this color" → "like" is CONTENT, keep it
    - "So basically what happened was" → "so basically" is FILLER, remove both
    - "So here's the plan" → "so" is CONTENT (sentence opener), keep it
    - "You know what I mean?" → "you know" is CONTENT (question), keep it
    - "And then, you know, he just left" → "you know" is FILLER, remove it

  REMOVE:
  - Filler words: "like" (when filler), "you know" (when filler), "basically", "literally", "honestly", "obviously"
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

  Speed ramping is a COMEDIC and DRAMATIC tool. It creates exaggerated contrast between
  fast and slow moments for humor and impact. The viewer must FEEL the video ramp down
  and ramp up — the pitch shift and tempo change IS the effect.

  THE RUBRIC — follow this exactly:

  SPEED UP (1.3x-1.4x):
  - Filler words and "um", "uh", "like", "you know"
  - Setup and context ("So I was at the store and...")
  - Buildup before a punchline or reveal
  - Transitions between story beats
  - Any moment that is NOT the payoff

  SLOW DOWN (0.67x-0.8x):
  - Punchlines ("...and she said WHO IS STELIUS?")
  - Funny moments (the absurd thing, the unexpected twist)
  - Dramatic reveals (the shocking information drops)

  This is not a suggestion. Every fast section MUST be filler/setup/buildup.
  Every slow section MUST be a punchline/funny moment/dramatic moment.
  If you cannot identify a clear punchline or funny moment, do NOT use speed ramping.

  THE RAMP:
  The pipeline smoothly ramps between your keypoints frame-by-frame. The viewer feels the
  video accelerate and decelerate — this curve is the whole point. The ramp should be quick
  but noticeable — you feel the gear shift, not a hard snap cut between speeds.

  Place keypoints where the speed should be at that moment. The pipeline handles the smooth
  transition between them automatically.

  Speed range: 0.67x to 1.4x. Never go outside this range.

  GUIDELINES:
  - Slow moments MUST land on spoken words (the actual punchline), never on silence.
  - Use the Deepgram word timestamps to place keypoints precisely on the right words.
  - NEVER use 1.0x — every moment is either fast or slow.

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

  thumbnail_timestamp — the source timestamp (in seconds) of the single best frame to use as the video's cover image / thumbnail. Pick the frame where the speaker has the most expressive or emotional face — surprise, laughter, intensity, reaction. Avoid frames where eyes are closed, face is blurry, or expression is blank. This frame needs to make someone scrolling stop and click.

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

  caption_keywords — list of words that should be visually emphasized in captions (larger, colored). These are auto-derived from emphasis_moments word_indices, but you can add extra keywords here for words that should stand out even outside emphasis moments.

Text overlays:
  text_overlays — Short, bold text that gives the viewer instant context. Use ONE overlay maximum.
  Put appear_at_clip on clip 0.
  This overlay sets the stakes in a few words — e.g. "My 6yo exposed my wife", "He said WHAT?!".
  The pipeline ensures the overlay appears at the start of the video. Do NOT place overlays in the middle or end.
  If the story doesn't need context-setting text, use an empty array.
  text — under 5 words, no emojis
  position — top (default for talking heads), center (only when no face in frame), bottom
  appear_at_clip — which clip number
  style — title (72px), callout (56px), cta (64px)

Sound effects — audio accents that make the edit feel physical and professional. Every sound must be EARNED — placed at a moment that justifies it. The wrong sound at the wrong time makes the edit feel amateur. The right sound at the right time makes it feel like a Netflix trailer.

  Available sounds and WHEN to use each:

  bass_drop — deep sub-bass drop impact. The most powerful sound in the toolkit. Use it when a statement LANDS — the moment the viewer's jaw should drop. Dramatic reveals, shocking statements, the punchline of a story. Place it at the exact word that carries the weight. 1 per video MAX.
    Example: "and then she said... I'M PREGNANT" → bass_drop on "pregnant"
    Example: "they offered me TWO MILLION dollars" → bass_drop on "million"

  riser — tension-building rising tone (2.5s). Place it 1-2s BEFORE a big reveal. It creates anticipation. Pairs perfectly with bass_drop or stinger immediately after.
    Example: riser at 12.0s → bass_drop at 13.5s (buildup → payoff)
    Example: speaker pauses for dramatic effect → riser fills the silence before the reveal

  riser_short — quick 1-second riser. Use for minor tension moments or rapid buildups in fast-paced content.

  stinger — dramatic orchestral hit. Use for "movie trailer" moments — big statements, dramatic pauses, or when the speaker drops a bombshell.
    Example: "I'm starting my OWN company" → stinger on "own"

  boom — explosive cinematic boom. Use for explosive statements or when something metaphorically "blows up."
    Example: "the video went VIRAL" → boom on "viral"

  punch — physical impact hit. Use for aggressive or confrontational moments.
    Example: "I told him STRAIGHT to his face" → punch on "straight"

  slam — heavy door slam impact. Powerful and abrupt. Use for finality moments.

  whoosh_fast — fast cinematic whoosh. Use ONLY on actual scene transitions (wipes, fades). If all transitions are hard cuts, do NOT use whoosh_fast — hard cuts are silent by design.

  reveal — sparkle/shimmer discovery sound. Use when something positive is revealed, an answer is given, or a solution is presented.
    Example: "and the secret is..." → reveal on the answer word

  vinyl_scratch — record scratch. Use for comedy — when the speaker says something unexpected, contradicts themselves, or the story takes a sudden turn.
    Example: "everything was going great... until it WASN'T" → vinyl_scratch on "wasn't"

  notification — modern UI chime. Use when the speaker references digital communication — "text", "notification", "email", "message", "DM", "alert".
    Example: "she texted me at 3am" → notification on "texted"

  click — clean digital click. Use when something APPEARS visually or for emphasis on choices/decisions.

  unlock — satisfying achievement chime with sparkle. Use when money is the topic or something positive is achieved.
    Example: "I got it for FREE" → unlock on "free"

  camera_flash — camera shutter click. Use when the speaker references taking a photo, screenshots, or camera-related actions.
    Example: "I took a screenshot" → camera_flash on "screenshot"

  text_appear — soft digital text appearing sound. Use when the speaker references writing, typing, coding, or sending messages.
    Example: "so I looked it up" → text_appear on "looked"

  glitch — digital distortion sound. Use for tech content, internet culture, or when something "breaks."
    Example: "the app completely crashed" → glitch on "crashed"

  heartbeat — dramatic single heartbeat. Use for suspenseful moments when the stakes are high.
    Example: "my heart was RACING" → heartbeat on "racing"

  sad_trombone — comedic failure sound. Use for humorous disappointment.

  boing — cartoonish bounce. Use for playful, lighthearted moments.

  Transitions — the visual effect between two clips. Most cuts should be HARD CUTS (transition_out: "none") — they're fast, clean, and professional. Transitions are a tool, not decoration. Use them sparingly and with purpose.

  Available transition_out values and when to use each:

  none — hard cut. DEFAULT. Use for 90%+ of cuts. Continuous speech flows best with silent hard cuts. Never add a transition just because you can.

  fadewhite — brief white flash between clips. Use at major topic shifts or emotional resets. Feels like a camera flash or memory shift. 1-2 per video maximum.
    Example: speaker finishes one story, starts a completely different one → fadewhite

  fadeblack — fade through black. Use for somber or serious tone shifts. Feels like a scene ending in a film.
    Example: speaker delivers a heavy statement, then shifts to reflection → fadeblack

  dissolve — cross-dissolve blend. Smooth overlap between clips. Use for dreamy, reflective, or nostalgic transitions.
    Example: speaker reminisces about the past → dissolve

  whip_left — fast wipe with motion blur sweeping left. High-energy, punchy. Use for comedic cuts, rapid topic changes, or "meanwhile" moments.
    Example: "and then on the OTHER hand..." → whip_left

  whip_right — fast wipe with motion blur sweeping right. Same energy as whip_left but opposite direction. Alternate with whip_left if using multiple whip transitions.

  smoothleft / smoothright / smoothup / smoothdown — smooth directional slides. More subtle than whip transitions. Use for structured content where you're moving through a list or sequence.
    Example: "first... second... third..." → smoothright between each point

  wipeleft / wiperight / wipeup / wipedown — clean directional wipes without motion blur. More editorial, less energetic than whips. Good for interview-style content.

  flash — brief bright flash (more intense than fadewhite). Use for shock moments or dramatic reveals.

  glitch — pixelated digital glitch effect. Use for tech content, internet culture, or when something "breaks" in the story.
    Example: "the app completely crashed" → glitch

  zoomin — zoom-in transition between clips. Use for escalation or "zooming in" on a topic.

  Rules:
  - Default to "none" (hard cut) for every transition. Only add a transition when it EARNS its place.
  - Never use the same transition type more than 2-3 times in a single video.
  - Match transition energy to content energy: somber content gets dissolve/fadeblack, high-energy gets whip/flash.
  - Pair whoosh_fast sound effects with whip/wipe/smooth transitions. Hard cuts are SILENT.
  - transition_out goes on the clip BEFORE the transition (the outgoing clip).

  Rules:
  - Sound effects should punctuate emphasis_moments. Place sounds where they amplify the moment.
  - Every sound effect MUST have a "word" field (the trigger word that justifies this sound).
  - Use the word timestamps to place each sound at the EXACT millisecond of the trigger word.
  - Most videos have 3-7 sound effects. Zero is fine if nothing earns one.
  - Never stack two sounds within 0.5s of each other — they compete and sound muddy.
  - bass_drop/stinger/boom are your power tools. The rest are contextual accents.
  - riser + impact combos (riser → bass_drop, riser → stinger) are the most cinematic pattern.
  - When in doubt, leave the sound out. Silence is better than a wrong sound.

  sound_effects: [
    {{"t": <seconds>, "sound": "<bass_drop|boom|punch|slam|riser|riser_short|stinger|reveal|whoosh_fast|whoosh_slow|swipe|transition_smooth|vinyl_scratch|sad_trombone|boing|notification|click|unlock|text_appear|camera_flash|glitch|heartbeat|static|thunder|wind_gust|record_stop|switch|page_turn>", "word": "<trigger word>"}}
  ]

B-roll — contextual stock footage overlays that illustrate what the speaker is talking about. B-roll makes the edit feel like a professional production, not just a talking head.

  WHEN TO USE B-ROLL:
  - When the speaker describes something that isn't visible (a place, an object, a concept)
  - During topic transitions to create visual variety
  - When the speaker says "this is what it looks like" or references something external
  - During longer stretches of talking head where the viewer might get bored

  WHEN NOT TO USE:
  - When the speaker IS the content (emotional reactions, demonstrations, tutorials)
  - When the speaker is showing something on screen already
  - When the video is under 15 seconds (too short for B-roll to add value)
  - Never more than 3 B-roll clips per video

  Each B-roll clip replaces the video (not audio) for its duration — the speaker's voice continues over the B-roll footage.

  broll_clips: [
    {{"keyword": "<search term for stock footage>", "timestamp": <source seconds where B-roll starts>, "duration": <seconds, 1-6>}}
  ]

  Rules:
  - keyword: descriptive search term for Pexels video search. Be specific ("city skyline night", "person typing laptop", "coffee shop interior"). Avoid abstract terms.
  - timestamp: source timeline position where this B-roll should appear. Place it DURING speech about the topic, not before.
  - duration: how long to show the B-roll (1-6 seconds). Shorter is usually better.
  - Maximum 3 B-roll clips per video. Most videos need 0-2.
  - Space B-roll clips at least 5 seconds apart.

Visual effects — additional visual treatments for emphasis moments.

  visual_effects: [
    {{"type": "white_flash", "t": <source seconds>}}
  ]

  white_flash — a brief brightness spike (like a camera flash) at a specific moment. Use at the peak of a high-intensity emphasis moment to make it hit harder visually. Maximum 1-2 per video.
    Example: speaker delivers the punchline → white_flash at that exact moment

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
    {{"keyword": "<search term>", "timestamp": <source seconds>, "duration": <seconds>}}
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


def generate_edit_gemini(video_path, vibe, duration, trend_context=None, deepgram_words=None, face_positions=None, gemini_file=None):
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=gemini_api_key)
    prompt = build_gemini_edit_prompt(
        vibe=vibe,
        duration=duration,
        trend_context=trend_context,
    )

    # Inject Deepgram word timestamps so Gemini can place cuts precisely
    if deepgram_words:
        # Build a readable paragraph transcript so Gemini can understand the narrative
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

    if trend_context:
        print(f"[generate-edit] Trend context included: {trend_context.get('sample_size', '?')} videos", flush=True)
    else:
        print("[generate-edit] No trend context available", flush=True)

    if gemini_file is None:
        print("[generate-edit] Uploading video to Gemini...", flush=True)
        gemini_file = genai.upload_file(video_path)
        # Poll for ACTIVE (only hits this path if pre-upload failed)
        _poll_delay = 0.2
        _poll_deadline = time.time() + 60
        while gemini_file.state.name == "PROCESSING":
            if time.time() > _poll_deadline:
                raise RuntimeError("Gemini file processing timed out after 60s")
            time.sleep(_poll_delay)
            _poll_delay = min(_poll_delay * 1.5, 2.0)
            gemini_file = genai.get_file(gemini_file.name)
        if gemini_file.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini file upload failed: {gemini_file.state.name}")
    else:
        print("[generate-edit] Using pre-uploaded Gemini file (already ACTIVE)", flush=True)
    print(f"[generate-edit] Video active: {gemini_file.uri}", flush=True)

    print(f"[generate-edit] Calling Gemini model={GEMINI_MODEL}...", flush=True)
    t = time.time()
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        [gemini_file, prompt],
        generation_config=genai.GenerationConfig(
            temperature=0.6,
            max_output_tokens=32768,
        ),
        request_options={"timeout": 90},
    )
    print(f"[generate-edit] Gemini complete in {time.time()-t:.1f}s", flush=True)

    response_text = str(getattr(response, "text", "") or "").strip()
    try:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            print(f"[generate-edit] Gemini finish_reason={finish_reason}", flush=True)
            fr_str = str(finish_reason).upper()
            if "MAX" in fr_str or finish_reason == 2:
                print("[generate-edit] WARNING: Gemini response TRUNCATED — increase max_output_tokens", flush=True)
            elif "SAFETY" in fr_str or finish_reason == 3:
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
    edit_plan["_deepgram_words"] = list(deepgram_words or [])
    analysis = build_analysis_from_gemini_recipe(edit_plan, duration=duration)
    has_burned_captions = infer_has_burned_captions(edit_plan, analysis, log_prefix="[generate-edit]")

    video_duration = float(analysis.get("duration") or 0)
    _dg_words = edit_plan.get("_deepgram_words", [])
    raw_remove_words = edit_plan.get("remove_words")
    raw_cuts = edit_plan.get("cuts") or edit_plan.get("clips")

    validated_cuts = []
    if isinstance(raw_remove_words, list):
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
            _speech_gap = 0.10  # aggressive — Captions-level tightness
        elif _pacing == "medium":
            _speech_gap = 0.13
        else:
            _speech_gap = 0.15  # slow pacing — more breathing room
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
        validated_cuts = build_clips_from_words(_dg_words, normalized_remove_words, max_silence_gap=_speech_gap)
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
        raise ValueError("Gemini response missing both remove_words and cuts")

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

    # Smart transition limits: max 4 transitions per video, max 2 of the same type.
    # Prevents Gemini from over-using transitions (which looks amateur, not professional).
    _MAX_TRANSITIONS = 4
    _MAX_SAME_TYPE = 2
    _tr_clips = [(i, c) for i, c in enumerate(validated_cuts) if str(c.get("transition_out") or "none") != "none"]
    if len(_tr_clips) > _MAX_TRANSITIONS:
        # Keep only the first N transitions
        for i, c in _tr_clips[_MAX_TRANSITIONS:]:
            print(f"[generate-edit] Stripping excess transition '{c['transition_out']}' from clip {i} (>{_MAX_TRANSITIONS} total)", flush=True)
            c["transition_out"] = "none"
    # Enforce per-type limit
    _tr_type_counts = {}
    for i, c in enumerate(validated_cuts):
        tr = str(c.get("transition_out") or "none")
        if tr == "none":
            continue
        _tr_type_counts[tr] = _tr_type_counts.get(tr, 0) + 1
        if _tr_type_counts[tr] > _MAX_SAME_TYPE:
            print(f"[generate-edit] Stripping duplicate transition '{tr}' from clip {i} (>{_MAX_SAME_TYPE} of same type)", flush=True)
            c["transition_out"] = "none"

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
    raw_broll = edit_plan.get("broll_clips") or []
    validated_broll = []
    for _br in raw_broll:
        if not isinstance(_br, dict):
            continue
        _br_kw = str(_br.get("keyword") or "").strip()
        _br_ts = float(_br.get("timestamp") or 0)
        _br_dur = float(_br.get("duration") or 2.0)
        if _br_kw and _br_ts >= 0 and 1.0 <= _br_dur <= 8.0:
            validated_broll.append({"keyword": _br_kw, "timestamp": _br_ts, "duration": min(_br_dur, 6.0)})
    edit_plan["broll_clips"] = validated_broll[:5]  # max 5 B-roll clips
    if validated_broll:
        print(f"[broll] Gemini requested {len(validated_broll)} B-roll clip(s)", flush=True)

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
    edit_plan["visual_effects"] = validated_vfx[:10]  # max 10 VFX
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
                    s = max(0.5, min(1.4, float(kp.get("speed") or kp.get("s"))))
                    speed_curve.append({"t": t, "speed": s})
                except Exception:
                    continue
        if len(speed_curve) < 2:
            speed_curve = None
        else:
            speed_curve.sort(key=lambda x: x["t"])

            # Enforce minimum ramp duration for large speed changes.
            # Going from 1.3x to 0.7x in 0.3s sounds jarring (pitch shifts
            # too fast). Spread keypoints apart so the ramp is at least 0.6s
            # for large deltas.
            MIN_RAMP_SECS = 0.6
            for i in range(len(speed_curve) - 1):
                dt = speed_curve[i + 1]["t"] - speed_curve[i]["t"]
                ds = abs(speed_curve[i + 1]["speed"] - speed_curve[i]["speed"])
                if ds > 0.3 and dt < MIN_RAMP_SECS:
                    # Spread the two keypoints symmetrically around their midpoint
                    mid_t = (speed_curve[i]["t"] + speed_curve[i + 1]["t"]) / 2
                    speed_curve[i]["t"] = round(max(0.0, mid_t - MIN_RAMP_SECS / 2), 3)
                    speed_curve[i + 1]["t"] = round(mid_t + MIN_RAMP_SECS / 2, 3)

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
            if 0.5 <= hook_dur <= 3.0:
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

    edit_plan["_hook_offset"] = 0.0

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
            # Resolve aliases (including legacy names like thud→bass_drop, swoosh→whoosh_fast, etc.)
            sound = _SFX_ALIASES.get(sound, sound)
            if sound in valid_sounds and t >= 0 and (video_duration <= 0 or t <= video_duration):
                word = str(sfx.get("word") or "").strip().lower()

                # whoosh/swipe/transition: only with wipe/fade transitions
                if sound in ("whoosh_fast", "whoosh_slow", "swipe", "transition_smooth"):
                    has_transitions = any(
                        str(c.get("transition_out") or "none").lower() not in ("none", "")
                        for c in (edit_plan.get("cuts") or [])
                    )
                    if not has_transitions:
                        print(f"[generate-edit] Filtered out {sound} at {t:.1f}s (no wipe/fade transitions)", flush=True)
                        continue

                # camera_flash: only on camera/photo-related trigger words
                if sound == "camera_flash":
                    VALID_CAMERA_WORDS = {"photo", "picture", "screenshot", "camera", "selfie", "snap", "shot", "pic", "image", "film", "filmed", "record", "recorded"}
                    word_clean = word.strip(".,!?;:'\"")
                    if word_clean not in VALID_CAMERA_WORDS:
                        print(f"[generate-edit] Filtered out camera_flash on '{word}' at {t:.1f}s (not a camera trigger)", flush=True)
                        continue

                # text_appear: only on writing/typing-related trigger words
                if sound == "text_appear":
                    VALID_TEXT_WORDS = {"typed", "typing", "wrote", "write", "writing", "googled", "searched", "coded", "coding", "texted", "dm", "dmed", "replied", "response", "looked"}
                    word_clean = word.strip(".,!?;:'\"")
                    if word_clean not in VALID_TEXT_WORDS:
                        print(f"[generate-edit] Filtered out text_appear on '{word}' at {t:.1f}s (not a writing trigger)", flush=True)
                        continue

                # notification: only on digital communication trigger words
                if sound == "notification":
                    VALID_NOTIF_WORDS = {"text", "texted", "notification", "email", "message", "alert", "ping", "dm", "phone"}
                    word_clean = word.strip(".,!?;:'\"")
                    if word_clean not in VALID_NOTIF_WORDS:
                        print(f"[generate-edit] Filtered out notification on '{word}' at {t:.1f}s (not a notification trigger)", flush=True)
                        continue

                # unlock: only on money/achievement-related trigger words
                if sound == "unlock":
                    VALID_UNLOCK_WORDS = {"free", "sold", "dollar", "dollars", "money", "price", "cost", "pay", "paid", "cash", "buy", "bought", "deal", "won", "earned", "achieved"}
                    word_clean = word.strip(".,!?;:'\"")
                    is_dollar_amount = "$" in word or word_clean.replace(".", "").replace(",", "").isdigit()
                    if word_clean not in VALID_UNLOCK_WORDS and not is_dollar_amount:
                        print(f"[generate-edit] Filtered out unlock on '{word}' at {t:.1f}s (not a money/achievement trigger)", flush=True)
                        continue

                sound_effects.append({"t": t, "sound": sound, "word": word})

    # ── Post-filter: enforce caps and minimum spacing ──────────────────
    if sound_effects:
        sound_effects.sort(key=lambda x: x["t"])

        # 1. Remove SFX that are too close together (< 0.5s apart = muddy)
        spaced = []
        for sfx in sound_effects:
            if spaced and sfx["t"] - spaced[-1]["t"] < 0.5:
                print(f"[sfx-filter] Dropped {sfx['sound']} at {sfx['t']:.1f}s (too close to {spaced[-1]['sound']} at {spaced[-1]['t']:.1f}s)", flush=True)
                continue
            spaced.append(sfx)
        sound_effects = spaced

        # 2. Cap heavy impact sounds — overuse kills the punch
        _MAX_PER_TYPE = {"bass_drop": 1, "stinger": 2, "boom": 1,
                         "vinyl_scratch": 2, "riser": 2, "heartbeat": 1, "slam": 2}
        _type_counts = {}
        capped = []
        for sfx in sound_effects:
            snd = sfx["sound"]
            cap = _MAX_PER_TYPE.get(snd)
            if cap is not None:
                _type_counts[snd] = _type_counts.get(snd, 0) + 1
                if _type_counts[snd] > cap:
                    print(f"[sfx-filter] Dropped {snd} at {sfx['t']:.1f}s (max {cap} per video)", flush=True)
                    continue
            capped.append(sfx)
        sound_effects = capped

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
        if overlay.get("position") == "center":
            print(f"[generate-edit] Moving text overlay '{overlay.get('text', '')}' from center to top (talking head safety)", flush=True)
            overlay["position"] = "top"
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

    # ── Map emphasis_moments to clips ────────────────────────────────────
    # High-intensity emphasis moments get cut_zoom (instant snap-in zoom)
    # and auto-placed SFX if no sound already exists nearby.
    # Debounce: require at least 3s gap between emphasis zooms to avoid
    # jarring rapid-fire zoom snapping.
    _last_zoom_t = -999.0
    _MIN_ZOOM_GAP = 3.0
    for em in emphasis_moments:
        em_t = em["t"]
        for clip in final_cuts:
            cs = float(clip["source_start"])
            ce = float(clip["source_end"])
            if cs <= em_t <= ce:
                if em["intensity"] == "high" and str(clip.get("zoom") or "none") == "none":
                    if em_t - _last_zoom_t >= _MIN_ZOOM_GAP:
                        clip["zoom"] = "cut_zoom"
                        clip["cut_zoom"] = True
                        _last_zoom_t = em_t
                        print(f"[emphasis] Applied cut_zoom to clip {cs:.1f}-{ce:.1f}s ({em['type']})", flush=True)
                    else:
                        print(f"[emphasis] Skipped cut_zoom at {em_t:.1f}s — too close to previous zoom at {_last_zoom_t:.1f}s", flush=True)
                break

        # Auto-place stinger on high-intensity moments that have no SFX nearby
        if em["intensity"] == "high":
            nearby_sfx = any(abs(sfx["t"] - em_t) < 1.0 for sfx in sound_effects)
            if not nearby_sfx:
                sound_effects.append({"t": em_t, "sound": "stinger", "word": f"emphasis_{em['type']}"})
                print(f"[emphasis] Auto-placed stinger at {em_t:.1f}s ({em['type']})", flush=True)

    # Re-sort and re-store sound effects after emphasis auto-placement
    sound_effects.sort(key=lambda x: x["t"])
    edit_plan["sound_effects"] = sound_effects
    edit_plan["_parsed_sound_effects"] = sound_effects

    # Color grading disabled — phone cameras already auto-correct color,
    # and artistic grades consistently make talking-head content look worse.
    edit_plan["color_intent"] = "none"
    edit_plan["color_grade"] = {}
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
#   "loud"   — impacts, stingers, punchy sounds (-10 dB below voice)
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
    # Transitions (medium — audible but not distracting)
    "whoosh_fast":       "medium",
    "whoosh_slow":       "quiet",
    "transition_smooth": "quiet",
    "swipe":             "medium",
    # Impacts (loud — meant to hit hard)
    "bass_drop":  "loud",
    "boom":       "loud",
    "punch":      "loud",
    "slam":       "loud",
    # Risers & stingers (medium — build tension, not overpower)
    "riser":       "quiet",
    "riser_short": "medium",
    "stinger":     "medium",
    "reveal":      "medium",
    # UI & notification (medium — clear but not jarring)
    "notification": "medium",
    "text_appear":  "medium",
    "click":        "medium",
    "unlock":       "medium",
    # Comedy & expressive (loud — punchline emphasis)
    "vinyl_scratch": "loud",
    "sad_trombone":  "medium",
    "boing":         "loud",
    "record_stop":   "medium",
    # Atmospheric (quiet — background texture only)
    "static":     "quiet",
    "tape_rewind": "quiet",
    "glitch":      "medium",
    "heartbeat":   "quiet",
    # Nature (quiet — ambient)
    "wind_gust": "quiet",
    "thunder":   "medium",
    # Camera & mechanical (medium)
    "camera_flash": "medium",
    "switch":       "medium",
    "page_turn":    "medium",
}

# RMS measurement cache — populated lazily, avoids re-measuring same file
_SFX_RMS_CACHE = {}
_SFX_TARGET_RMS = -18.0  # dBFS — reference level all SFX are normalized to


def _measure_sfx_rms(sfx_path):
    """Measure RMS loudness of an SFX file using ffmpeg astats. Cached."""
    if sfx_path in _SFX_RMS_CACHE:
        return _SFX_RMS_CACHE[sfx_path]
    try:
        cmd = [
            "ffmpeg", "-i", sfx_path, "-af",
            "astats=metadata=1:reset=0,ametadata=mode=print",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        rms_matches = re.findall(
            r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", result.stderr
        )
        rms_db = float(rms_matches[-1]) if rms_matches else _SFX_TARGET_RMS
        rms_db = max(-60.0, min(0.0, rms_db))
        _SFX_RMS_CACHE[sfx_path] = rms_db
        return rms_db
    except Exception:
        _SFX_RMS_CACHE[sfx_path] = _SFX_TARGET_RMS
        return _SFX_TARGET_RMS

_SFX_ALIASES = {
    "whoosh":     "whoosh_fast",
    # Legacy aliases: old SFX names → new equivalents
    "thud":       "bass_drop",
    "reverb_hit": "riser_short",
    "pop":        "click",
    "ching":      "unlock",
    "ding":       "notification",
    "swoosh":     "whoosh_fast",
    "shutter":    "camera_flash",
    "typing":     "text_appear",
    # Semantic aliases
    "cashier":    "unlock",
    "cash":       "unlock",
    "money":      "unlock",
    "rise":       "riser",
    "rising":     "riser",
    "buildup":    "riser",
    "tension":    "riser",
    "impact":     "bass_drop",
    "slide":      "swipe",
    "snap":       "click",
    "tape_stop":  "record_stop",
    "drop":       "bass_drop",
    "bass":       "bass_drop",
    "scratch":    "vinyl_scratch",
    "flash":      "camera_flash",
    "camera":     "camera_flash",
    "sparkle":    "reveal",
    "magic":      "reveal",
    "shimmer":    "reveal",
    "error":      "static",
    "buzz":       "static",
    "wind":       "wind_gust",
    "breeze":     "wind_gust",
    "button":     "click",
    "press":      "click",
    "bounce":     "boing",
    "fail":       "sad_trombone",
    "wah":        "sad_trombone",
    "page":       "page_turn",
    "flip":       "page_turn",
    "toggle":     "switch",
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


def extract_cover_frame(source_path, timestamp, work_dir):
    """Extract a single JPEG frame. Returns (bytes, 'image/jpeg') or (None, None)."""
    frame_path = os.path.join(work_dir, "cover_frame.jpg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", source_path,
         "-frames:v", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
         "-q:v", "3", frame_path],
        capture_output=True,
    )
    if result.returncode == 0 and os.path.exists(frame_path):
        with open(frame_path, "rb") as f:
            data = f.read()
        try:
            os.unlink(frame_path)
        except Exception:
            pass
        return data, "image/jpeg"
    return None, None


def generate_styled_thumbnail(source_path, timestamp, face_positions, work_dir, hook_text=None):
    """
    Generate an enhanced, styled thumbnail from the video.
    - Extract frame at AI-selected timestamp
    - Enhance with Pillow (contrast, brightness, saturation, sharpness)
    - Add vignette effect (dark edges, bright center)
    - Optional hook text overlay at bottom
    Returns (bytes, 'image/jpeg') or falls back to basic extract_cover_frame.
    """
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
    except ImportError:
        print("[thumbnail] Pillow not available — using basic extraction", flush=True)
        return extract_cover_frame(source_path, timestamp, work_dir)

    # Step 1: Extract raw frame via FFmpeg
    raw_path = os.path.join(work_dir, "thumb_raw.png")
    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", source_path,
         "-frames:v", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
         raw_path],
        capture_output=True, timeout=15,
    )
    if result.returncode != 0 or not os.path.exists(raw_path):
        print("[thumbnail] Frame extraction failed — falling back to basic", flush=True)
        return extract_cover_frame(source_path, timestamp, work_dir)

    try:
        img = Image.open(raw_path).convert("RGB")
    except Exception as e:
        print(f"[thumbnail] Could not open frame: {e}", flush=True)
        return extract_cover_frame(source_path, timestamp, work_dir)

    w, h = img.size

    # Step 2: Enhance — subtle but impactful
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = ImageEnhance.Color(img).enhance(1.18)
    img = ImageEnhance.Sharpness(img).enhance(1.25)

    # Step 3: Vignette (dark edges, bright center) — cinematic look
    vignette = Image.new("L", (w, h), 0)
    vignette_draw = ImageDraw.Draw(vignette)
    for i in range(40):
        opacity = int(255 * (1 - i / 40.0) ** 0.6)
        shrink_x = int(w * 0.05 * i / 40)
        shrink_y = int(h * 0.05 * i / 40)
        vignette_draw.ellipse(
            [shrink_x, shrink_y, w - shrink_x, h - shrink_y],
            fill=opacity,
        )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=60))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = Image.composite(img, dark, vignette)

    # Step 4: Optional text overlay (hook/title)
    if hook_text and len(hook_text.strip()) > 0:
        hook_text = hook_text.strip()[:80]
        draw = ImageDraw.Draw(img)
        font = None
        font_size = 64
        for font_path in [
            "/assets/fonts/Montserrat-ExtraBold.ttf",
            "/assets/fonts/Montserrat-Bold.ttf",
            "/assets/fonts/Poppins-ExtraBold.ttf",
        ]:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    continue
        if font is None:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Word-wrap the text
        max_width = w - 80
        words = hook_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Draw text at bottom third with shadow
        line_height = font_size + 8
        total_text_height = len(lines) * line_height
        y_start = h - total_text_height - 120

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (w - text_w) // 2
            y = y_start + i * line_height
            for offset in [(3, 3), (2, 2), (1, 1)]:
                draw.text((x + offset[0], y + offset[1]), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))

    # Step 5: Save as high-quality JPEG
    thumb_path = os.path.join(work_dir, "styled_thumbnail.jpg")
    img.save(thumb_path, "JPEG", quality=92, optimize=True)

    with open(thumb_path, "rb") as f:
        data = f.read()

    for p in [raw_path, thumb_path]:
        try:
            os.unlink(p)
        except Exception:
            pass

    print(
        f"[thumbnail] Styled thumbnail: {len(data)//1024}KB, "
        f"enhanced+vignette{'+text' if hook_text else ''}",
        flush=True,
    )
    return data, "image/jpeg"


def fetch_broll_clip(keyword, duration_needed, work_dir):
    """Search Pexels for a portrait video clip. Returns local path or None."""
    pexels_key = os.environ.get("PEXELS_API_KEY")
    if not pexels_key:
        print(f"[broll] PEXELS_API_KEY not set — skipping '{keyword}'", flush=True)
        return None

    try:
        resp = None
        for attempt in range(2):
            try:
                resp = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers={"Authorization": pexels_key},
                    params={
                        "query": keyword,
                        "per_page": 15,
                        "orientation": "portrait",
                        "size": "medium",
                    },
                    timeout=25,
                )
                resp.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt == 0:
                    print(f"[broll] Pexels timed out for '{keyword}' — retrying...", flush=True)
                    continue
                print(f"[broll] Pexels timed out for '{keyword}' after retry — skipping", flush=True)
                return None
            except Exception as e:
                print(f"[broll] Pexels API error for '{keyword}': {e}", flush=True)
                return None

        if resp is None:
            return None
        videos = resp.json().get("videos") or []

        if not videos:
            print(f"[broll] No Pexels results for '{keyword}'", flush=True)
            return None

        print(f"[broll] Pexels returned {len(videos)} results for '{keyword}'", flush=True)

        best_match = None
        best_score = -1
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
                quality = f.get("quality") or ""

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

                portrait_files.append({
                    "link": link,
                    "height": h,
                    "width": w,
                    "file_type": file_type,
                    "quality": quality,
                })

            if not portrait_files:
                continue

            portrait_files.sort(key=lambda x: x["height"], reverse=True)
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

            if score > best_score:
                best_match = {
                    "video_id": vid_id,
                    "video_idx": vid_idx,
                    "duration": vid_dur,
                    "file": best_file,
                    "score": score,
                }
                best_score = score

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

        with open(dest, "wb") as f:
            total_bytes = 0
            for chunk in dl.iter_content(65536):
                f.write(chunk)
                total_bytes += len(chunk)

        print(f"[broll] Downloaded '{keyword}': {total_bytes / 1024:.0f}KB -> {dest}", flush=True)

        try:
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

            frame_check_cmd = [
                "ffmpeg", "-y",
                "-i", dest,
                "-t", "2",
                "-vf", "fps=5",
                "-f", "null", "-",
            ]
            frame_result = subprocess.run(frame_check_cmd, capture_output=True, text=True, timeout=15)

            frame_count = 0
            for line in frame_result.stderr.split("\n"):
                if "frame=" in line:
                    try:
                        frame_part = line.split("frame=")[1].strip().split()[0]
                        frame_count = int(frame_part)
                    except (IndexError, ValueError):
                        pass

            if frame_count < 8:
                print(
                    f"[broll] REJECTED '{keyword}': only {frame_count} decoded frames in first 2s — likely a still image or frozen clip",
                    flush=True,
                )
                os.remove(dest)
                return None

            # Motion check: compare frames at 0.5s and 2.0s to reject frozen/static clips.
            # Uses timestamp seeks instead of frame-number select (more robust across codecs).
            try:
                import numpy as np
                _raw_path_a = os.path.join(work_dir, f"_broll_motion_{safe_kw}_a.raw")
                _raw_path_b = os.path.join(work_dir, f"_broll_motion_{safe_kw}_b.raw")
                _frame_size = 160 * 284
                _seek_b = min(2.0, max(0.5, fmt_duration - 1.0))
                for _seek, _rp in [(0.3, _raw_path_a), (_seek_b, _raw_path_b)]:
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", f"{_seek:.2f}", "-i", dest,
                         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "160x284",
                         "-loglevel", "warning", _rp],
                        capture_output=True, timeout=10)
                if os.path.exists(_raw_path_a) and os.path.exists(_raw_path_b):
                    _da = open(_raw_path_a, "rb").read()
                    _db = open(_raw_path_b, "rb").read()
                    if len(_da) >= _frame_size and len(_db) >= _frame_size:
                        _f1 = np.frombuffer(_da[:_frame_size], dtype=np.uint8).astype(np.float32)
                        _f2 = np.frombuffer(_db[:_frame_size], dtype=np.uint8).astype(np.float32)
                        _diff = np.mean(np.abs(_f1 - _f2))
                        if _diff < 1.5:
                            print(f"[broll] REJECTED '{keyword}': frozen/static clip (frame diff={_diff:.1f})", flush=True)
                            os.remove(dest)
                            for _rp in [_raw_path_a, _raw_path_b]:
                                try: os.remove(_rp)
                                except: pass
                            return None
                        print(f"[broll] Motion check OK for '{keyword}': frame diff={_diff:.1f}", flush=True)
                for _rp in [_raw_path_a, _raw_path_b]:
                    try: os.remove(_rp)
                    except: pass
            except Exception as _me:
                print(f"[broll] Motion check skipped for '{keyword}': {_me}", flush=True)

            is_portrait = stream_h > stream_w
            print(
                f"[broll] VALIDATED '{keyword}': {stream_w}x{stream_h} ({codec_name}), "
                f"{fmt_duration:.1f}s, {frame_count} test frames, portrait={is_portrait}",
                flush=True,
            )

            if not is_portrait:
                print(f"[broll] REJECTED '{keyword}': landscape orientation", flush=True)
                os.remove(dest)
                return None
        except Exception as e:
            print(f"[broll] Could not validate '{keyword}': {e} — rejecting to be safe", flush=True)
            if os.path.exists(dest):
                os.remove(dest)
            return None

        return dest
    except Exception as e:
        print(f"[broll] Failed to fetch '{keyword}': {e}", flush=True)
        return None


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
    try:
        data = json.loads(result.stdout or "{}")
    except Exception:
        data = {}
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


def get_source_duration(video_path):
    """Get duration of source video in seconds."""
    return probe_duration(video_path) or 0.0


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
        ["ffmpeg", "-v", "warning", "-nostats", "-threads", "0"] + [str(a) for a in args],
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


def create_keyframed_source(source_path, keyframe_timestamps, work_dir):
    unique_kf = sorted(set(round(t*1000)/1000 for t in keyframe_timestamps if t > 0))
    kf_str = ",".join(str(t) for t in unique_kf)
    keyframed_path = os.path.join(work_dir, "keyframed_source.mp4")
    print(f"[ffmpeg] Forcing keyframes at {len(unique_kf)} cut points", flush=True)
    run_ffmpeg([
        "-y","-i",source_path,
    ] + get_encode_args("lossless") + [
        "-force_key_frames",kf_str,
        "-r","30","-vsync","cfr","-pix_fmt","yuv420p",
        "-c:a","copy",
        keyframed_path,
    ])
    _kpd = _probe_full(keyframed_path)
    _kvs = next((s for s in (_kpd.get("streams") or []) if s.get("codec_type") == "video"), {})
    print(f"[DIAG] Keyframed source: codec={_kvs.get('codec_name')} dur={(_kpd.get('format') or {}).get('duration')}", flush=True)
    return keyframed_path




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


def _smoothstep(x):
    """Attempt smoothstep easing: ease-in and ease-out (3x² - 2x³).

    Converts linear fraction [0,1] into a smooth S-curve that starts
    slow, accelerates through the middle, and decelerates at the end.
    This makes speed ramps feel organic — like a natural gear shift
    instead of a constant mechanical ramp.
    """
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def get_speed_for_timestamp(t, speed_curve):
    """Smoothly interpolate speed at time t from keypoints.

    Uses smoothstep easing between keypoints so speed ramps accelerate
    and decelerate naturally. Fast→slow transitions build anticipation
    before dropping into the slow moment. Slow→fast transitions snap
    out with energy. This is what separates CapCut-level speed ramping
    from flat mechanical ramps.
    """
    if not speed_curve or speed_curve == "none":
        return 1.0
    if not isinstance(speed_curve, list) or len(speed_curve) == 0:
        return 1.0
    # Before first keypoint
    if t <= float(speed_curve[0]["t"]):
        return float(speed_curve[0]["speed"])
    # After last keypoint
    if t >= float(speed_curve[-1]["t"]):
        return float(speed_curve[-1]["speed"])
    # Interpolate between surrounding keypoints with smoothstep easing
    for i in range(len(speed_curve) - 1):
        t0 = float(speed_curve[i]["t"])
        t1 = float(speed_curve[i + 1]["t"])
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
            frac = _smoothstep(frac)
            s0 = float(speed_curve[i]["speed"])
            s1 = float(speed_curve[i + 1]["speed"])
            return s0 + (s1 - s0) * frac
    return 1.0


def is_hard_cut(transition):
    t = str(transition or "").strip().lower()
    return not t or t in ("none", "clean_cut")


def project_words_to_output(transcript, cuts, effective_durations, hook_offset=0.0, hook_clip=None, speed_curve=None, transition_duration=None):
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    clip_ranges = get_output_clip_ranges(cuts, effective_durations, transition_duration=transition_duration)
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        speed   = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        _has_curve = speed_curve and speed_curve != "none"
        for w in words:
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            if we <= c_start or ws >= c_end:
                continue
            # Per-word speed: evaluate curve at each word's midpoint for accurate timing
            w_mid = (max(ws, c_start) + min(we, c_end)) / 2.0
            curve_speed = max(0.5, min(1.4, get_speed_for_timestamp(w_mid, speed_curve))) if _has_curve else 1.0
            combined_speed = speed * curve_speed
            local_s = (max(ws, c_start) - c_start) / combined_speed
            local_e = (min(we, c_end) - c_start) / combined_speed
            projected.append({
                "start": round((output_cursor + local_s)*1000)/1000,
                "end":   round((output_cursor + local_e)*1000)/1000,
                "word":  w.get("punctuated_word") or w.get("word") or "",
                "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                "speaker": int(w.get("speaker", 0) or 0),
                "_source_start": max(ws, c_start),
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        _td = transition_duration if transition_duration is not None else TRANSITION_DURATION_DEFAULT
        overlap = _td if i < len(cuts)-1 and not is_hard_cut(cut.get("transition_out")) else 0
        output_cursor = round((output_cursor + dur - overlap)*1000)/1000

    projected = [w for w in projected if w["end"] > w["start"]]
    if hook_offset > 0:
        for w in projected:
            w["start"] = round((w["start"] + hook_offset) * 1000) / 1000
            w["end"] = round((w["end"] + hook_offset) * 1000) / 1000
        print(f"[hook] Shifted caption timestamps by +{hook_offset:.2f}s for hook", flush=True)

        if isinstance(hook_clip, dict):
            hook_start = float(hook_clip.get("source_start") or 0.0)
            hook_end = float(hook_clip.get("source_end") or 0.0)
            hook_render_start = project_source_time_to_output(hook_start, cuts, clip_ranges, speed_curve)
            hook_words = []
            for w in words:
                ws = float(w.get("start") or 0)
                we = float(w.get("end") or 0)
                if ws >= hook_start and we <= hook_end:
                    if hook_render_start is None:
                        continue
                    projected_start = project_source_time_to_output(ws, cuts, clip_ranges, speed_curve)
                    projected_end = project_source_time_to_output(we, cuts, clip_ranges, speed_curve)
                    if projected_start is None or projected_end is None:
                        continue
                    hook_words.append({
                        "start": round((projected_start - hook_render_start) * 1000) / 1000,
                        "end": round((projected_end - hook_render_start) * 1000) / 1000,
                        "word": w.get("punctuated_word") or w.get("word") or "",
                        "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                        "speaker": int(w.get("speaker", 0) or 0),
                    })
            projected = hook_words + projected

    return projected


def _face_at(source_t, fp_list, fallback_cx=540):
    """Return (cx, cy) at a source timestamp, or (None, None).
    Shared helper for all face-aware caption styles.
    """
    if not fp_list or source_t is None:
        return None, None
    best = None
    best_dt = float("inf")
    for fp in fp_list:
        if not fp.get("found"):
            continue
        dt = abs(float(fp.get("t", 0)) - source_t)
        if dt < best_dt:
            best_dt = dt
            best = fp
    if best and best_dt < 2.0:
        return float(best.get("cx", fallback_cx)), float(best.get("cy", 0))
    return None, None


def _build_keyword_set(words, caption_keywords):
    """Build a set of lowercase keyword strings for caption highlighting.
    Shared helper for all caption styles that highlight keywords.
    """
    _kw_input = caption_keywords or []
    if isinstance(_kw_input, str):
        _kw_input = _kw_input.split()
    elif not isinstance(_kw_input, (list, tuple)):
        _kw_input = []
    keyword_set = set(re.sub(r"[.,!?;:'\"\\]", "", str(k).lower()) for k in _kw_input)
    if not keyword_set:
        _sentence_words = []
        for wd in words:
            _w_clean = re.sub(r"[.,!?;:'\"\\]", "", str(wd.get("word") or "").lower())
            _sentence_words.append(_w_clean)
            _ends_sent = bool(re.search(r"[.!?]$", str(wd.get("word") or "")))
            if _ends_sent or wd == words[-1]:
                if _sentence_words:
                    _best = max(_sentence_words, key=len)
                    if len(_best) >= 4:
                        keyword_set.add(_best)
                _sentence_words = []
    return keyword_set

def render_remotion_overlay(
    words, caption_style, output_res, caption_keywords, work_dir,
    total_duration=0.0, fps=30, cuts=None, emphasis_moments=None, vibe="",
):
    """Render captions + visual effects as a transparent overlay video.

    Returns path to a transparent ProRes 4444 (.mov) file.
    Raises RuntimeError if rendering fails.
    """
    remotion_dir = "/remotion"
    render_cli = os.path.join(remotion_dir, "render-cli.mjs")

    if not os.path.exists(render_cli):
        raise RuntimeError(f"[remotion] render-cli.mjs not found at {render_cli}")

    w = output_res.get("width") or 1080
    h = output_res.get("height") or 1920

    # Build cut points for effect timing
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

    # Build emphasis moments for effect timing
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

    # Write input JSON for the render CLI (OverlayInput format)
    input_data = {
        "words": words or [],
        "captionStyle": caption_style,
        "keywords": caption_keywords or [],
        "effects": [],  # auto-generated by Remotion from vibe + cuts + emphasis
        "cuts": cut_points,
        "emphasisMoments": em_list,
        "width": w,
        "height": h,
        "fps": fps,
        "duration": total_duration,
        "fontDir": "/assets/fonts",
        "vibe": vibe,
    }

    input_json_path = os.path.join(work_dir, "remotion_input.json")
    output_mov_path = os.path.join(work_dir, "overlay_remotion.webm")

    with open(input_json_path, "w") as f:
        json.dump(input_data, f)

    _n_words = len(words) if words else 0
    _total_frames = max(1, round(total_duration * fps))
    print(f"[remotion] Rendering overlay: {caption_style} captions ({_n_words} words), "
          f"{len(cut_points)} cuts, {len(em_list)} emphasis, vibe=\"{vibe}\", "
          f"{total_duration:.1f}s @ {fps}fps ({_total_frames} frames)", flush=True)
    t0 = time.time()

    # Always try GPU-accelerated Chrome (angle-egl) when a GPU is present.
    # NVENC encode may fail while EGL rendering still works (different GPU subsystem).
    _gl_mode = "angle-egl" if _HAS_HWACCEL else "swiftshader"

    # Use multiple concurrent browser tabs to render frames in parallel.
    # Remotion caps concurrency at the system core count (Node's os.cpus().length).
    # Modal H100 reports 32 cores to Node even though Python sees 48.
    _concurrency = min(48, max(4, os.cpu_count() or 32))

    _render_cmd = [
        "node", render_cli, "--input", input_json_path, "--output", output_mov_path,
        "--concurrency", str(_concurrency), "--gl", _gl_mode,
    ]
    print(f"[remotion] Chrome GL: {_gl_mode}, concurrency: {_concurrency}", flush=True)
    result = subprocess.run(
        _render_cmd,
        capture_output=True, text=True,
        timeout=300,
        cwd=remotion_dir,
    )

    # If GPU GL failed, retry with SwiftShader
    if result.returncode != 0 and _gl_mode == "angle-egl":
        _stderr_check = (result.stderr or "").lower()
        if "gl" in _stderr_check or "gpu" in _stderr_check or "egl" in _stderr_check or "angle" in _stderr_check:
            print("[remotion] GPU GL failed — retrying with SwiftShader (CPU)...", flush=True)
            _render_cmd[-1] = "swiftshader"
            result = subprocess.run(
                _render_cmd,
                capture_output=True, text=True,
                timeout=300,
                cwd=remotion_dir,
            )

    # Print Remotion stdout (progress + timing info)
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                print(f"  {line.strip()}", flush=True)

    if result.returncode != 0:
        full_stderr = result.stderr or ""
        # Print full stderr for debugging (truncated in the exception)
        if full_stderr:
            print(f"[remotion] FULL STDERR ({len(full_stderr)} chars):", flush=True)
            for line in full_stderr.strip().split("\n")[-30:]:
                print(f"  {line}", flush=True)
        stderr_tail = full_stderr[-2000:]
        raise RuntimeError(f"[remotion] Render failed (rc={result.returncode}): {stderr_tail}")

    elapsed = time.time() - t0

    if not os.path.exists(output_mov_path):
        raise RuntimeError("[remotion] Render completed but output file not found")

    sz = os.path.getsize(output_mov_path)
    print(f"[remotion] Caption overlay: {sz / 1024 / 1024:.1f}MB in {elapsed:.1f}s", flush=True)
    return output_mov_path


def get_output_clip_ranges(cuts, effective_durations, transition_duration=None):
    """
    Return list of {"start": float, "end": float} for each clip's position
    in the output timeline, accounting for transition overlap.
    """
    _td_base = transition_duration if transition_duration is not None else TRANSITION_DURATION_DEFAULT
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = round(cursor * 1000) / 1000
        end   = round((cursor + dur) * 1000) / 1000
        ranges.append({"start": start, "end": end})
        transition = str(cut.get("transition_out") or "none").lower()
        td      = _td_base if transition not in ("none", "clean_cut", "") else 0.0
        overlap = td if i < len(cuts) - 1 else 0.0
        cursor  = round((end - overlap) * 1000) / 1000
    return ranges


def resolve_overlay_clip_idx(orig_clip_idx, original_cuts, current_cuts):
    """
    Map an overlay's appear_at_clip (0-indexed into original/pre-tighten cuts)
    to the correct index in the current (post-tighten) cuts by matching source timestamps.
    """
    if orig_clip_idx < 0 or orig_clip_idx >= len(original_cuts):
        return None
    target_source_time = float(original_cuts[orig_clip_idx]["source_start"])
    for ci, cut in enumerate(current_cuts):
        if float(cut["source_start"]) <= target_source_time <= float(cut["source_end"]):
            return ci
        if abs(float(cut["source_start"]) - target_source_time) < 1.0:
            return ci
    return None


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


def build_clips_from_words(deepgram_words, remove_words, max_silence_gap=0.15):
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
    """
    if not deepgram_words:
        return []

    # ── Step 0: Prepare sorted word list with metadata ────────────────────
    sorted_words = sorted(
        [
            {
                **w,
                "_word_index": i,
                "_start": float(w.get("start") or 0.0),
                "_end": float(w.get("end") or 0.0),
                "_text": str(w.get("punctuated_word") or w.get("word") or "").strip(),
                "_clean": re.sub(r"[^a-z']", "", str(w.get("word") or w.get("punctuated_word") or "").strip().lower()),
            }
            for i, w in enumerate(deepgram_words)
        ],
        key=lambda w: w["_start"],
    )

    removed_indices = set()

    # ── Step 1: Apply Gemini's remove_words ───────────────────────────────
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item:
            try:
                idx = int(item["word_index"])
                if 0 <= idx < len(sorted_words):
                    removed_indices.add(idx)
            except Exception:
                continue

    # Time ranges only remove silence/dead air — they NEVER remove spoken words.
    # Words can only be removed via explicit word_index. This prevents Gemini's
    # slightly-off timestamps from accidentally killing real content.

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
            # A real stutter happens close together. If there's a large gap
            # between the two words, it's a conversational repeat, not a stutter.
            gap = next_w["_start"] - w["_end"]
            if gap > 1.0:
                print(
                    f"[tighten] Skipping repeat '{w['_text']}' → '{next_w['_text']}' "
                    f"(gap={gap:.2f}s too large for stutter)",
                    flush=True,
                )
                continue
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

    # ── Step 5: Add audio padding ─────────────────────────────────────────
    # Deepgram's word boundaries mark where acoustic energy is detected, but
    # consonant releases (t, k, p, s) and breaths extend past the endpoint.
    # Pad start by -15ms (catch onset) and end by +40ms (catch release).
    PAD_START = 0.015  # 15ms before first word
    PAD_END = 0.060    # 60ms after last word — catches sibilant tails (s, sh, ch)

    raw_clips = []
    for word_group in clips:
        first_start = word_group[0]["_start"]
        last_end = word_group[-1]["_end"]

        raw_clips.append({
            "raw_start": first_start,
            "raw_end": last_end,
            "padded_start": max(0.0, first_start - PAD_START),
            "padded_end": last_end + PAD_END,
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

    # ── Step 8: Mid-word boundary safety ──────────────────────────────────
    # If any clip boundary lands inside a word (shouldn't happen with this
    # approach, but as a safety net), expand the clip to include the full word.
    for rc in raw_clips:
        for w in sorted_words:
            if w["_word_index"] in removed_indices:
                continue
            # Check start boundary
            if w["_start"] < rc["padded_start"] < w["_end"]:
                old = rc["padded_start"]
                rc["padded_start"] = max(0.0, w["_start"] - 0.01)
                print(
                    f"[tighten] Safety: expanded clip start {old:.3f}s → {rc['padded_start']:.3f}s to include '{w['_text']}'",
                    flush=True,
                )
            # Check end boundary
            if w["_start"] < rc["padded_end"] < w["_end"]:
                old = rc["padded_end"]
                rc["padded_end"] = w["_end"] + 0.01
                print(
                    f"[tighten] Safety: expanded clip end {old:.3f}s → {rc['padded_end']:.3f}s to include '{w['_text']}'",
                    flush=True,
                )

    # ── Build final clip dicts ────────────────────────────────────────────
    final_clips = []
    for rc in raw_clips:
        s = round(rc["padded_start"] * 1000) / 1000
        e = round(rc["padded_end"] * 1000) / 1000
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

    return final_clips


def tighten_clips_with_deepgram(cuts, deepgram_words, min_silence_to_remove=0.08):
    """
    Go inside each of Gemini's clips and:
    1. Remove filler words (uh, um, etc.)
    2. Remove silence gaps longer than min_silence_to_remove
    3. Trim each clip to start at its first word and end at its last word

    Every clip starts on a word and ends on a word. Zero dead air.
    """
    if not deepgram_words or not cuts:
        return cuts

    sorted_words = sorted(deepgram_words, key=lambda w: float(w.get("start") or 0))

    total_filler_removed = 0.0
    total_silence_removed = 0.0
    total_edge_trimmed = 0.0
    new_cuts = []

    for clip_idx, clip in enumerate(cuts):
        clip_start = float(clip["source_start"])
        clip_end = float(clip["source_end"])

        # Get all words that overlap with this clip (generous matching)
        clip_words = []
        for w in sorted_words:
            w_start = float(w.get("start") or 0)
            w_end = float(w.get("end") or 0)
            # Word is inside clip if it starts within the clip bounds (with small tolerance)
            if w_start >= clip_start - 0.05 and w_start < clip_end + 0.05:
                clip_words.append(w)

        if not clip_words:
            new_cuts.append(dict(clip))
            continue

        print(
            f"[tighten] Clip {clip_idx}: {len(clip_words)} words, "
            f"first='{clip_words[0].get('word') if clip_words else 'N/A'}' "
            f"last='{clip_words[-1].get('word') if clip_words else 'N/A'}'",
            flush=True,
        )

        # Filter out filler words
        keep_segments = []
        for idx, w in enumerate(clip_words):
            w_text = str(w.get("punctuated_word") or w.get("word") or "").strip().lower()
            w_clean = w_text.strip(".,!?;:'\"")

            if w_clean in FILLER_WORDS:
                filler_dur = float(w.get("end") or 0) - float(w.get("start") or 0)
                total_filler_removed += filler_dur
                print(
                    f"[tighten] Removing filler '{w_clean}' at {float(w.get('start') or 0):.3f}s ({filler_dur:.3f}s)",
                    flush=True,
                )
                continue

            next_word_text = ""
            if idx + 1 < len(clip_words):
                next_word_text = str(
                    clip_words[idx + 1].get("punctuated_word") or clip_words[idx + 1].get("word") or ""
                ).strip().lower()

            if _is_stutter(w_clean, next_word_text):
                stutter_dur = float(w.get("end") or 0) - float(w.get("start") or 0)
                total_filler_removed += stutter_dur
                print(
                    f"[tighten] Removing stutter '{w_clean}' before '{next_word_text}' at "
                    f"{float(w.get('start') or 0):.3f}s ({stutter_dur:.3f}s)",
                    flush=True,
                )
                continue

            keep_segments.append({
                "start": float(w.get("start") or 0),
                "end": float(w.get("end") or 0),
                "word": w_text,
            })

        if not keep_segments:
            continue

        # Track edge trimming
        first_word_start = keep_segments[0]["start"]
        last_word_end = keep_segments[-1]["end"]
        if first_word_start > clip_start:
            total_edge_trimmed += first_word_start - clip_start
        if clip_end > last_word_end:
            total_edge_trimmed += clip_end - last_word_end

        # Build sub-clips by splitting at silence gaps
        sub_clips = []
        current_sub_start = keep_segments[0]["start"]
        current_sub_end = keep_segments[0]["end"]

        for i in range(1, len(keep_segments)):
            gap = keep_segments[i]["start"] - keep_segments[i - 1]["end"]

            if gap > min_silence_to_remove:
                total_silence_removed += gap
                sub_clips.append({
                    "start": current_sub_start,
                    "end": current_sub_end,
                })
                current_sub_start = keep_segments[i]["start"]

            current_sub_end = keep_segments[i]["end"]

        sub_clips.append({
            "start": current_sub_start,
            "end": current_sub_end,
        })

        # Buffer: tiny pad before words, small pad after words
        for j, sc in enumerate(sub_clips):
            if clip_idx == 0 and j == 0:
                # First sub-clip of the first clip: start exactly on the word, zero buffer
                # No dead air before the first word of the video
                pass
            else:
                sc["start"] = sc["start"] - 0.01
            sc["end"] = sc["end"] + 0.05

        # Convert sub-clips to full clip dicts
        for sc in sub_clips:
            if sc["end"] - sc["start"] < 0.15:
                continue  # Skip tiny fragments
            new_clip = dict(clip)
            new_clip["source_start"] = round(max(0.0, sc["start"]) * 1000) / 1000
            new_clip["source_end"] = round(sc["end"] * 1000) / 1000
            new_cuts.append(new_clip)

    # Fix overlaps: earlier clip wins, later clip starts where earlier ends
    for i in range(1, len(new_cuts)):
        if new_cuts[i]["source_start"] < new_cuts[i - 1]["source_end"]:
            new_cuts[i]["source_start"] = new_cuts[i - 1]["source_end"]

    # Remove any clips that became zero-length or negative after overlap fix
    new_cuts = [c for c in new_cuts if c["source_end"] > c["source_start"] + 0.05]

    print(
        f"[tighten] Deepgram tightening: {len(cuts)} clips → {len(new_cuts)} clips, "
        f"removed {total_filler_removed:.2f}s filler + {total_silence_removed:.2f}s silence + {total_edge_trimmed:.2f}s edge trim",
        flush=True,
    )

    return new_cuts


def snap_cuts_to_word_boundaries(cuts, deepgram_words):
    """
    Move every clip source_start and source_end into a silence gap
    between words. Cuts NEVER land mid-word.
    """
    if not deepgram_words or not cuts:
        return cuts

    sorted_words = sorted(deepgram_words, key=lambda w: float(w.get("start") or 0))
    silences = []

    first_word_start = float(sorted_words[0].get("start") or 0)
    if first_word_start > 0.01:
        silences.append({"start": 0.0, "end": first_word_start})

    for i in range(len(sorted_words) - 1):
        gap_start = float(sorted_words[i].get("end") or 0)
        gap_end = float(sorted_words[i + 1].get("start") or 0)
        if gap_end > gap_start + 0.01:
            silences.append({"start": gap_start, "end": gap_end})

    last_word_end = float(sorted_words[-1].get("end") or 0)
    silences.append({"start": last_word_end, "end": last_word_end + 10.0})

    if not silences:
        print("[generate-edit] No silence gaps found — cannot snap cuts", flush=True)
        return cuts

    print(f"[generate-edit] Found {len(silences)} silence gaps for cut snapping", flush=True)

    MAX_SNAP_DISTANCE = 0.5  # Never snap more than 0.5 seconds in either direction

    def find_silence_backward(t):
        """Find the nearest silence gap AT or BEFORE timestamp t, within MAX_SNAP_DISTANCE."""
        best = None
        best_dist = float("inf")
        for s in silences:
            if s["start"] <= t <= s["end"]:
                return t
            mid = (s["start"] + s["end"]) / 2
            if mid <= t:
                dist = t - mid
                if dist < best_dist and dist <= MAX_SNAP_DISTANCE:
                    best_dist = dist
                    best = mid
        return best if best is not None else t

    def find_silence_forward(t):
        """Find the nearest silence gap AT or AFTER timestamp t, within MAX_SNAP_DISTANCE."""
        best = None
        best_dist = float("inf")
        for s in silences:
            if s["start"] <= t <= s["end"]:
                return t
            mid = (s["start"] + s["end"]) / 2
            if mid >= t:
                dist = mid - t
                if dist < best_dist and dist <= MAX_SNAP_DISTANCE:
                    best_dist = dist
                    best = mid
        return best if best is not None else t

    for i, cut in enumerate(cuts):
        old_start = cut["source_start"]
        old_end = cut["source_end"]

        new_start = find_silence_backward(old_start)
        new_start = round(new_start * 1000) / 1000
        if abs(new_start - old_start) > 0.01:
            print(
                f"[generate-edit] Snapped clip {i} start: {old_start:.3f}s → {new_start:.3f}s (backward)",
                flush=True,
            )
        cut["source_start"] = new_start

        new_end = find_silence_forward(old_end)
        new_end = round(new_end * 1000) / 1000
        if abs(new_end - old_end) > 0.01:
            print(
                f"[generate-edit] Snapped clip {i} end: {old_end:.3f}s → {new_end:.3f}s (forward)",
                flush=True,
            )
        cut["source_end"] = new_end

        # Safety: ensure start < end after snapping
        if cut["source_start"] >= cut["source_end"]:
            print(
                f"[generate-edit] WARNING: clip {i} start >= end after snapping, reverting",
                flush=True,
            )
            cut["source_start"] = old_start
            cut["source_end"] = old_end

    # Fix any overlaps created by snapping: earlier clip wins
    for i in range(1, len(cuts)):
        if cuts[i]["source_start"] < cuts[i - 1]["source_end"]:
            # Don't split at midpoint — just close the gap
            # The later clip starts where the earlier clip ends
            print(
                f"[generate-edit] Resolved overlap: clip {i} start moved from {cuts[i]['source_start']:.3f}s to {cuts[i-1]['source_end']:.3f}s",
                flush=True,
            )
            cuts[i]["source_start"] = cuts[i - 1]["source_end"]

    # If a boundary lands inside a word, EXPAND the clip to include the full word
    # Never remove words — only include them
    for i, cut in enumerate(cuts):
        for boundary_name in ["start", "end"]:
            boundary_t = cut[f"source_{boundary_name}"]
            for w in sorted_words:
                w_start = float(w.get("start") or 0)
                w_end = float(w.get("end") or 0)
                if w_start < boundary_t < w_end:
                    word_text = w.get("punctuated_word") or w.get("word") or ""
                    if boundary_name == "start":
                        # Move start EARLIER to include the word
                        new_val = round((w_start - 0.01) * 1000) / 1000
                        print(f"[generate-edit] Including word '{word_text}' in clip {i} (start {boundary_t:.3f}s → {new_val:.3f}s)", flush=True)
                        cut["source_start"] = max(0.0, new_val)
                    else:
                        # Move end LATER to include the word
                        new_val = round((w_end + 0.01) * 1000) / 1000
                        print(f"[generate-edit] Including word '{word_text}' in clip {i} (end {boundary_t:.3f}s → {new_val:.3f}s)", flush=True)
                        cut["source_end"] = new_val
                    break

    return cuts


def snap_sfx_to_word(sfx_entry, deepgram_words):
    """
    Snap a sound effect to the exact timestamp of a spoken word using Deepgram.

    Args:
        sfx_entry: dict with "t" (approx timestamp), "sound", and optionally "word"
        deepgram_words: list of {"word": str, "start": float, "end": float, "punctuated_word": str}

    Returns:
        float: the exact source timestamp to place the sound, or the original "t" as fallback
    """
    target_word = str(sfx_entry.get("word") or "").strip().lower()
    approx_t = float(sfx_entry.get("t") or 0.0)

    if not deepgram_words:
        return approx_t

    # Strategy 1: Find the exact word near the approximate timestamp
    if target_word:
        # Search for the word within ±3 seconds of the approximate timestamp
        candidates = []
        for w in deepgram_words:
            w_text = str(w.get("punctuated_word") or w.get("word") or "").strip().lower()
            w_text_clean = w_text.strip(".,!?;:'\"")
            w_start = float(w.get("start") or 0)

            if w_text_clean == target_word or target_word in w_text_clean:
                distance = abs(w_start - approx_t)
                if distance < 3.0:
                    candidates.append({"start": w_start, "distance": distance, "word": w_text})

        if candidates:
            # Pick the closest match to the approximate timestamp
            best = min(candidates, key=lambda c: c["distance"])
            return best["start"]

    # Strategy 2: No word match found — snap to the nearest word boundary
    # Find the word whose start time is closest to the approximate timestamp
    nearest = None
    nearest_dist = float("inf")
    for w in deepgram_words:
        w_start = float(w.get("start") or 0)
        dist = abs(w_start - approx_t)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest = w_start

    if nearest is not None and nearest_dist < 1.0:
        return nearest

    # Strategy 3: Nothing close — use the original timestamp
    return approx_t


def project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve=None):
    """
    Map a source-timeline timestamp to the output-timeline timestamp.
    Returns the output time, or None if the source time falls in a removed gap.
    """
    for i, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        speed = max(0.25, float(cut.get("speed") or 1.0))

        if src_start <= source_t <= src_end:
            # Integrate speed from clip start to source_t for accurate offset
            _, local_offset, _ = build_variable_speed_setpts(src_start, source_t, speed, speed_curve)
            output_t = float(clip_ranges[i]["start"]) + local_offset
            return round(output_t * 1000) / 1000

    for i, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        if source_t < src_start:
            return float(clip_ranges[i]["start"])

    if clip_ranges:
        return float(clip_ranges[-1]["end"]) - 0.1

    return None


def project_output_time_through_speed_curve(output_t, speed_curve, pre_speed_duration):
    return round(output_t * 1000) / 1000


def project_source_time_to_final_output(source_t, cuts, effective_durations, speed_curve=None, hook_offset=0.0):
    """Map a source timestamp to the final output timeline after cut compression."""
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    pre_speed_t = project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve)
    if pre_speed_t is None:
        return None
    return round((pre_speed_t + hook_offset) * 1000) / 1000


def build_variable_speed_setpts(clip_start, clip_end, clip_speed, speed_curve, log=False):
    """Build a per-frame variable-speed setpts expression for one clip.

    The speed curve flows continuously across the entire timeline — it doesn't
    care about clip boundaries. Each clip samples the curve at multiple points
    and builds a piecewise setpts expression that smoothly ramps speed within
    the clip, just like CapCut/Captions frame-level speed ramping.

    Returns (setpts_value, effective_dur, avg_speed):
        setpts_value: string for setpts=VALUE (None if speed is ~1.0x throughout)
        effective_dur: output duration after variable speed applied
        avg_speed: average speed for audio (constant speed applied via pitch-preserving filter or asetrate for speed ramps)
    """
    dur = clip_end - clip_start
    if dur <= 0.01:
        return None, max(dur, 0.001), clip_speed

    has_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))

    # Sample speed at multiple points across the clip (~1 sample per 0.4s)
    n = max(2, min(8, round(dur / 0.4)))
    interval_dur = dur / n

    speeds = []
    for i in range(n):
        t_mid = clip_start + (i + 0.5) * interval_dur
        curve_speed = 1.0
        if has_curve:
            curve_speed = max(0.5, min(1.4, get_speed_for_timestamp(t_mid, speed_curve)))
        combined = max(0.25, min(4.0, clip_speed * curve_speed))
        speeds.append(combined)

    # Numerical integration for accurate effective duration
    eff_dur = sum(interval_dur / s for s in speeds)
    avg_speed = dur / eff_dur if eff_dur > 0 else 1.0

    # If speed is ~1.0 across the entire clip, skip setpts
    if all(abs(s - 1.0) < 0.005 for s in speeds):
        return None, round(eff_dur, 4), avg_speed

    # Use simple CONSTANT*PTS with the curve-integrated average speed.
    # The numerical integration above already accounts for the speed curve
    # varying across this clip — avg_speed captures that smoothly.
    setpts_val = f"{1.0/avg_speed:.4f}*PTS"
    if log:
        speed_range = f"{min(speeds):.2f}x-{max(speeds):.2f}x"
        print(f"[speed] Curve-averaged setpts: {n} samples, {speed_range}, avg={avg_speed:.3f}x, eff={eff_dur:.3f}s", flush=True)
    return setpts_val, round(eff_dur, 4), avg_speed



def compute_effective_durations(cuts, speed_curve=None):
    """Compute output duration for each clip using numerical integration of speed curve."""
    durations = []
    for cut in (cuts or []):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        _, eff_dur, _ = build_variable_speed_setpts(src_start, src_end, clip_speed, speed_curve)
        durations.append(round(eff_dur, 3))
    return durations


def prepend_hook_clip(output_path, edit_plan, work_dir):
    """Extract hook from rendered output using filter-based trim (frame-precise) and prepend."""
    hook_clip_data = edit_plan.get("hook_clip")
    edit_plan["_hook_offset"] = 0.0
    if not isinstance(hook_clip_data, dict):
        return

    cuts = edit_plan.get("cuts") or []
    speed_curve = edit_plan.get("_parsed_speed_curve")
    effective_durations = compute_effective_durations(cuts, speed_curve)
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)

    hook_src_start = float(hook_clip_data.get("source_start") or 0.0)
    hook_src_end = float(hook_clip_data.get("source_end") or 0.0)
    hook_src_dur = hook_src_end - hook_src_start
    if not (0.5 <= hook_src_dur <= 3.0):
        print(f"[hook] Hook duration {hook_src_dur:.2f}s out of range — skipping", flush=True)
        return

    hook_clip_idx = None
    for i, cut in enumerate(cuts):
        cs = float(cut["source_start"])
        ce = float(cut["source_end"])
        if hook_src_start >= cs - 0.1 and hook_src_start <= ce:
            hook_clip_idx = i
            break

    if hook_clip_idx is not None:
        ce = float(cuts[hook_clip_idx]["source_end"])
        if hook_src_end > ce:
            print(f"[hook] Clamping hook end from {hook_src_end:.2f} to cut end {ce:.2f}", flush=True)
            hook_src_end = ce
            hook_clip_data["source_end"] = ce

    if hook_clip_idx is None:
        print("[hook] Could not find hook clip in cuts array — skipping", flush=True)
        return

    # Detect where audio goes silent after hook start — that's the true end of the hook moment
    # Adaptive: use noise floor + 10dB for hook silence (less sensitive than tightening)
    source_path = edit_plan.get("_source_path")
    _loudness = edit_plan.get("_source_loudness") or {}
    _hook_silence_db = -30  # default
    if _loudness.get("noise_floor_db") is not None:
        _hook_silence_db = max(-45, min(-20, _loudness["noise_floor_db"] + 10))
    if source_path and os.path.exists(source_path):
        try:
            silence_cmd = [
                "ffmpeg", "-i", source_path,
                "-af", f"atrim=start={hook_src_start:.3f}:end={hook_src_end:.3f},asetpts=PTS-STARTPTS,silencedetect=noise={_hook_silence_db:.0f}dB:d=0.15",
                "-f", "null", "-"
            ]
            silence_result = subprocess.run(silence_cmd, capture_output=True, text=True, timeout=15)
            silence_starts = re.findall(r"silence_start:\s*([\d.]+)", silence_result.stderr)
            if silence_starts:
                # Use the LAST silence_start — that's the trailing silence after all speech/audio ends
                last_silence = float(silence_starts[-1])
                if last_silence >= 0.3:
                    true_end = hook_src_start + last_silence
                    if true_end < hook_src_end - 0.1:
                        print(
                            f"[hook] Audio ends at {last_silence:.2f}s into hook — "
                            f"tightening source_end: {hook_src_end:.2f} -> {true_end:.2f}",
                            flush=True,
                        )
                        hook_src_end = true_end
        except Exception as e:
            print(f"[hook] Silence detection failed ({e}) — using original end", flush=True)

    clip_src_start = float(cuts[hook_clip_idx]["source_start"])
    clip_src_end = float(cuts[hook_clip_idx]["source_end"])
    clip_speed = max(0.25, float(cuts[hook_clip_idx].get("speed") or 1.0))
    curve_speed = 1.0
    if speed_curve and speed_curve != "none":
        clip_mid = (clip_src_start + clip_src_end) / 2.0
        curve_speed = max(0.5, min(1.4, get_speed_for_timestamp(clip_mid, speed_curve)))
    combined_speed = clip_speed * curve_speed

    clip_render_start = float(clip_ranges[hook_clip_idx]["start"])
    clip_render_end = float(clip_ranges[hook_clip_idx]["end"])
    start_offset = (hook_src_start - clip_src_start) / combined_speed
    end_offset = (hook_src_end - clip_src_start) / combined_speed
    hook_render_start = clip_render_start + start_offset
    hook_render_end = min(clip_render_start + end_offset, clip_render_end)

    hook_render_dur = hook_render_end - hook_render_start
    if hook_render_dur <= 0.1:
        print("[hook] Hook render duration too short — skipping", flush=True)
        return

    print(
        f"[hook] Extracting hook: src {hook_src_start:.2f}-{hook_src_end:.2f} "
        f"-> rendered {hook_render_start:.3f}-{hook_render_end:.3f} ({hook_render_dur:.2f}s)",
        flush=True,
    )

    # Build hook video filter — add zoom if the hook's clip had it
    _hook_zoom = edit_plan.get("_hook_zoom")
    if _hook_zoom and _hook_zoom != "none":
        face_positions = edit_plan.get("_face_positions") or []
        hook_mid = (hook_src_start + hook_src_end) / 2.0
        cf = min(face_positions, key=lambda p: abs(float(p.get("t", 0)) - hook_mid)) if face_positions else None
        hf = max(1, round((hook_render_end - hook_render_start) * 30))
        # Adaptive hook zoom: stronger when face is detected and close, subtler otherwise
        if cf and cf.get("found"):
            _face_conf = float(cf.get("confidence", 0.5))
            # Confident face detection: stronger zoom (up to 0.10)
            # Low confidence: gentler zoom (0.04)
            zr = 0.04 + 0.06 * min(1.0, _face_conf)
        else:
            # No face: minimal zoom to avoid zooming into empty space
            zr = 0.04
        print(f"[zoom] Hook zoom ratio: {zr:.3f} (face={'yes' if cf and cf.get('found') else 'no'})", flush=True)
        prog = f"min(n/{hf}\\,1.0)"
        if cf and cf.get("found"):
            fx, fy = float(cf.get("cx", 540)), float(cf.get("cy", 960))
            ox = max(-240, min(240, fx - 540))
            oy = max(-320, min(320, fy - 960))
            cx = f"max(0\\,min((iw-1080)/2+{ox:.1f}*{prog}*{zr:.4f}\\,iw-1080))"
            cy = f"max(0\\,min((ih-1920)/2+{oy:.1f}*{prog}*{zr:.4f}\\,ih-1920))"
        else:
            cx, cy = "(iw-1080)/2", "(ih-1920)/2"
        zoom_vf = (
            f",scale=w='trunc(iw*(1.0+{zr:.4f}*{prog})/2)*2'"
            f":h='trunc(ih*(1.0+{zr:.4f}*{prog})/2)*2'"
            f":eval=frame:flags=bicubic"
            f",crop=1080:1920:x='{cx}':y='{cy}'"
        )
        print(f"[zoom] Applying zoom to hook extraction", flush=True)
    else:
        zoom_vf = ""

    hook_vf = (
        f"[0:v]trim=start={hook_render_start:.3f}:end={hook_render_end:.3f},"
        f"setpts=PTS-STARTPTS{zoom_vf}[hv]"
    )
    hook_af = (
        f"[0:a]atrim=start={hook_render_start:.3f}:end={hook_render_end:.3f},"
        f"asetpts=PTS-STARTPTS[ha]"
    )
    print(f"[DIAG] Hook timing: src={hook_src_start:.3f}-{hook_src_end:.3f} clip_src={clip_src_start:.3f}-{float(cuts[hook_clip_idx]['source_end']):.3f} clip_render={clip_render_start:.3f}-{clip_render_end:.3f} speed={combined_speed:.3f} start_offset={start_offset:.3f} end_offset={end_offset:.3f} render={hook_render_start:.3f}-{hook_render_end:.3f}", flush=True)

    hook_path = os.path.join(work_dir, "hook_clip.mp4")
    hook_cmd = [
        "ffmpeg", "-threads", "0", "-y",
        "-i", output_path,
        "-filter_complex",
        f"{hook_vf};{hook_af}",
        "-map", "[hv]", "-map", "[ha]",
    ] + get_encode_args("lossless") + [
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        hook_path,
    ]
    result = subprocess.run(hook_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 or not os.path.exists(hook_path) or os.path.getsize(hook_path) <= 0:
        print("[hook] Hook extraction failed — continuing without hook", flush=True)
        if result.stderr:
            print(f"[hook] stderr (last 300): {result.stderr[-300:]}", flush=True)
        return

    hook_actual_dur = probe_duration(hook_path) or hook_render_dur
    # Stream-level diagnostics from cached probe (no extra ffprobe call)
    try:
        _hpd = _probe_full(hook_path)
        _hcv = _hca = 0.0
        for _hs in (_hpd.get("streams") or []):
            if _hs.get("codec_type") == "video" and _hs.get("duration"): _hcv = float(_hs["duration"])
            elif _hs.get("codec_type") == "audio" and _hs.get("duration"): _hca = float(_hs["duration"])
        print(f"[DIAG] Hook clip: video={_hcv:.3f}s audio={_hca:.3f}s diff={_hcv - _hca:.4f}s", flush=True)
    except Exception:
        pass

    concat_list_path = os.path.join(work_dir, "concat_list.txt")
    with open(concat_list_path, "w") as f:
        f.write(f"file '{hook_path}'\n")
        f.write(f"file '{output_path}'\n")

    hooked_output = os.path.join(work_dir, "hooked_output.mp4")
    concat_cmd = [
        "ffmpeg", "-threads", "0", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        "-movflags", "+faststart",
        hooked_output,
    ]
    concat_result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=60)
    if concat_result.returncode != 0 or not os.path.exists(hooked_output) or os.path.getsize(hooked_output) <= 0:
        print("[hook] Concat failed — continuing without hook", flush=True)
        if concat_result.stderr:
            print(f"[hook] concat stderr (last 300): {concat_result.stderr[-300:]}", flush=True)
        return

    os.replace(hooked_output, output_path)
    probe_cache_clear(output_path)  # file changed — invalidate cache
    try:
        _hcpd = _probe_full(output_path)
        _hv = _ha = 0.0
        for _hs in (_hcpd.get("streams") or []):
            if _hs.get("codec_type") == "video" and _hs.get("duration"): _hv = float(_hs["duration"])
            elif _hs.get("codec_type") == "audio" and _hs.get("duration"): _ha = float(_hs["duration"])
        print(f"[DIAG] After hook concat: video={_hv:.3f}s audio={_ha:.3f}s diff={_hv - _ha:.4f}s", flush=True)
    except Exception:
        pass
    edit_plan["_hook_offset"] = hook_actual_dur
    print(f"[hook] Prepended {hook_actual_dur:.2f}s hook teaser", flush=True)


def mix_sfx_after_speed_curve(output_path, edit_plan, cuts, effective_durations, work_dir):
    """
    Mix sound effects into the final video AFTER the speed curve has been applied.
    Uses -c:v copy so the video stream is not re-encoded.
    Timestamps are projected from source time to final output time.
    """
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    parsed_sfx = list(edit_plan.get("_parsed_sound_effects", []))
    hook_offset = float(edit_plan.get("_hook_offset") or 0.0)
    speech_segments = (edit_plan.get("analysis_data") or {}).get("speech", {}).get("segments") or []

    if not parsed_sfx:
        print("[sfx] No sound effects to mix", flush=True)
        return

    sfx_entries = []
    for sfx in parsed_sfx:
        sound_style = normalize_sfx_style(sfx.get("sound") or "none")
        if sound_style == "none":
            continue
        sound_path = get_sfx_path(sound_style)
        if not sound_path:
            continue

        raw_t = float(sfx.get("t") or 0.0)
        word = str(sfx.get("word") or "")
        is_auto = sfx.get("_auto", False)

        if is_auto:
            final_t = max(0.0, hook_offset + raw_t)
            sfx_entries.append({
                "sound": sfx.get("sound", "click"),
                "path": get_sfx_path(normalize_sfx_style(sfx.get("sound", "click"))),
                "source_t": raw_t,
                "final_t": final_t,
            })
            if sfx_entries[-1]["path"]:
                print(f"[sfx] auto {sfx.get('sound')}: output={final_t:.3f}s (text overlay)", flush=True)
            else:
                sfx_entries.pop()
            continue

        if word == "scene_change":
            nearest_boundary = raw_t
            for cr in clip_ranges:
                for edge in [float(cr["start"]), float(cr["end"])]:
                    if abs(edge - raw_t) < abs(nearest_boundary - raw_t) or nearest_boundary == raw_t:
                        if abs(edge - raw_t) < 2.0:
                            nearest_boundary = edge
            source_t = nearest_boundary
            if source_t != raw_t:
                print(f"[sfx] Snapped transition sound to clip boundary: {raw_t:.3f}s → {source_t:.3f}s", flush=True)
        else:
            deepgram_words = edit_plan.get("_deepgram_words", [])
            source_t = snap_sfx_to_word(sfx, deepgram_words)
            if source_t != raw_t:
                print(
                    f"[sfx] Snapped {sfx.get('sound')} from {raw_t:.3f}s to {source_t:.3f}s (word='{word}')",
                    flush=True,
                )

        # Step 1: Project source time → pre-speed-curve output time (accounts for tightening)
        pre_sc_t = project_source_time_to_output(source_t, cuts, clip_ranges, edit_plan.get("_parsed_speed_curve"))
        if pre_sc_t is None:
            print(f"[sfx] {sound_style} at source={source_t:.3f}s — could not project, skipping", flush=True)
            continue

        final_t = hook_offset + pre_sc_t
        final_t = max(0.0, final_t)

        sfx_entries.append({
            "sound": sound_style,
            "path": sound_path,
            "source_t": source_t,
            "final_t": final_t,
        })
        print(
            f"[sfx] {sound_style}: source={source_t:.3f}s → tightened={pre_sc_t:.3f}s → final={final_t:.3f}s",
            flush=True,
        )

    if not sfx_entries:
        print("[sfx] No valid sound effects after projection", flush=True)
        return

    input_args = ["-i", output_path]
    filter_parts = []
    labels = []

    for i, entry in enumerate(sfx_entries):
        input_args += ["-i", entry["path"]]
        offset_ms = round(entry["final_t"] * 1000)
        label = f"[sfx{i}]"
        _vol = get_sfx_volume(entry["sound"], entry["final_t"], speech_segments, is_text_overlay=False)
        filter_parts.append(
            f"[{i + 1}:a]volume={_vol:.3f},adelay={offset_ms}|{offset_ms}{label}"
        )
        labels.append(label)

    n_inputs = len(labels) + 1
    all_inputs = "[0:a]" + "".join(labels)
    filter_parts.append(
        f"{all_inputs}amix=inputs={n_inputs}:duration=first:dropout_transition=0:normalize=0[mixed]"
    )

    filter_complex = ";".join(filter_parts)

    temp_output = os.path.join(work_dir, "sfx_mixed.mp4")
    cmd = [
        "ffmpeg", "-threads", "0", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[mixed]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        temp_output,
    ]

    print(f"[sfx] Mixing {len(sfx_entries)} sound effect(s) into final video...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        print(f"[sfx] Mix failed: {result.stderr[-300:]}", flush=True)
        print("[sfx] Keeping video without sound effects", flush=True)
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return

    if not validate_output(temp_output, "sfx_mix"):
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return

    os.replace(temp_output, output_path)
    print("[sfx] Sound effects mixed successfully", flush=True)


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None,
                      broll_clips=None, broll_fetch_futures=None):
    speed_curve = edit_plan.get("_parsed_speed_curve")
    _normalize_vf = edit_plan.get("_normalize_vf")  # scale/crop filter (None if native 1080x1920)
    # Adaptive transition duration based on Gemini pacing assessment
    TRANSITION_DURATION = get_transition_duration(edit_plan.get("pacing"))
    print(f"[render] transition_duration={TRANSITION_DURATION:.2f}s (pacing={edit_plan.get('pacing')})", flush=True)
    original_cuts = list(cuts)
    render_cuts = list(cuts)
    edit_plan["_hook_offset"] = 0.0

    hook_clip = edit_plan.get("hook_clip")
    if isinstance(hook_clip, dict):
        # Hook clips ALWAYS get tight zoom (slow_in) — this is the "grab attention"
        # moment. Research: tight framing + immediate speech = >65% 3-second retention.
        hook_zoom = "slow_in"
        edit_plan["_hook_zoom"] = hook_zoom

        # Trim hook to start at speech — no dead air before first word in hook
        _hook_start = float(hook_clip.get("source_start") or 0.0)
        _hook_end = float(hook_clip.get("source_end") or 0.0)
        if transcript and isinstance(transcript, dict):
            _hook_words = transcript.get("words") or []
            for _hw in _hook_words:
                _hw_start = float(_hw.get("start") or 0)
                _hw_end = float(_hw.get("end") or 0)
                if _hw_start >= _hook_start - 0.05 and _hw_start <= _hook_end:
                    # Found first word in hook range — start 0.1s before it
                    _new_start = max(0.0, _hw_start - 0.10)
                    if _new_start > _hook_start + 0.15:
                        print(f"[hook] Trimmed hook start {_hook_start:.3f}→{_new_start:.3f} (speech at {_hw_start:.3f})", flush=True)
                        _hook_start = _new_start
                    break

        render_cuts = [{
            "source_start": _hook_start,
            "source_end": _hook_end,
            "zoom": hook_zoom,
            "speed": 1.0,
            "transition_out": "none",
            "freeze_frame": False,
            "_is_hook": True,
        }] + render_cuts

    # Tag each cut with its pre-split index so text overlays can map back
    # Hook clip(s) get _original_idx = -1; content clips get 0, 1, 2, ...
    _content_idx = 0
    for _rc in render_cuts:
        if _rc.get("_is_hook"):
            _rc["_original_idx"] = -1
        else:
            _rc["_original_idx"] = _content_idx
            _content_idx += 1

    # Speed ramping is applied per-frame via variable setpts expressions —
    # no clip splitting needed. Each clip evaluates the speed curve continuously.

    n = len(render_cuts)
    source_res = probe_resolution(source_path)
    # Skip keyframe forcing — trim filter works on decoded frames, always frame-accurate
    render_source = source_path
    # Diagnostic probe uses cached data — no extra ffprobe call
    _cached = _probe_full(render_source)
    _vs = next((s for s in (_cached.get("streams") or []) if s.get("codec_type") == "video"), {})
    print(f"[DIAG] Render source: codec={_vs.get('codec_name')} pix_fmt={_vs.get('pix_fmt')} fps={_vs.get('r_frame_rate')}", flush=True)
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

    # Compute effective durations from recipe with per-segment speed applied.
    # Frame-quantize to match what fps=30 actually produces — each clip's output
    # is round(dur * 30) frames, so its true duration is round(dur * 30) / 30.
    # Without this, xfade offsets can exceed the actual stream duration → EINVAL.
    effective_durations = compute_effective_durations(render_cuts, speed_curve)
    effective_durations = [round(d * 30) / 30 for d in effective_durations]
    hook_offset = 0.0
    if isinstance(hook_clip, dict) and effective_durations:
        # Sum durations of all hook clip segments
        for _hi, _hcut in enumerate(render_cuts):
            if _hcut.get("_is_hook"):
                hook_offset += effective_durations[_hi] if _hi < len(effective_durations) else 0.0
            else:
                break  # hook segments are always at the start
        edit_plan["_hook_offset"] = hook_offset
    # Store render's split cuts and effective_durations so B-roll/SFX projection
    # uses the same timeline as the actual render (not the pre-split approximation)
    edit_plan["_render_cuts"] = render_cuts
    edit_plan["_render_effective_durations"] = effective_durations

    _caption_pngs = []
    caption_style = str(edit_plan.get("caption_style") or "none").lower()
    _all_caption_styles = {"volt", "clarity", "impact", "ember", "velocity",
                           "archive", "lumen", "rebel"}

    # Project words to output timeline for captions
    _projected_words = []
    if caption_style != "none" and caption_style in _all_caption_styles and transcript.get("words"):
        _projected_words = project_words_to_output(
            transcript, render_cuts, effective_durations,
            hook_offset=0.0,
            hook_clip=None, speed_curve=speed_curve,
            transition_duration=TRANSITION_DURATION,
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
    _total_render_dur = sum(effective_durations)
    _vibe = str(edit_plan.get("_user_vibe") or edit_plan.get("notes") or "")
    _emphasis_moments_raw = edit_plan.get("emphasis_moments") or []

    # Project emphasis moment timestamps from source time → output timeline
    # (Gemini gives source timestamps, but Remotion overlay uses output timeline)
    _clip_ranges_for_em = get_output_clip_ranges(render_cuts, effective_durations, transition_duration=TRANSITION_DURATION)
    _emphasis_moments = []
    for _em in _emphasis_moments_raw:
        _em_copy = dict(_em)
        _src_t = float(_em.get("t") or 0)
        _out_t = project_source_time_to_output(_src_t, render_cuts, _clip_ranges_for_em, speed_curve)
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

    # Launch Remotion overlay render in background thread (captions + visual effects)
    _overlay_future = None
    _caption_video = None
    _caption_pngs = []
    if _projected_words and caption_style:
        def _do_overlay_render():
            return render_remotion_overlay(
                _projected_words, caption_style,
                {"width": 1080, "height": 1920},
                _cap_kw, work_dir,
                total_duration=_total_render_dur, fps=30,
                cuts=_cuts_for_remotion,
                emphasis_moments=_emphasis_moments,
                vibe=_vibe,
            )

        _overlay_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _overlay_future = _overlay_pool.submit(_do_overlay_render)
        print(f"[remotion] Background render started: {caption_style} ({len(_projected_words)} words), "
              f"{len(_emphasis_moments)} emphasis, vibe=\"{_vibe[:50]}\"", flush=True)
    else:
        print(f"[captions] No captions (style={caption_style}, words={len(_projected_words)})", flush=True)

    for i, cut in enumerate(render_cuts):
        src_dur = round((float(cut["source_end"]) - float(cut["source_start"])) * 1000) / 1000
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        _, _eff, _avg = build_variable_speed_setpts(
            float(cut["source_start"]), float(cut["source_end"]), clip_speed, speed_curve
        )
        eff_dur = effective_durations[i]
        print(
            f"[ffmpeg] Segment {i}: {cut['source_start']:.3f}s->{cut['source_end']:.3f}s "
            f"(dur={src_dur:.3f}s, eff={eff_dur:.3f}s @ avg_speed={_avg:.2f}x)",
            flush=True,
        )

    video_filters = []
    audio_filters = []
    _segment_data = []  # per-segment data for parallel rendering
    face_positions = edit_plan.get("_face_positions") or []
    dense_face_trajectory = edit_plan.get("_dense_face_trajectory") or []
    _has_dense_trajectory = len(dense_face_trajectory) > 0
    n_segment_inputs = len(render_cuts)  # each segment gets its own input

    for i, cut in enumerate(render_cuts):
        start = float(cut["source_start"])
        end = float(cut["source_end"])
        seg_dur = end - start
        # Each segment is a separate input with pre-seeking.
        # NVDEC hardware decode: GPU decodes video → auto-transfers to CPU for filter chain.
        # Using -hwaccel cuda (without -hwaccel_output_format cuda) so frames land in system
        # memory automatically — no hwdownload filter needed, works with all filter chains.
        _hw_args = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
        _seg_input = (
            _hw_args
            + ["-ss", f"{start:.3f}", "-t", f"{seg_dur:.3f}",
               "-analyzeduration", "5000000", "-probesize", "5000000",
               "-i", render_source]
        )
        input_args += _seg_input
        speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))

        # Build variable-speed setpts expression — speed curve flows continuously
        # across the timeline, independent of clip boundaries
        setpts_val, _, avg_speed = build_variable_speed_setpts(start, end, speed, speed_curve, log=True)
        combined_speed = avg_speed  # for audio (constant) and logging
        zoom = str(cut.get("zoom") or "none")
        if has_burned_captions and zoom in ["punch_in", "punch_out"]:
            zoom = "slow_in" if zoom == "punch_in" else "slow_out"
        # Always-on Ken Burns: no clip is ever truly static.
        # Matches Captions app where every talking-head shot has subtle movement.
        if zoom == "none" and not cut.get("_is_broll") and not cut.get("_is_hook"):
            zoom = "slow_in"

        eff_dur = effective_durations[i]
        fps = 30
        total_frames = max(1, round(eff_dur * fps))
        MIN_ZOOM_FRAMES = 90
        if zoom != "none" and total_frames < MIN_ZOOM_FRAMES:
            zoom_scale_factor = total_frames / MIN_ZOOM_FRAMES
            total_frames_for_zoom = MIN_ZOOM_FRAMES
        else:
            zoom_scale_factor = 1.0
            total_frames_for_zoom = total_frames
        # 2-camera simulation: alternate between wide (100%) and tight (115%) per cut.
        # Tight cuts get a static 15% zoom (instant crop, face-centered) + subtle drift.
        # Wide cuts get subtle 4-5% Ken Burns drift. Research: 115% is standard reframe.
        _is_tight_cut = (i % 2 == 1) and zoom not in ("cut_zoom",) and not cut.get("_is_broll") and not cut.get("_is_hook")
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
        if not cut.get("_is_broll") and not cut.get("_is_hook") and zoom != "cut_zoom":
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
            _t = f"min(n/{tf_val}\\,1.0)"
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

        if zoom == "slow_in":
            tf = max(1, total_frames_for_zoom) if zoom_scale_factor < 1.0 else max(1, total_frames)
            zoom_range = (zoom_max - 1.0) * zoom_scale_factor
            # Smoothstep easing for buttery smooth zoom
            _si_p = f"min(n/{tf}\\,1.0)"
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
            smooth = f"(min(n/{tf}\\,1))*(min(n/{tf}\\,1))*(3-2*(min(n/{tf}\\,1)))"
            scale_expr = (
                f"scale=w='trunc(iw*({1.0 + zoom_range:.4f}-{zoom_range:.4f}*{smooth})/2)*2'"
                f":h='trunc(ih*({1.0 + zoom_range:.4f}-{zoom_range:.4f}*{smooth})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf, reverse=True)
        elif zoom == "punch_in":
            punch_range = 0.18 * zoom_scale_factor  # aggressive punch for Captions-level impact
            tf = max(1, total_frames_for_zoom)
            # Smoothstep ease for natural feel
            _pi_p = f"min(n/{tf}\\,1.0)"
            _pi_ease = f"({_pi_p}*{_pi_p}*(3-2*{_pi_p}))"
            scale_expr = (
                f"scale=w='trunc(iw*(1.0+{punch_range:.4f}*{_pi_ease})/2)*2'"
                f":h='trunc(ih*(1.0+{punch_range:.4f}*{_pi_ease})/2)*2'"
            )
            zoom_filter = _face_crop(scale_expr, tf)
        elif zoom == "punch_out":
            punch_range = 0.18 * zoom_scale_factor  # aggressive punch for Captions-level impact
            tf = max(1, total_frames_for_zoom)
            _po_p = f"min(n/{tf}\\,1.0)"
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
            cz_p = f"min(n/{cz_frames}\\,1.0)"
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
        # fps=30 AFTER speed change to avoid frame count drift at clip boundaries
        v_chain = []
        if _normalize_vf:
            v_chain.append(_normalize_vf)
        v_chain.append("setpts=PTS-STARTPTS")

        if setpts_val:
            v_chain.append(f"setpts={setpts_val}")
        v_chain.append("fps=30")
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
        if not cut.get("_is_broll") and not cut.get("_is_hook"):
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

        # Audio: each segment has its own pre-seeked input (no atrim needed)
        a_chain = ["asetpts=PTS-STARTPTS"]
        _has_active_speed_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
        if abs(combined_speed - 1.0) > 0.001:
            if _has_active_speed_curve:
                # Speed ramping is active — pitch shift is intentional (the effect)
                a_chain.append(f"asetrate={sample_rate}*{combined_speed:.4f}")
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

        # Collect per-segment data for parallel rendering
        _segment_data.append({
            "input_args": list(_seg_input),
            "v_chain": ','.join(v_chain),
            "a_chain": ','.join(a_chain),
        })

    # ── Parallel segment pre-rendering ─────────────────────────────────────
    # When GPU is available, render each segment independently in parallel.
    # This distributes heavy per-frame work (zoompan, scale, speed curves)
    # across all CPU cores simultaneously instead of the single-threaded
    # filter_complex scheduler processing them sequentially.
    # The concat pass then only handles transitions, overlays, and final
    # encoding — no per-segment processing needed, so it's blazing fast.
    _PARALLEL_RENDER = n >= 2  # parallel pre-render works with both NVENC and CPU encoder

    if _PARALLEL_RENDER:
        _n_cores = os.cpu_count() or 32
        _max_workers = min(n, 8, _n_cores // 3)  # 3 threads per worker
        print(f"[render] PARALLEL MODE: {n} segments, {_max_workers} workers, {_n_cores} cores", flush=True)
        _seg_t0 = time.time()
        _seg_paths = [None] * n
        _seg_errors = []

        # Choose lossless encoder: NVENC if available, otherwise libx264 ultrafast crf 0
        _seg_venc = (
            ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "lossless"]
            if _HAS_NVENC else
            ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "0"]
        )

        def _render_one_segment(seg_idx):
            """Render one segment to lossless intermediate."""
            seg_out = os.path.join(work_dir, f"_seg_{seg_idx}.mkv")
            sd = _segment_data[seg_idx]
            fc = f"[0:v]{sd['v_chain']}[outv];[0:a]{sd['a_chain']}[outa]"
            cmd = (
                ["ffmpeg", "-y", "-v", "warning", "-nostats", "-threads", "3"]
                + sd["input_args"]
                + ["-filter_complex", fc, "-map", "[outv]", "-map", "[outa]"]
                + _seg_venc
                + ["-c:a", "aac", "-b:a", "192k", seg_out]
            )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                    env={**os.environ})
            if result.returncode != 0:
                raise RuntimeError(f"Segment {seg_idx}: {(result.stderr or '')[-500:]}")
            return seg_out

        with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as seg_pool:
            _seg_futures = {seg_pool.submit(_render_one_segment, i): i for i in range(n)}
            for fut in concurrent.futures.as_completed(_seg_futures):
                idx = _seg_futures[fut]
                try:
                    _seg_paths[idx] = fut.result()
                except Exception as seg_err:
                    _seg_errors.append((idx, str(seg_err)))
                    print(f"[render] Segment {idx} FAILED: {seg_err}", flush=True)

        _seg_elapsed = time.time() - _seg_t0

        if _seg_errors:
            print(f"[render] {len(_seg_errors)} segment(s) failed in {_seg_elapsed:.1f}s — falling back to single-pass", flush=True)
            _PARALLEL_RENDER = False
        else:
            print(f"[render] Parallel pre-render: {n} segments in {_seg_elapsed:.1f}s", flush=True)
            # Replace inputs with pre-rendered segments (no hwaccel needed)
            input_args = []
            for _sp in _seg_paths:
                input_args += ["-i", _sp]
            # Replace per-segment filters with fps=30 to normalize timebase to 1/30
            # (MKV intermediates default to 1/1000 timebase which breaks xfade)
            video_filters = [f"[{i}:v]fps=30[v{i}]" for i in range(n)]
            audio_filters = [f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]" for i in range(n)]
            print(f"[render] Concat pass: transitions + overlay + SFX + final encode", flush=True)

    # ── SFX collection ───────────────────────────────────────────────────────
    sfx_input_args   = []
    sfx_filter_strs  = []
    sfx_audio_labels = []
    sfx_timestamps   = []  # collect timestamps for audio ducking
    extra_input_index = n_segment_inputs  # SFX inputs start after segment inputs

    if True:
        _speech_segs = speech_segments or (edit_plan.get("analysis_data") or {}).get("speech", {}).get("segments") or []
        _base_cuts = original_cuts
        _base_effective_durations = compute_effective_durations(_base_cuts, speed_curve) if _base_cuts else []

        _running = hook_offset + (_base_effective_durations[0] if _base_effective_durations else 0.0)
        _transition_times = []
        for _i in range(max(0, len(_base_cuts) - 1)):
            _transition = str(_base_cuts[_i].get("transition_out") or "none").lower()
            _td = TRANSITION_DURATION if _transition not in ("none", "clean_cut", "") else 0.0
            _event_time = max(0.0, _running - 0.15)
            _transition_times.append(_event_time)
            _running = _running + _base_effective_durations[_i + 1] - _td

        for _i in range(max(0, len(_base_cuts) - 1)):
            _sound_style = normalize_sfx_style(_base_cuts[_i].get("transition_sound") or _base_cuts[_i].get("sfx_style") or "none")
            if _sound_style == "none":
                continue
            _sound_path = get_sfx_path(_sound_style)
            if not _sound_path:
                continue
            _event_time = _transition_times[_i]
            _offset_ms  = max(0, round(_event_time * 1000))
            _vol        = get_sfx_volume(_sound_style, _event_time, _speech_segs, is_text_overlay=False)
            _label      = f"[snd{_i}]"
            sfx_input_args  += ["-i", _sound_path]
            sfx_filter_strs.append(
                f"[{extra_input_index}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}{_label}"
            )
            sfx_audio_labels.append(_label)
            sfx_timestamps.append(_event_time)
            print(f"[sfx] transition {_i}: {_sound_style} vol={_vol:.3f} at {_event_time:.3f}s", flush=True)
            extra_input_index += 1

        _clip_ranges = get_output_clip_ranges(_base_cuts, _base_effective_durations, transition_duration=TRANSITION_DURATION) if _base_cuts else []
        for _i, _overlay in enumerate(edit_plan.get("text_overlays") or []):
            _clip_idx = int(_overlay.get("appear_at_clip") or 0)
            if _clip_idx < 0 or _clip_idx >= len(_clip_ranges):
                continue
            _sfx_style = normalize_sfx_style(_overlay.get("sfx_style") or "none")
            if _sfx_style == "none":
                continue
            _sound_path = get_sfx_path(_sfx_style)
            if not _sound_path:
                continue
            _ts        = max(0.0, hook_offset + float(_clip_ranges[_clip_idx].get("start") or 0) + 0.02)
            _offset_ms = round(_ts * 1000)
            _vol       = get_sfx_volume(_sfx_style, _ts, _speech_segs, is_text_overlay=True)
            _label     = f"[txtsnd{_i}]"
            sfx_input_args  += ["-i", _sound_path]
            sfx_filter_strs.append(
                f"[{extra_input_index}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}{_label}"
            )
            sfx_audio_labels.append(_label)
            sfx_timestamps.append(_ts)
            print(f"[sfx] text_overlay {_i}: {_sfx_style} vol={_vol:.3f} at {_ts:.3f}s", flush=True)
            extra_input_index += 1

        # Use the full render cuts (with hook prepended) so SFX that land
        # in the hook clip map to the start of the video automatically.
        _full_durations = compute_effective_durations(render_cuts, speed_curve) if render_cuts else []
        _full_ranges = get_output_clip_ranges(render_cuts, _full_durations, transition_duration=TRANSITION_DURATION) if render_cuts else []

        parsed_sfx = edit_plan.get("_parsed_sound_effects", [])
        for _i, _sfx in enumerate(parsed_sfx):
            _sound_style = normalize_sfx_style(_sfx.get("sound") or "none")
            if _sound_style == "none":
                continue
            _sound_path = get_sfx_path(_sound_style)
            if not _sound_path:
                continue
            _source_t = float(_sfx.get("t") or 0.0)
            _projected_t = project_source_time_to_output(_source_t, render_cuts, _full_ranges, edit_plan.get("_parsed_speed_curve"))
            if _projected_t is None:
                print(
                    f"[sfx] sound_effect: {_sound_style} at source {_source_t:.3f}s — could not project, skipping",
                    flush=True,
                )
                continue
            _ts = max(0.0, _projected_t)
            _offset_ms = round(_ts * 1000)
            _vol = get_sfx_volume(_sound_style, _ts, _speech_segs, is_text_overlay=False)
            _label = f"[timesfx{_i}]"
            sfx_input_args += ["-i", _sound_path]
            sfx_filter_strs.append(
                f"[{extra_input_index}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}{_label}"
            )
            sfx_audio_labels.append(_label)
            sfx_timestamps.append(_ts)
            print(
                f"[sfx] sound_effect: {_sound_style} vol={_vol:.3f} at source={_source_t:.3f}s → output={_ts:.3f}s",
                flush=True,
            )
            extra_input_index += 1

    transition_filters = []
    tl_video = "v0"
    tl_audio = "a0"
    running_dur = effective_durations[0] if effective_durations else 0.0

    CUSTOM_TRANSITIONS = {"flash", "glitch", "whip_left", "whip_right"}
    XFADE_TRANSITIONS = {
        "fade","fadeblack","dissolve",
        "wipeleft","wiperight","wipeup","wipedown",
        "smoothleft","smoothright","smoothup","smoothdown",
        "zoomin",
    }

    # ── Auto-transition assignment ──────────────────────────────────────
    # When Gemini assigns "none" (hard cut), auto-upgrade ~30% of cuts to
    # subtle transitions based on context. This matches the Captions app
    # where hard cuts are mixed with smooth dissolves for professional flow.
    _auto_transitions_added = 0
    _em_all = edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or []
    _SUBTLE_TRANSITIONS = ["dissolve", "smoothleft", "smoothright", "fade"]
    for _ci in range(1, n):
        _existing = str(render_cuts[_ci - 1].get("transition_out") or "none").lower()
        if _existing != "none" or render_cuts[_ci].get("_is_broll") or render_cuts[_ci - 1].get("_is_hook"):
            continue
        # Auto-assign at emphasis moments or every 3rd cut (whichever comes first)
        _cut_source_end = float(render_cuts[_ci - 1].get("source_end") or 0)
        _near_emphasis = any(abs(float(em.get("t") or 0) - _cut_source_end) < 1.5 for em in _em_all)
        if _near_emphasis or (_ci % 3 == 0 and _auto_transitions_added < 4):
            _auto_t = _SUBTLE_TRANSITIONS[_auto_transitions_added % len(_SUBTLE_TRANSITIONS)]
            render_cuts[_ci - 1]["transition_out"] = _auto_t
            _auto_transitions_added += 1
    if _auto_transitions_added:
        print(f"[transitions] Auto-assigned {_auto_transitions_added} subtle transition(s)", flush=True)

    for i in range(1, n):
        transition = str(render_cuts[i-1].get("transition_out") or "none").lower()
        out_v     = "vout" if i == n-1 else f"vx{i}"
        out_v_raw = f"{out_v}_raw"
        out_a     = "aout" if i == n-1 else f"ax{i}"

        # Safety: if either clip is shorter than the transition, force hard cut
        prev_dur = effective_durations[i-1] if i-1 < len(effective_durations) else 1.0
        curr_dur = effective_durations[i] if i < len(effective_durations) else 1.0
        if transition != "none" and (prev_dur < TRANSITION_DURATION + 0.1 or curr_dur < TRANSITION_DURATION + 0.1):
            print(f"[render] Clip {i-1}/{i} too short for {transition} ({prev_dur:.2f}s/{curr_dur:.2f}s) — forcing hard cut", flush=True)
            transition = "none"

        if transition in CUSTOM_TRANSITIONS:
            td = TRANSITION_DURATION
            offset = max(0, running_dur - td)

            if transition == "flash":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=fadewhite:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "glitch":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=pixelize:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                # Glitch saturation boost: 1.25x (professional range 1.2-1.3 for digital distortion)
                transition_filters.append(f"[{out_v_raw}]hue=h=0:s=1.25:enable='between(t,{offset:.3f},{offset + td:.3f})',fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "whip_left":
                # Motion blur only during the transition window, not the entire stream
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=wipeleft:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "whip_right":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=wiperight:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            running_dur = running_dur + effective_durations[i] - td

        elif transition in XFADE_TRANSITIONS:
            td = TRANSITION_DURATION
            offset = max(0, running_dur - td)
            transition_filters.append(f"[{tl_video}][v{i}]xfade=transition={transition}:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
            transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
            transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")
            running_dur = running_dur + effective_durations[i] - td

        else:
            # Hard cut: video is a clean concat, but audio gets a 4ms
            # crossfade to eliminate splice clicks/pops at the cut point.
            # 4ms is imperceptible as a fade but smooths the waveform
            # discontinuity where two audio segments meet.
            transition_filters.append(f"[{tl_video}][v{i}]concat=n=2:v=1:a=0[{out_v_raw}]")
            transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
            transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d=0.004:c1=tri:c2=tri[{out_a}]")
            running_dur = running_dur + effective_durations[i]

        tl_video = out_v
        tl_audio = out_a

    if n == 1:
        tl_video = "v0"
        tl_audio = "a0"

    post_filters = []
    video_out = "[video_base]"
    post_filters.append(f"[{tl_video}]null{video_out}")

    if edit_plan.get("cinematic_bars"):
        bar_h = int((1920 - int(1080 / 2.35)) / 2)
        bars_label = f"[video_bars]"
        post_filters.append(
            f"{video_out}drawbox=x=0:y=0:w=1080:h={bar_h}:color=black:t=fill,"
            f"drawbox=x=0:y={1920-bar_h}:w=1080:h={bar_h}:color=black:t=fill{bars_label}"
        )
        video_out = bars_label

    # Depth blur mask disabled — generated but never used in render (maskedmerge
    # incompatible with FFmpeg 8.x). Vignette handles edge emphasis instead.
    depth_mask_path = None

    # Caption PNGs were already rendered above (instant, no Chrome needed)

    text_overlays = edit_plan.get("text_overlays") or []
    if text_overlays and not _HAS_DRAWTEXT:
        print(f"[render] Skipping {len(text_overlays)} text overlay(s) — drawtext filter not available", flush=True)
        text_overlays = []
    if text_overlays:
        clip_ranges = get_output_clip_ranges(render_cuts, effective_durations, transition_duration=TRANSITION_DURATION)
        # Build mapping from original content clip index → (first, last) post-split clip range
        # so Gemini's appear_at_clip correctly spans the full original clip after speed splitting
        _orig_idx_to_range = {}
        for _ci, _rc in enumerate(render_cuts):
            _oi = _rc.get("_original_idx")
            if _oi is not None and _oi >= 0 and _ci < len(clip_ranges):
                if _oi not in _orig_idx_to_range:
                    _orig_idx_to_range[_oi] = (_ci, _ci)
                else:
                    _orig_idx_to_range[_oi] = (_orig_idx_to_range[_oi][0], _ci)
        # Sample background brightness once for text overlay color decisions
        _overlay_sample_ts = float(render_cuts[0].get("source_start", 0)) + 0.5
        _y_positions = {"top": 0.10, "center": 0.50, "bottom": 0.75}
        for i, overlay in enumerate(text_overlays):
            gemini_idx = int(overlay.get("appear_at_clip") or 0)
            if not clip_ranges:
                print(f"[render] Text overlay '{overlay.get('text')}' — no clip ranges, skipping", flush=True)
                continue
            # Map Gemini's original clip index to post-split clip range span
            if gemini_idx in _orig_idx_to_range:
                first_ci, last_ci = _orig_idx_to_range[gemini_idx]
            else:
                # Fallback: find closest original index
                valid_indices = sorted(_orig_idx_to_range.keys()) if _orig_idx_to_range else [0]
                closest = min(valid_indices, key=lambda x: abs(x - gemini_idx))
                first_ci, last_ci = _orig_idx_to_range.get(closest, (0, 0))
            first_ci = max(0, min(first_ci, len(clip_ranges) - 1))
            last_ci = max(0, min(last_ci, len(clip_ranges) - 1))
            raw_text = _EMOJI_RE.sub("", str(overlay.get("text") or "")).strip()
            text = raw_text.strip()
            if not text:
                continue
            start = clip_ranges[first_ci]["start"]
            end = clip_ranges[last_ci]["end"]
            style = str(overlay.get("style") or "callout")
            char_count = len(text)
            # Font sizes for 1080x1920 — title should be 4-5% of screen height for impact
            base_size = 84 if style == "title" else (72 if style == "cta" else 60)
            if char_count <= 18:
                font_size = base_size
            elif char_count <= 25:
                font_size = round(base_size * 0.85)
            elif char_count <= 35:
                font_size = round(base_size * 0.70)
            else:
                font_size = round(base_size * 0.60)
            pos = str(overlay.get("position") or "top")
            # Face-aware overlay positioning: find face at overlay start time
            # and place text where it won't block the face
            _ov_source_t = float(render_cuts[min(first_ci, len(render_cuts) - 1)].get("source_start", 0)) + 0.3
            _ov_face = None
            if face_positions:
                _ov_fp = min(face_positions, key=lambda p: abs(float(p.get("t", 0)) - _ov_source_t))
                if _ov_fp.get("found") and abs(float(_ov_fp.get("t", 0)) - _ov_source_t) < 2.0:
                    _ov_face = _ov_fp
            if _ov_face:
                _ov_face_y_frac = float(_ov_face.get("cy", 960)) / 1920.0
                if _ov_face_y_frac < 0.4:
                    # Face is high — put text below
                    y_expr = "h*0.65"
                    pos = "bottom"
                elif _ov_face_y_frac > 0.6:
                    # Face is low — put text above
                    y_expr = "h*0.10"
                    pos = "top"
                else:
                    # Face centered — put text at top (smaller, less intrusive)
                    y_expr = "h*0.08"
                    pos = "top"
            else:
                y_expr = "h*0.10" if pos == "top" else ("(h-th)/2" if pos == "center" else "h*0.75")
            end_t = max(start + 0.8, end)
            fade_in = 0.15
            fade_out = 0.15
            # Adaptive text color: sample background brightness at overlay position
            _y_frac = _y_positions.get(pos, 0.10)
            _bg_brightness = sample_background_brightness(source_path, _overlay_sample_ts, _y_frac)
            if _bg_brightness > 160:
                # Light background — use dark text
                _fg_color = "black"
                _border_color = "white"
                _box_color = "white@0.35"
            elif _bg_brightness > 100:
                # Medium background — white text with stronger box
                _fg_color = "white"
                _border_color = "black"
                _box_color = "black@0.5"
            else:
                # Dark background — white text, subtle box
                _fg_color = "white"
                _border_color = "black"
                _box_color = "black@0.35"
            print(f"[overlay] bg={_bg_brightness:.0f} → text={_fg_color}, border={_border_color}", flush=True)
            _font_clause = (
                f":fontfile='{OVERLAY_FONT_PATH}'"
                if os.path.exists(OVERLAY_FONT_PATH)
                else ""
            )
            escaped_text = text.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,").replace(";", "\\;").replace("[", "\\[").replace("]", "\\]").replace("%", "%%").replace("'", "\u2019").replace('"', "")
            out_label = f"[video_overlay_{i}]"
            alpha_expr = (
                f"if(lt(t-{start:.3f},{fade_in}),(t-{start:.3f})/{fade_in},"
                f"if(gt(t,{end_t-fade_out:.3f}),({end_t:.3f}-t)/{fade_out},1))"
            )
            _shadow_color2 = "black@0.6" if _fg_color == "white" else "white@0.4"
            _bw2 = max(3, round(font_size * 0.06))
            _sw2 = max(2, round(font_size * 0.04))
            post_filters.append(
                f"{video_out}drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={_fg_color}"
                f"{_font_clause}"
                f":x=(w-tw)/2:y={y_expr}"
                f":borderw={_bw2}:bordercolor={_border_color}@0.5"
                f":shadowcolor={_shadow_color2}:shadowx={_sw2}:shadowy={_sw2}"
                f":alpha='{alpha_expr}'"
                f":enable='between(t,{start:.3f},{end_t:.3f})'{out_label}"
            )
            video_out = out_label

    # Emphasis splash text REMOVED — no professional editing app uses giant centered
    # text overlays. Emphasis comes from captions (keyword highlight + size), zoom
    # (punch-in), and audio (SFX). Splash text screams "AI generated."

    audio_out = "[audio_timed]"
    post_filters.append(
        f"[{tl_audio}]asetpts=PTS-STARTPTS{audio_out}"
    )

    if sfx_audio_labels:
        # ── Audio ducking: dip voice volume at SFX timestamps (Captions AI V1/V2 pattern) ──
        # Build a volume expression that dips ~7dB for 0.3s around each SFX hit.
        # This mimics the "silence-then-spike" pattern observed in professional edits.
        if sfx_timestamps:
            _duck_parts = []
            for _dt in sorted(set(sfx_timestamps)):
                # Dip: starts 0.05s before SFX, deepest at SFX time, recovers over 0.25s
                _dip_start = max(0, _dt - 0.05)
                _dip_end = _dt + 0.25
                # Smooth envelope: ramp down then back up. Min volume = 0.45 (~7dB dip)
                _duck_parts.append(
                    f"if(between(t,{_dip_start:.3f},{_dip_end:.3f}),"
                    f"0.45+0.55*max(0,min(abs(t-{_dt:.3f})/0.15,1)),"
                    f"1)"
                )
            if _duck_parts:
                # Multiply all duck envelopes together (concurrent SFX stack)
                _duck_expr = "*".join(_duck_parts[:20])  # limit to 20 to avoid expr overflow
                _duck_label = "[audio_ducked]"
                post_filters.append(
                    f"{audio_out}volume='{_duck_expr}':eval=frame{_duck_label}"
                )
                audio_out = _duck_label
                print(f"[sfx] Audio ducking: {len(_duck_parts)} dip point(s)", flush=True)

        _n_inputs   = len(sfx_audio_labels) + 1
        _sfx_inputs = audio_out + "".join(sfx_audio_labels)
        post_filters.append(
            f"{_sfx_inputs}amix=inputs={_n_inputs}:duration=first:dropout_transition=0:normalize=0[audio_sfx_mixed]"
        )
        audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio", flush=True)

    audio_denoise = bool(edit_plan.get("audio_denoise"))
    _src_loudness = edit_plan.get("_source_loudness") or {}
    _src_rms = _src_loudness.get("rms_db", -18.0)
    _src_peak = _src_loudness.get("peak_db", -6.0)
    _src_nf = _src_loudness.get("noise_floor_db", -45.0)
    # Adaptive denoise: stronger for noisier sources
    if audio_denoise:
        _nr = 6 if _src_nf > -40 else (10 if _src_nf > -50 else 14)
        denoise_part = f"afftdn=nr={_nr}:nf={int(_src_nf)}:tn=1,"
    else:
        denoise_part = ""
    # Adaptive compressor thresholds based on source loudness:
    #   Quiet source (RMS < -24dB): lower thresholds to catch more, more makeup gain
    #   Normal source (RMS -18 to -12): standard thresholds
    #   Hot source (RMS > -12dB): higher thresholds to avoid over-compression
    _fast_thresh = max(-28, min(-16, _src_rms - 4))
    _level_thresh = max(-22, min(-10, _src_rms + 2))
    _makeup = max(1, min(4, round(-_src_rms / 6)))
    print(
        f"[audio] Adaptive chain: rms={_src_rms:.0f}dB peak={_src_peak:.0f}dB "
        f"fast_thresh={_fast_thresh:.0f}dB level_thresh={_level_thresh:.0f}dB makeup={_makeup}dB",
        flush=True,
    )
    # Voice processing chain — follows broadcast voice standards:
    #   75 Hz HPF: remove rumble/plosives (standard mic technique)
    #   200 Hz -1.5dB: reduce muddiness (standard voice EQ)
    #   3 kHz +1.5dB: presence/clarity boost (broadcast standard)
    #   Fast compressor: tame transients (3:1 ratio, 3ms attack = peak control)
    #   14 kHz LPF: remove hiss/artifacts above speech range
    #   Level compressor: smooth overall dynamics (1.8:1, gentle)
    #   EBU R128 loudnorm: broadcast-standard output level
    #     -14 LUFS integrated (YouTube/podcast standard)
    #     -1 dBTP true peak (EBU R128 compliant)
    #     LRA 11 (standard loudness range)
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
    # Force audio duration to match actual video duration (running_dur accounts for
    # transition overlaps). Frame-quantize to avoid sub-frame drift.
    _target_v_dur = round(running_dur * 30) / 30
    audio_chain += f",apad=whole_dur={_target_v_dur:.4f},atrim=end={_target_v_dur:.4f}"

    post_filters.append(f"{audio_out}{audio_chain}[final_audio]")
    audio_out = "[final_audio]"

    # ── B-roll compositing in first pass (no second encode) ──────────────────
    # B-roll fetch was launched in parallel with Remotion. Collect results now,
    # project timestamps, and add overlay filters before captions.
    broll_input_args = []
    broll_filter_strs = []
    _n_broll_inputs = 0
    if broll_fetch_futures:
        speed_curve = edit_plan.get("_parsed_speed_curve")
        hook_offset_val = float(edit_plan.get("_hook_offset") or 0.0)
        total_duration = sum(effective_durations)
        _broll_base_idx = n_segment_inputs + len(sfx_input_args) // 2

        # Collect fetched B-roll files (should be done by now — Remotion took longer)
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
            # Project timestamps and build filters
            BROLL_FADE = 0.4
            _broll_overlay_idx = 0
            for _bi, _bc in enumerate(broll_clips):
                if _bi not in _broll_files:
                    continue
                _local_path = _broll_files[_bi]
                _src_ts = float(_bc.get("timestamp") or 0)
                _out_ts = project_source_time_to_final_output(
                    _src_ts, render_cuts, effective_durations, speed_curve,
                    hook_offset=hook_offset_val,
                )
                if _out_ts is None or _out_ts >= total_duration:
                    continue

                _input_idx = _broll_base_idx + _n_broll_inputs
                broll_input_args += ["-i", _local_path]
                _n_broll_inputs += 1

                needed_duration = float(_bc.get("duration") or 2.0)
                broll_duration = get_video_duration(_local_path)
                if broll_duration > 0 and needed_duration > broll_duration:
                    needed_duration = broll_duration
                seek_point = 0.0
                if broll_duration > needed_duration + 1.0:
                    seek_point = min(broll_duration * 0.25, max(0.0, broll_duration - needed_duration - 0.5))

                # Ken Burns with directional variety
                _kb_total_frames = max(1, round(needed_duration * 30))
                _kb_zoom = 0.08
                _kb_progress = f"min(n/{_kb_total_frames}\\,1.0)"
                _kb_smooth = f"({_kb_progress}*{_kb_progress}*(3-2*{_kb_progress}))"
                _kb_dir = _KB_DIRECTIONS[_broll_overlay_idx % len(_KB_DIRECTIONS)]
                _fade_out_start = max(0, needed_duration - BROLL_FADE)
                _extra_px_w = round(1080 * _kb_zoom)
                _extra_px_h = round(1920 * _kb_zoom)
                _crop_x, _crop_y = _kb_crop_exprs(_kb_dir, _kb_smooth, _extra_px_w, _extra_px_h)

                _bv_label = f"bv{_broll_overlay_idx}"
                broll_filter_strs.append(
                    f"[{_input_idx}:v]trim=start={seek_point:.3f}:duration={needed_duration:.3f},"
                    f"setpts=PTS-STARTPTS,"
                    f"scale=w='trunc(1080*(1.0+{_kb_zoom})/2)*2':h='trunc(1920*(1.0+{_kb_zoom})/2)*2'"
                    f":force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop=1080:1920:x={_crop_x}:y={_crop_y},"
                    f"setsar=1,"
                    f"eq=saturation=0.92:contrast=1.02,"
                    f"fade=t=in:st=0:d={BROLL_FADE:.2f}:alpha=1,"
                    f"fade=t=out:st={_fade_out_start:.2f}:d={BROLL_FADE:.2f}:alpha=1,"
                    f"setpts=PTS-STARTPTS"
                    f"[{_bv_label}]"
                )
                _ov_label = f"broll_ov{_broll_overlay_idx}"
                broll_filter_strs.append(
                    f"{video_out}[{_bv_label}]overlay=0:0:enable='between(t,{_out_ts:.3f},{_out_ts + needed_duration:.3f})'[{_ov_label}]"
                )
                video_out = f"[{_ov_label}]"
                print(f"[broll] '{_bc.get('keyword')}' at {_out_ts:.1f}s ({needed_duration:.1f}s) Ken Burns: {_kb_dir}", flush=True)
                _broll_overlay_idx += 1

            if _broll_overlay_idx > 0:
                print(f"[broll] Integrated {_broll_overlay_idx} B-roll clip(s) into first pass", flush=True)

    # Wait for Remotion overlay render (launched in background thread earlier)
    caption_overlay_path = None
    if _overlay_future is not None:
        try:
            caption_overlay_path = _overlay_future.result(timeout=180)
            _overlay_pool.shutdown(wait=False)
            print(f"[remotion] Overlay ready: {caption_overlay_path}", flush=True)
        except Exception as _ov_err:
            print(f"[remotion] Overlay failed: {_ov_err}", flush=True)

    # Caption overlay — transparent video from Remotion (VP8 WebM with alpha)
    caption_input_args = []
    caption_filter_strs = []
    if caption_overlay_path:
        _cap_idx = n_segment_inputs + len(sfx_input_args) // 2 + _n_broll_inputs
        # Force libvpx decoder — FFmpeg's native vp8 decoder strips alpha channel
        caption_input_args = ["-c:v", "libvpx", "-i", caption_overlay_path]
        # Ensure alpha channel is preserved through format conversion
        caption_filter_strs.append(
            f"[{_cap_idx}:v]format=yuva420p[_cap_alpha];"
            f"{video_out}[_cap_alpha]overlay=eof_action=pass[video_captioned]"
        )
        video_out = "[video_captioned]"
        print(f"[render] Remotion caption overlay at input index {_cap_idx} (libvpx decoder)", flush=True)

    # Order matters: post_filters (zoom pulses etc) → broll → captions
    filter_complex = ";".join(video_filters + audio_filters + transition_filters + sfx_filter_strs + post_filters + broll_filter_strs + caption_filter_strs)
    _total_expected_v = sum(round(d * 30) / 30 for d in effective_durations)
    _total_expected_a = sum(effective_durations)
    print(f"[DIAG] Expected totals: video(fps30)={_total_expected_v:.4f}s audio(raw)={_total_expected_a:.4f}s gap={_total_expected_v - _total_expected_a:.6f}s", flush=True)
    print(f"[DIAG] filter_complex: {len(filter_complex)} chars, {len(video_filters)} v_filters, {len(audio_filters)} a_filters, {len(transition_filters)} transitions", flush=True)
    print(f"[DIAG] filter_complex (first 2000): {filter_complex[:2000]}", flush=True)
    print(f"[DIAG] filter_complex (last 1000): {filter_complex[-1000:]}", flush=True)
    encode_args = get_encode_args("high") + [
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k",
        "-movflags","+faststart",
        "-max_muxing_queue_size","4096",
        "-shortest",  # stop when video ends — audio pad may overshoot due to xfade timing
    ]

    # Maximize parallelism: all available CPU cores for filter graph + decoding
    _n_threads = os.cpu_count() or 32
    args = (
        ["-y"]
        + input_args
        + sfx_input_args
        + broll_input_args
        + caption_input_args
        + ["-filter_complex_threads", str(_n_threads),
           "-filter_complex", filter_complex, "-map", video_out, "-map", audio_out]
        + ["-threads", str(_n_threads)]
        + encode_args
        + [output_path]
    )

    _mode = "CONCAT pass (segments pre-rendered)" if _PARALLEL_RENDER else "Single-pass"
    print(f"[render] {_mode}: {n} segments, ~{running_dur:.1f}s output", flush=True)

    run_ffmpeg(args)



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

        # Step 1 — Download
        send_progress(job_id, "download", 5, "Got your video, loading it in...", app_url)
        t = time.time()
        print("[pipeline] step=download", flush=True)
        r = requests.get(video_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(source_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4194304):  # 4MB chunks for maximum throughput
                f.write(chunk)
        size_mb = os.path.getsize(source_path) / (1024*1024)
        _timings["download"] = time.time() - t
        print(f"[pipeline] download complete: {size_mb:.1f}MB in {_timings['download']:.1f}s", flush=True)

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

        # Configure Gemini API early so we can pre-upload
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

        # All 5 operations run in parallel — Deepgram, Gemini upload, loudness,
        # and beats all read from the RAW source (audio is identical pre/post normalize).
        # Unix file semantics keep the raw file accessible even after normalize unlinks it.
        _raw_source = source_path  # raw path — analyze_source_video reads but doesn't modify

        def _do_normalize():
            return analyze_source_video(_raw_source)

        def _do_transcribe():
            audio_path = os.path.join(work_dir, "audio_for_words.wav")
            # -vn skips video decode entirely — no need for hwaccel here
            subprocess.run(
                ["ffmpeg", "-threads", "0", "-y", "-i", _raw_source,
                 "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            result = transcribe_audio(audio_path)
            _words = result.get("words", [])
            if len(_words) == 0:
                print("[pipeline] Deepgram returned 0 words — retrying once...", flush=True)
                try:
                    result = transcribe_audio(audio_path)
                except Exception as e2:
                    print(f"[pipeline] Deepgram retry also failed: {e2}", flush=True)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return result

        def _do_gemini_upload():
            try:
                # Encode a tiny 360p proxy for Gemini — raw upload triggers 10-30s server-side
                # processing wait. 360p encodes in <1s and processes in <3s on Gemini side.
                # Gemini only needs to see composition/content, not pixel quality.
                _upload_t = time.time()
                _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
                # Use NVENC for proxy encode if available — instant on H100
                _proxy_venc = (["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "35"]
                               if _HAS_NVENC else
                               ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"])
                _proxy_cmd = subprocess.run(
                    ["ffmpeg", "-y", "-threads", "4", "-i", _raw_source,
                     "-vf", "scale=360:-2"] + _proxy_venc + [
                     "-c:a", "aac", "-b:a", "48k", "-ac", "1",
                     "-movflags", "+faststart", _proxy_path],
                    capture_output=True, text=True, timeout=15,
                )
                if _proxy_cmd.returncode == 0 and os.path.exists(_proxy_path):
                    _proxy_mb = os.path.getsize(_proxy_path) / (1024 * 1024)
                    print(f"[pipeline] Gemini proxy: 360p {_proxy_mb:.1f}MB in {time.time()-_upload_t:.1f}s", flush=True)
                    gf = genai.upload_file(_proxy_path)
                else:
                    print(f"[pipeline] Proxy encode failed, uploading raw", flush=True)
                    gf = genai.upload_file(_raw_source)
                # Poll for ACTIVE here (overlaps with transcription, beats, face detect)
                # instead of blocking inside generate_edit_gemini on the critical path
                _poll_delay = 0.2
                _poll_deadline = time.time() + 60
                while gf.state.name == "PROCESSING":
                    if time.time() > _poll_deadline:
                        raise RuntimeError("Gemini file processing timed out after 60s")
                    time.sleep(_poll_delay)
                    _poll_delay = min(_poll_delay * 1.5, 2.0)
                    gf = genai.get_file(gf.name)
                if gf.state.name != "ACTIVE":
                    raise RuntimeError(f"Gemini file upload failed: {gf.state.name}")
                print(f"[pipeline] Gemini upload done + ACTIVE: {gf.name} ({time.time()-_upload_t:.1f}s)", flush=True)
                return gf
            except Exception as e:
                print(f"[pipeline] Gemini pre-upload failed: {e} — will upload inline", flush=True)
                return None

        def _do_loudness():
            return measure_source_loudness(_raw_source)

        def _do_beats():
            try:
                return detect_beats(_raw_source)
            except Exception as _be:
                print(f"[pipeline] Beat detection failed (non-fatal): {_be}", flush=True)
                return []

        # ── ALL initialization + Gemini edit in ONE parallel phase ────────────
        # Gemini starts as soon as transcript + upload + trend context are ready.
        # Everything runs concurrently — no sequential network calls on main thread.

        # Shared futures — edit recipe and face detect wait on their deps internally
        future_normalize = None
        future_transcribe = None
        future_gemini_upload = None
        future_trend = None  # trend context fetched in parallel

        def _do_trend_context():
            tc = get_trend_context()
            if not tc:
                print("[trend] WARNING: Style guide not available — Gemini will edit without reference video patterns", flush=True)
            return tc

        def _do_edit_recipe_overlapped():
            """Start Gemini as soon as transcript + upload + trend are ready."""
            _transcript = future_transcribe.result()
            _gemini_ref = future_gemini_upload.result()
            _trend = future_trend.result()
            _dg_words = _transcript.get("words", [])
            if len(_dg_words) == 0:
                raise RuntimeError("Deepgram transcription failed — 0 words returned.")
            send_progress(job_id, "edit_recipe", 52, "Putting your edit together...", app_url)
            print(f"[pipeline] Gemini edit starting (transcript ready: {len(_dg_words)} words)", flush=True)
            return generate_edit_gemini(
                video_path=_raw_source,
                vibe=vibe,
                duration=source_duration,
                trend_context=_trend,
                deepgram_words=_dg_words,
                face_positions=None,
                gemini_file=_gemini_ref,
            )

        def _do_face_detect_overlapped():
            """Run face detection on raw source (no longer waits for normalize)."""
            send_progress(job_id, "analysis", 20, "Watching your footage...", app_url)
            try:
                # every_n_frames=15 → 2fps detection on 30fps source — smooth enough for zoom
                # tracking, saves ~3s on a 30s video vs every_n_frames=10
                dense = detect_face_positions_dense(_raw_source, every_n_frames=15)
                if dense:
                    smoothed = smooth_face_trajectory(dense, total_duration=source_duration)
                    print(f"[dense-face] Smoothed trajectory: {len(smoothed)} keyframes", flush=True)
                    return dense, smoothed
            except Exception as e:
                print(f"[dense-face] Dense detection failed ({e}), falling back to sparse", flush=True)
            sparse = detect_face_positions(_raw_source, sample_timestamps) if sample_timestamps else []
            return sparse, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as mega_pool:
            future_normalize = mega_pool.submit(_do_normalize)
            future_transcribe = mega_pool.submit(_do_transcribe)
            future_gemini_upload = mega_pool.submit(_do_gemini_upload)
            future_trend = mega_pool.submit(_do_trend_context)
            future_loudness = mega_pool.submit(_do_loudness)
            future_beats = mega_pool.submit(_do_beats)
            # Edit recipe waits on transcript + upload internally
            future_edit = mega_pool.submit(_do_edit_recipe_overlapped)
            # Face detection runs directly on raw source (no normalize dependency)
            future_faces = mega_pool.submit(_do_face_detect_overlapped)

            # Collect results — get edit_plan FIRST so we can start B-roll fetch early
            edit_plan = future_edit.result()  # critical path — longest wait (Gemini)

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
                    )
                    _broll_fetch_futures[_fut] = _bi

            # Now collect remaining futures (may already be done)
            source_info = future_normalize.result()
            source_path = source_info["source_path"]
            _normalize_vf = source_info.get("normalize_vf")
            transcript = future_transcribe.result()
            gemini_file_ref = future_gemini_upload.result()
            source_loudness = future_loudness.result()
            source_beats = future_beats.result()
            face_positions, dense_face_trajectory = future_faces.result()

        # Source res is what it is — normalize filter will handle conversion in render
        source_res = {"width": source_info["width"], "height": source_info["height"]}
        print(f"[DIAG] Source: {source_res['width']}x{source_res['height']} @ {source_info['fps']:.1f}fps, normalize_vf={'yes' if _normalize_vf else 'no'}", flush=True)

        # Transform face positions from raw source space → 1080x1920 space
        # (Face detection ran on the raw source since we no longer pre-encode a normalized copy)
        _ft = source_info.get("face_transform", {})
        _ft_mode = _ft.get("mode", "identity")
        if _ft_mode != "identity" and (face_positions or dense_face_trajectory):
            if _ft_mode == "crop_then_scale":
                # Reframe path: crop in raw space, then scale to 1080x1920
                _cx_off = _ft["crop_x"]
                _cy_off = _ft["crop_y"]
                _sx = 1080.0 / _ft["crop_w"] if _ft["crop_w"] > 0 else 1.0
                _sy = 1920.0 / _ft["crop_h"] if _ft["crop_h"] > 0 else 1.0
                def _transform_face(fp):
                    fp["cx"] = round((fp["cx"] - _cx_off) * _sx, 2)
                    fp["cy"] = round((fp["cy"] - _cy_off) * _sy, 2)
                    return fp
            elif _ft_mode == "scale_then_crop":
                # Center crop path: scale up first, then crop center
                _scale = _ft["scale"]
                _cx_off = _ft["crop_x"]  # offset in post-scale space
                _cy_off = _ft["crop_y"]
                def _transform_face(fp):
                    fp["cx"] = round(fp["cx"] * _scale - _cx_off, 2)
                    fp["cy"] = round(fp["cy"] * _scale - _cy_off, 2)
                    return fp
            else:
                _transform_face = lambda fp: fp

            face_positions = [_transform_face(dict(fp)) for fp in face_positions]
            dense_face_trajectory = [_transform_face(dict(fp)) for fp in dense_face_trajectory]
            print(f"[faces] Transformed {len(face_positions)} + {len(dense_face_trajectory)} trajectory points → 1080x1920 ({_ft_mode})", flush=True)

        _timings["normalize_transcribe_upload"] = time.time() - t
        _dg_words = transcript.get("words", [])
        if len(_dg_words) == 0:
            raise RuntimeError("Deepgram transcription failed — 0 words returned. Cannot proceed without word timestamps.")
        print(f"[pipeline] All init complete: {len(_dg_words)} words, edit recipe + faces done ({_timings['normalize_transcribe_upload']:.1f}s)", flush=True)

        print(f"[edit] User vibe: \"{vibe}\"", flush=True)

        # Face positions are already transformed to 1080x1920 space (normalize_vf handles raw→output)
        if _normalize_vf:
            print(f"[reframe] Smart reframe active via normalize_vf (folded into render pass)", flush=True)
        else:
            print("[reframe] Source is native 9:16 — no reframe needed", flush=True)

        edit_plan["_user_vibe"] = vibe
        edit_plan["_source_path"] = source_path
        edit_plan["_normalize_vf"] = _normalize_vf  # scale/crop filter for render pass (None if native 1080x1920)
        edit_plan["_face_positions"] = face_positions
        edit_plan["_dense_face_trajectory"] = dense_face_trajectory
        edit_plan["_source_loudness"] = source_loudness
        edit_plan["_source_beats"] = source_beats
        _timings["edit_recipe_faces"] = 0  # folded into normalize_transcribe_upload
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
        )
        if _broll_fetch_pool:
            _broll_fetch_pool.shutdown(wait=False)
        edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        _timings["render"] = render_elapsed
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        _enc_label = "NVENC" if _HAS_NVENC else "libx264/fast"
        print(f"[render] Encoding: {_enc_label} threads=auto", flush=True)
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
            hook_offset=float(edit_plan.get("_hook_offset") or 0.0),
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
            with open(output_path, "rb") as f:
                resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                resp.raise_for_status()
            print("[pipeline] upload complete", flush=True)

        def _extract_cover():
            # Try styled thumbnail first (enhanced + vignette + optional text)
            _face_pos = edit_plan.get("_face_positions") or []
            _hook_text = None  # Could use edit_plan hook text if desired
            try:
                data, mime = generate_styled_thumbnail(
                    output_path, cover_frame_ts, _face_pos, work_dir,
                    hook_text=_hook_text,
                )
            except Exception as _thumb_err:
                print(f"[thumbnail] Styled thumbnail failed ({_thumb_err}), using basic", flush=True)
                data, mime = extract_cover_frame(output_path, cover_frame_ts, work_dir)
            if data:
                print(
                    f"[pipeline] cover frame at {cover_frame_ts:.2f}s "
                    f"(AI-selected from source {float(thumbnail_source_ts):.2f}s, {len(data)//1024}KB)",
                    flush=True,
                )
            return data, mime

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as post_executor:
            f_upload = post_executor.submit(_upload_main)
            f_cover  = post_executor.submit(_extract_cover)
            f_upload.result()
            cover_bytes, _ = f_cover.result()

        if cover_bytes:
            import base64
            cover_frame_b64 = base64.b64encode(cover_bytes).decode()
            upload_url_thumb = input_data.get("upload_url_thumb")
            if upload_url_thumb:
                try:
                    thumb_resp = requests.put(
                        upload_url_thumb, data=cover_bytes,
                        headers={"Content-Type": cover_frame_mime}, timeout=30,
                    )
                    thumb_resp.raise_for_status()
                    print("[pipeline] thumbnail uploaded", flush=True)
                except Exception as thumb_err:
                    print(f"[pipeline] thumbnail upload failed (non-fatal): {thumb_err}", flush=True)

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
