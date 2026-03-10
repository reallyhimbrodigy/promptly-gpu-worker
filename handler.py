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


# ─── COLOR INTENTS ────────────────────────────────────────────────────────────

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
      "editing_value": "<essential | strong | usable | filler | dead>"
    }
  ],
  "audio": {
    "music": "<genre/tempo/energy if present, or 'none'>"
  },
  "footage_assessment": {
    "content_type": "<what kind of video>",
    "visual_character": "<color palette, lighting, exposure, white balance>",
    "strongest_moments": "<timestamps and what makes them compelling>",
    "weakest_moments": "<timestamps and why they are weak, or 'none'>",
    "editing_brief": "<how to edit this: what to keep, what to cut, pacing, feel>"
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
            "description":   s.get("action") or s.get("visual") or f"Shot {i+1}",
            "score":         float(s.get("energy") or 0.5),
        })
    if not shots:
        shots = [{"start": 0, "end": duration, "description": "Full video", "score": 0.5,
                  "visual": "", "action": "", "energy": 0.5, "editing_value": ""}]

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
        "duration":        duration,
        "shots":           shots,
        "speech":          parsed.get("speech") or {"has_speech": False, "segments": [], "sentence_boundaries": []},
        "audio":           parsed.get("audio") or {},
        "safe_cut_points": safe_cut_points,
        "peak_moments":    peak_moments,
        "video_profile":   vp,
        "frame_layout":    frame_layout,
        "color_baseline":  color_baseline,
        "footage_quality": footage_quality,
        "metadata":        parsed.get("metadata") or {},
        "visual_cuts":     [],
    }



# ─── SCENE DETECTION ─────────────────────────────────────────────────────────

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

def build_prompt(analysis, transcript, expanded_vibe):
    shots = analysis.get("shots") or []
    shots_block = "\n\n".join(
        f"[{s['start']:.2f}s – {s['end']:.2f}s]\n  {s.get('visual','')}\n  {s.get('action','')}\n  Energy: {s.get('energy',0.5):.1f}"
        + (f"\n  Value: {s['editing_value']}" if s.get("editing_value") else "")
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
            # Find preceding segment text (mirrors JS buildPrompt)
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

    # highlights block (mirrors JS highlightsBlock)
    highlights_block = ""
    highlights = analysis.get("peak_moments") or []
    if highlights:
        sorted_h = sorted(highlights, key=lambda h: -(h.get("importance") or 0))
        highlights_block = "\nHighlights:\n" + "\n".join(
            f"  {float(h.get('time',0)):.2f}s — {h.get('what') or h.get('description','')} ({float(h.get('importance',0.5)):.1f})"
            for h in sorted_h
        )

    tightened = analysis.get("tightened_timeline") or {}
    if tightened and (tightened.get("segments") or []):
        original_duration = float(analysis.get("duration") or 0)
        tightened_duration = sum(max(0, s.get("end",0) - s.get("start",0)) for s in tightened["segments"])
        seg_text = ", ".join(f"{s.get('start',0):.2f}s-{s.get('end',0):.2f}s" for s in tightened["segments"])
        tightened_block = f"Tightened timeline (dead air and filler words already removed):\n  Original: {original_duration:.2f}s → Tightened: {tightened_duration:.2f}s (removed {float(tightened.get('removedSeconds',0)):.2f}s)\n  Keep segments: {seg_text}"
    else:
        original_duration = float(analysis.get("duration") or 0)
        tightened_block = None  # use fallback in template

    broll_candidates = analysis.get("broll_candidates") or []
    broll_candidates_block = ""
    if broll_candidates:
        broll_candidates_block = "\n".join(
            f"  - {c['keyword']} @ {float(c.get('timestamp',0)):.2f}s"
            for c in broll_candidates[:6]
        )


    # profileBlock (mirrors JS)
    vp = analysis.get("video_profile") or {}
    profile_parts = []
    if vp.get("content_type"):     profile_parts.append(f"Type: {vp['content_type']}")
    if vp.get("visual_character") or vp.get("visual_style"):
        profile_parts.append(f"Look: {vp.get('visual_character') or vp.get('visual_style')}")
    if vp.get("strongest_moments"): profile_parts.append(f"Best parts: {vp['strongest_moments']}")
    if vp.get("weakest_moments"):   profile_parts.append(f"Weakest parts: {vp['weakest_moments']}")
    profile_block = "\n" + "\n".join(profile_parts) if profile_parts else ""

    # audioBlock (mirrors JS)
    audio_block = ""
    audio = analysis.get("audio") or {}
    music_info = audio.get("music") or (audio.get("has_music") and audio.get("music_description"))
    if music_info:
        audio_block = f"\nMusic: {music_info}"

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

    # Build render recommendations from Gemini's direct observations
    render_recs = []

    noise = fq.get("noise_level", "low")
    sharpness = fq.get("source_sharpness", "normal")
    highlights = fq.get("highlight_condition", "normal")
    shadows = fq.get("shadow_condition", "normal")
    richness = fq.get("color_richness", "normal")
    skin = fq.get("skin_tones_present", True)
    lighting = fq.get("lighting_type", "unknown")

    # Noise → denoise
    if noise in ("medium", "high"):
        render_recs.append(f"NOISE: {noise}-level noise observed directly — denoise=true (renderer will apply calibrated hqdn3d strength for {noise} noise)")
    else:
        render_recs.append(f"NOISE: Clean footage (noise_level={noise}) — denoise=false")

    # Sharpness → sharpening
    if sharpness == "soft":
        render_recs.append(f"SHARPNESS: Source is soft — sharpening=true (renderer will apply strong unsharp for soft footage)")
    elif sharpness == "normal":
        render_recs.append(f"SHARPNESS: Normal sharpness — sharpening=true applies a calibrated subtle pass; false leaves it as-is")
    else:
        render_recs.append(f"SHARPNESS: Source is already sharp — sharpening=false (renderer would apply only minimal pass, but it's not needed)")

    # Highlights → highlight_rolloff
    if highlights == "clipped":
        render_recs.append(f"HIGHLIGHTS: Blown out/clipped — highlight_rolloff=true (renderer will apply hard rolloff curve for clipped footage)")
    elif highlights == "bright":
        render_recs.append(f"HIGHLIGHTS: Near-clipping — highlight_rolloff=true (renderer will apply soft rolloff for bright footage)")
    else:
        render_recs.append(f"HIGHLIGHTS: {highlights} — highlight_rolloff=false unless a filmic look is intended")

    # Shadows → shadow_lift
    if shadows == "crushed":
        render_recs.append(f"SHADOWS: Crushed to pure black — shadow_lift=true (renderer will apply high lift for crushed shadows)")
    elif shadows == "deep":
        render_recs.append(f"SHADOWS: Deep and rich — shadow_lift=false preserves the look; true applies a low lift if the vibe is faded/editorial")
    elif shadows == "lifted":
        render_recs.append(f"SHADOWS: Already elevated in raw footage — shadow_lift=false (additional lift will look washed out)")
    else:
        render_recs.append(f"SHADOWS: Balanced — shadow_lift is purely a stylistic choice")

    # Color richness → vibrance
    if richness == "flat":
        render_recs.append(f"COLOR: Color-flat footage — vibrance=true (renderer will apply high vibrance for flat footage)" + (" — skin tones present, vibrance protects them" if skin else ""))
    elif richness == "muted":
        render_recs.append(f"COLOR: Muted colors — vibrance=true (renderer applies medium vibrance for muted footage)" + (" — skin tones present, vibrance protects them" if skin else ""))
    elif richness == "vivid":
        render_recs.append(f"COLOR: Already vivid — vibrance=false (boosting vivid footage produces neon/artificial results)")
    else:
        render_recs.append(f"COLOR: Normal color richness — vibrance=false unless the vibe calls for more punch")

    # Lighting type context (informational only)
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

    tightened_fallback = (
        f"Tightened timeline (dead air and filler words already removed):\n"
        f"  Original: {duration:.2f}s → Tightened: {tightened_duration_val:.2f}s "
        f"(removed {float((tightened or {}).get('removedSeconds', 0)):.2f}s)\n"
        f"  Keep segments: none"
    )

    full_prompt = f"""You are the professional editor inside Promptly, a mobile app that competes with CapCut and Captions. Users upload raw talking-head footage and receive back a fully edited short-form video (TikTok, Instagram Reels, YouTube Shorts) in under 90 seconds. You produce the edit recipe — every creative decision about how this video gets cut, graded, and polished.

Your output needs to be indistinguishable from a video edited by a skilled freelance editor who specializes in short-form content for TikTok and Instagram Reels.

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

  outro — what happens after the last frame of the last clip:
    none — video ends immediately on the last frame
    fade_black — last clip gradually fades to black
    fade_white — last clip gradually fades to white

  background_music — always "none"
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

Transition sounds: These are short audio accents timed to the transition frame. swoosh is a fast air-swipe. thud is a punchy impact. shutter is a camera click. pop is a bright snap. ding is a single-note bell. reverb_hit is an impact with a tail that lingers. typing is rapid keyboard clicks. ching is a cash register sound. The sound plays during the 0.3-second transition window and blends with any audio already playing.

Zoom: slow_in gradually scales the clip from 100% to 110% across its full duration — the subject slowly fills more of the frame. slow_out does the reverse. punch_in jumps quickly to 115% at the first 10 frames then holds. punch_out jumps quickly to 85% at the first 10 frames then holds. All zoom modes crop the edges of the frame to maintain 1080x1920.

Cut-zoom: At each sentence boundary within the clip, the framing alternates between normal and slightly zoomed-in. On a 1080px screen this creates the visual effect of a two-camera shoot from a single angle.

Speed: The speech pitch is preserved regardless of speed value. At 1.05–1.15x the change is imperceptible to most viewers. At 1.25x+ the motion is visibly faster. At 0.75x and below the motion is visibly slower and the voice lowers slightly in tempo.

Speed ramp: Creates non-linear acceleration within a single clip. hero_time compresses the first half of the clip and expands the second half into slow motion — whatever is happening at the midpoint of the clip becomes the lingering focal moment. bullet expands the first third into slow motion then compresses the rest into fast motion. flash_in compresses the opening frames then eases to normal pacing. flash_out plays at normal speed then compresses the final frames. montage alternates between fast and slow in four equal segments across the clip.

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
  "background_music": "none",
  "caption_style": "<style>",
  "caption_position": "<position>",
  "caption_keywords": [],
  "audio_ducking": false,
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
    {{ "source_start": <n>, "source_end": <n>, "transition_out": "<transition>", "transition_sound": "<sound>", "sfx_style": "<sfx>", "zoom": "<zoom>", "cut_zoom": <true|false>, "speed": <n>, "speed_ramp": "<ramp>" }}
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
    static_prefix, dynamic_suffix = build_prompt(analysis, transcript, expanded_vibe)

    content_blocks = [
        {"type": "text", "text": static_prefix, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_suffix},
    ]

    if scene_frames:
        content_blocks.append({
            "type": "text",
            "text": "\nHere are frame thumbnails from the opening and scene-change moments. Use them as visual context when deciding transitions, zoom, cut-zoom, b-roll, text overlays, and color intent.",
        })
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
        content_blocks.append({
            "type": "text",
            "text": "\nUse these frames to make shot-specific decisions. If a shot is a screen recording or demo, avoid unnecessary cut-zoom/text clutter. If framing and lighting are already strong, use a lighter touch.",
        })

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
    edit_plan["background_music"] = "none"
    edit_plan["audio_ducking"] = False

    # Hard coerce quality-correction fields to bool — Claude may return string "true"/"false"
    # Intensity is derived from footage_quality in the renderer; Claude only enables/disables.
    for bool_field in ("sharpening", "denoise", "shadow_lift", "highlight_rolloff", "vibrance", "cinematic_bars"):
        v = edit_plan.get(bool_field)
        if isinstance(v, str):
            edit_plan[bool_field] = v.strip().lower() in ("true", "1", "yes")
        else:
            edit_plan[bool_field] = bool(v)

    # Hard coerce stylistic enum fields — clamp to allowed values
    valid_grain      = {"none", "subtle", "medium", "heavy"}
    valid_teal       = {"none", "subtle", "strong"}
    valid_vignette   = {"none", "light", "medium", "strong"}
    if edit_plan.get("grain") not in valid_grain:
        edit_plan["grain"] = "none"
    if edit_plan.get("teal_orange") not in valid_teal:
        edit_plan["teal_orange"] = "none"
    if edit_plan.get("vignette") not in valid_vignette:
        edit_plan["vignette"] = "none"

    final_cuts = []
    for clip_entry in validated_cuts:
        transition = str(clip_entry.get("transition_out") or "").lower()
        transition_out = "none" if not transition or transition == "clean_cut" else transition
        speed = max(0.25, min(4.0, float(clip_entry.get("speed") or 1.0)))
        valid_ramps = {"none","hero_time","bullet","flash_in","flash_out","montage"}
        speed_ramp = str(clip_entry.get("speed_ramp") or "none").lower()
        if speed_ramp not in valid_ramps:
            speed_ramp = "none"
        final_cuts.append({
            "source_start":    clip_entry["source_start"],
            "source_end":      clip_entry["source_end"],
            "transition_out":  transition_out,
            "transition_sound": clip_entry.get("transition_sound") or "none",
            "sfx_style":       clip_entry.get("sfx_style") or "none",
            "zoom":            clip_entry.get("zoom") or "none",
            "cut_zoom":        bool(clip_entry.get("cut_zoom")),
            "speed":           speed,
            "speed_ramp":      speed_ramp,
            "speed_segments":  [],
        })

    baseline = analysis.get("color_baseline") or {}
    intent = normalize_intent(edit_plan.get("color_intent") or "none")
    edit_plan["color_intent"] = intent
    edit_plan["color_grade"] = build_color_grade(baseline, intent)
    edit_plan["cuts"] = final_cuts
    if "clips" in edit_plan:
        del edit_plan["clips"]

    # target_duration (mirrors JS)
    if final_cuts:
        edit_plan["target_duration"] = final_cuts[-1]["source_end"] - final_cuts[0]["source_start"]

    # coverage ratio warning (mirrors JS)
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
        raise RuntimeError(f"Landscape video ({w}x{h}) — Promptly requires vertical video")

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
        "-c:a","aac","-b:a","128k","-ar","48000","-ac","1",
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
        "-c:a","aac","-b:a","128k","-threads","1",
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
    return not t or t == "none" or t == "clean_cut"


def build_video_filter_chain(color_grade, source_res, edit_plan=None):
    ep = edit_plan or {}
    fq = (ep.get("analysis_data") or {}).get("footage_quality") or {}
    filters = []

    # ── 1. Denoise — calibrated to Gemini-observed noise level ──────────────────
    if ep.get("denoise"):
        noise = fq.get("noise_level", "low")
        # hqdn3d: luma_spatial:chroma_spatial:luma_temporal:chroma_temporal
        denoise_params = {
            "none":   "1:1:2:2",    # minimal pass just in case
            "low":    "2:2:3:3",    # light denoising
            "medium": "3:3:5:5",    # medium — visible noise, indoor footage
            "high":   "5:5:8:8",    # heavy — dark/noisy phone footage
        }.get(noise, "2:2:3:3")
        filters.append(f"hqdn3d={denoise_params}")
        print(f"[render] denoise: noise_level={noise} → hqdn3d={denoise_params}", flush=True)

    # ── 2. Color grade (eq: brightness/contrast/saturation/gamma) ───────────────
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

    # ── 3. Color temperature ─────────────────────────────────────────────────────
    temp = color_grade.get("color_temperature") or "neutral"
    temp_filter = TEMPERATURE_FILTERS.get(temp)
    if temp_filter:
        filters.append(temp_filter)

    # ── 4. Shadow lift — calibrated to Gemini-observed shadow condition ──────────
    if ep.get("shadow_lift"):
        shadow_cond = fq.get("shadow_condition", "normal")
        # curves: raise black point. More crushed shadows → more lift needed
        lift_curves = {
            "crushed": "curves=r='0/0.09 1/1':g='0/0.09 1/1':b='0/0.09 1/1'",   # high lift
            "deep":    "curves=r='0/0.05 1/1':g='0/0.05 1/1':b='0/0.05 1/1'",   # medium lift
            "normal":  "curves=r='0/0.04 1/1':g='0/0.04 1/1':b='0/0.04 1/1'",   # subtle lift
            "lifted":  "curves=r='0/0.02 1/1':g='0/0.02 1/1':b='0/0.02 1/1'",   # minimal — already lifted
        }.get(shadow_cond, "curves=r='0/0.04 1/1':g='0/0.04 1/1':b='0/0.04 1/1'")
        filters.append(lift_curves)
        print(f"[render] shadow_lift: shadow_condition={shadow_cond} → lift applied", flush=True)

    # ── 5. Highlight rolloff — calibrated to Gemini-observed highlight condition ─
    if ep.get("highlight_rolloff"):
        hl_cond = fq.get("highlight_condition", "normal")
        # curves: compress top of tonal range. More clipped → harder rolloff
        rolloff_curves = {
            "clipped": "curves=r='0/0 0.6/0.58 0.85/0.80 1/0.88':g='0/0 0.6/0.58 0.85/0.80 1/0.88':b='0/0 0.6/0.58 0.85/0.80 1/0.88'",
            "bright":  "curves=r='0/0 0.75/0.72 1/0.95':g='0/0 0.75/0.72 1/0.95':b='0/0 0.75/0.72 1/0.95'",
            "normal":  "curves=r='0/0 0.82/0.80 1/0.97':g='0/0 0.82/0.80 1/0.97':b='0/0 0.82/0.80 1/0.97'",
            "dark":    "curves=r='0/0 0.88/0.87 1/0.98':g='0/0 0.88/0.87 1/0.98':b='0/0 0.88/0.87 1/0.98'",
        }.get(hl_cond, "curves=r='0/0 0.82/0.80 1/0.97':g='0/0 0.82/0.80 1/0.97':b='0/0 0.82/0.80 1/0.97'")
        filters.append(rolloff_curves)
        print(f"[render] highlight_rolloff: highlight_condition={hl_cond} → rolloff applied", flush=True)

    # ── 6. Vibrance — calibrated to Gemini-observed color richness ───────────────
    if ep.get("vibrance"):
        richness = fq.get("color_richness", "normal")
        # More flat/muted → bigger boost needed. Already vivid → minimal touch only
        vibrance_hue = {
            "flat":   "hue=s=1.35",   # large boost for color-flat footage
            "muted":  "hue=s=1.22",   # medium boost for muted footage
            "normal": "hue=s=1.12",   # subtle boost for normal footage
            "vivid":  "hue=s=1.06",   # near-nothing for already-vivid footage
        }.get(richness, "hue=s=1.12")
        filters.append(vibrance_hue)
        print(f"[render] vibrance: color_richness={richness} → {vibrance_hue}", flush=True)

    # ── 7. Teal-orange split grade (stylistic — Claude controls level) ───────────
    teal_orange = str(ep.get("teal_orange") or "none").lower()
    if teal_orange == "subtle":
        filters.append("colorbalance=rs=-0.08:gs=0.04:bs=0.10:rm=0.04:gm=0:bm=-0.04:rh=0.05:gh=0.01:bh=-0.05")
    elif teal_orange == "strong":
        filters.append("colorbalance=rs=-0.16:gs=0.06:bs=0.18:rm=0.07:gm=0:bm=-0.07:rh=0.09:gh=0.02:bh=-0.09")

    # ── 8. Sharpening — calibrated to Gemini-observed source sharpness ───────────
    if ep.get("sharpening"):
        src_sharp = fq.get("source_sharpness", "normal")
        # Softer source needs more aggressive unsharp. Already-sharp source gets minimal pass
        unsharp_params = {
            "soft":   "unsharp=7:7:1.2:5:5:0.0",   # strong sharpening for soft footage
            "normal": "unsharp=5:5:0.6:3:3:0.0",   # moderate for normal footage
            "sharp":  "unsharp=3:3:0.3:3:3:0.0",   # minimal pass for already-sharp footage
        }.get(src_sharp, "unsharp=5:5:0.6:3:3:0.0")
        filters.append(unsharp_params)
        print(f"[render] sharpening: source_sharpness={src_sharp} → {unsharp_params}", flush=True)

    # ── 9. Film grain (stylistic — Claude controls level) ────────────────────────
    grain = str(ep.get("grain") or "none").lower()
    if grain == "subtle":
        filters.append("noise=c0s=4:c0f=t+u")
    elif grain == "medium":
        filters.append("noise=c0s=9:c0f=t+u")
    elif grain == "heavy":
        filters.append("noise=c0s=16:c0f=t+u")

    return ",".join(filters) if filters else "null"


def get_output_clip_ranges(cuts, effective_durations):
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur = effective_durations[i] if i < len(effective_durations) else (float(cut["source_end"]) - float(cut["source_start"]))
        start = round(cursor*1000)/1000
        end   = round((cursor+dur)*1000)/1000
        ranges.append({"start": start, "end": end})
        overlap = TRANSITION_DURATION if i < len(cuts)-1 and not is_hard_cut(cut.get("transition_out")) else 0
        cursor = round((end - overlap)*1000)/1000
    return ranges



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

    styles_map = {
        "standard":       {"fontsize": 42, "fontname": "Arial", "bold": 0, "alignment": 2},
        "bold_centered":  {"fontsize": 56, "fontname": "Arial", "bold": 1, "alignment": 5},
        "minimal_bottom": {"fontsize": 36, "fontname": "Arial", "bold": 0, "alignment": 2},
        "animated_word":  {"fontsize": 52, "fontname": "Arial", "bold": 1, "alignment": 5},
        "bold_white":     {"fontsize": 58, "fontname": "Arial", "bold": 1, "alignment": 5},
        "bold_yellow":    {"fontsize": 58, "fontname": "Arial", "bold": 1, "alignment": 5},
        "keyword_pop":    {"fontsize": 52, "fontname": "Arial", "bold": 1, "alignment": 5},
        "box_caption":    {"fontsize": 44, "fontname": "Arial", "bold": 1, "alignment": 2},
    }
    style = styles_map.get(caption_style) or styles_map["standard"]
    pos_margin = {"top": 1500, "center": 800, "lower-third": 450, "bottom": 100}
    margin_v = pos_margin.get(caption_position or "lower-third", 450)

    color_map = {
        "bold_white":  ("&H00FFFFFF", "&H00000000", "&H80000000", 1, 3, 2),
        "bold_yellow": ("&H0000FFFF", "&H00000000", "&H80000000", 1, 3, 2),
        "box_caption": ("&H00FFFFFF", "&H00000000", "&HC0000000", 3, 0, 8),
        "keyword_pop": ("&H00FFFFFF", "&H00000000", "&H80000000", 1, 3, 1),
    }
    primary, outline_c, back_c, border_style, outline_w, shadow = color_map.get(
        caption_style, ("&H00FFFFFF", "&H00000000", "&H80000000", 1, 2, 1)
    )
    w = output_res.get("width") or 1080
    h = output_res.get("height") or 1920

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['fontname']},{style['fontsize']},{primary},&H000000FF,{outline_c},{back_c},{style['bold']},0,0,0,100,100,0,0,{border_style},{outline_w},{shadow},{style['alignment']},20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    if caption_style == "animated_word":
        for word in words:
            ass += f"Dialogue: 0,{format_ass_time(word['start'])},{format_ass_time(word['end'])},Default,,0,0,0,,{word['word']}\n"
    elif caption_style == "keyword_pop":
        keyword_set = set(re.sub(r"[.,!?;:'\"\\]","",k.lower()) for k in (caption_keywords or []))
        highlight_colors = ["\\c&H0000FF00&","\\c&H000055FF&","\\c&H0000FFFF&"]
        reset_color = "\\c&H00FFFFFF&"
        group = []
        for i, word in enumerate(words):
            group.append(word)
            next_w = words[i+1] if i+1 < len(words) else None
            pause = (next_w["start"] - word["end"]) if next_w else 1
            if not next_w or pause > 0.35 or len(group) >= 8:
                start = group[0]["start"]
                end = group[-1]["end"]
                color_idx = 0
                parts = []
                for g in group:
                    clean = re.sub(r"[.,!?;:'\"\\]","",g["word"].lower())
                    if clean in keyword_set:
                        col = highlight_colors[color_idx % len(highlight_colors)]
                        color_idx += 1
                        parts.append(f"{{{col}\\b1}}{g['word']}{{  {reset_color}\\b1}}")
                    else:
                        parts.append(g["word"])
                text = " ".join(parts)
                ass += f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
                group = []
    else:
        group = []
        for i, word in enumerate(words):
            group.append(word)
            next_w = words[i+1] if i+1 < len(words) else None
            pause = (next_w["start"] - word["end"]) if next_w else 1
            if not next_w or pause > 0.35 or len(group) >= 8:
                start = group[0]["start"]
                end = group[-1]["end"]
                text = " ".join(g["word"] for g in group)
                ass += f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}\n"
                group = []

    ass_path = os.path.join(work_dir, "captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    return ass_path



def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir):
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
        zoom_max = 1.06 if has_burned_captions else 1.10

        zoom_filter = None
        if zoom == "slow_in":
            zoom_filter = f"scale=w='trunc(iw*(1.0+{zoom_max-1.0}*n/{total_frames})/2)*2':h='trunc(ih*(1.0+{zoom_max-1.0}*n/{total_frames})/2)*2':eval=frame:flags=bilinear,crop=1080:1920"
        elif zoom == "slow_out":
            zoom_filter = f"scale=w='trunc(iw*({zoom_max}-{zoom_max-1.0}*n/{total_frames})/2)*2':h='trunc(ih*({zoom_max}-{zoom_max-1.0}*n/{total_frames})/2)*2':eval=frame:flags=bilinear,crop=1080:1920"
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

        # Speed ramp: non-linear setpts curve across the clip
        speed_ramp = str(cut.get("speed_ramp") or "none").lower()
        if speed_ramp != "none" and speed_ramp in {"hero_time","bullet","flash_in","flash_out","montage"}:
            # All ramps use expr-based setpts applied AFTER constant speed
            # N = frame number, TB = 1/30, total_frames already computed above
            tf = max(1, total_frames)
            if speed_ramp == "hero_time":
                # Fast start (0.5x duration = 2x speed), slow end (0.5x duration = 0.4x speed)
                # setpts: first half compressed, second half expanded
                expr = f"if(lt(N\\,{tf//2})\\,PTS*0.5\\,{tf//2}*TB/30+({tf//2}*TB+(N-{tf//2})*TB)*2.5)"
                v_chain.append(f"setpts='if(lt(N\\,{tf//2})\\,PTS*0.5\\,{tf//4*1.0/30:.6f}+(PTS-{tf//2*1.0/30:.6f})*2.5)'")
            elif speed_ramp == "bullet":
                # Slow start (0.4x speed first third), fast rest (1.4x)
                v_chain.append(f"setpts='if(lt(N\\,{tf//3})\\,PTS*2.5\\,{tf//3*2.5/30:.6f}+(PTS-{tf//3*1.0/30:.6f})*0.7)'")
            elif speed_ramp == "flash_in":
                # Fast at start, eases to normal
                v_chain.append(f"setpts='if(lt(N\\,{tf//3})\\,PTS*0.4\\,{tf//3*0.4/30:.6f}+(PTS-{tf//3*1.0/30:.6f})*1.0)'")
            elif speed_ramp == "flash_out":
                # Normal speed, then fast at end
                v_chain.append(f"setpts='if(lt(N\\,{tf*2//3})\\,PTS*1.0\\,{tf*2//3*1.0/30:.6f}+(PTS-{tf*2//3*1.0/30:.6f})*0.4)'")
            elif speed_ramp == "montage":
                # Alternating fast/slow every quarter
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

    # Transition chaining
    transition_filters = []
    tl_video = "v0"
    tl_audio = "a0"
    running_dur = effective_durations[0]

    for i in range(1, n):
        transition = str(cuts[i-1].get("transition_out") or "none").lower()
        out_v     = "vout" if i == n-1 else f"vx{i}"
        out_v_raw = f"{out_v}_raw"
        out_a     = "aout" if i == n-1 else f"ax{i}"
        hard = is_hard_cut(transition)

        if hard:
            transition_filters.append(f"[{tl_video}][v{i}]concat=n=2:v=1:a=0[{out_v_raw}]")
            transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
            transition_filters.append(f"[{tl_audio}][a{i}]concat=n=2:v=0:a=1[{out_a}]")
            running_dur = running_dur + effective_durations[i]
        else:
            td = TRANSITION_DURATION
            offset = max(0, running_dur - td)
            transition_filters.append(f"[{tl_video}][v{i}]xfade=transition={transition}:duration={td:.3f}:offset={offset:.3f}[{out_v_raw}]")
            transition_filters.append(f"[{out_v_raw}]fps=30[{out_v}]")
            transition_filters.append(f"[{tl_audio}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[{out_a}]")
            running_dur = running_dur + effective_durations[i] - td

        tl_video = out_v
        tl_audio = out_a

    if n == 1:
        tl_video = "v0"
        tl_audio = "a0"

    # Post: captions + text overlays + audio
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
            post_filters.append(f"{video_out}subtitles='{escaped}'[video_captioned]")
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
            post_filters.append(
                f"{video_out}drawtext=text='{text}':fontsize={font_size}:fontcolor=white"
                f":x=(w-tw)/2:y={y_expr}:alpha='{alpha_expr}'"
                f":borderw=5:bordercolor=black:enable='between(t\\,{start:.3f}\\,{end_t:.3f})'{out_label}"
            )
            video_out = out_label

    # Cinematic bars (2.35:1 letterbox on 9:16 — horizontal black bars top and bottom)
    if edit_plan.get("cinematic_bars"):
        # On 1080x1920, 2.35:1 crop height = 1080/2.35 = 459px. Bar height = (1920-459)/2 = 730px
        bar_h = int((1920 - int(1080 / 2.35)) / 2)
        bars_label = f"[video_bars]"
        post_filters.append(
            f"{video_out}drawbox=x=0:y=0:w=1080:h={bar_h}:color=black:t=fill,"
            f"drawbox=x=0:y={1920-bar_h}:w=1080:h={bar_h}:color=black:t=fill{bars_label}"
        )
        video_out = bars_label

    audio_out = f"[{tl_audio}]"
    post_filters.append(
        f"{audio_out}highpass=f=80,lowpass=f=12000,"
        f"equalizer=f=2800:t=q:w=1.5:g=3,"
        f"equalizer=f=200:t=q:w=0.8:g=1.5,"
        f"acompressor=threshold=-20dB:ratio=3:attack=5:release=50:makeup=2,"
        f"dynaudnorm=f=150:g=15:p=0.95:m=10,"
        f"alimiter=limit=0.95:attack=1:release=10[final_audio]"
    )
    audio_out = "[final_audio]"

    filter_complex = ";".join(video_filters + audio_filters + transition_filters + post_filters)

    encode_args = [
        "-c:v","libx264","-preset","veryfast","-crf","26",
        "-b:v","4M","-maxrate","5M","-bufsize","10M",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        "-movflags","+faststart",
        "-max_muxing_queue_size","1024",
    ]

    args = (
        ["-y","-threads","1"]
        + input_args
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

def handler(job):
    input_data = job["input"]
    work_dir = None
    try:
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
        print("[pipeline] step=normalize", flush=True)
        source_path = normalize_source_video(source_path, work_dir)

        # Step 3 — Gemini analysis
        if cached_analysis:
            print("[pipeline] step=analysis (cache HIT)", flush=True)
            analysis = normalize_analysis(cached_analysis) if isinstance(cached_analysis, dict) else cached_analysis
        else:
            print("[pipeline] step=analysis (Gemini)", flush=True)
            t = time.time()
            analysis = run_gemini_analysis(source_path)
            print(f"[pipeline] Gemini complete in {time.time()-t:.1f}s", flush=True)

        # Step 4 — Scene detection
        print("[pipeline] step=scene_detection", flush=True)
        t = time.time()
        visual_cuts = detect_scene_cuts(source_path)
        analysis["visual_cuts"] = visual_cuts
        print(f"[pipeline] scene detection complete in {time.time()-t:.1f}s ({len(visual_cuts)} cuts)", flush=True)

        # Step 5 — Transcription
        print("[pipeline] step=transcription", flush=True)
        t = time.time()
        transcript = transcribe_audio(source_path)
        deepgram_words = transcript.get("words") or []
        print(f"[pipeline] transcription complete in {time.time()-t:.1f}s ({len(deepgram_words)} words)", flush=True)

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

        # Step 10 — Expand vibe
        print("[pipeline] step=vibe_expansion", flush=True)
        t = time.time()
        expanded_vibe = expand_vibe_intent(vibe)
        print(f"[pipeline] vibe expansion complete in {time.time()-t:.1f}s", flush=True)

        # Step 11 — Generate edit recipe
        print("[pipeline] step=edit_recipe", flush=True)
        t = time.time()
        edit_plan = generate_edit(analysis, transcript, vibe, expanded_vibe, scene_frames)
        print(f"[pipeline] edit recipe complete in {time.time()-t:.1f}s", flush=True)

        # Attach analysis for render context
        edit_plan["analysis_data"] = analysis

        # Step 12 — FFmpeg render
        print("[pipeline] step=ffmpeg_render", flush=True)
        t = time.time()
        render_multi_clip(
            source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
        )
        render_elapsed = time.time() - t
        print(f"[pipeline] FFmpeg render complete in {render_elapsed:.1f}s", flush=True)

        if not os.path.exists(output_path):
            return {"error": "No output file produced by FFmpeg"}

        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        print(f"[pipeline] output: {output_size_mb:.1f}MB", flush=True)

        # Step 13 — Upload
        print("[pipeline] step=upload", flush=True)
        with open(output_path, "rb") as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type":"video/mp4"}, timeout=120)
            resp.raise_for_status()
        print("[pipeline] upload complete", flush=True)

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id} COMPLETE", flush=True)
        print(f"{'='*80}\n", flush=True)

        return {
            "status": "success",
            "job_id": job_id,
            "render_time": round(render_elapsed, 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": {k: v for k, v in edit_plan.items() if k != "analysis_data"},
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


runpod.serverless.start({"handler": handler})
