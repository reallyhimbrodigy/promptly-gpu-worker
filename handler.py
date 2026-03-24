# Modal worker entrypoint
import subprocess
import os
import sys
import ssl
import requests
import tempfile
import time
import shutil
import json
import re
import math
import concurrent.futures
from datetime import datetime
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

HANDLER_VERSION = "3.0.0"
GEMINI_MODEL = "gemini-3.1-pro-preview"

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

try:
    ff_check = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=5)
    if "rubberband" in (ff_check.stdout or ""):
        print("[startup] FFmpeg rubberband filter: available", flush=True)
    else:
        print("[startup] WARNING: FFmpeg rubberband filter not available", flush=True)
except Exception:
    pass

# Real-ESRGAN removed from pipeline — not needed for clean phone footage

print("[startup] all import checks done", flush=True)

EMOJI_STRIP = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937"
    "\U00010000-\U0010ffff"
    "\u2640-\u2642"
    "\u2600-\u2B55"
    "\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
    "]+",
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

Use this to inform your editing decisions. Where the user's footage naturally fits these patterns, lean into them. Where it doesn't, use your judgment.

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


# ─── COLOR INTENTS ────────────────────────────────────────────────────────────

# ─── MUSIC LIBRARY ────────────────────────────────────────────────────────────
# Tracks stored at /assets/music/<filename>.mp3 in the Docker image.
# The model picks by filename. Values are for prompt context only — not used in code.
MUSIC_LIBRARY = {
    "none": {"mood": "none", "energy": "none", "description": "No background music."},

    # Hype / High energy
    "hype_trap_01":       {"mood": "hype",      "energy": "high",   "description": "Hard-hitting trap beat, 140bpm, heavy 808s. Feels aggressive, powerful, unstoppable — the kind of energy that makes a viewer sit up straight."},
    "hype_electronic_01": {"mood": "hype",      "energy": "high",   "description": "Festival electronic drop, 128bpm, euphoric synths. Feels massive and celebratory — pure forward momentum and release."},
    "upbeat_pop_01":      {"mood": "upbeat",    "energy": "high",   "description": "Bright pop energy, 120bpm, driving beat. Feels fun, alive, and optimistic — like something good is happening right now."},
    "upbeat_hip_hop_01":  {"mood": "upbeat",    "energy": "high",   "description": "Chill hip-hop groove, 95bpm, confident swagger. Feels cool and self-assured — low-key energy that still moves."},

    # Cinematic / Emotional
    "cinematic_epic_01":  {"mood": "cinematic", "energy": "high",   "description": "Orchestral swell, 90bpm, building tension. Feels like something significant is unfolding — weight and momentum growing toward a peak."},
    "cinematic_tense_01": {"mood": "cinematic", "energy": "medium", "description": "Dark atmospheric strings, 80bpm, suspense. Feels heavy and serious — like the air before something important is said."},
    "emotional_piano_01": {"mood": "emotional", "energy": "low",    "description": "Intimate solo piano, 70bpm, melancholy. Feels quiet and personal — the kind of music that makes a viewer lean in and listen carefully."},
    "emotional_indie_01": {"mood": "emotional", "energy": "medium", "description": "Indie folk guitar, 85bpm, warmth. Feels genuine and heartfelt — honest emotion without being dramatic."},

    # Calm / Lo-fi
    "calm_ambient_01":    {"mood": "calm",      "energy": "low",    "description": "Soft ambient pads, no strong beat. Feels spacious and unhurried — the viewer exhales and settles in."},
    "lo_fi_chill_01":     {"mood": "calm",      "energy": "low",    "description": "Lo-fi hip-hop, 75bpm, warm vinyl texture. Feels comfortable and easy — like a lazy afternoon where nothing is urgent."},
    "lo_fi_beats_01":     {"mood": "calm",      "energy": "medium", "description": "Lo-fi trap, 85bpm, understated groove. Feels focused and quietly driven — calm on the surface but moving underneath."},

    # Corporate / Clean
    "corporate_inspire_01": {"mood": "upbeat",  "energy": "medium", "description": "Clean pop production, 110bpm, bright and optimistic. Feels polished and forward-moving — confident without being aggressive."},
    "corporate_tech_01":    {"mood": "clean",   "energy": "medium", "description": "Minimal electronic, 100bpm, precise and clean. Feels modern and purposeful — steady energy that supports without distracting."},

    # Dark / Moody
    "dark_moody_01":      {"mood": "moody",     "energy": "medium", "description": "Dark atmospheric hip-hop, 90bpm, brooding bass. Feels mysterious and a little dangerous — tension that never fully releases."},
    "dark_cinematic_01":  {"mood": "moody",     "energy": "high",   "description": "Dark orchestral, 85bpm, heavy and intense. Feels like something is at stake — the kind of music that makes a moment feel consequential."},

    # Fun / Playful
    "fun_quirky_01":      {"mood": "fun",       "energy": "high",   "description": "Quirky ukulele pop, 115bpm, bouncy and light. Feels playful and a little silly — instantly puts a viewer in a good mood."},
    "fun_retro_01":       {"mood": "fun",       "energy": "medium", "description": "Retro synth-pop, 105bpm, nostalgic warmth. Feels familiar and fun — like something from a better, simpler time."},

    # Romantic / Warm
    "romantic_soft_01":   {"mood": "romantic",  "energy": "low",    "description": "Soft acoustic guitar, 65bpm, tender and intimate. Feels gentle and close — the emotional equivalent of a quiet moment between two people."},
    "warm_acoustic_01":   {"mood": "warm",      "energy": "medium", "description": "Warm acoustic strumming, 90bpm, feel-good brightness. Feels open-hearted and sincere — the kind of warmth that makes a viewer smile without knowing why."},

    # Epic / Dramatic
    "epic_trailer_01":    {"mood": "epic",      "energy": "high",   "description": "Orchestral and electronic hybrid, 120bpm, building intensity. Feels like something big is about to happen — anticipation and scale."},
    "epic_sports_01":     {"mood": "epic",      "energy": "high",   "description": "Stadium-sized energy, 130bpm, relentless drive. Feels like peak physical effort — the music itself is pushing forward."},
}

_MUSIC_DIR = "/assets/music"

COLOR_INTENTS = {
    "none":      {"brightness": 0,     "contrast": 0,     "saturation": 0,     "gamma": 0,     "color_temperature": None},
    "neutral":   {"brightness": 0,     "contrast": 0,     "saturation": 0,     "gamma": 0,     "color_temperature": "neutral"},
    "cinematic": {"brightness": -0.05, "contrast": 0.2,   "saturation": -0.18, "gamma": -0.06, "color_temperature": "cool"},
    "warm":      {"brightness": 0.02,  "contrast": 0.08,  "saturation": 0.12,  "gamma": 0.01,  "color_temperature": "warm"},
    "cozy":      {"brightness": 0.04,  "contrast": 0.06,  "saturation": 0.08,  "gamma": 0.05,  "color_temperature": "warm"},
    "cool":      {"brightness": -0.01, "contrast": 0.08,  "saturation": -0.1,  "gamma": -0.01, "color_temperature": "cool"},
    "moody":     {"brightness": -0.09, "contrast": 0.24,  "saturation": -0.24, "gamma": -0.1,  "color_temperature": "cool"},
    "vibrant":   {"brightness": 0.03,  "contrast": 0.16,  "saturation": 0.28,  "gamma": 0,     "color_temperature": None},
    "punchy":    {"brightness": 0.01,  "contrast": 0.22,  "saturation": 0.2,   "gamma": -0.06, "color_temperature": None},
    "vivid":     {"brightness": 0.04,  "contrast": 0.18,  "saturation": 0.32,  "gamma": -0.01, "color_temperature": None},
    "clean":     {"brightness": 0.01,  "contrast": 0.07,  "saturation": 0.05,  "gamma": 0.01,  "color_temperature": "neutral"},
    "polished":  {"brightness": 0.02,  "contrast": 0.1,   "saturation": 0.08,  "gamma": 0.01,  "color_temperature": "neutral"},
    "enhanced":  {"brightness": 0.01,  "contrast": 0.13,  "saturation": 0.12,  "gamma": 0,     "color_temperature": None},
    "faded":     {"brightness": 0.05,  "contrast": -0.18, "saturation": -0.32, "gamma": 0.09,  "color_temperature": "warm"},
    "vintage":   {"brightness": 0.03,  "contrast": -0.14, "saturation": -0.26, "gamma": 0.08,  "color_temperature": "warm"},
    "dramatic":  {"brightness": -0.08, "contrast": 0.28,  "saturation": -0.12, "gamma": -0.11, "color_temperature": "cool"},
    "bold":      {"brightness": 0.02,  "contrast": 0.25,  "saturation": 0.24,  "gamma": -0.05, "color_temperature": None},
    "soft":      {"brightness": 0.05,  "contrast": -0.14, "saturation": -0.1,  "gamma": 0.07,  "color_temperature": "warm"},
    "dreamy":    {"brightness": 0.07,  "contrast": -0.12, "saturation": -0.18, "gamma": 0.1,   "color_temperature": "warm"},
}

TEMPERATURE_FILTERS = {
    "warm":    "colorbalance=rs=0.05:gs=0.02:bs=-0.05:rm=0.03:gm=0.01:bm=-0.03:rh=0.02:gh=0:bh=-0.02",
    "cool":    "colorbalance=rs=-0.04:gs=0:bs=0.04:rm=-0.02:gm=0:bm=0.02:rh=-0.02:gh=0:bh=0.02",
    "neutral": None,
}


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def normalize_intent(intent_name):
    key = str(intent_name or "").strip().lower()
    if key and key in COLOR_INTENTS:
        return key
    if key:
        print(f"[generate-edit] Unknown color_intent '{intent_name}', falling back to 'none'")
    return "none"


def detect_face_positions(video_path, sample_timestamps):
    """
    Sample frames at given timestamps and detect the dominant face position.
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

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    positions = []
    for t in sample_timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            positions.append({"t": float(t), "cx": center_x, "cy": center_y, "found": False})
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )

        if len(faces) > 0:
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            positions.append({
                "t": float(t),
                "cx": int(fx + fw // 2),
                "cy": int(fy + fh // 2),
                "found": True,
            })
        else:
            positions.append({"t": float(t), "cx": center_x, "cy": center_y, "found": False})

    cap.release()
    found_count = sum(1 for p in positions if p["found"])
    print(f"[reframe] Detected faces in {found_count}/{len(positions)} sampled frames", flush=True)
    return positions


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


def build_color_grade(baseline, intent_name):
    raw_b = float(baseline.get("brightness", 1.0)) if isinstance(baseline.get("brightness"), (int, float)) else 1.0
    raw_c = float(baseline.get("contrast", 1.0)) if isinstance(baseline.get("contrast"), (int, float)) else 1.0
    raw_s = float(baseline.get("saturation", 1.0)) if isinstance(baseline.get("saturation"), (int, float)) else 1.0
    raw_g = float(baseline.get("gamma", 1.0)) if isinstance(baseline.get("gamma"), (int, float)) else 1.0

    if raw_c > 3.0 or raw_s > 3.0 or raw_b > 2.0 or raw_b < -1.0 or raw_g > 3.0 or raw_g < 0.1:
        print(
            f"[color] WARNING: Gemini output extreme color_baseline values: "
            f"b={raw_b} c={raw_c} s={raw_s} g={raw_g} — using safe defaults",
            flush=True,
        )
        raw_b = 1.0
        raw_c = 1.0
        raw_s = 1.0
        raw_g = 1.0

    safe_baseline = {
        # Gemini reports brightness around 1.0 as neutral, but FFmpeg eq brightness is centered at 0.0.
        "brightness":        raw_b - 1.0,
        "contrast":          raw_c,
        "saturation":        raw_s,
        "gamma":             raw_g,
        "color_temperature": baseline.get("color_temperature", "neutral") if baseline.get("color_temperature") in ["warm", "cool", "neutral"] else "neutral",
    }
    baseline_temp = safe_baseline.get("color_temperature", "neutral")
    print(f"[color] Temperature: baseline={baseline_temp}", flush=True)
    intent = normalize_intent(intent_name)
    delta = COLOR_INTENTS[intent]
    intended_temp = delta["color_temperature"] if delta["color_temperature"] in ("warm", "cool") else None
    color_grade = {
        "brightness":        clamp(safe_baseline["brightness"] + delta["brightness"], -0.15, 0.15),
        "contrast":          clamp(safe_baseline["contrast"] + delta["contrast"], 0.8, 1.4),
        "saturation":        clamp(safe_baseline["saturation"] + delta["saturation"], 0.8, 1.20),
        "gamma":             clamp(safe_baseline["gamma"] + delta["gamma"], 0.8, 1.2),
        "color_temperature": intended_temp or safe_baseline["color_temperature"] or "neutral",
    }
    print(
        f"[color] Clamped color_grade: b={color_grade['brightness']:.2f} "
        f"c={color_grade['contrast']:.2f} s={color_grade['saturation']:.2f} "
        f"g={color_grade['gamma']:.2f}",
        flush=True,
    )
    print(f"[color] Temperature: grade={color_grade.get('color_temperature', 'not set')}", flush=True)
    return color_grade

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
        capture_output=True, text=True
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


def tighten_transcript(words, scene_cuts=None, shots=None, original_duration=0, source_path=None):
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
    silence_regions = []
    if source_path and os.path.exists(source_path):
        silence_regions = detect_silence_regions(source_path, silence_db=-40, min_silence_duration=0.2)
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


# ─── BROLL KEYWORD EXTRACTION ─────────────────────────────────────────────────

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being","have","has","had",
             "do","does","did","will","would","could","should","may","might","shall","can",
             "not","no","nor","so","yet","both","either","or","and","but","if","then",
             "because","as","until","while","of","at","by","for","with","about","against",
             "between","into","through","during","before","after","above","below","to","from",
             "up","down","in","out","on","off","over","under","again","further","once",
             "that","this","these","those","i","me","my","we","our","you","your","he",
             "him","his","she","her","it","its","they","them","their","what","which","who",
             "when","where","why","how","all","each","every","both","few","more","most",
             "other","some","such","than","too","very","just","also","like","really","get",
             "got","know","think","said","say","go","going","make","made","want","way"}


def extract_broll_keywords(words, limit=8):
    freq = {}
    timestamps = {}
    for w in words:
        text = re.sub(r"[^a-z]", "", str(w.get("word") or "").lower())
        if len(text) < 4 or text in STOPWORDS:
            continue
        freq[text] = freq.get(text, 0) + 1
        if text not in timestamps:
            timestamps[text] = float(w.get("start", 0))
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    return [{"keyword": kw, "timestamp": timestamps[kw]} for kw, _ in sorted_words[:limit]]


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

    intents = "none, neutral, cinematic, warm, cozy, cool, moody, vibrant, punchy, vivid, clean, polished, enhanced, faded, vintage, dramatic, bold, soft, dreamy"

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

Pacing creates rhythm. Filler and setup should move faster. Key moments — reveals, punchlines, important statements — should breathe. The contrast between fast and slow is what makes pacing feel alive.

You are the editor. You decide what stays and what gets cut.

You are a professional short-form editor. You have the exact transcript with millisecond timestamps. Use them to place PRECISE cuts. Think like a human editor who can see the waveform and the video simultaneously.

DEAD AIR IN SPEECH CONTENT:
Look at the gaps between words in the transcript:
- Under 0.10 seconds between words — natural word spacing. KEEP. This is how speech flows.
- 0.10 seconds or more between words — this is a pause, breath, or dead air. REMOVE it by ending one clip before the gap and starting the next clip after it.
- Filler words (uh, um, hmm, er, ah) — skip these entirely. End the previous clip before the filler word and start the next clip at the word after it.
- Stutters and false starts — when the speaker starts a word then restarts it ("she shou- shouldn't", "I said, who is... I said, who is he?", "I'm going to... I'm gonna"), cut out the false start and keep only the corrected version. End the previous clip before the false start and start the next clip at the corrected word.

HOW TO CUT PRECISELY:
- source_end = the exact end timestamp of the last word you want to keep. The timestamps are accurate — use them exactly. If "electrocuted" ends at 26.07, set source_end to 26.07.
- source_start = the exact start timestamp of the first word in the clip. If "and" starts at 8.88, set source_start to 8.88. You have the exact timestamps. Use them exactly.
- The gap between clips is the dead air being removed

CONTINUOUS PHRASES:
Words within the same phrase that have small natural gaps (under 0.10s) must stay together in ONE clip. "Strategies built in" is one phrase — keep it in one clip. Only create a new clip when you see a gap of 0.10s or more in the transcript.

FIRST CLIP:
- If the video starts with someone talking, set source_start to the first word's start timestamp. Zero dead air.
- If the video starts with visuals, music, or action before speech begins, set source_start to 0.0 to preserve that content.

DEAD AIR IN NON-SPEECH CONTENT:
Not every video is a talking head. For videos with music, product shots, tutorials, vlogs, or mixed content:
- Watch the video. Dead air is any moment where NOTHING interesting is happening — no movement, no action, no visual change, no music energy.
- A car detailing video has dead air when the camera is static and nothing is being wiped or polished. The satisfying wipe moments are NOT dead air — they are the content.
- A cooking video has dead air when the person is walking to the fridge. The chopping and plating are the content.
- A product review has dead air when the person pauses to think. The demonstration is the content.
- A music video or montage rarely has dead air — the rhythm and visuals carry the pacing.

Your job as the editor: keep what's interesting, cut what isn't. Use the word timestamps for speech precision. Use your visual judgment for non-speech decisions. Every millisecond in the final video should earn its place.

GENERAL RULES:
- source_start and source_end MUST align with word boundaries from the transcript when speech is present. Never cut inside a word.
- For non-speech sections, place cuts at natural visual break points — scene changes, camera movements, action pauses.
- The source timeline only moves forward. Clips must stay chronological.

Sound design adds texture. A swoosh on a scene change, a thud when a statement lands, a pop when text appears — these make cuts feel physical instead of digital. But not every cut needs a sound. Continuous speech flows best with silent hard cuts.

B-roll elevates production value. When the speaker mentions a concept, a 2-3 second visual cutaway makes the video feel produced. One or two well-placed b-roll moments transform how professional the entire video feels.

The ending matters. On these platforms, videos auto-loop. A clean ending that flows back into the opening earns replay credit. Avoid fade to black — it creates a flash before the loop restarts.{trend_block}

  HOOK CLIP:
  BOTH of these conditions must be true to use a hook clip:
  1. The vibe mentions "viral", "engaging", "captivating", "hook", or "retention"
  2. The video does NOT already have a strong hook at the beginning — meaning the first 2-3 seconds are slow, boring setup, or dead air rather than something immediately compelling

  If the video already starts with a strong statement, a provocative question, action, or anything that grabs attention in the first 2 seconds, set hook_clip to null — it doesn't need one.

  If BOTH conditions are met: pick the single most captivating 1-2 second moment from the video — the punchline, the reveal, the reaction that makes someone stop scrolling. Set hook_clip to the source_start and source_end of that moment. This clip will play FIRST as a teaser, then the full video plays chronologically from the beginning.
  hook_clip source_start and source_end MUST be the exact timestamps of the punchline WORDS, not the cut boundaries. Use the word timestamps provided above. The hook should start at the first word of the punchline and end at the last word. No silence before or after.

  The hook clip should be short (1-2 seconds max), impactful, and make the viewer think "HOW did this happen?" It should NOT make sense without context — that's what makes them keep watching.

  If either condition is not met, or if the video doesn't have a clear punchline, set hook_clip to null.

=== TOOLS ===

Per-clip parameters:

  source_start / source_end — timestamps defining each clip. MUST be strictly chronological.
    Clips must be chronological. Leave gaps between clips to remove dead air, pauses, or dull moments — the pipeline preserves these gaps as intentional cuts. Only overlap or touch clips when the speech flows continuously with no pause.

  transition_out — visual transition between this clip and the next:

    none — hard cut. Use this for EVERY cut unless the user's vibe specifically asks for transitions. Hard cuts are what TikTok and Reels content uses. They are clean, instant, and professional.

    fadewhite — fades through white between clips. ONLY use if the user's vibe mentions "transitions" or "white fade" or similar. Never add transitions on your own.

    whip_left / whip_right — fast directional blur. ONLY use if the user's vibe specifically asks for it.

    DEFAULT: set every transition_out to "none" unless the user explicitly requests transitions in their vibe.

  transition_sound — always "none"

  sfx_style — always "none"

  zoom — camera movement across the clip:
    none — static. DEFAULT for all clips.
    slow_in — gentle push-in. Use ONLY on the first clip when ALL of these are true: (1) the subject is a talking head, (2) the subject's face is centered in the frame, and (3) the subject is looking directly at the camera. If the subject is off-center, looking away, or there are multiple people, use none. Do not use on any clip other than the first.
    slow_out / punch_in / punch_out — other zoom options. Rarely needed.
    Zoom crops the edges. If the footage has burned-in captions, use none on ALL clips.

  cut_zoom — always false. The pipeline controls this.

Global parameters:

  color_intent — the overall color feel: {intents}
    Choose based on what you see in the footage and what the vibe calls for. The pipeline applies the grade automatically.

  SPEED RAMPING (only when vibe mentions "speed ramp", "speed ramping", or "CapCut style"):
  Follow the speed ramping techniques described in the editing style guide above. The style guide was generated from watching real viral videos.

  When speed ramping is active, every moment in the video is either sped up or slowed down — there is no 1.0x normal speed. If a section is filler or setup, it gets sped up. If it is a punchline or reveal, it gets slowed down. The contrast between fast and slow is what makes speed ramping work. Do not use 1.0x in your speed curve.

  What each speed value does to speech:
    1.2x = slightly fast, natural sounding, good default for filler and setup
    1.3x = comfortably fast, pitch rises slightly, still easy to follow
    1.5x = fast, noticeable pitch shift — maximum speed
    0.8x = slightly slow, subtle dramatic effect
    0.6x = noticeably slow, voice gets deeper, clearly dramatic
    0.5x = very slow, deep voice, maximum dramatic impact

  SPEED CURVE FORMAT:
  speed_curve: [
    {{"t": <timestamp in source seconds>, "speed": <speed multiplier>}},
    ...
  ]

  Each keypoint means: "from this timestamp, play at this speed until the next keypoint."
  If speed ramping is not requested, set speed_curve to "none".

  caption_style — word-by-word animated captions synced to speech:
    none — no captions. Use when captions are already burned into the footage.
    capcut — bold white text with black outline, active word highlighted in yellow with scale bounce animation. This is the standard TikTok/Reels caption style. Use this as the default.
    word_pop — similar to capcut but with a smooth karaoke color sweep instead of bounce animation. Use when the user asks for something slightly different.
    hormozi — uppercase bold text, active word pops with scale bounce, keyword words highlighted in orange-red. Aggressive, high-energy style inspired by Alex Hormozi. Use for motivational/business content.
    minimal — lowercase thin text with subtle shadow, simple karaoke sweep. Clean, understated look. Use for aesthetic/lifestyle content.
    two_line — shows two lines at once: active line on top with karaoke highlight, upcoming line dimmed below. Use for longer sentences or interview-style content.
    boxed — text inside a semi-transparent black box with karaoke sweep highlight. High contrast, easy to read. Use for noisy backgrounds or outdoor footage.

    If the video has speech and no burned-in captions, choose the caption style that best fits the content and vibe. Match the energy — aggressive content gets hormozi, clean/aesthetic content gets minimal, storytelling gets capcut or two_line, fast-paced content gets word_pop.

  caption_position — where captions appear on screen. Always use "lower-third" — this places captions in the safe zone below faces and above the TikTok/Reels platform UI. This is the standard caption placement used by every major short-form editor.

  audio_denoise: true / false — AI noise removal for room tone, hiss, fan noise.

  outro: none, fade_black, fade_white — none is best for clean looping.

  background_music: always "none" — creators add their own music when posting.

  aspect_ratio: always "9:16"

  thumbnail_timestamp — the source timestamp (in seconds) of the single best frame to use as the video's cover image / thumbnail. Pick the frame where the speaker has the most expressive or emotional face — surprise, laughter, intensity, reaction. Avoid frames where eyes are closed, face is blurry, or expression is blank. This frame needs to make someone scrolling stop and click.

Text overlays:
  text — under 5 words, no emojis
  position — top (default for talking heads), center (only when no face in frame), bottom
  appear_at_clip — which clip number
  style — title (72px), callout (56px), cta (64px)
  If captions are already burned in, use overlays sparingly — maximum 2-3 per video.

Sound effects — audio accents that EMPHASIZE specific moments. Each sound must be tied to a real event you can see or hear. Use the word timestamps above to place sounds at the EXACT moment.

  ching — cash register. Place ONLY when the speaker says the word "free" or "sold" or states a specific dollar amount. No other words. Use the word timestamps to place the ching at the exact start of the trigger word.
    "word" = the exact trigger word (e.g. "free", "sold")

  ding — notification bell. Place ONLY when the speaker says the word "text", "notification", or "email". No other words.
    "word" = the exact trigger word (e.g. "text", "notification", "email")

  pop — bright snap. Place ONLY when a new visual element appears on screen mid-video that was NOT there before — such as a screen recording appearing, an image overlay appearing, or a picture-in-picture opening. This is a VISUAL event only. Do NOT place pop on:
    - The start of the video (nothing is "appearing")
    - Text overlays (they don't "pop")
    - Spoken words or phrases
    - Cuts between clips (cuts are silent)
    If you cannot point to a specific frame where something new visually appears on screen, do not use pop.
    "word" = "visual_appear"

  swoosh — air swipe. Place ONLY when you are using a wipe or fade transition between clips. If all transitions are "none" (hard cuts), do not use swoosh at all.
    "word" = "scene_change"

  Rules:
  - Most videos have 1-3 sound effects total. Many have zero. Zero is fine.
  - Every sound effect MUST have a "word" field.
  - Use the word timestamps to place each sound at the EXACT millisecond.
  - If you are unsure whether a sound belongs, leave it out. Silence is better than a wrong sound.

  sound_effects: [
    {{"t": <seconds>, "sound": "<pop|ching|ding|swoosh>", "word": "<trigger word or event>"}}
  ]

=== RESPONSE FORMAT ===

First, write a <vision> block describing your creative plan — what happens in the opening, how pacing flows, where you place b-roll and text, what the color feel is.

Then output the JSON:

```json
{{
  "notes": "<50 words max>",
  "color_intent": "<intent>",
  "hook_clip": {{"source_start": <seconds>, "source_end": <seconds>}} or null,
  "thumbnail_timestamp": <seconds>,
  "caption_style": "<style>",
  "caption_position": "<position>",
  "audio_denoise": <true|false>,
  "outro": "<none|fade_black|fade_white>",
  "background_music": "none",
  "aspect_ratio": "9:16",
  "speed_curve": [<keypoints>] or "none",
  "text_overlays": [
    {{"text": "<text>", "position": "<pos>", "appear_at_clip": <n>, "style": "<style>"}}
  ],
  "sound_effects": [
    {{"t": <seconds>, "sound": "<sound>", "word": "<trigger>"}}
  ],
  "cuts": [
    {{"source_start": <n>, "source_end": <n>, "transition_out": "<transition>", "zoom": "<zoom>", "cut_zoom": <bool>}}
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


def generate_edit_gemini(video_path, vibe, duration, trend_context=None, deepgram_words=None, face_positions=None):
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
        for w in deepgram_words:
            word_text = w.get("punctuated_word") or w.get("word") or ""
            start = float(w.get("start") or 0)
            end = float(w.get("end") or 0)
            word_lines.append(f"  {start:.2f}-{end:.2f}: {word_text}")

        transcript_block = "\n".join(word_lines)
        first_word_start = float(deepgram_words[0].get("start", 0))
        prompt += f"""

=== FULL TRANSCRIPT ===

Read this first to understand the full story before making any editing decisions. Identify the narrative structure — what is setup, what is filler, what is the buildup, and where are the punchlines or reveals. For speed ramping, use this understanding: the parts you'd skim if reading are filler (speed up), the parts that make you react are punchlines (slow down), and the parts that build tension should stay at normal speed.

{readable_transcript}

=== WORD-BY-WORD TIMESTAMPS ===

The following is the complete word-by-word transcript with millisecond-accurate timestamps from speech recognition. Use these timestamps to place your cuts PRECISELY in the silence gaps between words.

{transcript_block}

RULES FOR USING THESE TIMESTAMPS:
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

    print("[generate-edit] Uploading video to Gemini...", flush=True)
    gemini_file = genai.upload_file(video_path)
    deadline = time.time() + 180
    while gemini_file.state.name == "PROCESSING":
        if time.time() > deadline:
            raise RuntimeError("Gemini file upload timed out after 180s")
        time.sleep(2)
        gemini_file = genai.get_file(gemini_file.name)
    if gemini_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed: {gemini_file.state.name}")
    print(f"[generate-edit] Video active: {gemini_file.uri}", flush=True)

    last_err = None
    response = None
    for model_name in [GEMINI_MODEL]:
        try:
            print(f"[generate-edit] Calling Gemini model={model_name}...", flush=True)
            t = time.time()
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                [gemini_file, prompt],
                generation_config=genai.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=16384,
                ),
            )
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                finish_reason = getattr(candidates[0], "finish_reason", None)
                if finish_reason == 2:
                    print("[generate-edit] WARNING: Gemini response truncated — retrying with higher token limit", flush=True)
                    response = model.generate_content(
                        [gemini_file, prompt],
                        generation_config=genai.GenerationConfig(
                            temperature=0.6,
                            max_output_tokens=32768,
                        ),
                    )
                    retry_candidates = getattr(response, "candidates", None) or []
                    if retry_candidates and getattr(retry_candidates[0], "finish_reason", None) == 2:
                        raise RuntimeError("Gemini response truncated even with 32768 max tokens")
            print(f"[generate-edit] Gemini complete in {time.time()-t:.1f}s", flush=True)
            break
        except Exception as e:
            last_err = e
            print(f"[generate-edit] Gemini model {model_name} failed: {e}", flush=True)
    if response is None:
        raise RuntimeError(f"Gemini edit generation failed: {last_err}")

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

    vision_text = ""
    if "<vision>" in response_text and "</vision>" in response_text:
        try:
            vision_start = response_text.index("<vision>") + len("<vision>")
            vision_end = response_text.index("</vision>", vision_start)
            vision_text = response_text[vision_start:vision_end].strip()
        except Exception:
            vision_text = ""
    if vision_text:
        print(f"[generate-edit] VISION: {vision_text}", flush=True)
    print(f"[generate-edit] RAW RESPONSE:\n{response_text}\n[generate-edit] END RESPONSE", flush=True)

    edit_plan = extract_json(response_text)
    edit_plan["_deepgram_words"] = list(deepgram_words or [])
    analysis = build_analysis_from_gemini_recipe(edit_plan, duration=duration)
    has_burned_captions = infer_has_burned_captions(edit_plan, analysis, log_prefix="[generate-edit]")

    raw_cuts = edit_plan.get("cuts") or edit_plan.get("clips") or []
    if not raw_cuts:
        raise ValueError("Gemini response missing cuts array")
    for clip in raw_cuts:
        clip["freeze_frame"] = False
        clip["motion_blur_transition"] = False
        clip.pop("speed_ramp", None)
        clip.pop("freeze_frame", None)
        clip.pop("motion_blur_transition", None)
        clip.pop("speed_segments", None)

    video_duration = float(analysis.get("duration") or 0)
    validated_cuts = []
    for i, cut in enumerate(raw_cuts):
        src_start = float(cut.get("source_start") or 0)
        src_end = float(cut.get("source_end") or 0)
        if src_start >= src_end:
            raise ValueError(f"Cut {i}: source_start ({src_start}) >= source_end ({src_end})")
        if src_start < 0:
            raise ValueError(f"Cut {i}: source_start is negative")
        if video_duration > 0 and src_end > video_duration + 0.5:
            raise ValueError(f"Cut {i}: source_end ({src_end}) exceeds video duration ({video_duration})")
        if i > 0 and src_start < validated_cuts[i-1]["source_start"]:
            raise ValueError(f"Cut {i}: not in chronological order")
        validated_cuts.append({**cut, "source_start": src_start, "source_end": src_end, "clip": i + 1})

    for i in range(1, len(validated_cuts)):
        prev_end = validated_cuts[i - 1]["source_end"]
        curr_start = validated_cuts[i]["source_start"]
        if curr_start < prev_end:
            print(f"[generate-edit] Fixing clip {i} overlap: source_start {curr_start} -> {prev_end}", flush=True)
            validated_cuts[i]["source_start"] = prev_end

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

    _dg_words = edit_plan.get("_deepgram_words", [])
    if _dg_words:
        # Snapping disabled — Gemini has Deepgram timestamps and places cuts in silence gaps
        # validated_cuts = snap_cuts_to_word_boundaries(validated_cuts, _dg_words)
        print(f"[generate-edit] Snapping disabled — Gemini has word timestamps", flush=True)

        # Tightening disabled — Gemini has Deepgram timestamps and places precise cuts
        # validated_cuts = tighten_clips_with_deepgram(validated_cuts, _dg_words, min_silence_to_remove=0.08)
        print(f"[generate-edit] Tightening disabled — Gemini has word timestamps", flush=True)

        # Micro-gap closing not needed — Gemini places precise boundaries
    else:
        print("[generate-edit] No Deepgram words available — skipping word-boundary snapping and tightening", flush=True)

    vibe_lower = vibe.lower() if isinstance(vibe, str) else ""
    has_transition_request = any(
        word in vibe_lower for word in ["transition", "transitions", "white fade", "fadewhite", "whip", "flash"]
    )
    if not has_transition_request:
        for clip in validated_cuts:
            if clip.get("transition_out") != "none":
                print(f"[generate-edit] Removing transition '{clip['transition_out']}' (not requested in vibe)", flush=True)
                clip["transition_out"] = "none"

    visual_cuts = sorted(float(sc) for sc in (analysis.get("visual_cuts") or []) if sc is not None)
    if visual_cuts:
        for i in range(len(validated_cuts) - 1):
            clip_end = round(validated_cuts[i]["source_end"], 1)
            has_scene_change = any(abs(clip_end - sc) < 0.5 for sc in visual_cuts)
            if not has_scene_change and str(validated_cuts[i].get("transition_out") or "none").lower() != "none":
                print(
                    f"[generate-edit] Stripping transition={validated_cuts[i]['transition_out']} "
                    f"from clip {i} (no scene change at {clip_end}s)",
                    flush=True,
                )
                validated_cuts[i]["transition_out"] = "none"

    # Zoom rules:
    # - If burned-in captions: ALL zoom and cut_zoom disabled on ALL clips
    # - If no burned-in captions: zoom allowed ONLY on the first clip, disabled on all others
    # - cut_zoom disabled everywhere (too distracting, crops burned-in text)
    if has_burned_captions:
        for clip in validated_cuts:
            if clip.get("zoom") and clip["zoom"] != "none":
                print(f"[generate-edit] Overriding zoom={clip['zoom']} to none (burned-in captions)", flush=True)
                clip["zoom"] = "none"
            if clip.get("cut_zoom"):
                print(f"[generate-edit] Overriding cut_zoom=true to false (burned-in captions)", flush=True)
                clip["cut_zoom"] = False
    else:
        for i, clip in enumerate(validated_cuts):
            if i == 0:
                if clip.get("cut_zoom"):
                    clip["cut_zoom"] = False
            else:
                if clip.get("zoom") and clip["zoom"] != "none":
                    print(f"[generate-edit] Overriding zoom={clip['zoom']} to none (only first clip gets zoom)", flush=True)
                    clip["zoom"] = "none"
                if clip.get("cut_zoom"):
                    print(f"[generate-edit] Overriding cut_zoom=true to false (only first clip gets zoom)", flush=True)
                    clip["cut_zoom"] = False

    edit_plan.setdefault("background_music", "none")
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
    edit_plan.setdefault("broll", [])
    edit_plan.setdefault("sharpening", False)
    edit_plan.setdefault("grain", "none")
    edit_plan.setdefault("denoise", False)
    edit_plan.setdefault("cinematic_bars", False)
    edit_plan.setdefault("shadow_lift", False)
    edit_plan.setdefault("highlight_rolloff", False)
    edit_plan.setdefault("vibrance", False)
    edit_plan.setdefault("teal_orange", "none")
    edit_plan["background_music"] = "none"
    edit_plan["caption_keywords"] = []
    edit_plan["audio_ducking"] = True
    edit_plan["beat_sync"] = False
    edit_plan.setdefault("sound_effects", [])
    edit_plan.pop("teal_orange", None)
    edit_plan.pop("beat_sync", None)

    valid_caption_styles = {"none", "capcut", "word_pop", "hormozi", "minimal", "two_line", "boxed"}
    if str(edit_plan.get("caption_style") or "").lower() not in valid_caption_styles:
        edit_plan["caption_style"] = "capcut"
    else:
        edit_plan["caption_style"] = str(edit_plan.get("caption_style") or "none").lower()

    raw_curve = edit_plan.get("speed_curve", "none")
    if raw_curve == "none" or raw_curve is None or not isinstance(raw_curve, list):
        speed_curve = None
    else:
        speed_curve = []
        for kp in raw_curve:
            if isinstance(kp, dict) and "t" in kp and "speed" in kp:
                try:
                    t = max(0.0, float(kp["t"]))
                    s = max(0.5, min(1.5, float(kp["speed"])))
                    speed_curve.append({"t": t, "speed": s})
                except Exception:
                    continue
        if len(speed_curve) < 2:
            speed_curve = None
        else:
            speed_curve.sort(key=lambda x: x["t"])
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
    if hook_clip and _dg_words:
        hook_s = float(hook_clip.get("source_start") or 0.0)
        hook_e = float(hook_clip.get("source_end") or 0.0)
        print(f"[hook] Tightening: looking for words in {hook_s:.2f}-{hook_e:.2f} ({len(_dg_words)} total words)", flush=True)
        first_word_start = None
        last_word_end = None
        for w in _dg_words:
            ws = float(w.get("start") or 0.0)
            we = float(w.get("end") or 0.0)
            if ws >= hook_s - 0.05 and ws <= hook_e:
                if first_word_start is None:
                    first_word_start = ws
                last_word_end = we
        if first_word_start is not None and last_word_end is not None:
            print(f"[hook] Found speech: first_word={first_word_start:.2f}, last_word_end={last_word_end:.2f}", flush=True)
            new_start = max(hook_s, first_word_start - 0.05)
            new_end = min(hook_e, last_word_end + 0.1)
            if new_start != hook_s or new_end != hook_e:
                print(
                    f"[hook] Tightened hook: {hook_s:.2f}-{hook_e:.2f} → {new_start:.2f}-{new_end:.2f} "
                    f"(snapped to speech)",
                    flush=True,
                )
                hook_clip["source_start"] = round(new_start, 3)
                hook_clip["source_end"] = round(new_end, 3)
    edit_plan["hook_clip"] = hook_clip
    edit_plan["_hook_offset"] = 0.0
    if edit_plan.get("hook_clip"):
        for cut in edit_plan.get("cuts", []):
            cut["zoom"] = "none"

    raw_sfx = edit_plan.get("sound_effects", [])
    sound_effects = []
    valid_sounds = {"pop", "ching", "ding", "swoosh"}
    VALID_CHING_WORDS = {"free", "sold", "dollar", "dollars"}
    for sfx in raw_sfx:
        if isinstance(sfx, dict) and "t" in sfx and "sound" in sfx:
            try:
                t = float(sfx["t"])
            except Exception:
                continue
            sound = str(sfx["sound"]).lower()
            if sound in valid_sounds and t >= 0:
                word = str(sfx.get("word") or "").strip().lower()

                # Enforce ching only on approved trigger words
                if sound == "ching":
                    word_clean = word.strip(".,!?;:'\"")
                    is_dollar_amount = "$" in word or word_clean.replace(".", "").replace(",", "").isdigit()
                    if word_clean not in VALID_CHING_WORDS and not is_dollar_amount:
                        print(f"[generate-edit] Filtered out ching on '{word}' at {t:.1f}s (not an approved trigger)", flush=True)
                        continue

                # Enforce ding only on approved trigger words
                if sound == "ding":
                    VALID_DING_WORDS = {"text", "notification", "email"}
                    word_clean = word.strip(".,!?;:'\"")
                    if word_clean not in VALID_DING_WORDS:
                        print(f"[generate-edit] Filtered out ding on '{word}' at {t:.1f}s (not an approved trigger)", flush=True)
                        continue

                # Enforce swoosh only when transitions are present
                if sound == "swoosh":
                    has_transitions = any(
                        str(c.get("transition_out") or "none").lower() not in ("none", "")
                        for c in (edit_plan.get("cuts") or [])
                    )
                    if not has_transitions:
                        print(f"[generate-edit] Filtered out swoosh at {t:.1f}s (no transitions in video)", flush=True)
                        continue

                # Enforce pop: only when b-roll exists near this timestamp
                if sound == "pop":
                    pop_has_visual = False
                    for br in (edit_plan.get("broll") or []):
                        if abs(float(br.get("timestamp", 0)) - t) < 3.0:
                            pop_has_visual = True
                            break
                    if word == "visual_appear":
                        cuts_list = edit_plan.get("cuts") or []
                        for ci in range(1, len(cuts_list)):
                            gap = float(cuts_list[ci].get("source_start", 0)) - float(cuts_list[ci-1].get("source_end", 0))
                            if gap > 0.5:
                                skip_time = float(cuts_list[ci].get("source_start", 0))
                                if abs(skip_time - t) < 3.0:
                                    pop_has_visual = True
                                    break
                    if not pop_has_visual:
                        print(f"[generate-edit] Filtered out pop at {t:.1f}s (no visual event confirmed)", flush=True)
                        continue

                sound_effects.append({"t": t, "sound": sound, "word": word})
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
    valid_transitions = {"none", "fadewhite", "whip_left", "whip_right"}
    if edit_plan.get("grain") not in valid_grain:
        edit_plan["grain"] = "none"
    if edit_plan.get("vignette") not in valid_vignette:
        edit_plan["vignette"] = "none"

    for overlay in edit_plan.get("text_overlays", []):
        if overlay.get("position") == "center":
            print(f"[generate-edit] Moving text overlay '{overlay.get('text', '')}' from center to top (talking head safety)", flush=True)
            overlay["position"] = "top"
        overlay.setdefault("sfx_style", "none")
        overlay["sfx_style"] = "none"

    final_cuts = []
    for clip_entry in validated_cuts:
        transition = str(clip_entry.get("transition_out") or "").lower()
        if transition not in valid_transitions:
            if "fade" in transition or "dissolve" in transition:
                transition = "fadewhite"
            elif "whip" in transition or "wipe" in transition or "smooth" in transition:
                transition = "whip_right"
            else:
                transition = "none"
            print(f"[generate-edit] Mapped unsupported transition '{clip_entry.get('transition_out')}' -> '{transition}'", flush=True)
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

    baseline = analysis.get("color_baseline") or {}
    intent = normalize_intent(edit_plan.get("color_intent") or "none")
    edit_plan["color_intent"] = intent
    # Color grading filters are disabled; keep recipe metadata but emit no FFmpeg grading.
    edit_plan["color_grade"] = {}
    edit_plan["cuts"] = final_cuts
    edit_plan.pop("teal_orange", None)
    edit_plan.pop("beat_sync", None)
    edit_plan.pop("video_profile", None)
    edit_plan.pop("frame_layout", None)
    if "clips" in edit_plan:
        del edit_plan["clips"]
    if final_cuts:
        edit_plan["target_duration"] = final_cuts[-1]["source_end"] - final_cuts[0]["source_start"]
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
        f"{len(edit_plan.get('broll', []))} b-roll, "
        f"{len(edit_plan.get('sound_effects', []))} sfx, "
        f"intent={edit_plan.get('color_intent', 'none')}, "
        f"captions={edit_plan.get('caption_style', 'none')}",
        flush=True,
    )

    return edit_plan


# ─── SFX HELPERS ─────────────────────────────────────────────────────────────

_SFX_BASE_VOLUMES = {
    "shutter":    0.66,
    "swoosh":     0.62,
    "thud":       0.56,
    "pop":        0.72,
    "ding":       0.66,
    "typing":     0.60,
    "reverb_hit": 0.58,
    "ching":      0.72,
}

_TEXT_SFX_BASE_VOLUMES = {
    "pop":        0.64,
    "ding":       0.60,
    "ching":      0.66,
    "typing":     0.58,
    "reverb_hit": 0.56,
    "shutter":    0.62,
    "swoosh":     0.52,
    "thud":       0.54,
}

_SFX_ALIASES = {
    "whoosh":    "swoosh",
    "boom":      "thud",
    "cashier":   "ching",
    "cash":      "ching",
    "money":     "ching",
    "rise":      "reverb_hit",
    "click":     "pop",
    "impact":    "thud",
    "slide":     "swoosh",
    "snap":      "pop",
    "glitch":    "swoosh",
    "tape_stop": "reverb_hit",
    "drop":      "thud",
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
    normalized = normalize_sfx_style(sound_name)
    if is_text_overlay:
        base = _TEXT_SFX_BASE_VOLUMES.get(normalized, 0.56)
        duck = 0.80
    else:
        base = _SFX_BASE_VOLUMES.get(normalized, 0.60)
        duck = 0.75
    segs = speech_segments or []
    during_speech = any(
        float(seg.get("start") or 0) <= timestamp <= float(seg.get("end") or 0)
        for seg in segs
    )
    vol = base * duck if during_speech else base
    return round(vol, 3)


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
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
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
            probe_cmd = [
                "ffprobe", "-v", "quiet",
                "-show_entries", "stream=codec_type,duration,width,height,r_frame_rate,codec_name",
                "-show_entries", "format=duration",
                "-of", "json",
                dest,
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            probe_data = json.loads(probe_result.stdout)

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

            if frame_count < 5:
                print(
                    f"[broll] REJECTED '{keyword}': only {frame_count} decoded frames in first 2s — likely a still image",
                    flush=True,
                )
                os.remove(dest)
                return None

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
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def composite_broll(output_path, broll_entries, broll_files, work_dir):
    """Composite pre-downloaded b-roll clips onto the output video."""
    entries_with_files = []
    for i, entry in enumerate(broll_entries):
        local_path = broll_files.get(i)
        if local_path and os.path.exists(local_path):
            entries_with_files.append({**entry, "local_path": local_path})
    if not entries_with_files:
        return
    tmp_out = output_path + ".broll_tmp.mp4"
    input_args = ["-i", output_path]
    for entry in entries_with_files:
        input_args += ["-i", entry["local_path"]]
    filter_parts = []
    for i, entry in enumerate(entries_with_files):
        idx = i + 1
        keyword = str(entry.get("keyword") or "broll")
        needed_duration = float(entry.get("duration") or 2.0)
        broll_duration = get_video_duration(entry["local_path"])
        if broll_duration > needed_duration + 1.0:
            seek_point = broll_duration * 0.25
            seek_point = min(seek_point, max(0.0, broll_duration - needed_duration - 0.5))
            print(
                f"[broll] Trimming '{keyword}': {broll_duration:.1f}s clip, seeking to {seek_point:.1f}s, using {needed_duration}s",
                flush=True,
            )
        else:
            seek_point = 0.0
            print(
                f"[broll] Using '{keyword}' from start ({broll_duration:.1f}s clip, need {needed_duration}s)",
                flush=True,
            )
        filter_parts.append(
            f"[{idx}:v]trim=start={seek_point:.3f}:duration={needed_duration:.3f},"
            f"setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:(iw-1080)/2:(ih-1920)/2,setsar=1[bv{i}]"
        )
    prev = "0:v"
    for i, entry in enumerate(entries_with_files):
        ts    = float(entry["timestamp"])
        dur   = float(entry["duration"])
        label = f"ov{i}"
        filter_parts.append(
            f"[{prev}][bv{i}]overlay=0:0:enable='between(t,{ts:.3f},{ts+dur:.3f})'[{label}]"
        )
        prev = label
    run_ffmpeg([
        "-y",
        ] + input_args + [
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{prev}]",
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-c:a", "copy",
        "-movflags", "+faststart",
        tmp_out,
    ])
    os.replace(tmp_out, output_path)
    print(f"[broll] Composited {len(entries_with_files)} b-roll clip(s) onto output", flush=True)


def apply_filler_jump_cuts(cuts, deepgram_words):
    """
    Split model-generated clips at ALWAYS_FILLER word boundaries (um, uh, hmm, etc.)
    Context fillers (like, so, basically) are intentionally never removed.
    Returns the expanded cut list, or the original if no fillers found inside clips.
    """
    if not deepgram_words:
        return cuts

    all_fillers = detect_filler_words(deepgram_words)
    hard_fillers = [f for f in all_fillers if f["reason"] == "always-filler"]
    if not hard_fillers:
        return cuts

    MIN_SUBCLIP = 0.25

    result = []
    for cut in cuts:
        cs = float(cut["source_start"])
        ce = float(cut["source_end"])
        original_transition  = cut.get("transition_out") or "none"
        original_trans_sound = cut.get("transition_sound") or "none"

        interior_fillers = [
            f for f in hard_fillers
            if float(f["start"]) >= cs + 0.05 and float(f["end"]) <= ce - 0.05
        ]

        if not interior_fillers:
            result.append(cut)
            continue

        keep_ranges = []
        cursor = cs
        for filler in sorted(interior_fillers, key=lambda f: f["start"]):
            fs = float(filler["start"])
            fe = float(filler["end"])
            if fs > cursor:
                keep_ranges.append((round(cursor * 1000) / 1000, round(fs * 1000) / 1000))
            cursor = max(cursor, fe)
        if cursor < ce:
            keep_ranges.append((round(cursor * 1000) / 1000, round(ce * 1000) / 1000))

        keep_ranges = [(s, e) for s, e in keep_ranges if e - s >= MIN_SUBCLIP]

        if not keep_ranges:
            result.append(cut)
            continue

        for i, (sub_start, sub_end) in enumerate(keep_ranges):
            is_last = (i == len(keep_ranges) - 1)
            sub = dict(cut)
            sub["source_start"]     = sub_start
            sub["source_end"]       = sub_end
            sub["transition_out"]   = original_transition   if is_last else "none"
            sub["transition_sound"] = original_trans_sound  if is_last else "none"
            if not is_last:
                sub["freeze_frame"]           = False
                sub["motion_blur_transition"] = False
            result.append(sub)

        removed = [f["word"] for f in interior_fillers]
        print(f"[filler_cuts] clip {cs:.2f}s-{ce:.2f}s: removed {removed} -> {len(keep_ranges)} sub-clips", flush=True)

    return result


# ─── FFMPEG RENDER ────────────────────────────────────────────────────────────

TRANSITION_DURATION = 0.3


def probe_duration(file_path):
    result = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",file_path],
        capture_output=True, text=True
    )
    try:
        d = float(result.stdout.strip())
        return d if d > 0 else None
    except Exception:
        return None


def probe_audio_sample_rate(file_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path,
        ],
        capture_output=True, text=True
    )
    try:
        sample_rate = int((result.stdout or "").strip())
        return sample_rate if sample_rate > 0 else None
    except Exception:
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
    result = subprocess.run(
        ["ffprobe","-v","error","-select_streams","v:0",
         "-show_entries","stream=width,height","-of","json",file_path],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        s = (data.get("streams") or [{}])[0]
        return {"width": s.get("width") or 1080, "height": s.get("height") or 1920}
    except Exception:
        return {"width": 1080, "height": 1920}


def run_ffmpeg(args):
    print(f"[ffmpeg] Running: ffmpeg {' '.join(str(a) for a in args[:10])}...", flush=True)
    t = time.time()
    result = subprocess.run(["ffmpeg"] + [str(a) for a in args], capture_output=True, text=True)
    elapsed = time.time() - t
    if result.returncode != 0:
        print(f"[ffmpeg] FAILED after {elapsed:.1f}s", flush=True)
        print(f"[ffmpeg] stderr (last 800):\n{result.stderr[-800:]}", flush=True)
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-300:]}")
    print(f"[ffmpeg] Completed in {elapsed:.1f}s", flush=True)
    return result


def normalize_source_video(source_path, work_dir):
    result = subprocess.run(
        ["ffprobe","-v","quiet","-print_format","json","-show_streams","-show_format",source_path],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout or "{}")
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("No video stream found in source")

    w = int(video.get("width") or 0)
    h = int(video.get("height") or 0)
    if w > h:
        print(f"[normalize] Landscape input ({w}x{h}) — will center-crop to 9:16", flush=True)

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
    needs_normalize = (w != 1080 or h != 1920 or abs(fps - 30) > 1 or is_vfr)

    if not needs_normalize:
        print(f"[normalize] Source is already {w}x{h} @ {fps:.2f}fps — skipping", flush=True)
        return source_path

    normalized_path = os.path.join(work_dir, "normalized_source.mp4")
    print(f"[normalize] Converting {w}x{h} @ {fps:.2f}fps to 1080x1920 @ 30fps", flush=True)

    sample_timestamps = []
    source_duration = probe_duration(source_path) or 0.0
    if source_duration > 0:
        sample_timestamps = [round(i * 2.0, 3) for i in range(int(source_duration / 2.0) + 1)]
    face_positions = detect_face_positions(source_path, sample_timestamps) if sample_timestamps else []
    reframe_crops = calculate_reframe_crop(face_positions, w, h)

    normalize_vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if reframe_crops:
        avg_crops = [c for c in reframe_crops if c.get("found")] or reframe_crops
        avg_x = int(sum(c["crop_x"] for c in avg_crops) / len(avg_crops))
        avg_y = int(sum(c["crop_y"] for c in avg_crops) / len(avg_crops))
        crop_w = int(reframe_crops[0]["crop_w"])
        crop_h = int(reframe_crops[0]["crop_h"])
        normalize_vf = f"crop={crop_w}:{crop_h}:{avg_x}:{avg_y},scale=1080:1920,setsar=1"
        print(
            f"[reframe] Smart reframe active in normalize: crop={crop_w}x{crop_h}@({avg_x},{avg_y})",
            flush=True,
        )
    else:
        print("[reframe] Source is native 9:16 — using center crop", flush=True)

    normalize_args = [
        "-y","-i",source_path,
        "-vf", normalize_vf,
        "-r","30","-vsync","cfr","-pix_fmt","yuv420p",
        "-c:v","libx264","-preset","medium","-crf","18",
        "-c:a","aac","-b:a","192k","-ar","48000","-ac","2",
        "-threads","1","-map","0:v:0",
    ]
    if audio:
        normalize_args += ["-map","0:a:0"]
    normalize_args.append(normalized_path)
    run_ffmpeg(normalize_args)

    try:
        os.unlink(source_path)
    except Exception:
        pass
    os.rename(normalized_path, source_path)
    print("[normalize] Done", flush=True)
    return source_path


def create_keyframed_source(source_path, keyframe_timestamps, work_dir):
    unique_kf = sorted(set(round(t*1000)/1000 for t in keyframe_timestamps if t > 0))
    kf_str = ",".join(str(t) for t in unique_kf)
    keyframed_path = os.path.join(work_dir, "keyframed_source.mp4")
    print(f"[ffmpeg] Forcing keyframes at {len(unique_kf)} cut points", flush=True)
    run_ffmpeg([
        "-y","-i",source_path,
        "-c:v","libx264","-preset","ultrafast","-crf","0",
        "-force_key_frames",kf_str,
        "-r","30","-vsync","cfr","-pix_fmt","yuv420p",
        "-c:a","copy","-threads","1",
        keyframed_path,
    ])
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


def get_speed_for_timestamp(t, speed_curve):
    """Given a source timestamp, return the speed from the speed curve."""
    if not speed_curve or speed_curve == "none":
        return 1.0
    active_speed = 1.0
    for kp in speed_curve:
        if float(kp["t"]) <= t:
            active_speed = float(kp["speed"])
        else:
            break
    return active_speed


def _interpolate_speed(speed_curve, t):
    """Linearly interpolate speed at time t from keypoints."""
    if not speed_curve:
        return 1.0
    if t <= speed_curve[0]["t"]:
        return speed_curve[0]["speed"]
    if t >= speed_curve[-1]["t"]:
        return speed_curve[-1]["speed"]
    for i in range(len(speed_curve) - 1):
        t0 = speed_curve[i]["t"]
        t1 = speed_curve[i + 1]["t"]
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
            s0 = speed_curve[i]["speed"]
            s1 = speed_curve[i + 1]["speed"]
            return s0 + (s1 - s0) * frac
    return 1.0


def is_hard_cut(transition):
    t = str(transition or "").strip().lower()
    return not t or t in ("none", "clean_cut")


def build_video_filter_chain(color_grade, source_res, edit_plan=None):
    ep = edit_plan or {}
    filters = []

    # Color preset based on color_intent
    intent = str(ep.get("color_intent") or "none").lower()

    if intent == "polished" or intent == "clean" or intent == "warm" or intent == "punchy" or intent == "vibrant":
        # "polished" preset — contrast and saturation only
        # NO brightness, NO gamma, NO curves — those wash out well-exposed footage
        filters.append(
            "eq=contrast=1.06:saturation=1.08"
        )

    elif intent == "none":
        # No color processing — raw footage
        pass

    grain = str(ep.get("grain") or "none").lower()
    if grain == "subtle":
        filters.append("noise=c0s=4:c0f=t+u")
    elif grain == "medium":
        filters.append("noise=c0s=9:c0f=t+u")
    elif grain == "heavy":
        filters.append("noise=c0s=16:c0f=t+u")

    return ",".join(filters) if filters else "null"


def project_words_to_output(transcript, cuts, effective_durations, hook_offset=0.0, hook_clip=None, speed_curve=None):
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        speed   = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        curve_speed = 1.0
        if speed_curve and speed_curve != "none":
            curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(c_start, speed_curve)))
        combined_speed = speed * curve_speed
        for w in words:
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            if we <= c_start or ws >= c_end:
                continue
            local_s = (max(ws, c_start) - c_start) / combined_speed
            local_e = (min(we, c_end) - c_start) / combined_speed
            projected.append({
                "start": round((output_cursor + local_s)*1000)/1000,
                "end":   round((output_cursor + local_e)*1000)/1000,
                "word":  w.get("punctuated_word") or w.get("word") or "",
                "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                "speaker": int(w.get("speaker", 0) or 0),
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        overlap = TRANSITION_DURATION if i < len(cuts)-1 and not is_hard_cut(cut.get("transition_out")) else 0
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


def format_ass_time(seconds):
    s = max(0, float(seconds or 0))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    cs = round((s % 1) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def generate_subtitle_file(transcript, caption_style, cuts, effective_durations, output_res, caption_position, caption_keywords, work_dir, hook_offset=0.0, hook_clip=None, speed_curve=None):
    words = project_words_to_output(
        transcript,
        cuts,
        effective_durations,
        hook_offset=hook_offset,
        hook_clip=hook_clip,
        speed_curve=speed_curve,
    )
    if not words:
        return None

    w = output_res.get("width") or 1080
    h = output_res.get("height") or 1920

    # Vertical position margin — distance from BOTTOM of frame in pixels
    # On a 1920px tall frame:
    #   400px from bottom = 79% from top (below most faces, above TikTok/Reels UI)
    #   TikTok UI covers roughly the bottom 280px (username, caption, buttons)
    #   Faces are typically in the top 60% of the frame
    pos_margin = {"top": 1550, "lower-third": 400, "center": 800, "bottom": 100}
    margin_v = pos_margin.get(caption_position or "lower-third", 400)

    styles_map = {
        "capcut":         {"fontsize": 58, "fontname": "Montserrat ExtraBold", "bold": 0, "alignment": 5},
        "standard":       {"fontsize": 44, "fontname": "Montserrat",           "bold": 0, "alignment": 2},
        "bold_centered":  {"fontsize": 58, "fontname": "Montserrat Black",     "bold": 0, "alignment": 5},
        "minimal_bottom": {"fontsize": 36, "fontname": "Montserrat",           "bold": 0, "alignment": 2},
        "word_pop":       {"fontsize": 54, "fontname": "Montserrat ExtraBold", "bold": 0, "alignment": 5},
        "hormozi":        {"fontsize": 62, "fontname": "Montserrat Black",     "bold": 0, "alignment": 5},
        "minimal":        {"fontsize": 40, "fontname": "Montserrat Bold",      "bold": 0, "alignment": 5},
        "two_line":       {"fontsize": 50, "fontname": "Montserrat ExtraBold", "bold": 0, "alignment": 5},
        "boxed":          {"fontsize": 48, "fontname": "Montserrat Bold",      "bold": 0, "alignment": 5},
        "bold_white":     {"fontsize": 60, "fontname": "Montserrat Black",     "bold": 0, "alignment": 5},
        "bold_yellow":    {"fontsize": 60, "fontname": "Montserrat Black",     "bold": 0, "alignment": 5},
        "keyword_pop":    {"fontsize": 54, "fontname": "Montserrat ExtraBold", "bold": 0, "alignment": 5},
        "box_caption":    {"fontsize": 46, "fontname": "Montserrat",           "bold": 0, "alignment": 2},
    }

    # ── Style definitions ───────────────────────────────────────────────────
    # All styles use the same CapCut-inspired base:
    #   - Filled semi-transparent background box (BorderStyle=3)
    #   - Karaoke highlight color (SecondaryColour) = yellow for active word
    #   - No outline, no shadow — the box provides all contrast
    # Override per style below.

    STYLE_CONFIGS = {
        # name: (fontsize, primary, secondary, backcolour, bold, border_style, outline, shadow, alignment, spacing)
        # primary = text color (inactive words)
        # secondary = highlight color (active word during karaoke sweep)
        # backcolour = background box color (&HAA = alpha, BB=blue, GG=green, RR=red)
        #   &H90000000 = ~56% opacity black box
        #   &H00000000 = fully opaque black box
        #   &HA0000000 = ~37% opacity black box
        "capcut":         ("&H00FFFFFF", "&H0000FFFF", "&H00000000", 1, 5, 0,  0.5),
        "standard":       ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "bold_centered":  ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "minimal_bottom": ("&H00FFFFFF", "&H0000CCFF", "&HA0000000", 3, 0, 0,  1.0),
        "word_pop":       ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "hormozi":        ("&H00FFFFFF", "&H0000FFFF", "&H00000000", 1, 5, 0,  0.5),
        "minimal":        ("&H00FFFFFF", "&H00AAAAAA", "&H00000000", 1, 2, 1,  0.5),
        "two_line":       ("&H00FFFFFF", "&H0000FFFF", "&H00000000", 1, 4, 0,  0.5),
        "boxed":          ("&H00FFFFFF", "&H0000FFFF", "&HB0000000", 3, 0, 0,  0.5),
        "bold_white":     ("&H00FFFFFF", "&H00FFFFFF", "&H90000000", 3, 0, 0,  1.2),
        "bold_yellow":    ("&H0000FFFF", "&H00FFFFFF", "&H90000000", 3, 0, 0,  1.2),
        "keyword_pop":    ("&H00FFFFFF", "&H0000FF00", "&H90000000", 3, 0, 0,  1.2),
        "box_caption":    ("&H00FFFFFF", "&H0000FFFF", "&HB0000000", 3, 0, 0,  1.0),
    }

    # Per-speaker active word highlight colors (ASS BGR format)
    SPEAKER_HIGHLIGHT_COLORS = {
        0: None,
        1: None,
        2: "&H00FFFF00&",  # cyan
        3: "&H0000FF00&",  # green
        4: "&H00FF00FF&",  # magenta
        5: "&H000080FF&",  # orange
    }

    style_meta = styles_map.get(caption_style, styles_map["standard"])
    font_name = style_meta["fontname"]
    fontsize = style_meta["fontsize"]
    bold = style_meta["bold"]
    alignment = style_meta["alignment"]
    position_alignment = {"top": 8, "center": 5, "lower-third": 2, "bottom": 2}
    alignment = position_alignment.get(caption_position or "lower-third", alignment)

    cfg = STYLE_CONFIGS.get(caption_style, STYLE_CONFIGS["standard"])
    primary, secondary, back_c, border_style, outline_w, shadow, spacing = cfg
    all_speakers = set(int(wd.get("speaker", 0) or 0) for wd in words)
    is_multi_speaker = len(all_speakers) > 1
    if is_multi_speaker:
        print(f"[captions] Multi-speaker mode: {len(all_speakers)} speakers detected", flush=True)

    def _speaker_highlight(default_color, word_dict):
        if not is_multi_speaker:
            return default_color
        speaker_id = int((word_dict or {}).get("speaker", 0) or 0)
        speaker_color = SPEAKER_HIGHLIGHT_COLORS.get(speaker_id)
        return speaker_color or default_color

    if caption_style in ("capcut", "hormozi"):
        style_line = (
            f"Style: Default,{font_name},{fontsize},{primary},{secondary},"
            f"&H00000000,&H00000000,{bold},0,0,0,100,100,{spacing},0,"
            f"1,{outline_w},0,{alignment},30,30,{margin_v},1"
        )
    else:
        style_line = (
            f"Style: Default,{font_name},{fontsize},{primary},{secondary},"
            f"&H00000000,{back_c},{bold},0,0,0,100,100,{spacing},0,"
            f"{border_style},{outline_w},{shadow},{alignment},30,30,{margin_v},1"
        )

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _capcut_group(group, highlight_color="&H0000FFFF"):
        """
        Build a CapCut-style animated dialogue line for a group of words.
        Each word gets:
        - A scale bounce animation (80% -> 110% -> 100%)
        - Color highlight while active
        - No background box — uses outline for contrast
        """
        parts = []
        cumulative_ms = 0

        for word_dict in group:
            dur_s = max(0.05, float(word_dict["end"]) - float(word_dict["start"]))
            dur_ms = max(50, round(dur_s * 1000))
            clean = str(word_dict["word"]).strip()
            word_highlight = _speaker_highlight(highlight_color, word_dict)

            pop_in_ms = 80
            settle_ms = 100

            word_tag = (
                f"{{\\fscx80\\fscy80\\1c&H00FFFFFF&}}"
                f"{{\\t({cumulative_ms},{cumulative_ms + pop_in_ms},"
                f"\\fscx115\\fscy115\\1c{word_highlight})}}"
                f"{{\\t({cumulative_ms + pop_in_ms},{cumulative_ms + pop_in_ms + settle_ms},"
                f"\\fscx100\\fscy100)}}"
                f"{{\\t({cumulative_ms + dur_ms - 30},{cumulative_ms + dur_ms},"
                f"\\1c&H00FFFFFF&)}}"
                f"{clean} "
            )
            parts.append(word_tag)
            cumulative_ms += dur_ms

        return "".join(parts).rstrip()

    def _kf_group(group):
        """
        Build a karaoke dialogue line for a group of word dicts.
        Each word gets a {\\kf<cs>} tag where cs = word duration in centiseconds.
        The entire group gets {\\fad(80,60)} for fade in/out.
        Returns the dialogue text string (without the Dialogue prefix).
        """
        parts = ["{\\fad(80,60)}"]
        for word_dict in group:
            dur_s  = max(0.05, float(word_dict["end"]) - float(word_dict["start"]))
            dur_cs = max(5, round(dur_s * 100))
            clean  = str(word_dict["word"]).strip()
            speaker_color = _speaker_highlight(None, word_dict)
            if speaker_color:
                parts.append(f"{{\\2c{speaker_color}\\kf{dur_cs}}}{clean} ")
            else:
                parts.append(f"{{\\kf{dur_cs}}}{clean} ")
        return "".join(parts).rstrip()

    # ── Group words into batches of max 3 words ─────────────────────────────
    # Split on: pause > 0.3s, sentence end punctuation on previous word, or group size == 3
    PUNCT_END = re.compile(r"[.!?,;:]$")
    MAX_WORDS = 3

    def _flush_group(group, ass_acc):
        if not group:
            return
        start = group[0]["start"]
        end   = group[-1]["end"]
        # Small buffer so karaoke highlight finishes before event ends
        end_buffered = end + 0.05
        text = _kf_group(group)
        ass_acc.append(
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end_buffered)}"
            f",Default,,0,0,0,,{text}\n"
        )

    if caption_style == "keyword_pop":
        # keyword_pop: same karaoke groups but highlight is keyword color instead of yellow
        # Override secondary color per-word via inline tags
        keyword_set = set(re.sub(r"[.,!?;:'\"\\]", "", k.lower()) for k in (caption_keywords or []))
        highlight_color = "&H0000FF00"  # green
        normal_color    = "&H00FFFFFF"  # white

        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause  = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                start = group[0]["start"]
                end   = group[-1]["end"] + 0.05
                parts = ["{\\fad(80,60)}"]
                for wd in group:
                    dur_cs = max(5, round(max(0.05, float(wd["end"]) - float(wd["start"])) * 100))
                    clean  = re.sub(r"[.,!?;:'\"\\]", "", (wd.get("word") or "").lower())
                    is_kw  = clean in keyword_set
                    col    = highlight_color if is_kw else normal_color
                    speaker_color = _speaker_highlight(None, wd)
                    if speaker_color:
                        parts.append(f"{{\\2c{speaker_color}\\kf{dur_cs}}}{{\\1c{col}}}{wd['word']} ")
                    else:
                        parts.append(f"{{\\kf{dur_cs}}}{{\\1c{col}}}{wd['word']} ")
                text = "".join(parts).rstrip()
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
                )
                group = []
        ass += "".join(ass_lines)

    elif caption_style == "capcut":
        highlight = "&H0000FFFF"
        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                start = group[0]["start"]
                end = group[-1]["end"] + 0.08
                text = _capcut_group(group, highlight_color=highlight)
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)}"
                    f",Default,,0,0,0,,{text}\n"
                )
                group = []
        ass += "".join(ass_lines)

    elif caption_style == "minimal":
        # Minimal: lowercase text, thin font, subtle shadow, simple karaoke sweep
        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                start = group[0]["start"]
                end = group[-1]["end"] + 0.05
                parts = ["{\\fad(80,60)}"]
                for wd in group:
                    dur_cs = max(5, round(max(0.05, float(wd["end"]) - float(wd["start"])) * 100))
                    clean = str(wd["word"]).strip().lower()
                    parts.append(f"{{\\kf{dur_cs}}}{clean} ")
                text = "".join(parts).rstrip()
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
                )
                group = []
        ass += "".join(ass_lines)

    elif caption_style == "boxed":
        # Boxed: text inside semi-transparent black box, karaoke sweep highlight
        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                start = group[0]["start"]
                end = group[-1]["end"] + 0.05
                parts = ["{\\fad(80,60)}"]
                for wd in group:
                    dur_cs = max(5, round(max(0.05, float(wd["end"]) - float(wd["start"])) * 100))
                    clean = str(wd["word"]).strip()
                    parts.append(f"{{\\kf{dur_cs}}}{clean} ")
                text = "".join(parts).rstrip()
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
                )
                group = []
        ass += "".join(ass_lines)

    elif caption_style == "two_line":
        # Two-line: show 2 groups at once — active line bright, upcoming line dimmed
        # Group words into pairs of groups, show both lines simultaneously
        TWO_LINE_MAX = 4  # words per line
        all_groups = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= TWO_LINE_MAX:
                all_groups.append(group)
                group = []

        ass_lines = []
        for gi in range(0, len(all_groups), 2):
            top_group = all_groups[gi]
            bot_group = all_groups[gi + 1] if gi + 1 < len(all_groups) else None

            pair_start = top_group[0]["start"]
            pair_end = (bot_group[-1]["end"] if bot_group else top_group[-1]["end"]) + 0.08

            # Top line: active with karaoke highlight
            top_parts = []
            for wd in top_group:
                dur_cs = max(5, round(max(0.05, float(wd["end"]) - float(wd["start"])) * 100))
                clean = str(wd["word"]).strip()
                top_parts.append(f"{{\\kf{dur_cs}}}{clean} ")
            top_text = "".join(top_parts).rstrip()

            if bot_group:
                # Bottom line: dimmed (shown as upcoming)
                bot_parts = []
                for wd in bot_group:
                    clean = str(wd["word"]).strip()
                    bot_parts.append(f"{{\\1c&H00888888&}}{clean} ")
                dim_text = "".join(bot_parts).rstrip()

                # Top line with bottom preview below
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(pair_start)},{format_ass_time(top_group[-1]['end'] + 0.05)}"
                    f",Default,,0,0,0,,{top_text}\\N{dim_text}\n"
                )

                # Bottom line becomes active
                bot_active_parts = []
                for wd in bot_group:
                    dur_cs = max(5, round(max(0.05, float(wd["end"]) - float(wd["start"])) * 100))
                    clean = str(wd["word"]).strip()
                    bot_active_parts.append(f"{{\\kf{dur_cs}}}{clean} ")
                bot_active_text = "".join(bot_active_parts).rstrip()

                # Show top line dimmed, bottom line active
                top_dim_parts = []
                for wd in top_group:
                    clean = str(wd["word"]).strip()
                    top_dim_parts.append(f"{{\\1c&H00888888&}}{clean} ")
                top_dim_text = "".join(top_dim_parts).rstrip()

                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(bot_group[0]['start'])},{format_ass_time(pair_end)}"
                    f",Default,,0,0,0,,{top_dim_text}\\N{bot_active_text}\n"
                )
            else:
                # Only top line (odd number of groups)
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(pair_start)},{format_ass_time(pair_end)}"
                    f",Default,,0,0,0,,{top_text}\n"
                )

        ass += "".join(ass_lines)

    elif caption_style == "hormozi":
        # Hormozi: uppercase, bold, keyword words highlighted in yellow
        # Active word gets scale bounce + color highlight (like capcut but uppercase + keyword color)
        keyword_set = set(re.sub(r"[.,!?;:'\"\\]", "", k.lower()) for k in (caption_keywords or []))
        highlight_color = "&H0000FFFF"  # yellow
        keyword_color = "&H004080FF"    # orange-red for keywords

        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                start = group[0]["start"]
                end = group[-1]["end"] + 0.08
                parts = []
                cumulative_ms = 0
                for wd in group:
                    dur_s = max(0.05, float(wd["end"]) - float(wd["start"]))
                    dur_ms = max(50, round(dur_s * 1000))
                    clean_word = str(wd["word"]).strip().upper()
                    clean_check = re.sub(r"[.,!?;:'\"\\]", "", str(wd["word"]).strip().lower())
                    is_kw = clean_check in keyword_set
                    active_color = keyword_color if is_kw else highlight_color
                    active_color = _speaker_highlight(active_color, wd)
                    pop_in_ms = 80
                    settle_ms = 100
                    word_tag = (
                        f"{{\\fscx80\\fscy80\\1c&H00FFFFFF&}}"
                        f"{{\\t({cumulative_ms},{cumulative_ms + pop_in_ms},"
                        f"\\fscx120\\fscy120\\1c{active_color})}}"
                        f"{{\\t({cumulative_ms + pop_in_ms},{cumulative_ms + pop_in_ms + settle_ms},"
                        f"\\fscx100\\fscy100)}}"
                        f"{{\\t({cumulative_ms + dur_ms - 30},{cumulative_ms + dur_ms},"
                        f"\\1c&H00FFFFFF&)}}"
                        f"{clean_word} "
                    )
                    parts.append(word_tag)
                    cumulative_ms += dur_ms
                text = "".join(parts).rstrip()
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)}"
                    f",Default,,0,0,0,,{text}\n"
                )
                group = []
        ass += "".join(ass_lines)

    else:
        # All other styles: uniform karaoke groups with the style's secondary colour as highlight
        ass_lines = []
        group = []
        for i, word_dict in enumerate(words):
            group.append(word_dict)
            next_w = words[i + 1] if i + 1 < len(words) else None
            pause  = (next_w["start"] - word_dict["end"]) if next_w else 1.0
            ends_sentence = bool(PUNCT_END.search(word_dict.get("word") or ""))
            if not next_w or pause > 0.3 or ends_sentence or len(group) >= MAX_WORDS:
                _flush_group(group, ass_lines)
                group = []
        ass += "".join(ass_lines)

    ass_path = os.path.join(work_dir, "captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    return ass_path


def get_output_clip_ranges(cuts, effective_durations):
    """
    Return list of {"start": float, "end": float} for each clip's position
    in the output timeline, accounting for transition overlap.
    """
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = round(cursor * 1000) / 1000
        end   = round((cursor + dur) * 1000) / 1000
        ranges.append({"start": start, "end": end})
        transition = str(cut.get("transition_out") or "none").lower()
        td      = TRANSITION_DURATION if transition not in ("none", "clean_cut", "") else 0.0
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

        # Filter out filler words
        keep_segments = []
        for w in clip_words:
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
        curve_speed = 1.0
        if speed_curve and speed_curve != "none":
            curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(src_start, speed_curve)))
        combined_speed = speed * curve_speed

        if src_start <= source_t <= src_end:
            local_offset = (source_t - src_start) / combined_speed
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


def compute_effective_durations(cuts, speed_curve=None):
    durations = []
    for cut in (cuts or []):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        raw_dur = src_end - src_start
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        curve_speed = 1.0
        if speed_curve and speed_curve != "none":
            curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(src_start, speed_curve)))
        effective_dur = raw_dur / clip_speed / curve_speed
        durations.append(round(effective_dur, 3))
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
        if hook_src_start >= cs - 0.1 and hook_src_end <= ce + 0.1:
            hook_clip_idx = i
            break

    if hook_clip_idx is None:
        print("[hook] Could not find hook clip in cuts array — skipping", flush=True)
        return

    clip_src_start = float(cuts[hook_clip_idx]["source_start"])
    clip_speed = max(0.25, float(cuts[hook_clip_idx].get("speed") or 1.0))
    curve_speed = 1.0
    if speed_curve and speed_curve != "none":
        curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(clip_src_start, speed_curve)))
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

    hook_path = os.path.join(work_dir, "hook_clip.mp4")
    hook_cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-filter_complex",
        f"[0:v]trim=start={hook_render_start:.3f}:end={hook_render_end:.3f},setpts=PTS-STARTPTS[hv];"
        f"[0:a]atrim=start={hook_render_start:.3f}:end={hook_render_end:.3f},asetpts=PTS-STARTPTS[ha]",
        "-map", "[hv]", "-map", "[ha]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
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

    hooked_output = os.path.join(work_dir, "hooked_output.mp4")
    concat_cmd = [
        "ffmpeg", "-y",
        "-i", hook_path,
        "-i", output_path,
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]",
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-c:a", "aac", "-b:a", "192k",
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
    edit_plan["_hook_offset"] = hook_actual_dur
    print(f"[hook] Prepended {hook_actual_dur:.2f}s hook teaser", flush=True)


def burn_in_captions(output_path, edit_plan, transcript, work_dir):
    """Burn captions and text overlays into the output video as a post-process."""
    caption_style = str(edit_plan.get("caption_style") or "none").lower()
    text_overlays = edit_plan.get("text_overlays") or []
    if caption_style == "none" and not text_overlays:
        return

    cuts = edit_plan.get("cuts") or []
    speed_curve = edit_plan.get("_parsed_speed_curve")
    effective_durations = compute_effective_durations(cuts, speed_curve)
    hook_offset = float(edit_plan.get("_hook_offset") or 0.0)
    hook_clip = edit_plan.get("hook_clip")
    projected_words = project_words_to_output(
        transcript,
        cuts,
        effective_durations,
        hook_offset=hook_offset,
        hook_clip=hook_clip,
        speed_curve=speed_curve,
    )
    post_filters = []
    video_out = "[video_base]"
    post_filters.append(f"[0:v]null{video_out}")

    if caption_style != "none" and transcript.get("words"):
        ass_path = generate_subtitle_file(
            transcript, caption_style, cuts, effective_durations,
            {"width": 1080, "height": 1920},
            edit_plan.get("caption_position") or "lower-third",
            edit_plan.get("caption_keywords") or [],
            work_dir,
            hook_offset=hook_offset,
            hook_clip=hook_clip,
            speed_curve=speed_curve,
        )
        if ass_path and os.path.exists(ass_path):
            escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            post_filters.append(f"{video_out}subtitles='{escaped}':fontsdir=/assets/fonts[video_captioned]")
            video_out = "[video_captioned]"
        else:
            print("[captions] No subtitle file generated — skipping ASS burn-in", flush=True)

    if text_overlays:
        clip_ranges = get_output_clip_ranges(cuts, effective_durations)
        if hook_offset > 0:
            for cr in clip_ranges:
                cr["start"] = round((cr["start"] + hook_offset) * 1000) / 1000
                cr["end"] = round((cr["end"] + hook_offset) * 1000) / 1000
        total_output_dur = sum(effective_durations)
        print(f"[render] Total output duration: {total_output_dur:.3f}s, {len(clip_ranges)} clip ranges", flush=True)
        for cr_i, cr in enumerate(clip_ranges):
            print(f"[render]   clip_range[{cr_i}]: {cr['start']:.3f}s - {cr['end']:.3f}s", flush=True)
        for i, overlay in enumerate(text_overlays):
            raw_idx = int(overlay.get("appear_at_clip") or 0)
            clip_idx = max(0, raw_idx - 1) if raw_idx > 0 else 0
            if clip_idx < 0 or clip_idx >= len(clip_ranges):
                print(f"[render] Text overlay '{overlay.get('text')}' — clip_idx={clip_idx} out of range ({len(clip_ranges)} clips), skipping", flush=True)
                continue
            raw_text = str(overlay.get("text") or "")
            text = EMOJI_STRIP.sub("", raw_text).strip()
            if not text:
                continue
            start = clip_ranges[clip_idx]["start"]
            end = clip_ranges[clip_idx]["end"]
            style = str(overlay.get("style") or "callout")
            char_count = len(text)
            base_size = 72 if style == "title" else (64 if style == "cta" else 56)
            if char_count <= 18:
                font_size = base_size
            elif char_count <= 25:
                font_size = round(base_size * 0.85)
            elif char_count <= 35:
                font_size = round(base_size * 0.70)
            else:
                font_size = round(base_size * 0.60)
            pos = str(overlay.get("position") or "center")
            y_expr = "250" if pos == "top" else ("(h-th)/2" if pos == "center" else str(max(0, 1920 - 350)))
            end_t = max(start + 0.8, end)
            print(f"[render] Text overlay '{text}' on clip {clip_idx}: start={start:.3f}s end_t={end_t:.3f}s (clip range {clip_ranges[clip_idx]['start']:.3f}-{clip_ranges[clip_idx]['end']:.3f})", flush=True)
            print(f"[render] drawtext enable: between(t,{start:.3f},{end_t:.3f})", flush=True)
            _font_clause = (
                f":fontfile='{OVERLAY_FONT_PATH}'"
                if os.path.exists(OVERLAY_FONT_PATH)
                else ""
            )
            escaped_text = text.replace("'", "").replace('"', "").replace("\\", "").replace(":", "\\:").replace(",", "\\,")
            out_label = f"[video_overlay_{i}]"
            post_filters.append(
                f"{video_out}drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor=white"
                f"{_font_clause}"
                f":x=(w-tw)/2:y={y_expr}"
                f":borderw=5:bordercolor=black"
                f":enable='between(t,{start:.3f},{end_t:.3f})'{out_label}"
            )
            video_out = out_label

    if len(post_filters) == 1:
        print("[captions] Nothing to burn in — skipping", flush=True)
        return

    temp_output = os.path.join(work_dir, "captioned.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-filter_complex", ";".join(post_filters),
        "-map", video_out, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-c:a", "copy",
        "-movflags", "+faststart",
        temp_output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[captions] Burn-in failed: {result.stderr[-300:]}", flush=True)
        return
    os.replace(temp_output, output_path)
    print("[captions] Burn-in complete", flush=True)


def mix_sfx_after_speed_curve(output_path, edit_plan, cuts, effective_durations, work_dir):
    """
    Mix sound effects into the final video AFTER the speed curve has been applied.
    Uses -c:v copy so the video stream is not re-encoded.
    Timestamps are projected from source time to final output time.
    """
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    parsed_sfx = list(edit_plan.get("_parsed_sound_effects", []))
    hook_offset = float(edit_plan.get("_hook_offset") or 0.0)

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
                "sound": sfx.get("sound", "pop"),
                "path": get_sfx_path(normalize_sfx_style(sfx.get("sound", "pop"))),
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
                print(f"[sfx] Snapped swoosh to clip boundary: {raw_t:.3f}s → {source_t:.3f}s", flush=True)
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
        filter_parts.append(
            f"[{i + 1}:a]volume=0.5,adelay={offset_ms}|{offset_ms}{label}"
        )
        labels.append(label)

    n_inputs = len(labels) + 1
    all_inputs = "[0:a]" + "".join(labels)
    filter_parts.append(
        f"{all_inputs}amix=inputs={n_inputs}:duration=first:dropout_transition=2[mixed]"
    )

    filter_complex = ";".join(filter_parts)

    temp_output = os.path.join(work_dir, "sfx_mixed.mp4")
    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[mixed]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
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


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None):
    speed_curve = edit_plan.get("_parsed_speed_curve")
    render_cuts = list(cuts)
    edit_plan["_hook_offset"] = 0.0

    n = len(render_cuts)
    source_res = probe_resolution(source_path)
    kf_timestamps = [float(c["source_start"]) for c in render_cuts]
    hook_clip = edit_plan.get("hook_clip")
    if isinstance(hook_clip, dict):
        hook_s = float(hook_clip.get("source_start") or 0.0)
        hook_e = float(hook_clip.get("source_end") or 0.0)
        if hook_s > 0:
            kf_timestamps.append(hook_s)
        if hook_e > 0:
            kf_timestamps.append(hook_e)
    kf_timestamps = sorted(set(kf_timestamps))
    keyframed_path = create_keyframed_source(source_path, kf_timestamps, work_dir)
    _kf_cmd = [
        "ffprobe", "-v", "quiet", "-select_streams", "v:0",
        "-show_entries", "frame=pts_time,key_frame",
        "-read_intervals", "33%+#20",
        "-of", "csv=p=0",
        keyframed_path,
    ]
    _kf_result = subprocess.run(_kf_cmd, capture_output=True, text=True, timeout=15)
    print(f"[DIAG] Keyframes near 33s: {_kf_result.stdout[:500]}", flush=True)

    color_grade = edit_plan.get("color_grade") or {}
    color_filter_str = build_video_filter_chain(color_grade, source_res, edit_plan)
    has_burned_captions = infer_has_burned_captions(
        edit_plan,
        edit_plan.get("analysis_data") or {},
        log_prefix="[render]",
    )

    # Single input: the keyframed source
    input_args = ["-analyzeduration", "10000000", "-probesize", "10000000", "-i", keyframed_path]
    sample_rate = probe_audio_sample_rate(source_path) or 48000

    # Compute effective durations from recipe with per-segment speed applied.
    effective_durations = compute_effective_durations(render_cuts, speed_curve)
    for i, cut in enumerate(render_cuts):
        src_dur = round((float(cut["source_end"]) - float(cut["source_start"])) * 1000) / 1000
        clip_speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        curve_speed = 1.0
        if speed_curve and speed_curve != "none":
            curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(float(cut["source_start"]), speed_curve)))
        eff_dur = effective_durations[i]
        print(
            f"[ffmpeg] Segment {i}: {cut['source_start']:.3f}s->{cut['source_end']:.3f}s "
            f"(dur={src_dur:.3f}s, eff={eff_dur:.3f}s @ clip={clip_speed}x curve={curve_speed}x)",
            flush=True,
        )

    video_filters = []
    audio_filters = []
    face_positions = edit_plan.get("_face_positions") or []

    for i, cut in enumerate(render_cuts):
        start = float(cut["source_start"])
        end = float(cut["source_end"])
        speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        curve_speed = 1.0
        if speed_curve and speed_curve != "none":
            curve_speed = max(0.5, min(1.5, get_speed_for_timestamp(start, speed_curve)))
        combined_speed = speed * curve_speed
        zoom = str(cut.get("zoom") or "none")
        if has_burned_captions and zoom in ["punch_in","punch_out"]:
            zoom = "slow_in" if zoom == "punch_in" else "slow_out"

        eff_dur = effective_durations[i]
        print(
            f"[DIAG] Segment {i}: src={start:.3f}-{end:.3f} raw_dur={end-start:.3f} "
            f"speed={speed} curve={curve_speed} combined={combined_speed:.4f} "
            f"eff_dur={eff_dur:.3f} v_setpts={1.0/combined_speed:.4f} "
            f"a_asetrate={sample_rate}*{combined_speed:.4f}",
            flush=True,
        )
        fps = 30
        total_frames = max(1, round(eff_dur * fps))
        zoom_max = 1.07 if has_burned_captions else 1.14

        zoom_filter = None
        if zoom == "slow_in":
            tf = max(1, total_frames)
            zoom_range = zoom_max - 1.0
            closest_face = None
            if face_positions:
                clip_mid = (start + end) / 2.0
                closest_face = min(face_positions, key=lambda p: abs(float(p.get("t") or 0.0) - clip_mid))
            if closest_face and closest_face.get("found"):
                face_cx = float(closest_face.get("cx") or 540.0)
                face_cy = float(closest_face.get("cy") or 960.0)
                offset_x = clamp(face_cx - 540.0, -240.0, 240.0)
                offset_y = clamp(face_cy - 960.0, -320.0, 320.0)
                progress = f"min(n/{tf}\\,1.0)"
                crop_x = (
                    f"max(0\\,min((iw-1080)/2+{offset_x:.1f}*{progress}*{zoom_range:.4f}\\,iw-1080))"
                )
                crop_y = (
                    f"max(0\\,min((ih-1920)/2+{offset_y:.1f}*{progress}*{zoom_range:.4f}\\,ih-1920))"
                )
                zoom_filter = (
                    f"scale=w='trunc(iw*(1.0+{zoom_range:.4f}*{progress})/2)*2'"
                    f":h='trunc(ih*(1.0+{zoom_range:.4f}*{progress})/2)*2'"
                    f":eval=frame:flags=bilinear,"
                    f"crop=1080:1920:x='{crop_x}':y='{crop_y}'"
                )
            else:
                zoom_filter = (
                    f"scale=w='trunc(iw*(1.0+{zoom_range:.4f}*min(n/{tf}\\,1.0))/2)*2'"
                    f":h='trunc(ih*(1.0+{zoom_range:.4f}*min(n/{tf}\\,1.0))/2)*2'"
                    f":eval=frame:flags=bilinear,crop=1080:1920"
                )
        elif zoom == "slow_out":
            tf = max(1, total_frames)
            zoom_range = zoom_max - 1.0
            zoom_filter = (
                f"scale=w='trunc(iw*({zoom_max:.4f}-{zoom_range:.4f}*(n/{tf})*(n/{tf})*(3-2*(n/{tf})))/2)*2'"
                f":h='trunc(ih*({zoom_max:.4f}-{zoom_range:.4f}*(n/{tf})*(n/{tf})*(3-2*(n/{tf})))/2)*2'"
                f":eval=frame:flags=bilinear,crop=1080:1920"
            )
        elif zoom == "punch_in":
            zoom_filter = f"scale=w='trunc(iw*(if(lt(n\\,10)\\,1.0+0.15*n/10\\,1.15))/2)*2':h='trunc(ih*(if(lt(n\\,10)\\,1.0+0.15*n/10\\,1.15))/2)*2':eval=frame:flags=bilinear,crop=1080:1920"
        elif zoom == "punch_out":
            zoom_filter = f"scale=w='trunc(iw*(if(lt(n\\,10)\\,1.15-0.15*n/10\\,1.0))/2)*2':h='trunc(ih*(if(lt(n\\,10)\\,1.15-0.15*n/10\\,1.0))/2)*2':eval=frame:flags=bilinear,crop=1080:1920"

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

        # Video: trim from source, then apply per-clip filters
        v_chain = [f"trim=start={start:.3f}:end={end:.3f}", "setpts=PTS-STARTPTS", "settb=AVTB"]

        if abs(combined_speed - 1.0) > 0.001:
            v_chain.append(f"setpts={1.0/combined_speed:.4f}*PTS")
        
        v_chain.append("fps=30")
        if zoom_filter:
            v_chain.append(zoom_filter)
        v_chain += ["format=yuv420p", color_filter_str]
        if vignette_filter:
            v_chain.append(vignette_filter)

        freeze_frame = bool(cut.get("freeze_frame"))
        if freeze_frame and eff_dur > 0.5:
            freeze_frames = 9
            v_chain.append(f"tpad=stop={freeze_frames}:stop_mode=clone")
            print(f"[render] clip {i}: freeze_frame=true (+{freeze_frames} frames @ end)", flush=True)

        if outro_filter:
            v_chain.append(outro_filter)

        video_filters.append(f"[0:v]{','.join(v_chain)}[v{i}]")

        # Audio: trim from source, then apply per-clip filters
        a_chain = [f"atrim=start={start:.3f}:end={end:.3f}", "asetpts=PTS-STARTPTS"]
        if abs(combined_speed - 1.0) > 0.001:
            a_chain.append(f"asetrate={sample_rate}*{combined_speed:.4f}")
            a_chain.append(f"aresample={sample_rate}")
        if i == n-1 and outro != "none":
            fade_start = max(0, eff_dur - 1.0)
            a_chain.append(f"afade=t=out:st={fade_start:.3f}:d=1.0")
        audio_filters.append(f"[0:a]{','.join(a_chain)}[a{i}]")

    # ── SFX collection ───────────────────────────────────────────────────────
    # SFX are NOT mixed during render — they are added as a post-processing
    # step AFTER the speed curve so timestamps are correct.
    sfx_input_args   = []
    sfx_filter_strs  = []
    sfx_audio_labels = []
    extra_input_index = 1  # single input (keyframed source)

    if False:  # SFX disabled in render — mixed after speed curve in mix_sfx_after_speed_curve()
        _speech_segs = speech_segments or (edit_plan.get("analysis_data") or {}).get("speech", {}).get("segments") or []

        _running = effective_durations[0]
        _transition_times = []
        for _i in range(n - 1):
            _transition = str(cuts[_i].get("transition_out") or "none").lower()
            _td = TRANSITION_DURATION if _transition not in ("none", "clean_cut", "") else 0.0
            _event_time = max(0.0, _running - 0.15)
            _transition_times.append(_event_time)
            _running = _running + effective_durations[_i + 1] - _td

        for _i in range(n - 1):
            _sound_style = normalize_sfx_style(cuts[_i].get("transition_sound") or cuts[_i].get("sfx_style") or "none")
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
            print(f"[sfx] transition {_i}: {_sound_style} vol={_vol:.3f} at {_event_time:.3f}s", flush=True)
            extra_input_index += 1

        _clip_ranges = get_output_clip_ranges(render_cuts, effective_durations)
        for _i, _overlay in enumerate(edit_plan.get("text_overlays") or []):
            _clip_idx = int(_overlay.get("appear_at_clip") or 0) - 1
            if _clip_idx < 0 or _clip_idx >= len(_clip_ranges):
                continue
            _sfx_style = normalize_sfx_style(_overlay.get("sfx_style") or "none")
            if _sfx_style == "none":
                continue
            _sound_path = get_sfx_path(_sfx_style)
            if not _sound_path:
                continue
            _ts        = max(0.0, float(_clip_ranges[_clip_idx].get("start") or 0) + 0.02)
            _offset_ms = round(_ts * 1000)
            _vol       = get_sfx_volume(_sfx_style, _ts, _speech_segs, is_text_overlay=True)
            _label     = f"[txtsnd{_i}]"
            sfx_input_args  += ["-i", _sound_path]
            sfx_filter_strs.append(
                f"[{extra_input_index}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}{_label}"
            )
            sfx_audio_labels.append(_label)
            print(f"[sfx] text_overlay {_i}: {_sfx_style} vol={_vol:.3f} at {_ts:.3f}s", flush=True)
            extra_input_index += 1

        parsed_sfx = edit_plan.get("_parsed_sound_effects", [])
        for _i, _sfx in enumerate(parsed_sfx):
            _sound_style = normalize_sfx_style(_sfx.get("sound") or "none")
            if _sound_style == "none":
                continue
            _sound_path = get_sfx_path(_sound_style)
            if not _sound_path:
                continue
            _source_t = float(_sfx.get("t") or 0.0)
            _output_t = project_source_time_to_output(_source_t, render_cuts, _clip_ranges, edit_plan.get("_parsed_speed_curve"))
            if _output_t is None:
                print(
                    f"[sfx] sound_effect: {_sound_style} at source {_source_t:.3f}s — could not project, skipping",
                    flush=True,
                )
                continue
            _ts = max(0.0, _output_t)
            _offset_ms = round(_ts * 1000)
            _vol = 0.5
            _label = f"[timesfx{_i}]"
            sfx_input_args += ["-i", _sound_path]
            sfx_filter_strs.append(
                f"[{extra_input_index}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}{_label}"
            )
            sfx_audio_labels.append(_label)
            print(
                f"[sfx] sound_effect: {_sound_style} vol={_vol:.3f} at source={_source_t:.3f}s → output={_ts:.3f}s",
                flush=True,
            )
            extra_input_index += 1

    transition_filters = []
    tl_video = "v0"
    tl_audio = "a0"
    running_dur = effective_durations[0]

    CUSTOM_TRANSITIONS = {"flash", "glitch", "whip_left", "whip_right"}
    XFADE_TRANSITIONS = {
        "fade","fadeblack","fadewhite","dissolve",
        "wipeleft","wiperight","wipeup","wipedown",
        "smoothleft","smoothright","smoothup","smoothdown",
        "zoomin",
    }

    for i in range(1, n):
        transition = str(render_cuts[i-1].get("transition_out") or "none").lower()
        out_v     = "vout" if i == n-1 else f"vx{i}"
        out_v_raw = f"{out_v}_raw"
        out_a     = "aout" if i == n-1 else f"ax{i}"

        if transition in CUSTOM_TRANSITIONS:
            td = TRANSITION_DURATION
            offset = max(0, running_dur - td)

            if transition == "flash":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=fadewhite:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "glitch":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=pixelize:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]hue=h=0:s=1.4,fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "whip_left":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=wipeleft:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]boxblur=luma_radius=6:luma_power=1:chroma_radius=0,fps=30[{out_v}]")
                transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")

            elif transition == "whip_right":
                transition_filters.append(f"[{tl_video}][v{i}]xfade=transition=wiperight:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
                transition_filters.append(f"[{out_v_raw}]boxblur=luma_radius=6:luma_power=1:chroma_radius=0,fps=30[{out_v}]")
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
            transition_filters.append(f"[{tl_video}][v{i}]concat=n=2:v=1:a=0[{out_v}]")
            transition_filters.append(f"[{tl_audio}][a{i}]concat=n=2:v=0:a=1[{out_a}]")
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

    fps = 30
    actual_video_dur = sum(round(d * fps) / fps for d in effective_durations)
    audio_out = "[audio_timed]"
    post_filters.append(
        f"[{tl_audio}]atrim=end={actual_video_dur:.3f},asetpts=PTS-STARTPTS{audio_out}"
    )

    if sfx_audio_labels:
        _n_inputs   = len(sfx_audio_labels) + 1
        _sfx_inputs = audio_out + "".join(sfx_audio_labels)
        post_filters.append(
            f"{_sfx_inputs}amix=inputs={_n_inputs}:duration=first:dropout_transition=2[audio_sfx_mixed]"
        )
        audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio", flush=True)

    audio_denoise = bool(edit_plan.get("audio_denoise"))
    denoise_filter = ""
    if audio_denoise:
        denoise_filter = "afftdn=nr=12:nf=-30:tn=1,"
        print(f"[render] audio_denoise=true — afftdn adaptive noise removal enabled", flush=True)
    post_filters.append(
        f"{audio_out}{denoise_filter}highpass=f=80,lowpass=f=12000,"
        f"equalizer=f=2800:t=q:w=1.5:g=3,"
        f"equalizer=f=200:t=q:w=0.8:g=1.5,"
        f"acompressor=threshold=-20dB:ratio=3:attack=5:release=50:makeup=2,"
        f"alimiter=limit=0.95:attack=1:release=10[final_audio]"
    )
    audio_out = "[final_audio]"

    # Background music mix
    music_input_idx = None
    music_filters = []
    music_track = str(edit_plan.get("background_music") or "none").strip()
    if music_track != "none" and music_track in MUSIC_LIBRARY:
        music_path = os.path.join(_MUSIC_DIR, f"{music_track}.mp3")
        if os.path.exists(music_path):
            music_input_idx = 1 + len(sfx_input_args) // 2
            input_args += ["-stream_loop", "-1", "-i", music_path]
            total_duration = sum(effective_durations)
            fade_out_start = max(0, total_duration - 2.0)
            music_vol = 0.05
            music_filters.append(
                f"[{music_input_idx}:a]"
                f"atrim=duration={total_duration:.3f},"
                f"afade=t=in:st=0:d=1.5,"
                f"afade=t=out:st={fade_out_start:.3f}:d=2.0,"
                f"volume={music_vol}"
                f"[music_track]"
            )
            music_filters.append(
                f"[final_audio][music_track]amix=inputs=2:duration=first:dropout_transition=2[mixed_audio]"
            )
            audio_out = "[mixed_audio]"
            print(f"[render] background_music={music_track} vol={music_vol} duration={total_duration:.1f}s", flush=True)
        else:
            print(f"[render] WARNING: music track not found at {music_path} — skipping", flush=True)

    filter_complex = ";".join(video_filters + audio_filters + transition_filters + sfx_filter_strs + post_filters + music_filters)
    print(f"[DIAG] filter_complex length: {len(filter_complex)} chars, segments: {n}", flush=True)
    print(f"[DIAG] video_filters: {len(video_filters)}, audio_filters: {len(audio_filters)}, transition_filters: {len(transition_filters)}", flush=True)
    for idx, vf in enumerate(video_filters[:3]):
        print(f"[DIAG] video_filter[{idx}]: {vf[:300]}", flush=True)
    for idx, af in enumerate(audio_filters[:3]):
        print(f"[DIAG] audio_filter[{idx}]: {af[:300]}", flush=True)

    encode_args = [
        "-c:v","libx264","-preset","ultrafast","-crf","0",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k",
        "-movflags","+faststart",
        "-max_muxing_queue_size","1024",
    ]

    args = (
        ["-y","-threads","1"]
        + input_args
        + sfx_input_args
        + ["-filter_complex", filter_complex, "-map", video_out, "-map", audio_out]
        + encode_args
        + [output_path]
    )

    print(f"[render] Single-pass render: {n} segments from keyframed source, ~{running_dur:.1f}s output", flush=True)

    try:
        run_ffmpeg(args)
    finally:
        if os.path.exists(keyframed_path):
            try:
                os.unlink(keyframed_path)
            except Exception:
                pass



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
    POST progress update to the JS server. Non-fatal — never raises.
    step: short machine key e.g. 'download', 'analysis', 'render'
    pct:  integer 0-100
    message: human-readable string shown to the user
    """
    if not app_url:
        return
    try:
        requests.post(
            f"{app_url}/api/modal-progress",
            json={"job_id": job_id, "step": step, "pct": pct, "message": message},
            timeout=3,
        )
    except Exception:
        pass  # progress updates are best-effort only


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

        # Step 1 — Download
        send_progress(job_id, "download", 5, "Got your video, loading it in...", app_url)
        t = time.time()
        print("[pipeline] step=download", flush=True)
        r = requests.get(video_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(source_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        size_mb = os.path.getsize(source_path) / (1024*1024)
        print(f"[pipeline] download complete: {size_mb:.1f}MB in {time.time()-t:.1f}s", flush=True)

        # Step 2 — Normalize
        send_progress(job_id, "normalize", 12, "Getting everything set up...", app_url)
        print("[pipeline] step=normalize", flush=True)
        source_path = normalize_source_video(source_path, work_dir)

        source_duration = get_source_duration(source_path)
        transcript = {"text": "", "words": []}

        print("[pipeline] step=face_detect", flush=True)
        source_res = probe_resolution(source_path)
        sample_timestamps = [round(i * 2.0, 3) for i in range(int(source_duration / 2.0) + 1)] if source_duration > 0 else []
        face_positions = detect_face_positions(source_path, sample_timestamps) if sample_timestamps else []
        reframe_crops = calculate_reframe_crop(face_positions, source_res.get("width") or 1080, source_res.get("height") or 1920)
        if reframe_crops:
            print(f"[reframe] Smart reframe active: {len(reframe_crops)} crop positions", flush=True)
        else:
            print("[reframe] Source is native 9:16 — using center crop", flush=True)

        print(f"[edit] User vibe: \"{vibe}\"", flush=True)

        # Run Deepgram for word timestamps (needed for cut snapping and SFX)
        print("[pipeline] step=transcribe", flush=True)
        audio_path = os.path.join(work_dir, "audio_for_words.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", source_path, "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1", audio_path],
            capture_output=True, text=True, timeout=30,
        )
        transcript = transcribe_audio(audio_path)
        _dg_words = transcript.get("words", [])
        if len(_dg_words) == 0:
            print("[pipeline] Deepgram returned 0 words — retrying once...", flush=True)
            try:
                transcript = transcribe_audio(audio_path)
                _dg_words = transcript.get("words", [])
            except Exception as e2:
                print(f"[pipeline] Deepgram retry also failed: {e2}", flush=True)
        if len(_dg_words) == 0:
            raise RuntimeError("Deepgram transcription failed — 0 words returned. Cannot proceed without word timestamps.")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        print(f"[pipeline] Deepgram: {len(transcript.get('words', []))} words", flush=True)

        send_progress(job_id, "analysis", 20, "Watching your footage...", app_url)
        send_progress(job_id, "edit_recipe", 52, "Putting your edit together...", app_url)
        print("[pipeline] step=edit_recipe", flush=True)
        t = time.time()
        trend_context = get_trend_context()
        if not trend_context:
            print("[trend] WARNING: Style guide not available — Gemini will edit without reference video patterns", flush=True)
        edit_plan = generate_edit_gemini(
            video_path=source_path,
            vibe=vibe,
            duration=source_duration,
            trend_context=trend_context,
            deepgram_words=transcript.get("words", []),
            face_positions=face_positions,
        )
        edit_plan["_face_positions"] = face_positions
        print(f"[pipeline] edit recipe complete in {time.time()-t:.1f}s", flush=True)
        analysis = edit_plan.get("analysis_data") or {}

        print("[pipeline] step=post_process", flush=True)
        caption_style = str(edit_plan.get("caption_style") or "none").lower()
        broll_requests = edit_plan.get("broll") or []

        print("[pipeline] step=parallel_render", flush=True)
        send_progress(job_id, "render", 62, "Rendering — almost there...", app_url)
        t = time.time()
        broll_files = {}

        def task_render():
            render_multi_clip(
                source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
            )

        def task_download_broll():
            """B-roll disabled."""
            return {}

        def task_deepgram():
            # Deepgram already ran before post-processing
            return transcript

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            future_render = pool.submit(task_render)
            future_broll = pool.submit(task_download_broll)
            future_deepgram = pool.submit(task_deepgram)
            future_render.result()
            broll_files = future_broll.result()
            transcript = future_deepgram.result()
            # Store Deepgram words for SFX word-snapping
            edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        print("[render] Encoding: crf=0 preset=ultrafast", flush=True)
        speed_curve = edit_plan.get("_parsed_speed_curve")
        _diag_cmd = [
            "ffprobe", "-v", "quiet", "-show_streams", "-show_format",
            "-print_format", "json", output_path
        ]
        _diag = subprocess.run(_diag_cmd, capture_output=True, text=True, timeout=10)
        print(f"[DIAG] Rendered output probe:\n{_diag.stdout[:2000]}", flush=True)

        if not validate_output(output_path, "render"):
            raise RuntimeError("Main render produced invalid output")

        print("[pipeline] step=hook", flush=True)
        prepend_hook_clip(output_path, edit_plan, work_dir)

        print("[pipeline] step=trim", flush=True)
        expected_duration = sum(compute_effective_durations(edit_plan["cuts"], speed_curve))
        expected_duration += float(edit_plan.get("_hook_offset") or 0.0)
        actual_duration = probe_duration(output_path) or 0.0
        if actual_duration > expected_duration + 2.0:
            print(f"[pipeline] Trimming dead air: {actual_duration:.1f}s → {expected_duration:.1f}s", flush=True)
            trimmed_path = os.path.join(work_dir, "trimmed_output.mp4")
            trim_backup_path = os.path.join(work_dir, "output_trim.backup.mp4")
            shutil.copy2(output_path, trim_backup_path)
            trim_result = subprocess.run(
                ["ffmpeg", "-y", "-i", output_path, "-t", f"{expected_duration:.2f}", "-c", "copy", trimmed_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if trim_result.returncode == 0 and os.path.exists(trimmed_path):
                os.replace(trimmed_path, output_path)
                if not validate_output(output_path, "trim"):
                    print("[trim] Trim produced invalid output — restoring backup", flush=True)
                    os.replace(trim_backup_path, output_path)
                elif os.path.exists(trim_backup_path):
                    os.remove(trim_backup_path)
            else:
                print(f"[pipeline] WARNING: trim failed, keeping original output: {trim_result.stderr[-400:]}", flush=True)
                if os.path.exists(trim_backup_path):
                    os.remove(trim_backup_path)

        # B-roll removed — Pexels free API cannot consistently produce good clips
        print("[pipeline] B-roll disabled", flush=True)
        for local_path in broll_files.values():
            try:
                os.unlink(local_path)
            except Exception:
                pass

        # AI enhancement removed — minimal visible improvement on clean phone footage

        _text_overlays = edit_plan.get("text_overlays") or []
        if (caption_style != "none" and transcript.get("words")) or _text_overlays:
            print(f"[pipeline] step=captions (style={caption_style}, overlays={len(_text_overlays)})", flush=True)
            captions_backup_path = os.path.join(work_dir, "output_captions.backup.mp4")
            shutil.copy2(output_path, captions_backup_path)
            burn_in_captions(output_path, edit_plan, transcript, work_dir)
            if not validate_output(output_path, "captions"):
                print("[captions] Caption burn-in produced invalid output — restoring backup", flush=True)
                os.replace(captions_backup_path, output_path)
            elif os.path.exists(captions_backup_path):
                os.remove(captions_backup_path)
        else:
            print("[pipeline] Captions skipped (no captions, no text overlays)", flush=True)

        if speed_curve:
            print("[pipeline] Speed curve applied in single-pass render — skipping post-process", flush=True)
        else:
            print("[pipeline] Speed curve skipped", flush=True)

        cuts = edit_plan.get("cuts") or []
        effective_durations = compute_effective_durations(cuts, speed_curve)
        print("[pipeline] step=sfx_mix", flush=True)
        mix_sfx_after_speed_curve(output_path, edit_plan, cuts, effective_durations, work_dir)

        output_size = os.path.getsize(output_path)
        output_dur = probe_duration(output_path) or 0
        if output_size > 100 * 1024 * 1024:
            print(
                f"[pipeline] step=final_encode (output is {output_size / 1024 / 1024:.0f}MB — needs compression)",
                flush=True,
            )
            final_path = os.path.join(work_dir, "final.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", output_path,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                final_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode == 0 and os.path.exists(final_path):
                final_size = os.path.getsize(final_path)
                final_dur = probe_duration(final_path) or 0
                if final_size > 100000 and final_dur > 1.0:
                    os.replace(final_path, output_path)
                    print(
                        f"[final_encode] {output_size / 1024 / 1024:.0f}MB → "
                        f"{final_size / 1024 / 1024:.1f}MB, {final_dur:.1f}s",
                        flush=True,
                    )
                else:
                    print(
                        f"[final_encode] Output invalid ({final_size} bytes, {final_dur}s) — keeping previous",
                        flush=True,
                    )
                    if os.path.exists(final_path):
                        os.remove(final_path)
            else:
                print("[final_encode] FFmpeg failed — keeping previous output", flush=True)
        else:
            print(f"[pipeline] Output already compressed: {output_size / 1024 / 1024:.1f}MB", flush=True)

        # ── Parallel group 2: cover frame + upload ────────────────────────────────
        source_duration = float(analysis.get("duration") or 0) or (probe_duration(source_path) or 0.0)
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
            cover_frame_ts = 1.0
        cover_frame_b64  = None
        cover_frame_mime = "image/jpeg"

        if not validate_output(output_path, "final"):
            raise RuntimeError(f"Final output is invalid: {output_path}")
        _v_dur_cmd = ["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", output_path]
        _a_dur_cmd = ["ffprobe", "-v", "quiet", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", output_path]
        _v_dur = subprocess.run(_v_dur_cmd, capture_output=True, text=True, timeout=10).stdout.strip()
        _a_dur = subprocess.run(_a_dur_cmd, capture_output=True, text=True, timeout=10).stdout.strip()
        print(f"[DIAG] Final output — video duration: {_v_dur}s, audio duration: {_a_dur}s, diff: {float(_v_dur or 0) - float(_a_dur or 0):.4f}s", flush=True)
        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        final_dur = probe_duration(output_path) or 0
        send_progress(job_id, "upload", 90, "Just about done...", app_url)
        print(f"[pipeline] output: {output_size_mb:.1f}MB, {final_dur:.1f}s — parallel upload + cover frame", flush=True)

        def _upload_main():
            print("[pipeline] step=upload", flush=True)
            with open(output_path, "rb") as f:
                resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                resp.raise_for_status()
            print("[pipeline] upload complete", flush=True)

        def _extract_cover():
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

        # Step 13.5 — Additional format exports (only if export_formats provided in job input)
        export_formats   = input_data.get("export_formats") or []
        exported_formats = []
        for fmt in export_formats:
            ar  = str(fmt.get("aspect_ratio") or "").strip()
            url = str(fmt.get("upload_url") or "").strip()
            if not ar or not url:
                continue
            try:
                fmt_path = os.path.join(work_dir, f"output_{ar.replace(':','x')}.mp4")
                export_additional_format(output_path, ar, fmt_path)
                with open(fmt_path, "rb") as f:
                    fmt_resp = requests.put(url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                    fmt_resp.raise_for_status()
                fmt_size = os.path.getsize(fmt_path) / (1024 * 1024)
                print(f"[pipeline] exported {ar} ({fmt_size:.1f}MB) -> uploaded", flush=True)
                exported_formats.append({"aspect_ratio": ar, "size_mb": round(fmt_size, 1)})
            except Exception as fmt_err:
                print(f"[pipeline] export {ar} failed (non-fatal): {fmt_err}", flush=True)

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id} COMPLETE", flush=True)
        print(f"{'='*80}\n", flush=True)

        send_progress(job_id, "complete", 100, "Your video is ready!", app_url)

        result_payload = {
            "status": "success",
            "job_id": job_id,
            "render_time": round(render_elapsed, 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": {k: v for k, v in edit_plan.items() if k != "analysis_data"},
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
