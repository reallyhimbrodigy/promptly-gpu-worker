import json
import os
import shutil
import subprocess
import time
import traceback
from datetime import datetime, timezone

import anthropic
import google.generativeai as genai
import requests
import runpod
from deepgram import DeepgramClient, PrerecordedOptions


GEMINI_SYSTEM_PROMPT = """You are a professional video editor analyzing footage for social media editing.

Analyze this video and return a JSON object with this exact structure:
{
  "duration": <float seconds>,
  "shots": [
    {
      "start": <float>,
      "end": <float>,
      "description": "<what's happening>",
      "action": "<motion/activity>",
      "visual": "<lighting, colors, composition>",
      "energy": <0.0-1.0>,
      "score": <0.0-1.0>,
      "editing_value": "essential|strong|moderate|weak"
    }
  ],
  "speech": {
    "has_speech": <bool>,
    "segments": [],
    "sentence_boundaries": []
  },
  "audio": { "music": "none|background|prominent" },
  "peak_moments": [],
  "safe_cut_points": [],
  "color_baseline": {
    "brightness": <-1 to 1>,
    "contrast": <0.5-2.0>,
    "saturation": <0.5-2.0>,
    "gamma": <0.5-2.0>,
    "color_temperature": "cool|neutral|warm",
    "assessment": "<one sentence>"
  },
  "frame_layout": {
    "subject_position": "<description>",
    "free_zones": "<description>",
    "existing_overlays": {
      "has_burned_captions": <bool>,
      "has_text_graphics": <bool>,
      "overlay_locations": "<description>"
    }
  },
  "video_profile": {
    "content_type": "<description>",
    "visual_character": "<description>",
    "strongest_moments": [],
    "weakest_moments": "<description>",
    "editing_brief": "<one paragraph>"
  },
  "metadata": {}
}

Return only valid JSON. No markdown, no explanation."""

EXPAND_VIBE_SYSTEM_PROMPT = (
    "You are a creative video editor. Expand the user's vibe description into a concrete "
    "editing intention in 2-3 sentences. Focus on pacing, mood, and visual style. "
    "Be specific and actionable."
)

EDIT_RECIPE_SYSTEM_PROMPT = """You are an expert video editor creating an automated edit recipe.

Return only valid JSON with this exact structure:
{
  "clips": [
    {
      "source_start": <float>,
      "source_end": <float>,
      "speed": <float, default 1.0>,
      "filters": []
    }
  ],
  "overlays": [
    {
      "type": "text",
      "text": "<string>",
      "start_time": <float>,
      "end_time": <float>,
      "x": "(w-text_w)/2",
      "y": "h*0.15",
      "fontsize": 52,
      "fontcolor": "white",
      "bordercolor": "black",
      "borderw": 3
    }
  ],
  "color_grade": {
    "brightness": <-1 to 1>,
    "contrast": <0.5-2.0>,
    "saturation": <0.5-2.0>,
    "gamma": <0.5-2.0>
  },
  "audio": {
    "original_volume": <0.0-1.0>
  },
  "notes": "<50 words max, editor notes>"
}

Rules:
- Clips must be sequential, with no overlaps and no reordering.
- Total clip duration must be less than or equal to the original duration.
- Keep the edit practical for FFmpeg rendering.
- Use overlays only when they materially improve clarity or impact.
- Keep filters arrays simple; empty arrays are acceptable."""


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_step(step, message):
    print(f"[pipeline] ts={timestamp()} step={step} {message}", flush=True)


def ensure_success(response):
    response.raise_for_status()
    return response


def parse_json_text(text):
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("Empty JSON response")
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    return json.loads(stripped)


def anthropic_text(response):
    parts = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def deepgram_to_dict(response):
    if hasattr(response, "to_dict"):
        return response.to_dict()
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, dict):
        return response
    raise TypeError("Unsupported Deepgram response type")


def ffprobe_duration(path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def source_has_audio(path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return bool(result.stdout.strip())


def sanitize_drawtext_text(text):
    safe = (text or "").encode("ascii", "ignore").decode("ascii")
    safe = safe.replace("\\", "\\\\")
    safe = safe.replace("'", "")
    safe = safe.replace('"', "")
    safe = safe.replace(":", "\\:")
    safe = safe.replace(",", "\\,")
    return safe.strip()


def atempo_chain(speed):
    if speed <= 0:
        return ["atempo=1.0"]

    factors = []
    remaining = speed
    while remaining > 2.0:
        factors.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        factors.append("atempo=0.5")
        remaining /= 0.5
    factors.append(f"atempo={remaining}")
    return factors


def download_source(video_url, source_path):
    response = ensure_success(requests.get(video_url, stream=True, timeout=300))
    total_bytes = 0
    with open(source_path, "wb") as file_obj:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            file_obj.write(chunk)
            total_bytes += len(chunk)
    size_mb = total_bytes / (1024 * 1024)
    print(f"[pipeline] downloaded_mb={size_mb:.1f}", flush=True)
    return size_mb


def wait_for_gemini_file(uploaded_file, timeout_seconds=60):
    deadline = time.time() + timeout_seconds
    current = uploaded_file
    while time.time() < deadline:
        state_name = getattr(getattr(current, "state", None), "name", None)
        if state_name == "ACTIVE":
            return current
        if state_name == "FAILED":
            raise RuntimeError("Gemini file processing failed")
        time.sleep(2)
        current = genai.get_file(current.name)
    raise TimeoutError("Gemini file did not become ACTIVE within 60 seconds")


def run_gemini_analysis(source_path):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    uploaded_file = genai.upload_file(source_path)
    active_file = wait_for_gemini_file(uploaded_file)
    model = genai.GenerativeModel(
        "gemini-1.5-pro",
        system_instruction=GEMINI_SYSTEM_PROMPT,
    )
    response = model.generate_content([active_file])
    return parse_json_text(response.text)


def run_deepgram_transcription(source_path):
    dg = DeepgramClient(os.environ["DEEPGRAM_API_KEY"])
    with open(source_path, "rb") as file_obj:
        payload = {"buffer": file_obj.read()}
    options = PrerecordedOptions(
        model="nova-3",
        smart_format=True,
        utterances=True,
        punctuate=True,
        diarize=False,
    )
    response = dg.listen.prerecorded.v("1").transcribe_file(payload, options)
    data = deepgram_to_dict(response)
    alternative = data["results"]["channels"][0]["alternatives"][0]
    transcript_text = alternative.get("transcript", "")
    words = alternative.get("words", []) or []
    utterances = data["results"].get("utterances", []) or []

    speech_segments = [
        {
            "start": utterance.get("start", 0.0),
            "end": utterance.get("end", 0.0),
            "text": utterance.get("transcript", "").strip(),
        }
        for utterance in utterances
        if utterance.get("transcript", "").strip()
    ]

    sentence_boundaries = []
    for word in words:
        token = (word.get("punctuated_word") or word.get("word") or "").strip()
        if token.endswith((".", "?", "!")):
            sentence_boundaries.append({"time": word.get("start", 0.0)})

    return transcript_text, words, speech_segments, sentence_boundaries


def expand_vibe(vibe):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=EXPAND_VIBE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Vibe: {vibe}"}],
    )
    return anthropic_text(response)


def generate_edit_recipe(analysis, transcript_text, expanded_vibe, duration):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_payload = {
        "video_duration": duration,
        "expanded_vibe": expanded_vibe,
        "transcript": transcript_text,
        "analysis": analysis,
    }
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=EDIT_RECIPE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(user_payload)}],
    )
    return parse_json_text(anthropic_text(response))


def normalize_recipe(recipe, duration):
    clips = recipe.get("clips") or []
    if not clips:
        raise ValueError("Edit recipe did not include any clips")

    normalized = []
    previous_end = 0.0
    for clip in clips:
        start = max(0.0, float(clip.get("source_start", 0.0)))
        end = min(duration, float(clip.get("source_end", duration)))
        if end <= start:
            continue
        start = max(start, previous_end)
        if end <= start:
            continue
        normalized.append(
            {
                "source_start": round(start, 3),
                "source_end": round(end, 3),
                "speed": float(clip.get("speed", 1.0) or 1.0),
                "filters": clip.get("filters", []) or [],
            }
        )
        previous_end = end

    if not normalized:
        raise ValueError("No valid clips remained after normalization")

    recipe["clips"] = normalized
    recipe.setdefault("overlays", [])
    recipe.setdefault("color_grade", {})
    recipe.setdefault("audio", {})
    recipe.setdefault("notes", "")
    return recipe


def build_ffmpeg_command(recipe, source_path, output_path, has_audio):
    clips = recipe["clips"]
    cmd = ["ffmpeg", "-y"]

    for clip in clips:
        cmd += [
            "-ss",
            str(clip["source_start"]),
            "-to",
            str(clip["source_end"]),
            "-i",
            source_path,
        ]

    filter_parts = []
    clip_count = len(clips)

    for index in range(clip_count):
        speed = float(clips[index].get("speed", 1.0) or 1.0)
        if speed <= 0:
            speed = 1.0
        filter_parts.append(
            f"[{index}:v]setpts={1 / speed}*PTS,"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v{index}]"
        )
        if has_audio:
            audio_filters = ",".join(atempo_chain(speed))
            filter_parts.append(f"[{index}:a]{audio_filters}[a{index}]")

    video_inputs = "".join(f"[v{index}]" for index in range(clip_count))
    filter_parts.append(f"{video_inputs}concat=n={clip_count}:v=1:a=0[vconcat]")

    if has_audio:
        audio_inputs = "".join(f"[a{index}]" for index in range(clip_count))
        filter_parts.append(f"{audio_inputs}concat=n={clip_count}:v=0:a=1[aconcat]")
    else:
        filter_parts.append("anullsrc=channel_layout=stereo:sample_rate=48000[aconcat]")

    color_grade = recipe.get("color_grade", {})
    eq_filter = (
        f"eq=brightness={color_grade.get('brightness', 0)}:"
        f"contrast={color_grade.get('contrast', 1)}:"
        f"saturation={color_grade.get('saturation', 1)}:"
        f"gamma={color_grade.get('gamma', 1)}"
    )
    filter_parts.append(f"[vconcat]{eq_filter}[vgraded]")
    last_v = "vgraded"

    overlay_index = 0
    for overlay in recipe.get("overlays", []):
        if overlay.get("type") != "text":
            continue
        text = sanitize_drawtext_text(overlay.get("text", ""))
        if not text:
            continue
        start = overlay.get("start_time", 0)
        end = overlay.get("end_time", 3)
        filter_parts.append(
            f"[{last_v}]drawtext="
            f"text={text}"
            f":fontsize={overlay.get('fontsize', 52)}"
            f":fontcolor={overlay.get('fontcolor', 'white')}"
            f":bordercolor={overlay.get('bordercolor', 'black')}"
            f":borderw={overlay.get('borderw', 3)}"
            f":x={overlay.get('x', '(w-text_w)/2')}"
            f":y={overlay.get('y', 'h*0.15')}"
            f":enable='between(t\\,{start}\\,{end})'"
            f"[vtxt{overlay_index}]"
        )
        last_v = f"vtxt{overlay_index}"
        overlay_index += 1

    volume = recipe.get("audio", {}).get("original_volume", 1.0)
    filter_parts.append(f"[aconcat]volume={volume}[afinal]")

    filter_complex = ";".join(filter_parts)
    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", f"[{last_v}]", "-map", "[afinal]"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]
    return cmd


def render_video(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[pipeline] ffmpeg_exit_code={result.returncode}", flush=True)
    stderr_lines = result.stderr.splitlines()
    tail = stderr_lines[-30:]
    if tail:
        print("[pipeline] ffmpeg_stderr_tail_start", flush=True)
        for line in tail:
            print(line, flush=True)
        print("[pipeline] ffmpeg_stderr_tail_end", flush=True)
    if result.returncode != 0:
        raise RuntimeError("FFmpeg render failed")


def upload_output(output_path, upload_url):
    with open(output_path, "rb") as file_obj:
        response = requests.put(
            upload_url,
            data=file_obj,
            headers={"Content-Type": "video/mp4"},
            timeout=300,
        )
    ensure_success(response)


def handler(job):
    work_dir = None
    try:
        input_data = job.get("input", {})

        log_step(1, "validate input")
        required = ["job_id", "video_url", "vibe", "user_id", "upload_url"]
        missing = [field for field in required if not input_data.get(field)]
        if missing:
            return {"error": f"Missing required input fields: {', '.join(missing)}"}

        job_id = input_data["job_id"]
        work_dir = f"/tmp/promptly-{job_id}"
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")
        os.makedirs(work_dir, exist_ok=True)

        log_step(2, "download source video")
        download_source(input_data["video_url"], source_path)

        log_step(3, "gemini visual analysis")
        analysis = input_data.get("cached_analysis")
        if analysis is None:
            analysis = run_gemini_analysis(source_path)
        else:
            print("[pipeline] using cached analysis", flush=True)

        log_step(4, "deepgram transcription")
        transcript_text, words, speech_segments, sentence_boundaries = run_deepgram_transcription(
            source_path
        )
        analysis.setdefault("speech", {})
        analysis["speech"]["has_speech"] = bool(transcript_text.strip())
        analysis["speech"]["segments"] = speech_segments
        analysis["speech"]["sentence_boundaries"] = sentence_boundaries
        analysis.setdefault("metadata", {})
        analysis["metadata"]["transcript_word_count"] = len(words)

        log_step(5, "expand vibe with claude haiku")
        expanded_vibe = expand_vibe(input_data["vibe"])

        log_step(6, "generate edit recipe with claude sonnet")
        duration = float(analysis.get("duration") or ffprobe_duration(source_path))
        recipe = generate_edit_recipe(analysis, transcript_text, expanded_vibe, duration)
        recipe = normalize_recipe(recipe, duration)

        log_step(7, "build and run ffmpeg")
        has_audio = source_has_audio(source_path)
        cmd = build_ffmpeg_command(recipe, source_path, output_path, has_audio)
        render_started = time.time()
        render_video(cmd)
        render_elapsed = time.time() - render_started

        log_step(8, "upload output")
        upload_output(output_path, input_data["upload_url"])

        log_step(9, "return result")
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        return {
            "status": "success",
            "job_id": job_id,
            "render_time": round(render_elapsed, 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": recipe,
        }
    except Exception as exc:
        traceback.print_exc()
        return {"error": str(exc)}
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


runpod.serverless.start({"handler": handler})
