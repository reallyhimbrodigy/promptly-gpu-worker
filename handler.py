import runpod
import subprocess
import os
import sys
import requests
import tempfile
import time
import shutil
import json
import re
import math
import concurrent.futures

print(f"[startup] Python {sys.version}", flush=True)

try:
    import runpod
    print("[startup] runpod OK", flush=True)
except Exception as e:
    print(f"[startup] runpod FAILED: {e}", flush=True)

try:
    import anthropic
    print("[startup] anthropic OK", flush=True)
except Exception as e:
    print(f"[startup] anthropic FAILED: {e}", flush=True)

try:
    import google.generativeai as genai
    print("[startup] google.generativeai OK", flush=True)
except Exception as e:
    print(f"[startup] google.generativeai FAILED: {e}", flush=True)

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

print("[startup] all import checks done", flush=True)

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
# Claude picks by filename. Values are for prompt context only — not used in code.
MUSIC_LIBRARY = {
    "none": {"mood": "none", "energy": "none", "description": "No background music."},

    # Hype / High energy
    "hype_trap_01":       {"mood": "hype",      "energy": "high",   "description": "Hard-hitting trap beat, 140bpm, heavy 808s. Nike ad, gym motivation, flex content."},
    "hype_electronic_01": {"mood": "hype",      "energy": "high",   "description": "Festival electronic drop, 128bpm, euphoric synths. Party, celebration, big reveal."},
    "upbeat_pop_01":      {"mood": "upbeat",    "energy": "high",   "description": "Bright pop energy, 120bpm, driving beat. Vlog highlight, travel, fun day out."},
    "upbeat_hip_hop_01":  {"mood": "upbeat",    "energy": "high",   "description": "Chill hip-hop groove, 95bpm, confident. Street style, fashion, lifestyle flex."},

    # Cinematic / Emotional
    "cinematic_epic_01":  {"mood": "cinematic", "energy": "high",   "description": "Orchestral swell, 90bpm, building tension. Dramatic reveal, sports highlight, transformation."},
    "cinematic_tense_01": {"mood": "cinematic", "energy": "medium", "description": "Dark atmospheric strings, 80bpm, suspense. Before/after, serious story, weight."},
    "emotional_piano_01": {"mood": "emotional", "energy": "low",    "description": "Intimate solo piano, 70bpm, melancholy. Personal story, reflection, vulnerability."},
    "emotional_indie_01": {"mood": "emotional", "energy": "medium", "description": "Indie folk guitar, 85bpm, warm. Life update, sentimental, nostalgia."},

    # Calm / Lo-fi
    "calm_ambient_01":    {"mood": "calm",      "energy": "low",    "description": "Soft ambient pads, no strong beat. Meditation, mindfulness, slow aesthetic content."},
    "lo_fi_chill_01":     {"mood": "calm",      "energy": "low",    "description": "Lo-fi hip-hop, 75bpm, warm vinyl texture. Study, casual vlog, relaxed lifestyle."},
    "lo_fi_beats_01":     {"mood": "calm",      "energy": "medium", "description": "Lo-fi trap, 85bpm, laid back. Day-in-the-life, morning routine, quiet hustle."},

    # Corporate / Clean
    "corporate_inspire_01": {"mood": "upbeat",  "energy": "medium", "description": "Clean corporate pop, 110bpm, optimistic. Product demo, explainer, professional content."},
    "corporate_tech_01":    {"mood": "clean",   "energy": "medium", "description": "Minimal electronic, 100bpm, forward-moving. App demo, tech review, startup content."},

    # Dark / Moody
    "dark_moody_01":      {"mood": "moody",     "energy": "medium", "description": "Dark atmospheric hip-hop, 90bpm, brooding. Edgy aesthetic, night content, fashion."},
    "dark_cinematic_01":  {"mood": "moody",     "energy": "high",   "description": "Dark orchestral, 85bpm, heavy. Intense story, villain arc, dramatic transformation."},

    # Fun / Playful
    "fun_quirky_01":      {"mood": "fun",       "energy": "high",   "description": "Quirky ukulele pop, 115bpm, lighthearted. Comedy, pets, kids, lighthearted content."},
    "fun_retro_01":       {"mood": "fun",       "energy": "medium", "description": "Retro synth-pop, 105bpm, nostalgic. Throwback content, 80s/90s aesthetic."},

    # Romantic / Warm
    "romantic_soft_01":   {"mood": "romantic",  "energy": "low",    "description": "Soft acoustic guitar, 65bpm, tender. Couple content, anniversary, heartfelt."},
    "warm_acoustic_01":   {"mood": "warm",      "energy": "medium", "description": "Warm acoustic strumming, 90bpm, feel-good. Family content, wholesome moments."},

    # Epic / Dramatic
    "epic_trailer_01":    {"mood": "epic",      "energy": "high",   "description": "Trailer-style orchestral + electronic, 120bpm. Big announcement, challenge, transformation."},
    "epic_sports_01":     {"mood": "epic",      "energy": "high",   "description": "Stadium energy, 130bpm, crowd hype. Sports highlights, competition, achievement."},
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


def build_color_grade(baseline, intent_name):
    safe_baseline = {
        "brightness":        baseline.get("brightness", 0) if isinstance(baseline.get("brightness"), (int, float)) else 0,
        "contrast":          baseline.get("contrast", 1) if isinstance(baseline.get("contrast"), (int, float)) else 1,
        "saturation":        baseline.get("saturation", 1) if isinstance(baseline.get("saturation"), (int, float)) else 1,
        "gamma":             baseline.get("gamma", 1) if isinstance(baseline.get("gamma"), (int, float)) else 1,
        "color_temperature": baseline.get("color_temperature", "neutral") if baseline.get("color_temperature") in ["warm", "cool", "neutral"] else "neutral",
    }
    intent = normalize_intent(intent_name)
    delta = COLOR_INTENTS[intent]
    return {
        "brightness":        clamp(safe_baseline["brightness"] + delta["brightness"], -0.3, 0.3),
        "contrast":          clamp(safe_baseline["contrast"] + delta["contrast"], 0.5, 2.0),
        "saturation":        clamp(safe_baseline["saturation"] + delta["saturation"], 0.5, 2.0),
        "gamma":             clamp(safe_baseline["gamma"] + delta["gamma"], 0.5, 2.0),
        "color_temperature": delta["color_temperature"] or safe_baseline["color_temperature"] or "neutral",
    }



# ─── GEMINI ANALYSIS ──────────────────────────────────────────────────────────

GEMINI_ANALYSIS_PROMPT = """You are analyzing video footage for a professional editor. Your job is to describe what you SEE — the visuals, the shots, the lighting, the energy. Do NOT transcribe or timestamp the speech; that will be handled separately by a dedicated audio tool.

For the audio.speech_source field, assess the relationship between any spoken words in the audio and the person on camera:
  on_camera    — a real person is visibly speaking to camera or to someone else; mouth movement matches the audio naturally; room tone and mic quality are consistent with the shooting environment
  lip_sync     — a person on camera is mouthing along to audio that is clearly pre-recorded or a platform sound; audio quality is polished/studio relative to the visuals; mouth movement is performed rather than natural
  voiceover    — narration or commentary plays over footage but no person on camera appears to be the source; could be the same creator recorded separately
  platform_sound — a trending audio clip, sound effect, or viral audio is playing over the footage; the spoken content has no relationship to what is happening visually
  none         — no speech present in the audio

Watch the ENTIRE video from first frame to last frame.
Describe each visually distinct segment of the video. Focus on what you see — the lighting, the framing, the action, the energy.
Frame layout analysis: Look at where the main subject is positioned in the frame. Report whether the video already has any burned-in text, captions, subtitles, logos, or lower-third graphics. Note where these existing overlays appear. Identify any open/free areas of the frame where new text could be placed without covering the subject or conflicting with existing graphics.

CRITICAL TIMESTAMP RULES:
- All timestamps must be in SECONDS (e.g. 15.000 for the 15-second mark, NOT 0.25).
- The last shot must end at or very near the total duration.
- Millisecond precision: three decimal places (1.234).

Return ONLY valid JSON:

{
  "duration": <total seconds, e.g. 38.780>,
  "shots": [
    {
      "start": <float seconds>,
      "end": <float seconds>,
      "visual": "<Lighting, color temp, exposure, dominant tones>",
      "action": "<What the subject is doing>",
      "energy": <0.0 to 1.0>,
      "editing_value": "<essential | strong | usable | filler | dead>",
      "delivery": "<excited | emphatic | conversational | calm | deadpan | intense | whisper — speaker's energy/style in this shot, or 'none' if no speaker>"
    }
  ],
  "audio": {
    "music": "<genre/tempo/energy if present, or 'none'>",
    "speech_source": "<on_camera | lip_sync | voiceover | platform_sound | none>"
  },
  "footage_assessment": {
    "content_type": "<what kind of video>",
    "visual_character": "<color palette, lighting, exposure, white balance>",
    "strongest_moments": "<timestamps and what makes them compelling>",
    "weakest_moments": "<timestamps and why they are weak, or 'none'>",
    "editing_brief": "<how to edit this: what to keep, what to cut, pacing, feel>",
    "recommended_duration": <target seconds for the final edit as an integer — how long should the finished video be>,
    "pacing": "<fast | medium | slow — how quickly should cuts come: fast=1-3s clips, medium=3-6s clips, slow=5-10s clips>",
    "hook": {
      "timestamp": <float seconds — the single best moment to START the edit. Could be 0.0 or could be mid-video if the opening is slow>,
      "description": "<what is happening at this timestamp>",
      "why": "<why a viewer would stop scrolling at this moment>",
      "quality": <0.0 to 1.0 — how compelling is this as a hook>
    }
  },
  "frame_layout": {
    "subject_position": "<where the main subject/person is in the frame>",
    "existing_overlays": {
      "has_burned_captions": <true|false>,
      "has_text_graphics": <true|false>,
      "overlay_locations": "<where existing text/graphics appear>"
    },
    "free_zones": "<areas of the frame with no subject or existing text>"
  },
  "color_baseline": {
    "assessment": "<what you see: overexposed, flat, warm-cast, etc.>",
    "brightness": <-1.0 to 1.0, 0 if good>,
    "contrast": <0.0 to 3.0, 1.0 if good>,
    "saturation": <0.0 to 3.0, 1.0 if good>,
    "gamma": <0.1 to 3.0, 1.0 if good>,
    "color_temperature": "<neutral | warm | cool>"
  },
  "footage_quality": {
    "noise_level": "<none | low | medium | high> — visible pixel noise/grain in flat areas like walls, skin, sky. 'high' means clearly visible noise at normal viewing distance. 'medium' means visible on close inspection. 'low' means clean. Use 'high' for dark/indoor/poorly lit phone footage.",
    "source_sharpness": "<soft | normal | sharp> — how crisp the image edges and fine details are. 'soft' means the footage looks slightly blurry or out-of-focus. 'normal' means standard phone camera sharpness. 'sharp' means highly detailed, crisp edges.",
    "highlight_condition": "<clipped | bright | normal | dark> — state of the brightest parts of the image. 'clipped' means areas are blown out to pure white with no detail. 'bright' means highlights are near-clipping but detail is preserved. 'normal' means balanced. 'dark' means underexposed.",
    "shadow_condition": "<crushed | deep | normal | lifted> — state of the darkest parts of the image. 'crushed' means shadows go to pure black with no visible detail. 'deep' means shadows are rich and dark but still have detail. 'normal' means balanced. 'lifted' means shadows are already elevated/faded.",
    "color_richness": "<flat | muted | normal | vivid> — overall color saturation and punch of the footage. 'flat' means very little color. 'muted' means colors present but subdued. 'normal' means typical phone camera colors. 'vivid' means already highly saturated.",
    "skin_tones_present": <true|false>,
    "lighting_type": "<natural_outdoor | natural_indoor | studio | mixed | unknown> — dominant light source type"
  }
}

For footage_assessment.hook: Watch the entire video and identify the single most compelling moment that would make a viewer stop scrolling. This is NOT always the opening frame — often the best hook is a reaction, a surprising moment, or the point where the speaker says something interesting. Report its timestamp in seconds.

For footage_assessment.recommended_duration: Based on the content density and engagement potential, estimate how long the final edited video should be. Talking-head educational content: 30-60s. Entertainment/reaction: 15-45s. Music/B-roll montage: 15-30s.

For footage_assessment.pacing: Assess how quickly the edit should move. fast = cuts every 1-3 seconds, high energy content. medium = cuts every 3-6 seconds, conversational. slow = cuts every 5-10 seconds, calm or contemplative.

For shots[].delivery: Describe the speaker's energy and style in each shot. Use one of: excited, emphatic, conversational, calm, deadpan, intense, whisper. Use 'none' if there is no speaker in the shot.

For shots[].editing_value: Be strict. 'dead' means no viewer would want to watch this shot — it adds nothing and should be excluded from the edit. 'filler' means the shot is weak and should only be included if needed for continuity. 'usable' means acceptable. 'strong' means a good shot. 'essential' means this shot must be in the edit.

Focus on visual accuracy — every shift in framing or content."""


def run_gemini_analysis(source_path):
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=gemini_api_key)
    print("[analyze] Uploading to Gemini...", flush=True)
    gemini_file = genai.upload_file(source_path)
    deadline = time.time() + 120
    while gemini_file.state.name != "ACTIVE":
        if time.time() > deadline:
            raise RuntimeError("Gemini file upload timed out after 120s")
        time.sleep(2)
        gemini_file = genai.get_file(gemini_file.name)

    print(f"[analyze] File active: {gemini_file.uri}", flush=True)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content([gemini_file, GEMINI_ANALYSIS_PROMPT])

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n?```\s*$", "", raw)
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[analyze] Direct JSON parse failed, attempting repair...", flush=True)
        try:
            parsed = repair_and_parse_json(raw)
            print(f"[analyze] JSON repair succeeded", flush=True)
        except Exception:
            raise RuntimeError(f"Failed to parse Gemini JSON: {raw[:500]}")
    return normalize_analysis(parsed)


def repair_and_parse_json(s):
    # Remove trailing commas before } or ]
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    braces = brackets = 0
    in_string = escaped = False
    for ch in s:
        if escaped:        escaped = False; continue
        if ch == '\\':     escaped = True;  continue
        if ch == '"':      in_string = not in_string; continue
        if in_string:      continue
        if ch == '{':      braces += 1
        elif ch == '}':    braces -= 1
        elif ch == '[':    brackets += 1
        elif ch == ']':    brackets -= 1
    if in_string:
        s += '"'
    if braces > 0 or brackets > 0:
        last_good = max(s.rfind('}'), s.rfind(']'), s.rfind(','))
        if last_good > len(s) * 0.5:
            s = s[:last_good + 1]
            s = re.sub(r",\s*$", "", s)
        while brackets > 0: s += ']'; brackets -= 1
        while braces > 0:   s += '}'; braces -= 1
    return json.loads(s)


def _apply_timestamp_multiplier(parsed, multiplier, label, skip_duration=False):
    import copy
    fixed = copy.deepcopy(parsed)
    original_duration = parsed.get("duration")
    if not skip_duration and isinstance(fixed.get("duration"), (int, float)):
        fixed["duration"] *= multiplier
    for shot in (fixed.get("shots") or []):
        if isinstance(shot.get("start"), (int, float)): shot["start"] *= multiplier
        if isinstance(shot.get("end"),   (int, float)): shot["end"]   *= multiplier
    speech = fixed.get("speech") or {}
    for seg in (speech.get("segments") or []):
        if isinstance(seg.get("start"), (int, float)): seg["start"] *= multiplier
        if isinstance(seg.get("end"),   (int, float)): seg["end"]   *= multiplier
    for sb in (speech.get("sentence_boundaries") or []):
        if isinstance(sb.get("time"),     (int, float)): sb["time"]     *= multiplier
        if isinstance(sb.get("end_time"), (int, float)): sb["end_time"] *= multiplier
        if isinstance(sb.get("pause_after"),    (int, float)) and sb["pause_after"] < 0.5:
            sb["pause_after"] *= multiplier
        if isinstance(sb.get("pause_duration"), (int, float)) and sb["pause_duration"] < 0.5:
            sb["pause_duration"] *= multiplier
    for cp in (fixed.get("cut_points") or []) + (fixed.get("safe_cut_points") or []):
        if isinstance(cp.get("time"), (int, float)): cp["time"] *= multiplier
    for h in (fixed.get("highlights") or []) + (fixed.get("peak_moments") or []):
        if isinstance(h.get("time"), (int, float)): h["time"] *= multiplier
    result_duration = original_duration if skip_duration else fixed.get("duration")
    print(f"[analyze] {label}: duration={result_duration}", flush=True)
    return fixed


def normalize_timestamps(parsed):
    duration = float(parsed.get("duration") or 0)
    all_ts = []
    non_dur_ts = []
    if duration > 0: all_ts.append(duration)
    for shot in (parsed.get("shots") or []):
        for k in ("start", "end"):
            if isinstance(shot.get(k), (int, float)):
                all_ts.append(shot[k]); non_dur_ts.append(shot[k])
    for cp in (parsed.get("cut_points") or []) + (parsed.get("safe_cut_points") or []):
        if isinstance(cp.get("time"), (int, float)):
            all_ts.append(cp["time"]); non_dur_ts.append(cp["time"])
    if not all_ts: return parsed
    max_ts = max(all_ts)
    max_non_dur = max(non_dur_ts) if non_dur_ts else 0
    if max_ts < 2.0 and len(all_ts) > 2:
        print(f"[analyze] TIMESTAMP UNIT FIX: max={max_ts:.3f} — converting minutes→seconds (×60)", flush=True)
        return _apply_timestamp_multiplier(parsed, 60, "minutes→seconds")
    if duration > 5 and len(non_dur_ts) > 2 and max_non_dur < 1.5 and max_non_dur < duration * 0.05:
        print(f"[analyze] TIMESTAMP SCALE FIX: duration={duration}s but max event={max_non_dur:.3f} — scaling by duration", flush=True)
        return _apply_timestamp_multiplier(parsed, duration, "normalized→seconds", skip_duration=True)
    # overshoot check across all fields
    max_all = 0.0
    speech = parsed.get("speech") or {}
    for seg in (speech.get("segments") or []):
        max_all = max(max_all, float(seg.get("start") or 0), float(seg.get("end") or 0))
    for sb in (speech.get("sentence_boundaries") or []):
        max_all = max(max_all, float(sb.get("time") or 0))
    for shot in (parsed.get("shots") or []):
        max_all = max(max_all, float(shot.get("start") or 0), float(shot.get("end") or 0))
    for cp in (parsed.get("cut_points") or []) + (parsed.get("safe_cut_points") or []):
        max_all = max(max_all, float(cp.get("time") or 0))
    for h in (parsed.get("highlights") or []) + (parsed.get("peak_moments") or []):
        max_all = max(max_all, float(h.get("time") or 0))
    if duration > 0 and max_all > duration * 1.1:
        factor = duration / max_all
        print(f"[analyze] TIMESTAMP OVERSHOOT FIX: duration={duration}s max={max_all:.3f}s — scaling ×{factor:.4f}", flush=True)
        return _apply_timestamp_multiplier(parsed, factor, "overshoot→scaled", skip_duration=True)
    return parsed


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

    # Normalize timestamps (minutes/seconds/overshoot fixes — mirrors JS parseAnalysisResponse)
    parsed = normalize_timestamps(parsed)

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
        "brightness":        float(raw_cb["brightness"]) if isinstance(raw_cb.get("brightness"), (int, float)) else 0,
        "contrast":          float(raw_cb["contrast"]) if isinstance(raw_cb.get("contrast"), (int, float)) else 1,
        "saturation":        float(raw_cb["saturation"]) if isinstance(raw_cb.get("saturation"), (int, float)) else 1,
        "gamma":             float(raw_cb["gamma"]) if isinstance(raw_cb.get("gamma"), (int, float)) else 1,
        "color_temperature": raw_cb.get("color_temperature") if raw_cb.get("color_temperature") in ["warm", "cool", "neutral"] else "neutral",
    }
    print(f"[analyze] Color baseline: b={color_baseline['brightness']}, c={color_baseline['contrast']}, s={color_baseline['saturation']}, g={color_baseline['gamma']}, temp={color_baseline['color_temperature']}", flush=True)

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
    print(f"[analyze] Footage quality: noise={footage_quality['noise_level']} sharpness={footage_quality['source_sharpness']} highlights={footage_quality['highlight_condition']} shadows={footage_quality['shadow_condition']} richness={footage_quality['color_richness']} lighting={footage_quality['lighting_type']}", flush=True)

    safe_cut_points = parsed.get("cut_points") or parsed.get("safe_cut_points") or []
    peak_moments = parsed.get("highlights") or parsed.get("peak_moments") or []
    vp = parsed.get("video_profile") or parsed.get("footage_assessment") or {}

    print(f"[analyze] Analysis complete: {duration}s, {len(shots)} shots, {len(safe_cut_points)} cut points, {len((parsed.get('speech') or {}).get('segments') or [])} speech segments", flush=True)

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


# ─── CONTENT MODE DETECTION ──────────────────────────────────────────────────

def detect_content_mode(deepgram_words, analysis):
    """
    Determine which editing path to use.

    Returns one of three modes:
      "speech"            — genuine on-camera speech drives cuts
      "speech_with_music" — genuine on-camera speech + background music; speech drives cuts,
                            beats inform transition/energy choices
      "music_edit"        — no genuine speech (music-only, platform sound, lip-sync, voiceover);
                            pipeline pre-solves beat-aligned cuts

    speech_source from Gemini is the primary signal. Deepgram word count is the fallback
    when speech_source is absent (e.g. cached analysis from before this field existed).

    TikTok/platform sounds and lip-sync audio are routed to music_edit regardless of
    how many words Deepgram transcribed — those words belong to someone else's audio
    and have no relationship to the visual cut points in this footage.
    """
    word_count = len([w for w in (deepgram_words or []) if (w.get("word") or "").strip()])
    has_beats = len(analysis.get("beat_timestamps") or []) > 3
    audio = analysis.get("audio") or {}
    audio_field = audio.get("music") or ""
    has_music = bool(audio_field) and str(audio_field).strip().lower() not in ("none", "no music", "")
    speech_source = str(audio.get("speech_source") or "").strip().lower()

    # speech_source values where the audio words do NOT belong to this creator's
    # on-camera performance and should NOT be used to drive editorial cuts
    NON_ORIGINAL_SPEECH = {"lip_sync", "voiceover", "platform_sound", "none", ""}

    if speech_source == "on_camera":
        # Genuine speech — words can drive cuts
        if word_count >= 5 and has_music and has_beats:
            mode = "speech_with_music"
        else:
            mode = "speech"
    elif speech_source in NON_ORIGINAL_SPEECH:
        # Non-original audio: TikTok sound, lip-sync, voiceover, or no speech at all
        # Words from Deepgram are irrelevant — use beat alignment if possible
        mode = "music_edit" if has_beats else "speech"
    else:
        # speech_source missing — old cached analysis without this field
        # Fall back to word_count heuristic
        if word_count < 5 and has_beats:
            mode = "music_edit"
        elif word_count >= 5 and has_music and has_beats:
            mode = "speech_with_music"
        else:
            mode = "speech"

    print(
        f"[pipeline] content_mode={mode} "
        f"(speech_source={speech_source or 'unknown'}, words={word_count}, "
        f"beats={len(analysis.get('beat_timestamps') or [])}, has_music={has_music})",
        flush=True
    )
    return mode


# ─── BEAT-ALIGNED CUT BUILDER ────────────────────────────────────────────────

def score_frame_difference(source_path, timestamp, work_dir):
    """
    Compute a normalized pixel difference score at a timestamp.
    0.0 = identical frames, 1.0 = very different.
    Uses PSNR between two frames 0.1s apart. Returns 0.0 on any error.
    """
    fa = os.path.join(work_dir, f"fda_{int(timestamp*1000)}.jpg")
    fb = os.path.join(work_dir, f"fdb_{int(timestamp*1000)}.jpg")
    try:
        t_a = max(0.0, timestamp - 0.05)
        t_b = timestamp + 0.05

        for t_seek, fout in [(t_a, fa), (t_b, fb)]:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t_seek), "-i", source_path,
                 "-frames:v", "1", "-vf", "scale=128:228", "-q:v", "10", fout],
                capture_output=True
            )

        if not os.path.exists(fa) or not os.path.exists(fb):
            return 0.0

        result = subprocess.run(
            ["ffmpeg", "-i", fa, "-i", fb, "-lavfi", "psnr", "-f", "null", "-"],
            capture_output=True, text=True
        )
        m = re.search(r"average:([\d.]+|inf)", result.stderr)
        if m:
            raw = m.group(1)
            if raw == "inf":
                return 0.0
            psnr = float(raw)
            return max(0.0, min(1.0, 1.0 - (psnr / 50.0)))
    except Exception as e:
        print(f"[framediff] error at {timestamp:.3f}s: {e}", flush=True)
    finally:
        for f in [fa, fb]:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass
    return 0.0


def align_beats_to_cuts(beat_timestamps, visual_cuts, source_duration, source_path, work_dir,
                         snap_window=0.5, min_clip_duration=0.8, frame_diff_threshold=0.25):
    """
    Build a beat-aligned cut list for music_edit mode.

    Priority hierarchy per beat:
      1. Scene change within snap_window  → snap (cleanest — footage already changing)
      2. Significant frame difference     → snap to beat (visually motivated)
      3. Static footage                   → force beat (user intent is beat sync;
                                            renderer masks continuity break with transitions)

    Frame difference scoring is parallelized across all beats lacking a nearby scene change.

    Returns list of dicts:
      { source_start, source_end, duration, beat_time, snap_type, offset }
    snap_type: "scene_change" | "frame_diff" | "beat_forced"
    """
    if not beat_timestamps or source_duration <= 0:
        return []

    beats = sorted(beat_timestamps)
    scene_set = sorted(visual_cuts or [])

    beats_need_scoring = [
        bt for bt in beats
        if not any(abs(bt - sc) <= snap_window for sc in scene_set)
    ]

    frame_scores = {}
    if beats_need_scoring:
        import concurrent.futures as _cf

        def _score(bt):
            return bt, score_frame_difference(source_path, bt, work_dir)

        with _cf.ThreadPoolExecutor(max_workers=min(8, len(beats_need_scoring))) as ex:
            for bt, score in ex.map(_score, beats_need_scoring):
                frame_scores[bt] = score

    candidates = {}
    for sc in scene_set:
        candidates[sc] = "scene_change"
    for bt in beats_need_scoring:
        score = frame_scores.get(bt, 0.0)
        candidates[bt] = "frame_diff" if score >= frame_diff_threshold else "beat_forced"

    candidate_times = sorted(candidates.keys())

    used = set()
    cut_points = []

    for bt in beats:
        best = None
        best_dist = float("inf")
        for ct in candidate_times:
            if ct in used:
                continue
            dist = abs(ct - bt)
            if dist <= snap_window and dist < best_dist:
                best = ct
                best_dist = dist
        if best is not None:
            used.add(best)
            cut_points.append({"time": best, "beat_time": bt,
                                "snap_type": candidates[best], "offset": round(best - bt, 3)})
        else:
            cut_points.append({"time": bt, "beat_time": bt,
                                "snap_type": "beat_forced", "offset": 0.0})

    seen_keys = set()
    unique_cuts = []
    for cp in sorted(cut_points, key=lambda x: x["time"]):
        key = round(cp["time"] * 10)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_cuts.append(cp)

    cut_times = sorted(cp["time"] for cp in unique_cuts)
    boundaries = [0.0] + cut_times + [source_duration]

    raw_clips = []
    for i in range(len(boundaries) - 1):
        start = round(boundaries[i] * 1000) / 1000
        end = round(boundaries[i + 1] * 1000) / 1000
        dur = end - start
        if dur < min_clip_duration:
            continue
        cp_meta = next((cp for cp in unique_cuts if abs(cp["time"] - start) < 0.05), None)
        raw_clips.append({
            "source_start": start,
            "source_end": end,
            "duration": round(dur * 1000) / 1000,
            "beat_time": cp_meta["beat_time"] if cp_meta else start,
            "snap_type": cp_meta["snap_type"] if cp_meta else "beat_forced",
            "offset": cp_meta["offset"] if cp_meta else 0.0,
        })

    n_scene = sum(1 for c in raw_clips if c["snap_type"] == "scene_change")
    n_diff = sum(1 for c in raw_clips if c["snap_type"] == "frame_diff")
    n_forced = sum(1 for c in raw_clips if c["snap_type"] == "beat_forced")
    print(f"[beat_align] {len(beats)} beats → {len(raw_clips)} clips "
          f"(scene={n_scene}, frame_diff={n_diff}, forced={n_forced})", flush=True)
    return raw_clips


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
            model="nova-3", detect_language=True, words=True,
            smart_format=True, utterances=True, punctuate=True, diarize=False,
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
            }
            for w in raw_words
        ]
        print(f"[deepgram] Transcribed {len(words)} words", flush=True)
        return {"text": alt.transcript or "", "words": words}
    except Exception as e:
        print(f"[pipeline] transcription failed (non-fatal): {e}", flush=True)
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


def tighten_transcript(words, scene_cuts=None, shots=None, original_duration=0):
    scene_cuts = scene_cuts or []
    max_gap = 0.15
    trim_to = 0.05
    min_segment = 0.3
    padding = 0.02

    if not words:
        if original_duration > 0:
            return {"segments": [{"start": 0, "end": round(original_duration*1000)/1000}], "removedSeconds": 0, "timeline_map": [], "tightened_duration": original_duration}
        return {"segments": [], "removedSeconds": 0, "timeline_map": [], "tightened_duration": 0}

    fillers = detect_filler_words(words)
    filler_keys = {f"{round(f['start']*1000)/1000}-{round(f['end']*1000)/1000}" for f in fillers}
    keep_words = [w for w in words if f"{round(w['start']*1000)/1000}-{round(w['end']*1000)/1000}" not in filler_keys]

    if not keep_words:
        return {"segments": [], "removedSeconds": 0, "timeline_map": [], "tightened_duration": 0}

    dead_air_cuts = []
    for i in range(1, len(keep_words)):
        prev_end  = keep_words[i-1]["end"]
        curr_start = keep_words[i]["start"]
        gap = curr_start - prev_end
        if gap <= max_gap:
            continue
        near_scene = any(abs(c - prev_end) < 0.05 or abs(c - curr_start) < 0.05 for c in scene_cuts)
        if near_scene:
            continue
        remove_end = curr_start
        remove_start = prev_end + trim_to
        if remove_end > remove_start:
            dead_air_cuts.append({"start": remove_start, "end": remove_end})

    first = max(0, keep_words[0]["start"] - padding)
    last  = keep_words[-1]["end"] + padding
    if original_duration > 0:
        last = min(last, original_duration)

    filler_cuts = [{"start": max(0, f["start"]-0.02), "end": f["end"]+0.02} for f in fillers]
    remove_ranges = sorted(filler_cuts + dead_air_cuts, key=lambda r: r["start"])

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


# ─── SCENE FRAME EXTRACTION ───────────────────────────────────────────────────

def extract_scene_frames(source_path, timestamps, work_dir):
    import base64
    frames = []
    seen = set()
    all_ts = sorted(set([0.1] + [round(t*1000)/1000 for t in timestamps if t > 0]))
    for ts in all_ts:
        key = f"{ts:.3f}"
        if key in seen:
            continue
        seen.add(key)
        frame_path = os.path.join(work_dir, f"frame_{key.replace('.','_')}.jpg")
        result = subprocess.run(
            ["ffmpeg","-y","-ss",str(ts),"-i",source_path,"-frames:v","1","-vf","scale=512:-1","-q:v","8",frame_path],
            capture_output=True
        )
        if result.returncode == 0 and os.path.exists(frame_path):
            with open(frame_path, "rb") as f:
                frames.append({"timestamp": ts, "base64": base64.b64encode(f.read()).decode(), "mediaType": "image/jpeg"})
            try:
                os.unlink(frame_path)
            except Exception:
                pass
    print(f"[frames] Extracted {len(frames)} scene frame thumbnails", flush=True)
    return frames



# ─── EXPAND VIBE ─────────────────────────────────────────────────────────────

def expand_vibe_intent(vibe):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        temperature=0,
        messages=[{"role": "user", "content": (
            f'The user described how they want their video edited in a few words. Your job is to turn their brief into a clear, complete creative direction that a professional video editor can follow. The expanded version will be passed directly to the editor as their instructions.\n\n'
            f'Keep every specific technique, effect, or style the user mentioned in the output — words like "transitions", "captions", "zoom", "speed", "sound effects", "fast", "slow", "cinematic" etc. should appear in your expansion exactly as the user stated them. Add clarity and detail around what the user\'s words mean for the edit, but preserve their original intent and specific requests.\n\n'
            f'User input: "{vibe}"'
        )}]
    )
    expanded = (resp.content[0].text or "").strip()
    print(f"[edit] Vibe expansion: \"{vibe}\" -> \"{expanded}\"", flush=True)
    return expanded or vibe



# ─── GENERATE EDIT (Claude Sonnet) ───────────────────────────────────────────

def build_music_edit_prompt(analysis, expanded_vibe):
    """
    Claude prompt for music_edit mode.
    Cut timestamps are pre-solved by the pipeline. Claude chooses which clips to keep,
    sets transitions, color grade, and effects. Scene frames are injected by generate_edit().
    """
    beat_clips = analysis.get("beat_aligned_clips") or []
    duration = float(analysis.get("duration") or 0)
    fq = analysis.get("footage_quality") or {}
    cb = analysis.get("color_baseline") or {}
    frame_layout = analysis.get("frame_layout") or {}
    vp = analysis.get("footage_assessment") or analysis.get("video_profile") or {}
    beat_timestamps = analysis.get("beat_timestamps") or []
    intents = ", ".join(COLOR_INTENTS.keys())

    clip_lines = []
    for i, clip in enumerate(beat_clips):
        snap = clip.get("snap_type", "beat_forced")
        label = {
            "scene_change": "scene cut — footage changes here, clean cut",
            "frame_diff": "visual change — significant movement, clean cut",
            "beat_forced": "beat forced — static footage, use masking transition",
        }.get(snap, snap)
        clip_lines.append(
            f"  Clip {i+1}: {clip['source_start']:.3f}s → {clip['source_end']:.3f}s "
            f"({clip['duration']:.2f}s) [{label}]"
        )
    clips_block = "\n".join(clip_lines) if clip_lines else "  none"

    noise = fq.get("noise_level", "low")
    sharpness = fq.get("source_sharpness", "normal")
    highlights = fq.get("highlight_condition", "normal")
    shadows = fq.get("shadow_condition", "normal")
    richness = fq.get("color_richness", "normal")
    skin = fq.get("skin_tones_present", True)
    lighting = fq.get("lighting_type", "unknown")

    render_recs = [
        f"NOISE: {'denoise=true' if noise in ('medium','high') else 'denoise=false'} (observed: {noise})",
        f"SHARPNESS: {'sharpening=true recommended' if sharpness == 'soft' else f'sharpening your call ({sharpness})'}",
        f"HIGHLIGHTS: {'highlight_rolloff=true recommended' if highlights in ('clipped','bright') else f'highlight_rolloff your call ({highlights})'}",
        f"SHADOWS: {'shadow_lift=true recommended' if shadows in ('crushed','deep') else f'shadow_lift your call ({shadows})'}",
        f"COLOR: {'vibrance=true recommended' if richness in ('flat','muted') else f'vibrance your call ({richness})'}",
    ]
    if skin:
        render_recs.append("SKIN: Skin tones present — vibrance and teal_orange affect them")
    render_recs.append(f"LIGHTING: {lighting}")
    render_recs_block = "\n".join(f"  {r}" for r in render_recs)

    content_type = vp.get("content_type") or "unknown"
    visual_character = vp.get("visual_character") or vp.get("visual_style") or "unknown"
    strongest = vp.get("strongest_moments") or "not specified"
    weakest = vp.get("weakest_moments") or "not specified"
    cb_assessment = cb.get("assessment") or "No major exposure issues detected."
    frame_overlays = (frame_layout.get("existing_overlays") or {}).get("overlay_locations", "none")

    static_part = f"""You are the professional editor inside Promptly, a mobile app that competes with CapCut and Captions. This video has no speech — it is footage set to music. The pipeline has already detected the audio beats and built a beat-aligned cut list. Your job is the creative treatment.

=== YOUR ROLE IN THIS EDIT ===

The cut timestamps are already solved. The pipeline detected {len(beat_timestamps)} beats and produced {len(beat_clips)} pre-aligned clips. The source_start and source_end values are fixed — do not invent or change timestamps. Copy them exactly from the clip list.

Your decisions:
1. Which clips to include and in what order (you may exclude clips by omitting them)
2. transition_out for each clip — your primary creative lever in a beat-sync edit
3. Color grade and all global visual parameters
4. Per-clip effects: zoom, speed, speed_ramp, freeze_frame, motion_blur_transition

This is a beat-sync edit. Every cut lands on or near a musical beat. Transitions and effects reinforce the rhythm — the viewer feels the music through the editing.

=== PRE-BUILT CLIP LIST (timestamps are locked — copy exactly) ===

{clips_block}

Cut type rules:
  scene cut or visual change → any transition works, footage supports it cleanly
  beat forced → footage is continuous here, cut is mid-movement
    REQUIRED: motion_blur_transition=true on every beat_forced clip
    USE: dissolve, flash, glitch, whip_left, or whip_right to mask the continuity break
    AVOID: none, fade, wipeleft/wiperight/wipeup/wipedown — these expose the break

=== THIS VIDEO ===

Duration: {duration:.2f}s
Content type: {content_type}
Visual character: {visual_character}
Strongest moments: {strongest}
Weakest moments: {weakest}

Color baseline: {cb_assessment}

Footage quality (Gemini directly observed):
{render_recs_block}

Frame layout:
  Subject: {frame_layout.get("subject_position", "unknown")}
  Existing overlays: {frame_overlays}
  Open space: {frame_layout.get("free_zones", "unknown")}

Platform safe zones (9:16): bottom 20% covered by TikTok/Reels UI. Top 10% status bar. Safe zone: middle 70%.

=== SCENE FRAMES ===

Frame thumbnails follow — use them to make shot-specific decisions on color grade, transitions, and whether clips have strong or weak visual content.

=== TOOLS ===

Per-clip (copy source_start/source_end exactly from the clip list above):
  source_start, source_end — LOCKED. Copy from clip list. Do not change.
  transition_out — none, fade, fadeblack, fadewhite, dissolve, wipeleft, wiperight, wipeup, wipedown,
    smoothleft, smoothright, smoothup, smoothdown, zoomin, flash, glitch, whip_left, whip_right
  transition_sound — none, swoosh, thud, pop, ding, reverb_hit, typing, ching, shutter
    Pairings: flash→pop or thud | glitch→thud or reverb_hit | whip→swoosh | dissolve→none or reverb_hit
    Do not use the same transition_sound on consecutive clips.
  sfx_style — none, swoosh, thud, shutter
  zoom — none, slow_in, slow_out, punch_in, punch_out
  cut_zoom — true/false
  speed — 0.5, 0.75, 1.0, 1.05, 1.1, 1.15, 1.25, 1.5, 2.0
  speed_ramp — none, hero_time, bullet, flash_in, flash_out, montage
  freeze_frame — true/false. Holds last frame 0.3s. Use sparingly on climactic beats for emphasis.
  motion_blur_transition — true/false. Required=true on all beat_forced clips. Optional on others.

Global:
  color_intent — {intents}
  vignette — none, light, medium, strong
  sharpening — true/false
  grain — none, subtle, medium, heavy
  denoise — true/false
  cinematic_bars — true/false
  shadow_lift — true/false
  highlight_rolloff — true/false
  vibrance — true/false
  teal_orange — none, subtle, strong
  caption_style — always "none"
  audio_denoise — always false (do not denoise music)
  beat_sync — always true
  outro — none, fade_black, fade_white
  text_overlays — optional. Title cards, location text, or visual emphasis only.
    Max 1-2. Keep minimal — this is a visual edit, not an information edit.
  background_music — choose one track filename from the library below, or "none" if the content works better without music.

  For most vibes, music is essential — pick the track that best matches the emotional tone and energy the user described. The track will be mixed under the speech at low volume with ducking, so it enhances rather than competes.

  Music library (pick the filename that best fits the vibe):
  {music_library_block}
  aspect_ratio — always "9:16"

=== RESPONSE FORMAT ===

Respond with ONLY this JSON:

{{
  "notes": "<50 words max>",
  "color_intent": "<intent>",
  "background_music": "<track_filename or none>",
  "caption_style": "none",
  "caption_position": "lower-third",
  "caption_keywords": [],
  "audio_ducking": false,
  "audio_denoise": false,
  "beat_sync": true,
  "outro": "<outro>",
  "aspect_ratio": "9:16",
  "vignette": "<level>",
  "sharpening": <true|false>,
  "grain": "<level>",
  "denoise": <true|false>,
  "cinematic_bars": <true|false>,
  "shadow_lift": <true|false>,
  "highlight_rolloff": <true|false>,
  "vibrance": <true|false>,
  "teal_orange": "<level>",
  "text_overlays": [
    {{ "text": "<text>", "position": "<pos>", "appear_at_clip": <n>, "style": "<style>", "sfx_style": "<sfx>" }}
  ],
  "broll": [],
  "cuts": [
    {{ "source_start": <locked>, "source_end": <locked>, "transition_out": "<t>", "transition_sound": "<s>", "sfx_style": "<sfx>", "zoom": "<zoom>", "cut_zoom": false, "speed": <n>, "speed_ramp": "<ramp>", "freeze_frame": <true|false>, "motion_blur_transition": <true|false> }}
  ]
}}

The user said: "{expanded_vibe}"
"""

    split_marker = "=== THIS VIDEO ==="
    split_index = static_part.index(split_marker)
    return static_part[:split_index].strip(), static_part[split_index:].strip()


# truncated in command preview; full user-provided file continues below unchanged
def build_prompt(analysis, transcript, expanded_vibe, music_library_block=""):
    shots = analysis.get("shots") or []
    shots_block = "\n\n".join(
        f"[{s['start']:.2f}s – {s['end']:.2f}s]\n  {s.get('visual','')}\n  {s.get('action','')}\n  Energy: {s.get('energy',0.5):.1f}"
        + (f"\n  Value: {s['editing_value']}" if s.get("editing_value") else "")
        + (f"\n  Delivery: {s['delivery']}" if s.get("delivery") and s["delivery"] != "none" else "")
        for s in shots
    )

    speech = analysis.get("speech") or {}
    speech_parts = []
    if speech.get("has_speech"):
        if speech.get("speaker_style") or speech.get("overall_delivery"):
            speech_parts.append(f"Speaker: {speech.get('speaker_style') or speech.get('overall_delivery')}")
        for seg in (speech.get("segments") or []):
            seg_line = f"[{seg['start']:.2f}s – {seg['end']:.2f}s] \"{seg.get('text','')}\" ({seg.get('emotion','neutral')}, energy {float(seg.get('energy_level',0.5)):.1f})"
            notes = seg.get("notes") or seg.get("delivery_notes")
            if notes:
                seg_line += f"\n    {notes}"
            speech_parts.append(seg_line)
    speech_block = "\n".join(speech_parts)

    scene_changes = sorted(analysis.get("visual_cuts") or [], key=lambda t: float(t or 0))
    if scene_changes:
        scene_changes_block = "\n".join(
            f"  {float(t):.2f}s — " + (
                next((s.get("description") or s.get("action") or s.get("visual") or "scene change"
                      for s in shots if float(t) >= s.get("start",0) and float(t) <= s.get("end",0)), "scene change")
            )
            for t in scene_changes
        )
    else:
        scene_changes_block = "  none"

    sentence_boundaries = sorted(
        (speech.get("sentence_boundaries") or []),
        key=lambda b: float(b.get("time") or 0)
    )
    if sentence_boundaries:
        sb_lines = []
        for b in sentence_boundaries:
            t = float(b.get("time") or 0)
            pause = float(b.get("pause_after") or 0)
            seg = next(
                (s for s in (speech.get("segments") or [])
                 if float(s.get("end") or 0) >= t - 0.05 and float(s.get("end") or 0) <= t + 0.6),
                None
            )
            prev_text = f', preceding text: "{seg["text"]}"' if seg and seg.get("text") else ""
            sb_lines.append(f"  {t:.2f}s — pause {pause:.3f}s{prev_text}")
        speech_boundaries_block = "\n".join(sb_lines)
    else:
        speech_boundaries_block = "  none"

    highlights_block = ""
    highlights = analysis.get("peak_moments") or []
    if highlights:
        sorted_h = sorted(highlights, key=lambda h: -(h.get("importance") or 0))
        highlights_block = "\nHighlights:\n" + "\n".join(
            f"  {float(h.get('time',0)):.2f}s — {h.get('what') or h.get('description','')} ({float(h.get('importance',0.5)):.1f})"
            for h in sorted_h
        )

    beat_timestamps = analysis.get("beat_timestamps") or []
    if beat_timestamps:
        step = max(1, len(beat_timestamps) // 40)
        sampled = beat_timestamps[::step]
        beats_str = ", ".join(f"{t:.2f}s" for t in sampled[:40])
        beat_block = f"\nAudio beat timestamps (detected from the audio track — snap cuts here for beat-sync editing):\n  {beats_str}"
    else:
        beat_block = ""

    tightened = analysis.get("tightened_timeline") or {}
    if tightened and (tightened.get("segments") or []):
        original_duration = float(analysis.get("duration") or 0)
        tightened_duration = sum(max(0, s.get("end",0) - s.get("start",0)) for s in tightened["segments"])
        seg_text = ", ".join(f"{s.get('start',0):.2f}s-{s.get('end',0):.2f}s" for s in tightened["segments"])
        tightened_block = f"Tightened timeline (dead air and filler words already removed):\n  Original: {original_duration:.2f}s → Tightened: {tightened_duration:.2f}s (removed {float(tightened.get('removedSeconds',0)):.2f}s)\n  Keep segments: {seg_text}"
    else:
        original_duration = float(analysis.get("duration") or 0)
        tightened_block = None

    broll_candidates = analysis.get("broll_candidates") or []
    broll_candidates_block = ""
    if broll_candidates:
        broll_candidates_block = "\n".join(
            f"  - {c['keyword']} @ {float(c.get('timestamp',0)):.2f}s"
            for c in broll_candidates[:6]
        )

    vp = analysis.get("video_profile") or {}
    profile_parts = []
    if vp.get("content_type"):     profile_parts.append(f"Type: {vp['content_type']}")
    if vp.get("visual_character") or vp.get("visual_style"):
        profile_parts.append(f"Look: {vp.get('visual_character') or vp.get('visual_style')}")
    if vp.get("strongest_moments"): profile_parts.append(f"Best parts: {vp['strongest_moments']}")
    if vp.get("weakest_moments"):   profile_parts.append(f"Weakest parts: {vp['weakest_moments']}")
    profile_block = "\n" + "\n".join(profile_parts) if profile_parts else ""

    audio_block = ""
    audio = analysis.get("audio") or {}
    music_info = audio.get("music") or (audio.get("has_music") and audio.get("music_description"))
    content_mode = analysis.get("content_mode", "speech")
    if music_info:
        audio_block = f"\nMusic: {music_info}"

    if content_mode == "speech_with_music":
        beat_ts = analysis.get("beat_timestamps") or []
        if beat_ts:
            step = max(1, len(beat_ts) // 20)
            sampled = beat_ts[::step][:20]
            beats_str = ", ".join(f"{t:.2f}s" for t in sampled)
            audio_block += (
                f"\n\nThis video has speech AND background music. "
                f"Speech boundaries drive all cut decisions — beats do not move cuts. "
                f"When a cut lands within ~0.15s of a beat timestamp, use a transition that "
                f"reinforces the rhythm: flash, glitch, whip_left, whip_right, or a hard cut "
                f"with transition_sound. When a cut lands off-beat, use a smoother transition: "
                f"dissolve, fade, smoothleft, smoothright. "
                f"Sample beat timestamps (reference only — do not move cuts): {beats_str}"
            )

    cb = analysis.get("color_baseline") or {}
    fq = analysis.get("footage_quality") or {}
    frame_layout = analysis.get("frame_layout") or {
        "subject_position": "unknown",
        "existing_overlays": {"has_burned_captions": False, "has_text_graphics": False, "overlay_locations": "none detected"},
        "free_zones": "unknown",
    }
    content_type = vp.get("content_type") or "unknown"
    visual_character = vp.get("visual_character") or vp.get("visual_style") or "unknown"
    strongest_moments = vp.get("strongest_moments") or "not specified"
    weakest_moments = vp.get("weakest_moments") or "not specified"
    frame_overlay_locations = (frame_layout.get("existing_overlays") or {}).get("overlay_locations") or "none detected"

    render_recs = []

    noise = fq.get("noise_level", "low")
    sharpness = fq.get("source_sharpness", "normal")
    highlights = fq.get("highlight_condition", "normal")
    shadows = fq.get("shadow_condition", "normal")
    richness = fq.get("color_richness", "normal")
    skin = fq.get("skin_tones_present", True)
    lighting = fq.get("lighting_type", "unknown")

    if noise in ("medium", "high"):
        render_recs.append(f"NOISE: {noise}-level noise observed directly — denoise=true (renderer will apply calibrated hqdn3d strength for {noise} noise)")
    else:
        render_recs.append(f"NOISE: Clean footage (noise_level={noise}) — denoise=false")

    if sharpness == "soft":
        render_recs.append(f"SHARPNESS: Source is soft — sharpening=true (renderer will apply strong unsharp for soft footage)")
    elif sharpness == "normal":
        render_recs.append(f"SHARPNESS: Normal sharpness — sharpening=true applies a calibrated subtle pass; false leaves it as-is")
    else:
        render_recs.append(f"SHARPNESS: Source is already sharp — sharpening=false (renderer would apply only minimal pass, but it's not needed)")

    if highlights == "clipped":
        render_recs.append(f"HIGHLIGHTS: Blown out/clipped — highlight_rolloff=true (renderer will apply hard rolloff curve for clipped footage)")
    elif highlights == "bright":
        render_recs.append(f"HIGHLIGHTS: Near-clipping — highlight_rolloff=true (renderer will apply soft rolloff for bright footage)")
    else:
        render_recs.append(f"HIGHLIGHTS: {highlights} — highlight_rolloff=false unless a filmic look is intended")

    if shadows == "crushed":
        render_recs.append(f"SHADOWS: Crushed to pure black — shadow_lift=true (renderer will apply high lift for crushed shadows)")
    elif shadows == "deep":
        render_recs.append(f"SHADOWS: Deep and rich — shadow_lift=false preserves the look; true applies a low lift if the vibe is faded/editorial")
    elif shadows == "lifted":
        render_recs.append(f"SHADOWS: Already elevated in raw footage — shadow_lift=false (additional lift will look washed out)")
    else:
        render_recs.append(f"SHADOWS: Balanced — shadow_lift is purely a stylistic choice")

    if richness == "flat":
        render_recs.append(f"COLOR: Color-flat footage — vibrance=true (renderer will apply high vibrance for flat footage)" + (" — skin tones present, vibrance protects them" if skin else ""))
    elif richness == "muted":
        render_recs.append(f"COLOR: Muted colors — vibrance=true (renderer applies medium vibrance for muted footage)" + (" — skin tones present, vibrance protects them" if skin else ""))
    elif richness == "vivid":
        render_recs.append(f"COLOR: Already vivid — vibrance=false (boosting vivid footage produces neon/artificial results)")
    else:
        render_recs.append(f"COLOR: Normal color richness — vibrance=false unless the vibe calls for more punch")

    if lighting == "natural_indoor":
        render_recs.append(f"LIGHTING: Indoor natural light observed")
    elif lighting == "natural_outdoor":
        render_recs.append(f"LIGHTING: Outdoor natural light observed")
    elif lighting == "studio":
        render_recs.append(f"LIGHTING: Studio lighting observed")

    render_recs_block = "\n".join(f"  {r}" for r in render_recs)
    has_burned_captions = bool((frame_layout.get("existing_overlays") or {}).get("has_burned_captions"))
    duration = float(analysis.get("duration") or 0)
    tightened_duration_val = sum(max(0, s.get("end",0) - s.get("start",0)) for s in (tightened.get("segments") or [])) if tightened else duration
    intents = ", ".join(COLOR_INTENTS.keys())

    # Hook block for Claude prompt
    hook          = analysis.get("hook") or {}
    hook_ts       = hook.get("timestamp")
    hook_block    = ""
    if hook and hook_ts is not None and float(hook_ts) > 1.0 and float(hook.get("quality") or 0) >= 0.5:
        hook_block = (
            f"\n⚡ HOOK DETECTED at {float(hook_ts):.2f}s — {hook.get('description', '')}\n"
            f"   Why compelling: {hook.get('why', '')}\n"
            f"   Strength: {float(hook.get('quality', 0.5)):.1f}/1.0\n"
            f"   → Consider starting your edit at {float(hook_ts):.2f}s instead of 0.0s"
        )

    # Pacing and duration block for Claude prompt
    rec_dur    = analysis.get("recommended_duration")
    pacing_val = analysis.get("pacing")
    pacing_block = ""
    if rec_dur or pacing_val:
        pacing_parts = []
        if rec_dur:
            pacing_parts.append(f"Recommended edit length: ~{rec_dur}s")
        if pacing_val:
            clip_guidance = {"fast": "1-3s clips", "medium": "3-6s clips", "slow": "5-10s clips"}.get(pacing_val, "")
            pacing_parts.append(f"Recommended pacing: {pacing_val}" + (f" ({clip_guidance})" if clip_guidance else ""))
        pacing_block = "\n" + "\n".join(pacing_parts)

    tightened_fallback = (
        f"Tightened timeline (dead air and filler words already removed):\n"
        f"  Original: {duration:.2f}s → Tightened: {tightened_duration_val:.2f}s "
        f"(removed {float((tightened or {}).get('removedSeconds', 0)):.2f}s)\n"
        f"  Keep segments: none"
    )

    full_prompt = f"""You are the professional editor inside Promptly, a mobile app that competes with CapCut and Captions. Users upload raw talking-head footage and receive back a fully edited short-form video (TikTok, Instagram Reels, YouTube Shorts) in under 90 seconds. You produce the edit recipe — every creative decision about how this video gets cut, graded, and polished.

Your output needs to be indistinguishable from a video edited by a skilled freelance editor who specializes in short-form content for TikTok and Instagram Reels.

=== HOW TO USE THE INFORMATION YOU ARE GIVEN ===

By the time you receive this prompt, the pipeline has already done the analytical work. Deepgram has transcribed every word with timestamps and scored speech energy. Gemini has watched the footage and identified shots, energy levels, peak moments with importance scores, color character, footage quality, and frame layout. Beat detection has found the audio tempo. You are not being asked to analyze the video - that is already done. You are being asked to make creative decisions using that analysis.

The information you are given is the complete picture of the video. Your job is to read it, understand what the footage actually contains, and then use the vibe to determine what the edit needs to become.

=== YOUR CREATIVE DIRECTION ===

Before writing any JSON, do this in order.

**Step 1 - Read the vibe as a creative directive.**

The expanded vibe is the user's brief. Determine from it: what energy level the finished video needs to carry, and whether the user named specific techniques or described a feeling. If they named a technique, it is a direct instruction. If they described a feeling, determine which combination of the available tools produces that feeling for this specific footage.

**Step 2 - Apply every parameter with purpose.**

For every parameter, the only question is whether it serves the energy and direction the vibe established. If it does, apply it. If it does not, set it to off or neutral. The number of active parameters is not what matters - what matters is that every active parameter has a purpose tied directly to the vibe, and that none are applied simply because they are available.

**Step 3 - Verify that every decision points in the same direction.**

Before writing the JSON, confirm that your choices are internally consistent. If any decision contradicts another, resolve it in favor of whichever choice is more directly tied to what the vibe asked for.

=== WHERE THIS VIDEO LIVES ===

This video will be posted to TikTok, Instagram Reels, or YouTube Shorts. Here is how these platforms work:

Feed behavior: Videos appear in a vertical infinite scroll feed. Each video takes up the full screen. The viewer swipes up to skip to the next video. The decision to stay or scroll happens in the first 2-3 seconds.

Looping: When a video ends, the platform automatically loops it back to the beginning. The transition from the last frame to the first frame is visible to the viewer. Videos that end abruptly loop seamlessly. Videos that fade to black show a flash of black before the first frame reappears.

Screen layout: The video plays at 1080x1920 on a phone screen. The platform overlays UI elements on top of the video:
  - Right side: a vertical stack of buttons (like, comment, share, save) covering roughly the right 15% of the frame from the middle down
  - Bottom 20%: the creator's username, video caption text, and a sound ticker
  - Top 10%: status bar, back button, search icon
  These UI elements are always present during playback. Text or important visual content placed in these zones is partially or fully hidden.

Captions on the platform: The majority of top-performing short-form content on TikTok and Reels in 2025 uses large, bold, word-by-word animated captions. These are typically centered or in the lower-third of the frame, with high contrast (white or yellow text with black outlines). Videos without any form of captions get significantly lower average watch time because a large portion of viewers browse with sound off or in noisy environments. Videos that already have captions burned into the frames already have this coverage.

Pacing: Short-form content on these platforms is edited with fast pacing relative to traditional video. Clips are typically 2-8 seconds long. Speed adjustments of 1.05x-1.15x are common on talking-head content to tighten delivery without being perceptible. Static framing (no zoom, no cut-zoom, no transitions) for more than 5-6 seconds reads as unedited raw footage on these platforms.

The video will be viewed on a 1080px wide phone screen.

=== YOUR RECIPE GOES DIRECTLY TO RENDER ===

Your edit recipe is a JSON object that controls every parameter of the FFmpeg render. The downstream system reads your JSON literally — every value you set becomes an FFmpeg filter parameter. There is no human review between your recipe and the rendered output. Your decisions go directly to the user's screen.

=== HOW THIS RENDERING PIPELINE WORKS ===

Some tool combinations produce specific results in this rendering pipeline. These are technical realities of how FFmpeg processes the video:

Captions and burned-in captions: The frame layout analysis below tells you whether this video already has captions burned into the frames. If it does, those captions are baked into the pixel data and cannot be removed. Adding a caption_style on top of existing burned-in captions means the viewer sees two overlapping text tracks. On TikTok and Reels, the bottom 20% of the screen is already covered by platform UI (username, caption text, buttons). Two caption layers plus platform UI produces three layers of overlapping text at the bottom of a phone screen.

Zoom effects and frame content: Zoom works by scaling the frame larger than 1080x1920 and cropping back to 1080x1920. This crops the edges. If the video has text burned into the frame — captions, watermarks, lower thirds — zoom crops into that text, cutting off letters or words. On videos without burned-in text, zoom works cleanly.

Zoom and cut-zoom on the same clip: Zoom applies a continuous scale change across the clip. Cut-zoom alternates between two framing levels at sentence boundaries. Both active on the same clip produces two competing scale changes — continuous drift plus sudden jumps.

Sound effect files: Each transition sound and text overlay sound is a single short audio recording. When the same sound file plays on consecutive transitions (e.g., whoosh then whoosh), the viewer hears the identical audio sample repeated back-to-back.

Fade-to-black timing: On TikTok, Reels, and Shorts, the platform auto-advances or loops when a video ends. A fade-to-black darkens the last second of the video. Viewers scrolling their feed see the darkening in peripheral vision before the video finishes.

Text overlay rendering: Text overlays use FFmpeg's drawtext filter at a fixed font size on the 1080px wide frame. Text longer than 4-5 words gets rendered at a smaller size to fit, or extends past the frame edges and gets clipped.

=== PIPELINE STEPS ===

Before you see anything, the pipeline has already:
1. Downloaded the user's raw footage
2. Normalized it to 1080x1920 at 30fps
3. Transcribed all speech with word-level timestamps (Deepgram)
4. Analyzed the footage visually — identified shots, scene changes, speaker energy, frame layout, existing overlays, color character (Gemini, with frame thumbnails)
5. Detected scene change timestamps from the raw video (FFmpeg scdet)
6. Tightened the timeline by removing dead air and filler words

You decide the clip structure for this video. Each clip in your response has a source_start and source_end timestamp — these are the exact timestamps the pipeline uses to extract clips from the source video.

Choose your cuts based on the shot analysis, transcript, and scene frames above. Effective cuts in short-form content land at moments where the visual content, speaker topic, or energy level changes.

For videos with speech: speech boundary timestamps (listed below) produce the cleanest audio cuts because the speaker is naturally pausing. Cutting mid-sentence produces an audible break in speech that sounds like a glitch.

For videos without speech or with continuous movement: scene change timestamps and visual transitions (indoor to outdoor, subject position changes, camera movement changes) are the best cut points.

Sections of the video that are static, blurry, or have no visual or narrative value can be excluded from your clips. The pipeline will only render the sections you include.

After you respond, the pipeline:
1. Extracts each clip from the source video at the timestamps
2. Downloads any b-roll clips you requested from Pexels
3. Builds a single FFmpeg filter graph using every value from your recipe
4. Sends it to a GPU server which renders the final video in one pass
5. Uploads the rendered video directly to the user's library

=== TOOLS ===

Each clip in your recipe has these parameters:
  source_start / source_end — timestamps in the source video that define this clip's boundaries. Clips must be strictly sequential and non-overlapping: each clip's source_start must be greater than or equal to the previous clip's source_end. You cannot reuse or revisit a segment of the source video that has already appeared in an earlier clip.

  transition_out — visual effect between this clip and the next:
    none — clean hard cut, no visual effect
    fade — gradual opacity fade between clips
    fadeblack — first clip fades to black, then next clip fades in from black
    fadewhite — same as fadeblack but through white
    dissolve — cross-fade blend where both clips are briefly visible
    wipeleft — next clip slides in from the right, pushing current clip left
    wiperight — next clip slides in from the left
    wipeup — next clip slides in from the bottom
    wipedown — next clip slides in from the top
    smoothleft / smoothright / smoothup / smoothdown — polished versions of the wipe transitions with eased motion
    zoomin — current clip zooms in and reveals next clip underneath
    flash — a single bright white frame hit between clips. An instant visual snap that punctuates a beat or a high-energy moment. No fade — just a flash and cut
    glitch — chromatic aberration and horizontal frame displacement on the transition frames. Signals disruption, intensity, or a topic/energy shift. Common on tech, hype, beat-drop content
    whip_left — directional motion blur streaking left, simulating a fast camera whip pan. The outgoing clip smears into the incoming one. Kinetic and high-energy
    whip_right — same as whip_left but streaking right

  transition_sound — audio that plays during the transition:
    none — silent transition
    swoosh — fast tight air swipe sound
    shutter — camera shutter click
    thud — short punchy impact hit
    pop — quick bright snap
    ding — clean single-note bell
    reverb_hit — impact with reverb tail
    typing — rapid keyboard clicks
    ching — cash register sound

  sfx_style — sound accent on the clip itself:
    none, swoosh, thud, shutter

  zoom — camera movement applied across the entire clip duration:
    none — static framing
    slow_in — gradually zooms in from wide to tight over the clip
    slow_out — gradually zooms out from tight to wide
    punch_in — quick zoom in at the start of the clip
    punch_out — quick zoom out at the start of the clip

  cut_zoom — simulates a multi-camera shoot from a single take:
    true — alternates between normal and slightly zoomed-in framing at sentence boundaries within the clip, creating the appearance of camera angle changes
    false — single continuous framing for the whole clip

  speed — playback speed multiplier. Values above 1.0 speed up the clip and shorten its duration. Values below 1.0 slow it down. Audio pitch is preserved.
    0.5, 0.75, 1.0, 1.05, 1.1, 1.15, 1.25, 1.5, 2.0

  speed_ramp — a non-linear speed curve applied within a single clip. The clip accelerates or decelerates across its duration, creating the signature CapCut speed-ramp effect. Works independently of the speed multiplier (speed sets the base tempo; speed_ramp shapes how it moves through that tempo over time).
    none — constant speed throughout the clip
    hero_time — starts fast, slams into slow motion at the emotional peak of the clip. The slow portion lingers on whatever is happening at that moment
    bullet — slow-motion intro, then rockets to fast speed through the rest of the clip. Builds anticipation then releases it
    flash_in — instant fast at the start, eases down to normal speed. Creates an urgent, high-energy opening
    flash_out — normal speed, then accelerates hard at the end. Propels the viewer into the next clip
    montage — alternating fast/slow bursts across the clip duration. High visual energy, works best on action or movement content

  freeze_frame — holds the last frame of the clip as a still image for a brief moment before the transition fires. Creates a punctuation beat — the action literally freezes and then cuts. Used for emphasis on a reaction, a word landing, or a visual moment worth letting sit. The freeze duration is automatically set to 0.3s.
    true, false

  motion_blur_transition — adds a directional motion blur to the outgoing frames at the moment of the transition. Makes the cut feel like a physical camera movement rather than an edit. Works with any transition_out value — the blur fires on the last few frames before the cut and the first few frames of the incoming clip.
    true, false

Global parameters:
  color_intent — sets the overall color character of the video.
    {intents}

  vignette — darkens the edges of the frame, drawing the eye toward the center:
    none, light, medium, strong

  sharpening — true/false. When true, the renderer measures the source sharpness Gemini observed and applies the calibrated unsharp filter strength for that footage. Counteracts compression softness and produces the clean, high-definition look of professionally shot content.
    true, false

  grain — adds film grain texture to the entire video. Transforms flat digital footage into something that looks like it was shot on film or with a high-end camera. Often used to make color-graded footage feel intentional and textured rather than processed. Pairs well with faded, vintage, cinematic, and moody color intents.
    none, subtle, medium, heavy

  denoise — true/false. When true, the renderer applies the calibrated denoising strength for the noise level Gemini observed. Cleans the base before the color grade so grading applies to clean pixels rather than noise.
    true, false

  cinematic_bars — adds horizontal black bars at the top and bottom of the frame (2.35:1 letterbox format). Creates an immediate cinematic, movie-like look on 9:16 vertical video. Narrows the visible frame vertically, which draws the eye to the center subject. The bars are permanently visible.
    true, false

  shadow_lift — true/false. When true, the renderer applies the calibrated shadow lift amount for the shadow condition Gemini observed. Raises the black point so shadows never crush to pure black. Creates a faded, elevated look where dark areas glow softly.
    true, false

  highlight_rolloff — true/false. When true, the renderer applies the calibrated rolloff curve for the highlight condition Gemini observed. Prevents blown-out whites and preserves detail in bright areas like windows, skin, and lights.
    true, false

  vibrance — true/false. When true, the renderer applies the calibrated vibrance boost for the color richness Gemini observed. Boosts under-saturated colors while protecting skin tones and already-vivid colors from over-processing.
    true, false

  teal_orange — applies the most recognizable cinematic color grade: shadows pushed toward teal/blue-green, skin tones pushed warm toward orange. Creates depth and contrast between the subject and background. Common in action films, music videos, and high-production TikTok content.
    none — no teal-orange split
    subtle — light push, adds depth without being obvious
    strong — pronounced split, a defining color statement

  caption_style — word-by-word captions synchronized to the speaker's voice:
    none, standard, bold_centered, minimal_bottom, animated_word, bold_white, bold_yellow, keyword_pop, box_caption

  caption_position — where captions are placed vertically: top, center, lower-third, bottom

  audio_denoise — true/false. When true, applies AI-based audio noise removal (arnndn) to the output. Strips background hiss, room tone, fan noise, and ambient rumble from the audio track. The result sounds like it was recorded in a treated studio rather than a bedroom or outdoor space. Captions uses this as a flagship feature called "Studio Sound."
    true, false

  beat_sync — true/false. A factual label, not a creative lever. Set beat_sync=true only if your cut timestamps actually land within ~0.15s of beat timestamps in the reference data. Beats do not move cuts — cuts are chosen on speech boundaries and scene changes first. After choosing all cuts on content grounds, check whether those timestamps happen to coincide with beats. If yes: beat_sync=true. If no: beat_sync=false. For music-only content, the pipeline pre-aligns cuts to beats and you receive a different prompt where beat_sync is always true.
    true, false

  outro — what happens after the last frame of the last clip:
    none — video ends immediately on the last frame
    fade_black — last clip gradually fades to black
    fade_white — last clip gradually fades to white

  background_music — choose one track filename from the library below, or "none" if the content works better without music.

  For most vibes, music is essential — pick the track that best matches the emotional tone and energy the user described. The track will be mixed under the speech at low volume with ducking, so it enhances rather than competes.

  Music library (pick the filename that best fits the vibe):
  {music_library_block}
  aspect_ratio — always "9:16"

Text overlays — text graphics displayed on specific clips:
  text — plain text only, no emojis
  position — top, center, or bottom
  appear_at_clip — which clip number the text appears on
  style — title (large, bold), callout (medium, emphasized), or cta (call-to-action styling)
  sfx_style — sound that plays when the text appears:
    none — silent appearance
    pop — quick bright snap
    ding — clean single-note bell
    typing — rapid keyboard clicks, gives text a "being typed" feel
    ching — cash register sound
    reverb_hit — impact with reverb tail
    shutter — camera shutter click

B-roll — stock footage clips overlaid briefly on the main video:
  keyword — search term for Pexels stock video API
  timestamp — when in the source video timeline the overlay starts (seconds)
  duration — how long the overlay is visible (1-3 seconds)

=== HOW THESE TOOLS LOOK AND SOUND ===

Transitions: On a phone screen, transitions occupy the 0.3-second window between clips. dissolve briefly shows both clips layered. fade passes through opacity to black or white. wipeleft/wiperight/wipeup/wipedown slides the incoming clip over the outgoing one. smoothleft/smoothright/smoothup/smoothdown are the same wipes with eased motion curves. zoomin magnifies the outgoing clip while revealing the incoming clip beneath it. fadeblack/fadewhite pass through a solid color between clips — fadewhite produces a bright white flash visible at full brightness on phone screens.

flash transition: A single frame is filled with pure white between the outgoing and incoming clip — an instant visual punch with no gradual fade. At 30fps this is one frame of white. On a phone screen at full brightness it reads as a sharp snap. Used to punctuate beats, emphasize an edit, or create high-energy rhythm. Pairs naturally with transition_sound=pop or thud.

glitch transition: The outgoing clip's last few frames are displaced horizontally in slices with RGB channel separation — the red, green, and blue channels are offset in opposite directions, creating a chromatic tear effect. The incoming clip cuts in hard after. On screen it reads as a digital disruption or signal break. Used for energy shifts, topic pivots, and high-intensity moments.

whip_left / whip_right: The outgoing clip's last frames are blurred with a strong horizontal directional smear — the image streaks in the direction of the whip before the incoming clip arrives. Creates the visual sensation of a fast camera pan between shots. Kinetic and physical-feeling. Frequently used in TikTok travel content, reaction edits, and fast-paced vlogs.

Transition sounds: These are short audio accents timed to the transition frame. swoosh is a fast air-swipe. thud is a punchy impact. shutter is a camera click. pop is a bright snap. ding is a single-note bell. reverb_hit is an impact with a tail that lingers. typing is rapid keyboard clicks. ching is a cash register sound. The sound plays during the 0.3-second transition window and blends with any audio already playing.

Freeze frame: The last frame of the clip is held as a still image for 0.3 seconds before the transition fires. The motion stops, the image hangs, then the cut happens. On screen this reads as a deliberate pause or emphasis beat — the action is frozen in place before moving on. Common for reactions, punchlines, or moments that deserve a visual breath.

Motion blur on transition: The outgoing clip's last frames receive a directional motion blur (boxblur on horizontal or vertical axis) before the cut. This makes the transition feel physically motivated — like the camera moved rather than the edit happened. Adds production value to any transition. The blur is applied to the last 5 frames of the outgoing clip and first 3 frames of the incoming clip.

Zoom: slow_in gradually scales the clip from 100% to 110% across its full duration — the subject slowly fills more of the frame. slow_out does the reverse. punch_in jumps quickly to 115% at the first 10 frames then holds. punch_out jumps quickly to 85% at the first 10 frames then holds. All zoom modes crop the edges of the frame to maintain 1080x1920.

Cut-zoom: At each sentence boundary within the clip, the framing alternates between normal and slightly zoomed-in. On a 1080px screen this creates the visual effect of a two-camera shoot from a single angle.

Speed: The speech pitch is preserved regardless of speed value. At 1.05–1.15x the change is imperceptible to most viewers. At 1.25x+ the motion is visibly faster. At 0.75x and below the motion is visibly slower and the voice lowers slightly in tempo.

Speed ramp: Creates non-linear acceleration within a single clip. hero_time compresses the first half of the clip and expands the second half into slow motion — whatever is happening at the midpoint of the clip becomes the lingering focal moment. bullet expands the first third into slow motion then compresses the rest into fast motion. flash_in compresses the opening frames then eases to normal pacing. flash_out plays at normal speed then compresses the final frames. montage alternates between fast and slow in four equal segments across the clip.

Beat sync: beat_sync is a truthful observation about your edit. It means your cut timestamps — chosen on speech boundaries and scene changes — happen to coincide with beat timestamps in the reference data. You do not move a cut to hit a beat. A cut that would land mid-sentence or mid-movement to chase a beat is a broken cut regardless of rhythmic alignment. Choose all cuts on content grounds first. Then check the beat list. If your timestamps land within ~0.15s of beats, set beat_sync=true. Otherwise false. For music-only content the pipeline pre-solves beat alignment before you see the video — you receive a different prompt where cut timestamps are pre-built and beat_sync is always true.

Audio denoise: arnndn AI neural audio denoising applied to the final output. Removes background hiss, room tone, fan noise, A/C hum, and ambient rumble from the speaker's audio. The result sounds like it was recorded with a professional microphone in a treated room rather than a phone in a bedroom or outdoor space. Captions markets this feature as "Studio Sound."

Color grade: color_intent is combined with the measured color baseline of the footage by the rendering system. The resulting grade is applied uniformly across all clips.

Vignette: A cosine-curve darkening applied radially from the center outward. light, medium, and strong control the angle of the falloff — stronger values begin the darkening closer to the center of the frame.

Sharpening: true/false. When true, the renderer reads the source_sharpness Gemini observed and selects the unsharp strength automatically — soft footage gets strong sharpening (1.2 luma strength), normal footage gets moderate (0.6), already-sharp footage gets a minimal pass (0.3). You cannot set the strength — only whether it runs.

Grain: Temporal uniform luma noise added on top of the final grade. subtle=noise strength 4, medium=9, heavy=16. The grain is animated frame-to-frame, producing living texture rather than a static overlay.

Denoise: true/false. When true, the renderer reads the noise_level Gemini observed and selects the hqdn3d strength automatically — high noise gets heavy denoising (5:5:8:8), medium noise gets moderate (3:3:5:5), low noise gets light (2:2:3:3). You cannot set the strength — only whether it runs.

Shadow lift: true/false. When true, the renderer reads the shadow_condition Gemini observed and selects the black-point lift automatically — crushed shadows get a high lift (9%), deep shadows get medium (5%), normal shadows get subtle (4%), already-lifted shadows get minimal (2%). You cannot set the level — only whether it runs.

Highlight rolloff: true/false. When true, the renderer reads the highlight_condition Gemini observed and selects the rolloff curve automatically — clipped footage gets a hard rolloff (compressed from 60% up), bright footage gets a soft rolloff (from 75%), normal footage gets a gentle touch (from 82%). You cannot set the curve — only whether it runs.

Vibrance: true/false. When true, the renderer reads the color_richness Gemini observed and selects the saturation multiplier automatically — flat footage gets 1.35x, muted gets 1.22x, normal gets 1.12x, already-vivid footage gets 1.06x. You cannot set the strength — only whether it runs.

Teal-orange: A colorbalance split where shadows are pushed toward blue-green and highlights/midtones are pushed warm toward orange. subtle produces a perceptible but natural-looking depth split. strong produces an unmistakable stylized grade where shadows are clearly teal and warm areas are clearly orange.

Cinematic bars: Two filled black rectangles drawn at the top and bottom of the 1080x1920 frame. The visible image area is narrowed to a 1080x459 horizontal band in the center of the frame, matching a 2.35:1 aspect ratio. The bars are composited on top of all other elements including captions and text overlays.

Captions: Rendered as ASS subtitle burn-in synchronized to word-level Deepgram timestamps. bold_white and bold_yellow use large outlined text. animated_word highlights each word as it is spoken. keyword_pop colorizes words from the caption_keywords list. box_caption draws a filled rectangle behind each word group.

Text overlays: drawtext rendered at the clip's output timecode. style title is 72px, callout is 56px, cta is 64px with a fade-in/out animation of 0.3–0.4 seconds. All text is white with a 5px black border.

B-roll: Stock footage clips from Pexels placed as full-frame overlays at the specified source timestamp. Overlays replace the main video for their full duration.

Outro: fade_black and fade_white apply a 1-second fade on the last clip's video and audio. The fade begins 1 second before the end of the last clip.

The "notes" field must be 50 words maximum. Be ruthlessly brief.


=== RESPONSE FORMAT ===

Respond with ONLY this JSON object:

{{
  "notes": "<50 words max. Key decisions only, no justification>",
  "color_intent": "<intent>",
  "background_music": "<track_filename or none>",
  "caption_style": "<style>",
  "caption_position": "<position>",
  "caption_keywords": [],
  "audio_ducking": false,
  "audio_denoise": <true|false>,
  "beat_sync": <true|false>,
  "outro": "<outro>",
  "aspect_ratio": "9:16",
  "vignette": "<level>",
  "sharpening": <true|false>,
  "grain": "<level>",
  "denoise": <true|false>,
  "cinematic_bars": <true|false>,
  "shadow_lift": <true|false>,
  "highlight_rolloff": <true|false>,
  "vibrance": <true|false>,
  "teal_orange": "<level>",
  "text_overlays": [
    {{ "text": "<text>", "position": "<position>", "appear_at_clip": <clip number>, "style": "<style>", "sfx_style": "<sfx>" }}
  ],
  "broll": [
    {{ "keyword": "<search term>", "timestamp": <seconds>, "duration": <1-3> }}
  ],
  "cuts": [
    {{ "source_start": <n>, "source_end": <n>, "transition_out": "<transition>", "transition_sound": "<sound>", "sfx_style": "<sfx>", "zoom": "<zoom>", "cut_zoom": <true|false>, "speed": <n>, "speed_ramp": "<ramp>", "freeze_frame": <true|false>, "motion_blur_transition": <true|false> }}
  ]
}}

=== WHO THE USER IS ===

The user is a content creator who either doesn't know how to edit or doesn't have time. They uploaded raw footage and chose a vibe because they want their content to look like they hired a professional editor. They will watch the output on their phone and compare it to what CapCut produces.

The user said: "{expanded_vibe}"

The user's vibe describes exactly what they want done to their video. Edit the video to match what they described — nothing more, nothing less. The tools and techniques you apply should be the ones the user's words call for. If their vibe doesn't reference a specific capability, they didn't ask for it.

=== THIS VIDEO ===

Duration: {duration:.2f}s
Content type: {content_type}
Visual character: {visual_character}
Strongest moments: {strongest_moments}
Weakest moments: {weakest_moments}{profile_block}{audio_block}
{hook_block}{pacing_block}

Color baseline (measured from the raw footage):
  {cb.get("assessment") or "No major exposure or white-balance issues detected."}
  Brightness: {cb.get("brightness", 0)}, Contrast: {cb.get("contrast", 1)}, Saturation: {cb.get("saturation", 1)}, Gamma: {cb.get("gamma", 1)}, Temperature: {cb.get("color_temperature", "neutral")}

Footage quality (Gemini directly observed the video — these are facts about the source material, not estimates):
{render_recs_block}

Frame layout:
  Subject: {frame_layout.get("subject_position", "unknown")}
  Existing overlays: {frame_overlay_locations}
  {"Captions are already burned into the video frames." if has_burned_captions else "No burned-in captions detected."}
  Open space for graphics: {frame_layout.get("free_zones", "unknown")}

Platform safe zones (9:16 vertical):
  Bottom 20% of frame is covered by TikTok/Reels/Shorts UI (username, caption text, like/comment/share buttons) — text placed here is hidden.
  Top 10% may be partially covered by status bar.
  Safe zone for text: middle 70% vertically.

=== SHOTS ===

{shots_block}

=== TRANSCRIPT ===

{speech_block}

=== SCENE FRAMES ===

Frame thumbnails with timestamps — the actual images from the video at each scene change.

=== REFERENCE DATA FOR YOUR CUTS ===

Scene changes detected by FFmpeg (reliable visual cut timestamps):
{scene_changes_block}

Speech boundaries detected by Deepgram (timestamps where sentences end with a natural pause):
{speech_boundaries_block}
{highlights_block}
{beat_block}

{tightened_block if tightened_block else tightened_fallback}

These are reference points for choosing your cuts. Scene change timestamps produce visually clean cuts because the image is already changing at that frame. Speech boundary timestamps produce audio-clean cuts because the speaker is pausing naturally. Cutting at other timestamps is valid when the footage calls for it — the pipeline will force keyframes at your chosen timestamps to ensure frame-perfect extraction.

B-roll keyword candidates from transcript:
{broll_candidates_block if broll_candidates_block else "  none"}

"""

    split_marker = "=== WHO THE USER IS ==="
    split_index = full_prompt.index(split_marker)
    static_prefix = full_prompt[:split_index].strip()
    dynamic_suffix = full_prompt[split_index:].strip()
    return static_prefix, dynamic_suffix


def extract_json(text):
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Empty Claude response")
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
    raise ValueError("Could not extract valid JSON from Claude response")


def generate_edit(analysis, transcript, vibe, expanded_vibe, scene_frames):
    print("[generate-edit] Building Claude prompt...", flush=True)
    content_mode = analysis.get("content_mode", "speech")
    if content_mode == "music_edit":
        print("[generate-edit] mode=music_edit — beat-aligned prompt", flush=True)
        static_prefix, dynamic_suffix = build_music_edit_prompt(analysis, expanded_vibe)
    else:
        # speech and speech_with_music both use build_prompt
        # speech_with_music gets extra beat context via the audio_block enrichment in build_prompt
        music_lines = []
        for fname, meta in MUSIC_LIBRARY.items():
            if fname == "none":
                continue
            music_lines.append(f"    {fname} — {meta['description']}")
        music_library_block = "\n".join(music_lines)

        static_prefix, dynamic_suffix = build_prompt(analysis, transcript, expanded_vibe, music_library_block)

    content_blocks = [
        {"type": "text", "text": static_prefix, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_suffix},
    ]

    if scene_frames:
        _is_music_edit = analysis.get("content_mode") == "music_edit"
        _frame_intro = (
            "\nHere are frame thumbnails from the video. Use them to assess the visual quality, "
            "color character, and strength of each clip when deciding which to keep, "
            "what transitions to use, and how to color grade."
            if _is_music_edit else
            "\nHere are frame thumbnails from the opening and scene-change moments. Use them as visual context "
            "when deciding transitions, zoom, cut-zoom, b-roll, text overlays, and color intent."
        )
        _frame_outro = (
            "\nUse these frames to assess clip quality and drive your color grade and transition choices."
            if _is_music_edit else
            "\nUse these frames to make shot-specific decisions. If a shot is a screen recording or demo, "
            "avoid unnecessary cut-zoom/text clutter. If framing and lighting are already strong, use a lighter touch."
        )
        content_blocks.append({"type": "text", "text": _frame_intro})
        for frame in scene_frames:
            if not frame.get("base64"):
                continue
            ts = float(frame.get("timestamp") or 0)
            content_blocks.append({"type": "text", "text": f"Frame at {ts:.1f}s:"})
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": frame.get("mediaType") or "image/jpeg",
                    "data": frame["base64"],
                },
            })
        content_blocks.append({"type": "text", "text": _frame_outro})

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print("[generate-edit] Calling Claude Sonnet...", flush=True)
    t = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0.4,
        messages=[{"role": "user", "content": content_blocks}],
    )
    print(f"[generate-edit] Claude complete in {time.time()-t:.1f}s", flush=True)
    usage = getattr(response, "usage", None) or {}
    cache_write = getattr(usage, "cache_creation_input_tokens", None) or (usage.get("cache_creation_input_tokens") if isinstance(usage, dict) else 0) or 0
    cache_read  = getattr(usage, "cache_read_input_tokens",     None) or (usage.get("cache_read_input_tokens")     if isinstance(usage, dict) else 0) or 0
    inp         = getattr(usage, "input_tokens",                None) or (usage.get("input_tokens")                if isinstance(usage, dict) else 0) or 0
    print(f"[claude] Cache: write={cache_write} read={cache_read} input={inp}", flush=True)

    response_text = response.content[0].text
    print(f"[generate-edit] RAW RESPONSE:\n{response_text}\n[generate-edit] END RESPONSE", flush=True)

    edit_plan = extract_json(response_text)

    raw_cuts = edit_plan.get("cuts") or edit_plan.get("clips") or []
    if not raw_cuts:
        raise ValueError("Claude response missing cuts array")

    video_duration = float(analysis.get("duration") or 0)

    # music_edit: verify Claude used the pre-built timestamps; correct any invented values
    if analysis.get("content_mode") == "music_edit":
        beat_clips = analysis.get("beat_aligned_clips") or []
        if beat_clips and raw_cuts:
            valid_pairs = {
                (round(c["source_start"] * 1000), round(c["source_end"] * 1000))
                for c in beat_clips
            }
            corrected = []
            for cut in raw_cuts:
                key = (
                    round(float(cut.get("source_start") or 0) * 1000),
                    round(float(cut.get("source_end") or 0) * 1000),
                )
                if key in valid_pairs:
                    corrected.append(cut)
                else:
                    cs = float(cut.get("source_start") or 0)
                    nearest = min(beat_clips, key=lambda c: abs(c["source_start"] - cs))
                    print(
                        f"[generate-edit] music_edit: corrected invented timestamp "
                        f"{cs:.3f}s → {nearest['source_start']:.3f}s",
                        flush=True
                    )
                    corrected.append({**cut,
                        "source_start": nearest["source_start"],
                        "source_end": nearest["source_end"],
                    })
            raw_cuts = corrected
        edit_plan["beat_sync"] = True

    validated_cuts = []
    for i, cut in enumerate(raw_cuts):
        src_start = float(cut.get("source_start") or 0)
        src_end   = float(cut.get("source_end") or 0)
        if src_start >= src_end:
            raise ValueError(f"Cut {i}: source_start ({src_start}) >= source_end ({src_end})")
        if src_start < 0:
            raise ValueError(f"Cut {i}: source_start is negative")
        if video_duration > 0 and src_end > video_duration + 0.5:
            raise ValueError(f"Cut {i}: source_end ({src_end}) exceeds video duration ({video_duration})")
        if i > 0 and src_start < validated_cuts[i-1]["source_start"]:
            raise ValueError(f"Cut {i}: not in chronological order")
        validated_cuts.append({**cut, "source_start": src_start, "source_end": src_end, "clip": i+1})

    edit_plan.setdefault("background_music", "none")
    edit_plan.setdefault("caption_style", "none")
    edit_plan.setdefault("caption_position", "lower-third")
    edit_plan.setdefault("audio_ducking", False)
    edit_plan.setdefault("audio_denoise", False)
    edit_plan.setdefault("beat_sync", False)
    edit_plan.setdefault("outro", "none")
    edit_plan.setdefault("aspect_ratio", "original")
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
    # Validate background_music against known library — fall back to none if unknown
    raw_music = str(edit_plan.get("background_music") or "none").strip()
    edit_plan["background_music"] = raw_music if raw_music in MUSIC_LIBRARY else "none"
    edit_plan["audio_ducking"] = False

    for bool_field in ("sharpening", "denoise", "shadow_lift", "highlight_rolloff", "vibrance",
                       "cinematic_bars", "audio_denoise", "beat_sync"):
        v = edit_plan.get(bool_field)
        if isinstance(v, str):
            edit_plan[bool_field] = v.strip().lower() in ("true", "1", "yes")
        else:
            edit_plan[bool_field] = bool(v)

    valid_grain      = {"none", "subtle", "medium", "heavy"}
    valid_teal       = {"none", "subtle", "strong"}
    valid_vignette   = {"none", "light", "medium", "strong"}
    valid_transitions = {
        "none","fade","fadeblack","fadewhite","dissolve",
        "wipeleft","wiperight","wipeup","wipedown",
        "smoothleft","smoothright","smoothup","smoothdown",
        "zoomin","flash","glitch","whip_left","whip_right",
    }
    if edit_plan.get("grain") not in valid_grain:
        edit_plan["grain"] = "none"
    if edit_plan.get("teal_orange") not in valid_teal:
        edit_plan["teal_orange"] = "none"
    if edit_plan.get("vignette") not in valid_vignette:
        edit_plan["vignette"] = "none"

    final_cuts = []
    for clip_entry in validated_cuts:
        transition = str(clip_entry.get("transition_out") or "").lower()
        transition_out = transition if transition in valid_transitions else "none"
        speed = max(0.25, min(4.0, float(clip_entry.get("speed") or 1.0)))
        valid_ramps = {"none","hero_time","bullet","flash_in","flash_out","montage"}
        speed_ramp = str(clip_entry.get("speed_ramp") or "none").lower()
        if speed_ramp not in valid_ramps:
            speed_ramp = "none"
        freeze_raw = clip_entry.get("freeze_frame")
        freeze_frame = freeze_raw.strip().lower() in ("true","1","yes") if isinstance(freeze_raw, str) else bool(freeze_raw)
        mb_raw = clip_entry.get("motion_blur_transition")
        motion_blur_transition = mb_raw.strip().lower() in ("true","1","yes") if isinstance(mb_raw, str) else bool(mb_raw)
        final_cuts.append({
            "source_start":           clip_entry["source_start"],
            "source_end":             clip_entry["source_end"],
            "transition_out":         transition_out,
            "transition_sound":       clip_entry.get("transition_sound") or "none",
            "sfx_style":              clip_entry.get("sfx_style") or "none",
            "zoom":                   clip_entry.get("zoom") or "none",
            "cut_zoom":               bool(clip_entry.get("cut_zoom")),
            "speed":                  speed,
            "speed_ramp":             speed_ramp,
            "freeze_frame":           freeze_frame,
            "motion_blur_transition": motion_blur_transition,
            "speed_segments":         [],
        })

    baseline = analysis.get("color_baseline") or {}
    intent = normalize_intent(edit_plan.get("color_intent") or "none")
    edit_plan["color_intent"] = intent
    edit_plan["color_grade"] = build_color_grade(baseline, intent)
    edit_plan["cuts"] = final_cuts
    if "clips" in edit_plan:
        del edit_plan["clips"]

    if final_cuts:
        edit_plan["target_duration"] = final_cuts[-1]["source_end"] - final_cuts[0]["source_start"]

    video_duration = float(analysis.get("duration") or 0)
    if video_duration > 0:
        total_clip_duration = sum(max(0, c["source_end"] - c["source_start"]) for c in final_cuts)
        coverage_ratio = total_clip_duration / video_duration
        if coverage_ratio < 0.3:
            print(f"[generate-edit] WARNING: Claude's clips only cover {coverage_ratio*100:.0f}% of the video ({total_clip_duration:.1f}s of {video_duration:.1f}s)", flush=True)

    print(f"[generateEdit] Final cuts ({len(final_cuts)} clips):", flush=True)
    for cut in final_cuts:
        print(f"  {cut['source_start']} -> {cut['source_end']} [{cut['transition_out']}]", flush=True)
    cg = edit_plan["color_grade"]
    print(f"  Created {len(final_cuts)} cuts, intent={intent}, color: brightness={cg['brightness']} contrast={cg['contrast']} sat={cg['saturation']} gamma={cg['gamma']} temp={cg['color_temperature']}", flush=True)

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
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
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
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": pexels_key},
            params={"query": keyword, "per_page": 5, "orientation": "portrait", "size": "medium"},
            timeout=15,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos") or []
        if not videos:
            print(f"[broll] No Pexels results for '{keyword}'", flush=True)
            return None
        chosen_url = None
        for video in videos:
            for vf in (video.get("video_files") or []):
                w = vf.get("width") or 0
                h = vf.get("height") or 0
                dur = float(video.get("duration") or 0)
                if h >= w and dur >= duration_needed and vf.get("link"):
                    chosen_url = vf["link"]
                    break
            if chosen_url:
                break
        if not chosen_url:
            for vf in (videos[0].get("video_files") or []):
                if vf.get("link"):
                    chosen_url = vf["link"]
                    break
        if not chosen_url:
            print(f"[broll] No usable file for '{keyword}'", flush=True)
            return None
        safe_kw = re.sub(r"[^a-z0-9]", "_", keyword.lower())[:30]
        dest = os.path.join(work_dir, f"broll_{safe_kw}.mp4")
        dl = requests.get(chosen_url, stream=True, timeout=30)
        dl.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in dl.iter_content(65536):
                f.write(chunk)
        print(f"[broll] Downloaded '{keyword}' -> {dest}", flush=True)
        return dest
    except Exception as e:
        print(f"[broll] Failed to fetch '{keyword}': {e}", flush=True)
        return None


def composite_broll(output_path, broll_entries, work_dir):
    """Overlay b-roll clips on the rendered output in a single FFmpeg pass. Overwrites output_path."""
    valid = [e for e in broll_entries if e.get("local_path") and os.path.exists(e["local_path"])]
    if not valid:
        return
    tmp_out = output_path + ".broll_tmp.mp4"
    input_args = ["-i", output_path]
    for entry in valid:
        input_args += ["-i", entry["local_path"]]
    filter_parts = []
    for i, entry in enumerate(valid):
        idx = i + 1
        filter_parts.append(
            f"[{idx}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1[bv{i}]"
        )
    prev = "0:v"
    for i, entry in enumerate(valid):
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
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        tmp_out,
    ])
    os.replace(tmp_out, output_path)
    print(f"[broll] Composited {len(valid)} b-roll clip(s) onto output", flush=True)


def apply_filler_jump_cuts(cuts, deepgram_words):
    """
    Split Claude's clips at ALWAYS_FILLER word boundaries (um, uh, hmm, etc.)
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

    normalize_args = [
        "-y","-i",source_path,
        "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
        "-r","30","-vsync","cfr","-pix_fmt","yuv420p",
        "-c:v","libx264","-preset","ultrafast","-crf","23",
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
        "-c:v","libx264","-preset","ultrafast","-crf","28",
        "-force_key_frames",kf_str,
        "-r","30","-vsync","cfr","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k","-threads","1",
        keyframed_path,
    ])
    return keyframed_path


def pre_split_clips(keyframed_path, cuts, work_dir):
    clip_files = []
    for i, cut in enumerate(cuts):
        clip_start = round(float(cut["source_start"])*1000)/1000
        clip_dur   = round((float(cut["source_end"]) - float(cut["source_start"]))*1000)/1000
        if clip_dur <= 0:
            clip_files.append(None)
            continue
        clip_path = os.path.join(work_dir, f"clip_{i}.mp4")
        run_ffmpeg(["-y","-ss",str(clip_start),"-i",keyframed_path,"-t",str(clip_dur),"-c","copy",clip_path])
        clip_files.append(clip_path)
    try:
        os.unlink(keyframed_path)
    except Exception:
        pass
    return clip_files


def get_atempo_filter(speed):
    safe = max(0.25, min(4.0, float(speed) or 1.0))
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


def is_hard_cut(transition):
    t = str(transition or "").strip().lower()
    return not t or t in ("none", "clean_cut")


def build_video_filter_chain(color_grade, source_res, edit_plan=None):
    ep = edit_plan or {}
    fq = (ep.get("analysis_data") or {}).get("footage_quality") or {}
    filters = []

    if ep.get("denoise"):
        noise = fq.get("noise_level", "low")
        denoise_params = {
            "none":   "1:1:2:2",
            "low":    "2:2:3:3",
            "medium": "3:3:5:5",
            "high":   "5:5:8:8",
        }.get(noise, "2:2:3:3")
        filters.append(f"hqdn3d={denoise_params}")
        print(f"[render] denoise: noise_level={noise} → hqdn3d={denoise_params}", flush=True)

    b = clamp(float(color_grade.get("brightness") or 0), -0.3, 0.3)
    c = clamp(float(color_grade.get("contrast") or 1), 0.5, 2.0)
    s = clamp(float(color_grade.get("saturation") or 1), 0.5, 2.0)
    g = clamp(float(color_grade.get("gamma") or 1), 0.5, 2.0)
    eq_parts = []
    if b != 0:   eq_parts.append(f"brightness={b:.4f}")
    if c != 1:   eq_parts.append(f"contrast={c:.4f}")
    if s != 1:   eq_parts.append(f"saturation={s:.4f}")
    if g != 1:   eq_parts.append(f"gamma={g:.4f}")
    if eq_parts:
        filters.append(f"eq={':'.join(eq_parts)}")

    temp = color_grade.get("color_temperature") or "neutral"
    temp_filter = TEMPERATURE_FILTERS.get(temp)
    if temp_filter:
        filters.append(temp_filter)

    if ep.get("shadow_lift"):
        shadow_cond = fq.get("shadow_condition", "normal")
        lift_curves = {
            "crushed": "curves=r='0/0.09 1/1':g='0/0.09 1/1':b='0/0.09 1/1'",
            "deep":    "curves=r='0/0.05 1/1':g='0/0.05 1/1':b='0/0.05 1/1'",
            "normal":  "curves=r='0/0.04 1/1':g='0/0.04 1/1':b='0/0.04 1/1'",
            "lifted":  "curves=r='0/0.02 1/1':g='0/0.02 1/1':b='0/0.02 1/1'",
        }.get(shadow_cond, "curves=r='0/0.04 1/1':g='0/0.04 1/1':b='0/0.04 1/1'")
        filters.append(lift_curves)
        print(f"[render] shadow_lift: shadow_condition={shadow_cond} → lift applied", flush=True)

    if ep.get("highlight_rolloff"):
        hl_cond = fq.get("highlight_condition", "normal")
        rolloff_curves = {
            "clipped": "curves=r='0/0 0.6/0.58 0.85/0.80 1/0.88':g='0/0 0.6/0.58 0.85/0.80 1/0.88':b='0/0 0.6/0.58 0.85/0.80 1/0.88'",
            "bright":  "curves=r='0/0 0.75/0.72 1/0.95':g='0/0 0.75/0.72 1/0.95':b='0/0 0.75/0.72 1/0.95'",
            "normal":  "curves=r='0/0 0.82/0.80 1/0.97':g='0/0 0.82/0.80 1/0.97':b='0/0 0.82/0.80 1/0.97'",
            "dark":    "curves=r='0/0 0.88/0.87 1/0.98':g='0/0 0.88/0.87 1/0.98':b='0/0 0.88/0.87 1/0.98'",
        }.get(hl_cond, "curves=r='0/0 0.82/0.80 1/0.97':g='0/0 0.82/0.80 1/0.97':b='0/0 0.82/0.80 1/0.97'")
        filters.append(rolloff_curves)
        print(f"[render] highlight_rolloff: highlight_condition={hl_cond} → rolloff applied", flush=True)

    if ep.get("vibrance"):
        richness = fq.get("color_richness", "normal")
        vibrance_hue = {
            "flat":   "hue=s=1.35",
            "muted":  "hue=s=1.22",
            "normal": "hue=s=1.12",
            "vivid":  "hue=s=1.06",
        }.get(richness, "hue=s=1.12")
        filters.append(vibrance_hue)
        print(f"[render] vibrance: color_richness={richness} → {vibrance_hue}", flush=True)

    teal_orange = str(ep.get("teal_orange") or "none").lower()
    if teal_orange == "subtle":
        filters.append("colorbalance=rs=-0.08:gs=0.04:bs=0.10:rm=0.04:gm=0:bm=-0.04:rh=0.05:gh=0.01:bh=-0.05")
    elif teal_orange == "strong":
        filters.append("colorbalance=rs=-0.16:gs=0.06:bs=0.18:rm=0.07:gm=0:bm=-0.07:rh=0.09:gh=0.02:bh=-0.09")

    if ep.get("sharpening"):
        src_sharp = fq.get("source_sharpness", "normal")
        unsharp_params = {
            "soft":   "unsharp=7:7:1.2:5:5:0.0",
            "normal": "unsharp=5:5:0.6:3:3:0.0",
            "sharp":  "unsharp=3:3:0.3:3:3:0.0",
        }.get(src_sharp, "unsharp=5:5:0.6:3:3:0.0")
        filters.append(unsharp_params)
        print(f"[render] sharpening: source_sharpness={src_sharp} → {unsharp_params}", flush=True)

    grain = str(ep.get("grain") or "none").lower()
    if grain == "subtle":
        filters.append("noise=c0s=4:c0f=t+u")
    elif grain == "medium":
        filters.append("noise=c0s=9:c0f=t+u")
    elif grain == "heavy":
        filters.append("noise=c0s=16:c0f=t+u")

    return ",".join(filters) if filters else "null"


def project_words_to_output(transcript, cuts, effective_durations):
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        speed   = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        for w in words:
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            if we <= c_start or ws >= c_end:
                continue
            local_s = (max(ws, c_start) - c_start) / speed
            local_e = (min(we, c_end) - c_start) / speed
            projected.append({
                "start": round((output_cursor + local_s)*1000)/1000,
                "end":   round((output_cursor + local_e)*1000)/1000,
                "word":  w.get("punctuated_word") or w.get("word") or "",
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        overlap = TRANSITION_DURATION if i < len(cuts)-1 and not is_hard_cut(cut.get("transition_out")) else 0
        output_cursor = round((output_cursor + dur - overlap)*1000)/1000
    return [w for w in projected if w["end"] > w["start"]]


def format_ass_time(seconds):
    s = max(0, float(seconds or 0))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    cs = round((s % 1) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def generate_subtitle_file(transcript, caption_style, cuts, effective_durations, output_res, caption_position, caption_keywords, work_dir):
    words = project_words_to_output(transcript, cuts, effective_durations)
    if not words:
        return None

    w = output_res.get("width") or 1080
    h = output_res.get("height") or 1920

    # Vertical position margin — how far from the bottom (or top) edge in pixels
    pos_margin = {"top": 1650, "center": 900, "lower-third": 300, "bottom": 80}
    margin_v = pos_margin.get(caption_position or "lower-third", 300)

    styles_map = {
        "standard":       {"fontsize": 44, "fontname": "Montserrat",           "bold": 0, "alignment": 2},
        "bold_centered":  {"fontsize": 58, "fontname": "Montserrat Black",     "bold": 0, "alignment": 5},
        "minimal_bottom": {"fontsize": 36, "fontname": "Montserrat",           "bold": 0, "alignment": 2},
        "animated_word":  {"fontsize": 54, "fontname": "Montserrat ExtraBold", "bold": 0, "alignment": 5},
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
        "standard":       ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "bold_centered":  ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "minimal_bottom": ("&H00FFFFFF", "&H0000CCFF", "&HA0000000", 3, 0, 0,  1.0),
        "animated_word":  ("&H00FFFFFF", "&H0000FFFF", "&H90000000", 3, 0, 0,  1.2),
        "bold_white":     ("&H00FFFFFF", "&H00FFFFFF", "&H90000000", 3, 0, 0,  1.2),
        "bold_yellow":    ("&H0000FFFF", "&H00FFFFFF", "&H90000000", 3, 0, 0,  1.2),
        "keyword_pop":    ("&H00FFFFFF", "&H0000FF00", "&H90000000", 3, 0, 0,  1.2),
        "box_caption":    ("&H00FFFFFF", "&H0000FFFF", "&HB0000000", 3, 0, 0,  1.0),
    }

    style_meta = styles_map.get(caption_style, styles_map["standard"])
    font_name = style_meta["fontname"]
    fontsize = style_meta["fontsize"]
    bold = style_meta["bold"]
    alignment = style_meta["alignment"]

    cfg = STYLE_CONFIGS.get(caption_style, STYLE_CONFIGS["standard"])
    primary, secondary, back_c, border_style, outline_w, shadow, spacing = cfg

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fontsize},{primary},{secondary},&H00000000,{back_c},{bold},0,0,0,100,100,{spacing},0,{border_style},{outline_w},{shadow},{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

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
                    parts.append(f"{{\\kf{dur_cs}}}{{\\1c{col}}}{wd['word']} ")
                text = "".join(parts).rstrip()
                ass_lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
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


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None):
    n = len(cuts)
    source_res = probe_resolution(source_path)
    kf_timestamps = [float(c["source_start"]) for c in cuts]
    keyframed_path = create_keyframed_source(source_path, kf_timestamps, work_dir)
    clip_files = pre_split_clips(keyframed_path, cuts, work_dir)

    if len(clip_files) != n:
        raise RuntimeError(f"Pre-split mismatch: expected {n}, got {len(clip_files)}")

    color_grade = edit_plan.get("color_grade") or {}
    color_filter_str = build_video_filter_chain(color_grade, source_res, edit_plan)
    has_burned_captions = bool(
        (edit_plan.get("analysis_data") or {})
        .get("frame_layout", {})
        .get("existing_overlays", {})
        .get("has_burned_captions")
    )

    input_args = []
    source_durations = []
    effective_durations = []

    for i, cut in enumerate(cuts):
        nominal_dur = round((float(cut["source_end"]) - float(cut["source_start"]))*1000)/1000
        probed = probe_duration(clip_files[i])
        src_dur = round((probed if probed else nominal_dur)*1000)/1000
        speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        eff_dur = round((src_dur / speed)*1000)/1000

        input_args += ["-analyzeduration","5000000","-probesize","5000000","-i",clip_files[i]]
        source_durations.append(src_dur)
        effective_durations.append(eff_dur)
        print(f"[ffmpeg] Input {i}: {cut['source_start']:.1f}s->{cut['source_end']:.1f}s (src={src_dur:.3f}s, eff={eff_dur:.3f}s @ {speed}x)", flush=True)

    video_filters = []
    audio_filters = []

    for i, cut in enumerate(cuts):
        speed = max(0.25, min(4.0, float(cut.get("speed") or 1.0)))
        zoom = str(cut.get("zoom") or "none")
        if has_burned_captions and zoom in ["punch_in","punch_out"]:
            zoom = "slow_in" if zoom == "punch_in" else "slow_out"

        eff_dur = effective_durations[i]
        fps = 30
        total_frames = max(1, round(eff_dur * fps))
        zoom_max = 1.07 if has_burned_captions else 1.14

        zoom_filter = None
        if zoom == "slow_in":
            # Smoothstep easing: t*t*(3-2*t) — ease in AND out, not linear
            tf = max(1, total_frames)
            zoom_range = zoom_max - 1.0
            zoom_filter = (
                f"scale=w='trunc(iw*(1.0+{zoom_range:.4f}*(n/{tf})*(n/{tf})*(3-2*(n/{tf})))/2)*2'"
                f":h='trunc(ih*(1.0+{zoom_range:.4f}*(n/{tf})*(n/{tf})*(3-2*(n/{tf})))/2)*2'"
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

        v_chain = ["settb=AVTB","fps=30"]

        speed_ramp = str(cut.get("speed_ramp") or "none").lower()
        if speed_ramp != "none" and speed_ramp in {"hero_time","bullet","flash_in","flash_out","montage"}:
            tf = max(1, total_frames)
            if speed_ramp == "hero_time":
                expr = f"if(lt(N\\,{tf//2})\\,PTS*0.5\\,{tf//2}*TB/30+({tf//2}*TB+(N-{tf//2})*TB)*2.5)"
                v_chain.append(f"setpts='if(lt(N\\,{tf//2})\\,PTS*0.5\\,{tf//4*1.0/30:.6f}+(PTS-{tf//2*1.0/30:.6f})*2.5)'")
            elif speed_ramp == "bullet":
                v_chain.append(f"setpts='if(lt(N\\,{tf//3})\\,PTS*2.5\\,{tf//3*2.5/30:.6f}+(PTS-{tf//3*1.0/30:.6f})*0.7)'")
            elif speed_ramp == "flash_in":
                v_chain.append(f"setpts='if(lt(N\\,{tf//3})\\,PTS*0.4\\,{tf//3*0.4/30:.6f}+(PTS-{tf//3*1.0/30:.6f})*1.0)'")
            elif speed_ramp == "flash_out":
                v_chain.append(f"setpts='if(lt(N\\,{tf*2//3})\\,PTS*1.0\\,{tf*2//3*1.0/30:.6f}+(PTS-{tf*2//3*1.0/30:.6f})*0.4)'")
            elif speed_ramp == "montage":
                q = tf // 4
                v_chain.append(
                    f"setpts='if(lt(N\\,{q})\\,PTS*0.5"
                    f"\\,if(lt(N\\,{2*q})\\,{q*0.5/30:.6f}+(PTS-{q*1.0/30:.6f})*2.0"
                    f"\\,if(lt(N\\,{3*q})\\,{q*0.5/30+q*2.0/30:.6f}+(PTS-{2*q*1.0/30:.6f})*0.5"
                    f"\\,{q*0.5/30+q*2.0/30+q*0.5/30:.6f}+(PTS-{3*q*1.0/30:.6f})*2.0)))'"
                )
            v_chain.append("fps=30")

        if speed != 1.0:
            v_chain.append(f"setpts={1.0/speed:.4f}*PTS")
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

        motion_blur_transition = bool(cut.get("motion_blur_transition"))
        if motion_blur_transition and i < n-1:
            v_chain.append(f"boxblur=luma_radius='if(gt(t\\,{max(0,eff_dur-0.17):.3f})\\,8\\,0)':luma_power=1:chroma_radius=0:chroma_power=0")
            print(f"[render] clip {i}: motion_blur_transition=true", flush=True)

        if outro_filter:
            v_chain.append(outro_filter)

        video_filters.append(f"[{i}:v]{','.join(v_chain)}[v{i}]")

        a_chain = ["asetpts=PTS-STARTPTS","afftdn=nr=10:nf=-25"]
        if speed != 1.0:
            a_chain.append(get_atempo_filter(speed))
        if i == n-1 and outro != "none":
            fade_start = max(0, eff_dur - 1.0)
            a_chain.append(f"afade=t=out:st={fade_start:.3f}:d=1.0")
        audio_filters.append(f"[{i}:a]{','.join(a_chain)}[a{i}]")

    # ── SFX collection ───────────────────────────────────────────────────────
    sfx_input_args   = []
    sfx_filter_strs  = []
    sfx_audio_labels = []
    extra_input_index = n

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

    _clip_ranges = get_output_clip_ranges(cuts, effective_durations)
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
        transition = str(cuts[i-1].get("transition_out") or "none").lower()
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
            transition_filters.append(f"[{tl_video}][v{i}]concat=n=2:v=1:a=0[{out_v_raw}]")
            transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
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

    caption_style = str(edit_plan.get("caption_style") or "none")
    if caption_style != "none":
        ass_path = generate_subtitle_file(
            transcript, caption_style, cuts, effective_durations,
            {"width": 1080, "height": 1920},
            edit_plan.get("caption_position") or "lower-third",
            edit_plan.get("caption_keywords") or [],
            work_dir,
        )
        if ass_path:
            escaped = ass_path.replace("\\","\\\\").replace(":","\\:").replace("'","\\'")
            post_filters.append(f"{video_out}subtitles='{escaped}':fontsdir=/assets/fonts[video_captioned]")
            video_out = "[video_captioned]"

    text_overlays = edit_plan.get("text_overlays") or []
    if text_overlays:
        clip_ranges = get_output_clip_ranges(cuts, effective_durations)
        for i, overlay in enumerate(text_overlays):
            clip_idx = int(overlay.get("appear_at_clip") or 0) - 1
            if clip_idx < 0 or clip_idx >= len(clip_ranges):
                continue
            raw_text = str(overlay.get("text") or "")
            text = re.sub(r"[^\x00-\x7F]","",raw_text).strip()
            if not text:
                continue
            text = text.replace("'","").replace('"',"").replace("\\","").replace(":","\\:").replace(",","\\,")
            start = clip_ranges[clip_idx]["start"]
            end   = clip_ranges[clip_idx]["end"]
            style = str(overlay.get("style") or "callout")
            char_count = len(text)
            base_size = 72 if style == "title" else (64 if style == "cta" else 56)
            if char_count <= 18:       font_size = base_size
            elif char_count <= 25:     font_size = round(base_size * 0.85)
            elif char_count <= 35:     font_size = round(base_size * 0.70)
            else:                      font_size = round(base_size * 0.60)
            pos = str(overlay.get("position") or "center")
            y_expr = "250" if pos == "top" else ("(h-th)/2" if pos == "center" else str(max(0, 1920-350)))
            anim_in = 0.4 if style == "cta" else 0.3
            anim_out = 0.3
            end_t = max(start + 0.8, end)
            alpha_expr = f"if(lt(t\\,{(start+anim_in):.3f})\\,(t-{start:.3f})/{anim_in}\\,if(lt(t\\,{(end_t-anim_out):.3f})\\,1\\,if(lt(t\\,{end_t:.3f})\\,({end_t:.3f}-t)/{anim_out}\\,0)))"
            out_label = f"[video_overlay_{i}]"
            _font_clause = (
                f":fontfile='{OVERLAY_FONT_PATH}'"
                if os.path.exists(OVERLAY_FONT_PATH)
                else ""
            )
            post_filters.append(
                f"{video_out}drawtext=text='{text}':fontsize={font_size}:fontcolor=white"
                f"{_font_clause}"
                f":x=(w-tw)/2:y={y_expr}:alpha='{alpha_expr}'"
                f":borderw=5:bordercolor=black:enable='between(t\\,{start:.3f}\\,{end_t:.3f})'{out_label}"
            )
            video_out = out_label

    if edit_plan.get("cinematic_bars"):
        bar_h = int((1920 - int(1080 / 2.35)) / 2)
        bars_label = f"[video_bars]"
        post_filters.append(
            f"{video_out}drawbox=x=0:y=0:w=1080:h={bar_h}:color=black:t=fill,"
            f"drawbox=x=0:y={1920-bar_h}:w=1080:h={bar_h}:color=black:t=fill{bars_label}"
        )
        video_out = bars_label

    audio_out = f"[{tl_audio}]"

    if sfx_audio_labels:
        _n_inputs   = len(sfx_audio_labels) + 1
        _sfx_inputs = audio_out + "".join(sfx_audio_labels)
        post_filters.append(
            f"{_sfx_inputs}amix=inputs={_n_inputs}:duration=first:dropout_transition=2[audio_sfx_mixed]"
        )
        audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio", flush=True)

    audio_denoise = bool(edit_plan.get("audio_denoise"))
    arnndn_filter = ""
    if audio_denoise:
        if os.path.exists(_RNNOISE_MODEL_PATH):
            arnndn_filter = f"arnndn=m={_RNNOISE_MODEL_PATH},"
            print(f"[render] audio_denoise=true — arnndn AI noise removal enabled", flush=True)
        else:
            print(f"[render] audio_denoise=true but model not found at {_RNNOISE_MODEL_PATH} — skipping", flush=True)
    post_filters.append(
        f"{audio_out}{arnndn_filter}highpass=f=80,lowpass=f=12000,"
        f"equalizer=f=2800:t=q:w=1.5:g=3,"
        f"equalizer=f=200:t=q:w=0.8:g=1.5,"
        f"acompressor=threshold=-20dB:ratio=3:attack=5:release=50:makeup=2,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11,"
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
            music_input_idx = n + len(sfx_input_args) // 2
            input_args += ["-stream_loop", "-1", "-i", music_path]
            total_duration = sum(effective_durations)
            fade_out_start = max(0, total_duration - 2.0)
            music_vol = 0.18 if any(
                str(cut.get("speed") or 1.0) != "1.0" or cut.get("zoom") != "none"
                for cut in cuts
            ) else 0.22
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

    encode_args = [
        "-c:v","libx264","-preset","fast","-crf","23",
        "-b:v","6M","-maxrate","8M","-bufsize","16M",
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

    print(f"[ffmpeg] Rendering: {n} clips, ~{running_dur:.1f}s output (captions={caption_style}, overlays={len(text_overlays)})", flush=True)

    try:
        run_ffmpeg(args)
    finally:
        for cf in clip_files:
            if cf and os.path.exists(cf):
                try:
                    os.unlink(cf)
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
    if "Empty Claude response" in msg or "valid JSON from Claude" in msg:
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
            f"{app_url}/api/runpod-progress",
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
        cached_analysis = input_data.get("cached_analysis")

        work_dir    = tempfile.mkdtemp(prefix=f"promptly-{job_id}-")
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id}: \"{vibe}\"", flush=True)
        print(f"{'='*80}", flush=True)

        # Step 1 — Download
        send_progress(job_id, "download", 5, "Downloading your video...", app_url)
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
        send_progress(job_id, "normalize", 12, "Preparing your video...", app_url)
        print("[pipeline] step=normalize", flush=True)
        source_path = normalize_source_video(source_path, work_dir)

        # ── Parallel group 0: vibe expansion — no video dep, start immediately ─────
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as vibe_executor:
            vibe_future = vibe_executor.submit(expand_vibe_intent, vibe)

            # Steps 1+2 (download + normalize) already done — source_path is ready

            # ── Parallel group 1: Gemini / scene+beat / transcription ──────────────
            # All three need only source_path. Gemini dominates (~18s); others finish inside.
            send_progress(job_id, "analysis", 20, "Analyzing your video with AI...", app_url)
            print("[pipeline] step=parallel_analysis (gemini + scene/beat + transcription)", flush=True)
            t_parallel = time.time()

            def _run_gemini():
                if cached_analysis:
                    print("[pipeline] analysis: cache HIT", flush=True)
                    return normalize_analysis(cached_analysis) if isinstance(cached_analysis, dict) else cached_analysis
                print("[pipeline] analysis: Gemini start", flush=True)
                t = time.time()
                result = run_gemini_analysis(source_path)
                print(f"[pipeline] Gemini complete in {time.time()-t:.1f}s", flush=True)
                return result

            def _run_scene_and_beat():
                t = time.time()
                cuts = detect_scene_cuts(source_path)
                print(f"[pipeline] scene detection complete in {time.time()-t:.1f}s ({len(cuts)} cuts)", flush=True)
                t = time.time()
                beats = detect_beats(source_path)
                print(f"[pipeline] beat detection complete in {time.time()-t:.1f}s ({len(beats)} beats)", flush=True)
                return cuts, beats

            def _run_transcription():
                t = time.time()
                result = transcribe_audio(source_path)
                words = result.get("words") or []
                print(f"[pipeline] transcription complete in {time.time()-t:.1f}s ({len(words)} words)", flush=True)
                return result

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as analysis_executor:
                f_gemini     = analysis_executor.submit(_run_gemini)
                f_scene_beat = analysis_executor.submit(_run_scene_and_beat)
                f_transcribe = analysis_executor.submit(_run_transcription)

                analysis                     = f_gemini.result()
                visual_cuts, beat_timestamps = f_scene_beat.result()
                transcript                   = f_transcribe.result()

            print(f"[pipeline] parallel analysis complete in {time.time()-t_parallel:.1f}s", flush=True)

            deepgram_words = transcript.get("words") or []
            analysis["visual_cuts"]     = visual_cuts
            analysis["beat_timestamps"] = beat_timestamps

            # Step 6 — Build speech from Deepgram
            speech_result = build_speech_from_deepgram(deepgram_words, float(analysis.get("duration") or 0))
            analysis["speech"] = speech_result["speech"]
            safe_cut_points = speech_result["safe_cut_points"]
            for cut_time in visual_cuts:
                if not any(abs(cp["time"] - cut_time) < 0.5 for cp in safe_cut_points):
                    safe_cut_points.append({"time": cut_time, "quality": 1.0, "why": "scene change"})
            safe_cut_points.sort(key=lambda cp: cp["time"])
            analysis["safe_cut_points"] = safe_cut_points

            # Map Gemini shots to scdet boundaries
            if visual_cuts and analysis.get("shots"):
                duration_val = float(analysis.get("duration") or 0)
                boundaries = [0] + visual_cuts + [duration_val]
                mapped_shots = []
                for i in range(len(boundaries)-1):
                    start = round(boundaries[i]*1000)/1000
                    end   = round(boundaries[i+1]*1000)/1000
                    gsrc = analysis["shots"][min(i, len(analysis["shots"])-1)] if analysis["shots"] else {}
                    mapped_shots.append({
                        "start":         start,
                        "end":           end,
                        "visual":        gsrc.get("visual") or "",
                        "action":        gsrc.get("action") or "",
                        "energy":        gsrc.get("energy") or 0.5,
                        "editing_value": gsrc.get("editing_value") or "usable",
                        "description":   gsrc.get("description") or "",
                        "score":         gsrc.get("score") or 0.5,
                    })
                analysis["shots"] = mapped_shots

            # Step 7 — Tighten transcript
            print("[pipeline] step=tighten", flush=True)
            tighten_result = tighten_transcript(
                deepgram_words,
                scene_cuts=visual_cuts,
                shots=analysis.get("shots") or [],
                original_duration=float(analysis.get("duration") or 0),
            )
            analysis["tightened_timeline"] = tighten_result

            # Step 8 — Broll keywords
            broll_candidates = extract_broll_keywords(deepgram_words, 8)
            if broll_candidates:
                analysis["broll_candidates"] = broll_candidates
                print(f"[broll] Candidates: {', '.join(c['keyword'] for c in broll_candidates)}", flush=True)

            # Step 9 — Scene frames
            print("[pipeline] step=scene_frames", flush=True)
            scene_frames = extract_scene_frames(source_path, visual_cuts, work_dir)

            # Step 10 — Collect vibe expansion (fired before download, ready by now)
            expanded_vibe = vibe_future.result()
            print("[pipeline] vibe expansion ready", flush=True)

        # ── End vibe_executor ─────────────────────────────────────────────────────

        # Step 11 — Generate edit recipe
        send_progress(job_id, "edit_recipe", 52, "Crafting your edit...", app_url)
        print("[pipeline] step=edit_recipe", flush=True)
        t = time.time()
        edit_plan = generate_edit(analysis, transcript, vibe, expanded_vibe, scene_frames)
        print(f"[pipeline] edit recipe complete in {time.time()-t:.1f}s", flush=True)

        edit_plan["analysis_data"] = analysis

        # Step 11.5 — Filler word jump cuts (speech only, ALWAYS_FILLER only)
        has_speech = bool((analysis.get("speech") or {}).get("has_speech"))
        if has_speech and deepgram_words:
            original_cut_count = len(edit_plan["cuts"])
            edit_plan["cuts"] = apply_filler_jump_cuts(edit_plan["cuts"], deepgram_words)
            expanded = len(edit_plan["cuts"]) - original_cut_count
            if expanded > 0:
                print(f"[pipeline] filler jump cuts: {original_cut_count} clips -> {len(edit_plan['cuts'])} clips", flush=True)

        # Step 12 — FFmpeg render
        send_progress(job_id, "render", 62, "Rendering your video...", app_url)
        print("[pipeline] step=ffmpeg_render", flush=True)
        t = time.time()
        render_multi_clip(
            source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
        )
        render_elapsed = time.time() - t
        print(f"[pipeline] FFmpeg render complete in {render_elapsed:.1f}s", flush=True)

        if not os.path.exists(output_path):
            return {"error": "No output file produced by FFmpeg"}

        # Step 12.5 — B-roll overlay (only if Claude requested broll in edit recipe)
        broll_requests = edit_plan.get("broll") or []
        if broll_requests:
            print(f"[pipeline] step=broll ({len(broll_requests)} request(s))", flush=True)
            broll_entries = []
            for req in broll_requests:
                kw  = str(req.get("keyword") or "").strip()
                dur = float(req.get("duration") or 2.0)
                ts  = float(req.get("timestamp") or 0.0)
                if not kw:
                    continue
                local = fetch_broll_clip(kw, dur, work_dir)
                if local:
                    broll_entries.append({"local_path": local, "timestamp": ts, "duration": dur})
            if broll_entries:
                composite_broll(output_path, broll_entries, work_dir)
            for entry in broll_entries:
                try:
                    os.unlink(entry["local_path"])
                except Exception:
                    pass

        # ── Parallel group 2: cover frame + upload ────────────────────────────────
        cover_frame_ts   = 1.0
        cover_frame_b64  = None
        cover_frame_mime = "image/jpeg"

        hook = (analysis.get("hook") or {})
        if hook.get("timestamp") is not None and float(hook.get("quality") or 0) >= 0.5:
            cover_frame_ts = float(hook["timestamp"])
        else:
            shots_sorted = sorted(
                analysis.get("shots") or [],
                key=lambda s: float(s.get("energy") or 0),
                reverse=True,
            )
            if shots_sorted:
                best = shots_sorted[0]
                cover_frame_ts = (float(best["start"]) + float(best["end"])) / 2

        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        send_progress(job_id, "upload", 90, "Uploading your video...", app_url)
        print(f"[pipeline] output: {output_size_mb:.1f}MB — parallel upload + cover frame", flush=True)

        def _upload_main():
            print("[pipeline] step=upload", flush=True)
            with open(output_path, "rb") as f:
                resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                resp.raise_for_status()
            print("[pipeline] upload complete", flush=True)

        def _extract_cover():
            data, mime = extract_cover_frame(source_path, cover_frame_ts, work_dir)
            if data:
                print(f"[pipeline] cover frame at {cover_frame_ts:.2f}s ({len(data)//1024}KB)", flush=True)
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


runpod.serverless.start({"handler": handler})
