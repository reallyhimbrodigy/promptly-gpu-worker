import base64
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
import google.generativeai as genai
import requests
import runpod

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not all([GEMINI_API_KEY, DEEPGRAM_API_KEY, ANTHROPIC_API_KEY]):
    missing = [k for k, v in {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "DEEPGRAM_API_KEY": DEEPGRAM_API_KEY,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    }.items() if not v]
    raise RuntimeError(f"Missing required environment variables: {missing}")

MAX_JOB_SECONDS = 300
FFMPEG_TIMEOUT_SECONDS = 120


FILLER_WORDS = {
    "uh",
    "um",
    "erm",
    "ah",
    "like",
    "you know",
    "sort of",
    "kind of",
    "actually",
    "basically",
    "literally",
}

GEMINI_ANALYSIS_PROMPT = """
Analyze this source video for a short-form editing pipeline.
Return JSON only. No markdown or commentary.

The JSON schema must include these top-level fields exactly:
- shots: array
- speech: object
- audio: object
- video_profile: object
- frame_layout: object
- color_baseline: object
- visual_cuts: array
- tightened_timeline: array

Requirements:
- shots should describe meaningful shot ranges with start/end, framing, subject/action, and editing relevance.
- speech should summarize pacing, hooks, emphasis moments, transcript observations, and quoted moments if available.
- audio should describe energy, noise, music/SFX presence, and mix considerations.
- video_profile should include width, height, fps, duration, aspect_ratio, and overall format observations.
- frame_layout should describe safe areas, headroom, text-safe guidance, and visual composition.
- color_baseline should describe exposure, contrast, saturation, white balance, and mood.
- visual_cuts should be an array of timestamps or timestamp objects indicating visually significant cut/change moments.
- tightened_timeline should be an array of candidate keep ranges with start/end/reason.

Be concrete and editor-facing. Return valid JSON only.
""".strip()

EDIT_PROMPT_STATIC_PREFIX = """
=== ROLE ===
You are an expert short-form video editor generating an edit recipe for an automated pipeline.

=== OUTPUT CONTRACT ===
Return JSON only.

=== REQUIRED JSON SHAPE ===
{
  "title": "string",
  "creative_rationale": "string",
  "caption_style": "none|clean|bold",
  "global_grade": {
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0
  },
  "cuts": [
    {
      "start": 0.0,
      "end": 0.0,
      "speed": 1.0,
      "transition": {
        "type": "hard_cut|fade|dissolve|wipeleft|wiperight|slideleft|slideright",
        "duration": 0.0
      },
      "grade": {
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0
      },
      "text_overlay": {
        "text": "string",
        "start": 0.0,
        "end": 0.0,
        "x": "(w-text_w)/2",
        "y": "h*0.14",
        "font_size": 52,
        "color": "white",
        "border_color": "black",
        "borderw": 3
      }
    }
  ]
}

=== EDITING RULES ===
- Optimize for fast, high-retention short-form pacing.
- Prefer strong hooks, remove dead air, and keep narrative coherence.
- Respect transcript meaning and avoid clipping words.
- Use transitions sparingly.
- Caption style can be none, clean, or bold.
- Assume final delivery is 1080x1920 at 30fps.

""".strip()


class PipelineStepError(Exception):
    def __init__(self, step, message):
        super().__init__(message)
        self.step = step
        self.message = message


def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"[download] {os.path.basename(dest)}: {size_mb:.1f}MB")


def download_file_task(args):
    """Wrapper for parallel downloads. Returns (key, path) on success."""
    url, dest, label = args
    download_file(url, dest)
    return (label, dest)


def download_all_parallel(tasks, max_workers=8):
    """
    Download all files in parallel.
    tasks: list of (url, dest_path, label) tuples
    Returns dict of {label: path}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file_task, task): task for task in tasks}
        for future in as_completed(futures):
            label, path = future.result()
            results[label] = path
    return results


def replace_placeholders(value, clip_paths, sfx_paths, broll_paths, watermark_path, font_path, captions_path, output_path):
    """Replace {CLIP_0}, {BROLL_0}, {FONT_PATH}, etc. in a string."""
    for i, path in enumerate(clip_paths):
        value = value.replace(f"{{CLIP_{i}}}", path)
    for i, path in enumerate(sfx_paths):
        value = value.replace(f"{{SFX_{i}}}", path)
    for i, path in enumerate(broll_paths):
        value = value.replace(f"{{BROLL_{i}}}", path)
    if watermark_path:
        value = value.replace("{WATERMARK}", watermark_path)
    if font_path:
        value = value.replace("{FONT_PATH}", font_path)
    if captions_path:
        value = value.replace("{CAPTIONS_PATH}", captions_path)
    value = value.replace("{OUTPUT}", output_path)
    return value


def now():
    return time.time()


def log_step(step, message):
    print(f"[{step}] {message}")


def run_command(cmd, step, fail_message=None):
    printable = cmd if isinstance(cmd, str) else " ".join(shlex.quote(part) for part in cmd)
    log_step(step, f"Running: {printable[:500]}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    if result.stderr:
        stderr_lines = result.stderr.strip().split("\n")
        tail = stderr_lines[-30:] if len(stderr_lines) > 30 else stderr_lines
        for line in tail:
            print(f"[{step}] {line}")
    if result.returncode != 0:
        error_tail = ""
        if result.stderr:
            error_tail = "\n".join(result.stderr.strip().split("\n")[-20:])
        raise PipelineStepError(step, fail_message or f"Command failed (exit {result.returncode}): {error_tail}")
    return result


def parse_json_response(text, step):
    if not text:
        raise PipelineStepError(step, "Empty JSON response")
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise PipelineStepError(step, f"Invalid JSON response: {stripped[:400]}")


def ffprobe_json(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise PipelineStepError("ffprobe", f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def log_probe(label, path):
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    print(f"[probe] {label}: {probe.stdout.strip()}")


def get_video_profile(path):
    metadata = ffprobe_json(path)
    video_stream = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise PipelineStepError("normalize", "No video stream found")
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    fps_num, fps_den = fps_raw.split("/")
    fps = float(fps_num) / float(fps_den) if float(fps_den) else 0.0
    duration = float(metadata.get("format", {}).get("duration", 0.0))
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "aspect_ratio": f"{width}:{height}" if width and height else None,
        "metadata": metadata,
    }


def normalize_source(source_path, work_dir):
    step = "normalize"
    started = now()
    log_step(step, "Starting")
    log_probe("source", source_path)
    profile = get_video_profile(source_path)
    needs_normalize = (
        profile["width"] != 1080
        or profile["height"] != 1920
        or abs(profile["fps"] - 30.0) > 0.01
    )
    if not needs_normalize:
        log_step(step, f"Skipped in {now() - started:.1f}s")
        return source_path, profile, False

    normalized_path = os.path.join(work_dir, "normalized_source.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        source_path,
        "-vf",
        "fps=30,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        normalized_path,
    ]
    run_command(cmd, step, "Failed to normalize source video")
    normalized_profile = get_video_profile(normalized_path)
    log_probe("normalized_source", normalized_path)
    log_step(step, f"Completed in {now() - started:.1f}s")
    return normalized_path, normalized_profile, True


def analyze_with_gemini(source_path, cached_analysis):
    step = "gemini"
    started = now()
    if cached_analysis:
        log_step(step, "Using cached analysis")
        return cached_analysis

    log_step(step, "Starting")
    genai.configure(api_key=GEMINI_API_KEY)
    with ThreadPoolExecutor(max_workers=1) as executor:
        uploaded = executor.submit(genai.upload_file, path=source_path).result(timeout=30)
    poll_started = now()
    while now() - poll_started < 60:
        uploaded = genai.get_file(uploaded.name)
        state_name = getattr(getattr(uploaded, "state", None), "name", "")
        if state_name == "ACTIVE":
            break
        if state_name == "FAILED":
            raise PipelineStepError(step, "Gemini file processing failed")
        time.sleep(1)
    else:
        raise PipelineStepError(step, "Gemini file did not become ACTIVE within 60s")

    model = genai.GenerativeModel("gemini-2.5-flash")
    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(model.generate_content, [GEMINI_ANALYSIS_PROMPT, uploaded]).result(timeout=60)
    analysis = parse_json_response(getattr(response, "text", ""), step)
    log_step(step, f"Analysis complete in {now() - started:.1f}s")
    return analysis


def build_transcript_segments(words):
    sentence_boundaries = []
    segments = []
    current = None
    prev_end = None

    for index, word in enumerate(words):
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        token = word.get("punctuated_word") or word.get("word") or ""
        gap = start - prev_end if prev_end is not None else 0.0
        if current is None or gap > 0.1:
            if current:
                current["text"] = " ".join(current["tokens"]).strip()
                segments.append(current)
                sentence_boundaries.append(current["end"])
            current = {
                "start": start,
                "end": end,
                "tokens": [token],
                "word_indexes": [index],
            }
        else:
            current["end"] = end
            current["tokens"].append(token)
            current["word_indexes"].append(index)

        if token.endswith((".", "!", "?")):
            current["text"] = " ".join(current["tokens"]).strip()
            segments.append(current)
            sentence_boundaries.append(current["end"])
            current = None
        prev_end = end

    if current:
        current["text"] = " ".join(current["tokens"]).strip()
        segments.append(current)
        sentence_boundaries.append(current["end"])

    return sentence_boundaries, segments


def transcribe_with_deepgram(source_path, work_dir):
    step = "deepgram"
    started = now()
    log_step(step, "Starting")
    audio_path = os.path.join(work_dir, "audio.wav")
    extract_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        source_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        audio_path,
    ]
    run_command(extract_cmd, step, "Failed to extract audio for Deepgram")

    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            "https://api.deepgram.com/v1/listen",
            params={
                "model": "nova-3",
                "punctuate": "true",
                "utterances": "false",
                "words": "true",
                "smart_format": "true",
            },
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "audio/wav",
            },
            data=audio_file,
            timeout=30,
        )
    response.raise_for_status()
    payload = response.json()
    alt = payload["results"]["channels"][0]["alternatives"][0]
    words = alt.get("words", [])
    sentence_boundaries, segments = build_transcript_segments(words)
    transcript = {
        "text": alt.get("transcript", ""),
        "duration": payload.get("metadata", {}).get("duration"),
        "words": [
            {
                "word": item.get("word", ""),
                "punctuated_word": item.get("punctuated_word", item.get("word", "")),
                "start": float(item.get("start", 0.0)),
                "end": float(item.get("end", 0.0)),
                "confidence": item.get("confidence"),
                "is_filler": item.get("word", "").strip().lower() in FILLER_WORDS,
            }
            for item in words
        ],
        "sentence_boundaries": sentence_boundaries,
        "segments": segments,
    }
    log_step(step, f"Completed in {now() - started:.1f}s")
    return transcript


def detect_scene_cuts(source_path):
    step = "scdet"
    started = now()
    log_step(step, "Starting")
    cmd = [
        "ffmpeg",
        "-i",
        source_path,
        "-vf",
        "scdet=threshold=10",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    stderr = result.stderr or ""
    timestamps = [float(match.group(1)) for match in re.finditer(r"lavfi\.scd\.time[:=]\s*([0-9.]+)", stderr)]
    if result.returncode != 0:
        error_tail = "\n".join(stderr.strip().split("\n")[-20:])
        raise PipelineStepError(step, f"Scene detection failed: {error_tail}")
    log_step(step, f"Detected {len(timestamps)} cuts in {now() - started:.1f}s")
    return timestamps


def expand_vibe(vibe):
    step = "vibe"
    started = now()
    log_step(step, "Starting")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=45.0)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Expand the user's raw vibe into detailed creative direction for a video editor. "
                            "Cover pacing, tone, captions, transitions, color, and audience feel.\n\n"
                            f"User vibe:\n{vibe}"
                        ),
                    }
                ],
            }
        ],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
    log_step(step, f"Completed in {now() - started:.1f}s")
    return text


def build_force_key_frames(timestamps):
    cleaned = []
    for ts in timestamps:
        if ts is None:
            continue
        ts = round(float(ts), 3)
        if ts < 0.05:
            continue
        cleaned.append(ts)
    unique = sorted(set(cleaned))
    return ",".join(f"{ts:.3f}" for ts in unique)


def encode_keyframed_source(source_path, transcript, work_dir):
    step = "keyframe"
    started = now()
    log_step(step, "Starting")
    timestamps = build_force_key_frames(transcript.get("sentence_boundaries", []))
    output_path = os.path.join(work_dir, "keyframed_source.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        source_path,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
    ]
    if timestamps:
        cmd.extend(["-force_key_frames", timestamps])
    cmd.extend(["-c:a", "copy", output_path])
    run_command(cmd, step, "Failed to encode keyframed source")
    log_probe("keyframed_source", output_path)
    log_step(step, f"Completed in {now() - started:.1f}s")
    return output_path


def tighten_transcript(transcript, duration):
    step = "tighten"
    started = now()
    log_step(step, "Starting")
    words = transcript.get("words", [])
    tightened_segments = []
    removed_seconds = 0.0
    current_start = None
    current_end = None
    prev_end = None

    for word in words:
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        token = word.get("word", "").strip().lower()
        is_filler = word.get("is_filler") or token in FILLER_WORDS

        if prev_end is not None and start - prev_end > 0.15:
            removed_seconds += start - prev_end
            if current_start is not None and current_end is not None:
                tightened_segments.append({"start": round(current_start, 3), "end": round(current_end, 3), "reason": "speech cluster"})
                current_start = None
                current_end = None

        if is_filler:
            removed_seconds += max(0.0, end - start)
            prev_end = end
            continue

        if current_start is None:
            current_start = max(0.0, start - 0.03)
        current_end = end + 0.03
        prev_end = end

    if current_start is not None and current_end is not None:
        tightened_segments.append({"start": round(current_start, 3), "end": round(min(duration, current_end), 3), "reason": "speech cluster"})

    log_step(step, f"Completed in {now() - started:.1f}s; removed {removed_seconds:.2f}s")
    return tightened_segments, round(removed_seconds, 2)


def extract_scene_frames(source_path, timestamps, work_dir):
    step = "scene_frames"
    started = now()
    log_step(step, "Starting")
    frame_dir = os.path.join(work_dir, "scene_frames")
    os.makedirs(frame_dir, exist_ok=True)
    images = []

    def extract_one(index, timestamp):
        output_path = os.path.join(frame_dir, f"scene_{index:03d}.jpg")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            source_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            output_path,
        ]
        run_command(cmd, step, f"Failed to extract scene frame at {timestamp:.3f}s")
        with open(output_path, "rb") as handle:
            return {
                "timestamp": round(timestamp, 3),
                "data": base64.b64encode(handle.read()).decode("ascii"),
                "path": output_path,
            }

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(extract_one, index, ts) for index, ts in enumerate(timestamps)]
        for future in as_completed(futures):
            images.append(future.result())

    images.sort(key=lambda item: item["timestamp"])
    log_step(step, f"Completed in {now() - started:.1f}s")
    return images


def build_edit_prompt_dynamic(job_input, expanded_vibe, analysis, transcript, tightened_segments, scene_cuts):
    return (
        "=== WHO THE USER IS ===\n"
        f"user_id: {job_input.get('user_id')}\n"
        f"job_id: {job_input.get('job_id')}\n\n"
        "=== USER VIBE ===\n"
        f"{job_input.get('vibe', '').strip()}\n\n"
        "=== EXPANDED VIBE ===\n"
        f"{expanded_vibe.strip()}\n\n"
        "=== ANALYSIS ===\n"
        f"{json.dumps(analysis, ensure_ascii=True)}\n\n"
        "=== TRANSCRIPT ===\n"
        f"{json.dumps(transcript, ensure_ascii=True)}\n\n"
        "=== TIGHTENED TIMELINE ===\n"
        f"{json.dumps(tightened_segments, ensure_ascii=True)}\n\n"
        "=== SCENE CUTS ===\n"
        f"{json.dumps(scene_cuts, ensure_ascii=True)}\n"
    )


def request_edit_recipe(job_input, expanded_vibe, analysis, transcript, tightened_segments, scene_frames, scene_cuts):
    step = "claude_recipe"
    started = now()
    log_step(step, "Starting")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=45.0)
    dynamic_suffix = build_edit_prompt_dynamic(job_input, expanded_vibe, analysis, transcript, tightened_segments, scene_cuts)
    content = [
        {
            "type": "text",
            "text": EDIT_PROMPT_STATIC_PREFIX,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": dynamic_suffix,
        },
    ]
    for frame in scene_frames:
        content.append({"type": "text", "text": f"Scene frame at {frame['timestamp']:.3f}s"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": frame["data"],
                },
            }
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    recipe = parse_json_response(text, step)
    log_step(step, f"Completed in {now() - started:.1f}s")
    return recipe


def normalize_cut(cut, fallback_end):
    start = float(cut.get("start", 0.0))
    end = cut.get("end")
    duration = cut.get("duration")
    if end is None and duration is not None:
        end = start + float(duration)
    if end is None:
        end = fallback_end
    end = float(end)
    if end <= start:
        end = start + 0.2
    speed = float(cut.get("speed", 1.0) or 1.0)
    transition = cut.get("transition") or {"type": "hard_cut", "duration": 0.0}
    grade = cut.get("grade") or {}
    text_overlay = cut.get("text_overlay")
    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(end - start, 3),
        "speed": speed,
        "transition": {
            "type": transition.get("type", "hard_cut"),
            "duration": float(transition.get("duration", 0.0) or 0.0),
        },
        "grade": {
            "brightness": float(grade.get("brightness", 0.0) or 0.0),
            "contrast": float(grade.get("contrast", 1.0) or 1.0),
            "saturation": float(grade.get("saturation", 1.0) or 1.0),
        },
        "text_overlay": text_overlay,
    }


def extract_stream_copy_clips(keyframed_source_path, recipe, work_dir):
    step = "extract_clips"
    started = now()
    log_step(step, "Starting")
    cuts = recipe.get("cuts") or []
    if not cuts:
        raise PipelineStepError(step, "Edit recipe returned no cuts")

    clip_dir = os.path.join(work_dir, "clips")
    os.makedirs(clip_dir, exist_ok=True)
    normalized_cuts = [normalize_cut(cut, 0.2) for cut in cuts]

    def extract_one(index, cut):
        clip_path = os.path.join(clip_dir, f"clip_{index:03d}.mp4")
        clip_started = now()
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{cut['start']:.3f}",
            "-t",
            f"{cut['duration']:.3f}",
            "-i",
            keyframed_source_path,
            "-c",
            "copy",
            clip_path,
        ]
        run_command(cmd, step, f"Failed to extract clip {index}")
        log_probe(f"clip_{index}", clip_path)
        log_step(step, f"clip_{index} extracted in {now() - clip_started:.1f}s")
        return {"path": clip_path, "cut": cut}

    clips = []
    with ThreadPoolExecutor(max_workers=min(8, len(normalized_cuts))) as executor:
        futures = [executor.submit(extract_one, index, cut) for index, cut in enumerate(normalized_cuts)]
        for future in as_completed(futures):
            clips.append(future.result())

    clips.sort(key=lambda item: item["cut"]["start"])
    log_step(step, f"Completed in {now() - started:.1f}s")
    return clips


def escape_drawtext(text):
    return (
        text.replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
        .replace(",", r"\,")
    )


def ffmpeg_color_expr(value, default):
    return f"{value:.3f}" if value is not None else f"{default:.3f}"


def atempo_chain(speed):
    if speed <= 0:
        speed = 1.0
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def build_ass_captions(transcript, recipe, work_dir):
    caption_style = recipe.get("caption_style", "clean")
    if caption_style == "none":
        return None

    ass_path = os.path.join(work_dir, "captions.ass")
    if caption_style == "bold":
        font_size = 64
        weight = 1
    else:
        font_size = 52
        weight = 0

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Montserrat,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,{weight},0,0,0,100,100,0,0,1,3,0,2,80,80,180,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for segment in transcript.get("segments", []):
        text = segment.get("text", "").replace("\n", " ").strip()
        if not text:
            continue
        start = ass_timestamp(segment["start"])
        end = ass_timestamp(segment["end"])
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return ass_path


def ass_timestamp(seconds):
    total = max(0.0, float(seconds))
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = int(total % 60)
    centis = int(round((total - math.floor(total)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
    if secs == 60:
        minutes += 1
        secs = 0
    if minutes == 60:
        hours += 1
        minutes = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def build_render_command(clips, recipe, captions_path, output_path):
    step = "build_render"
    started = now()
    log_step(step, "Starting")
    ffmpeg_cmd = ["ffmpeg", "-y"]
    for clip in clips:
        ffmpeg_cmd.extend(["-i", clip["path"]])

    global_grade = recipe.get("global_grade") or {}
    brightness = float(global_grade.get("brightness", 0.0) or 0.0)
    contrast = float(global_grade.get("contrast", 1.0) or 1.0)
    saturation = float(global_grade.get("saturation", 1.0) or 1.0)

    filter_parts = []
    video_labels = []
    audio_labels = []
    clip_output_durations = []

    for index, clip in enumerate(clips):
        cut = clip["cut"]
        speed = float(cut.get("speed", 1.0) or 1.0)
        grade = cut.get("grade") or {}
        clip_brightness = brightness + float(grade.get("brightness", 0.0) or 0.0)
        clip_contrast = contrast * float(grade.get("contrast", 1.0) or 1.0)
        clip_saturation = saturation * float(grade.get("saturation", 1.0) or 1.0)
        video_label = f"v{index}"
        audio_label = f"a{index}"
        filter_parts.append(
            f"[{index}:v]settb=AVTB,fps=30,"
            "crop='min(iw,ih*1080/1920)':'min(ih,iw*1920/1080)',"
            "scale=1080:1920,setpts=(PTS-STARTPTS)/"
            f"{speed:.4f},eq=brightness={ffmpeg_color_expr(clip_brightness, 0.0)}:"
            f"contrast={ffmpeg_color_expr(clip_contrast, 1.0)}:saturation={ffmpeg_color_expr(clip_saturation, 1.0)}"
            f"[{video_label}]"
        )
        filter_parts.append(
            f"[{index}:a]afftdn,{atempo_chain(speed)},dynaudnorm,alimiter[{audio_label}]"
        )
        video_labels.append(video_label)
        audio_labels.append(audio_label)
        clip_output_durations.append(cut["duration"] / speed)

    if all((clip["cut"]["transition"].get("type") == "hard_cut") for clip in clips):
        concat_inputs = "".join(f"[{video_labels[index]}][{audio_labels[index]}]" for index in range(len(clips)))
        filter_parts.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=1[vout][aout]")
    else:
        current_video = f"[{video_labels[0]}]"
        current_audio = f"[{audio_labels[0]}]"
        elapsed = clip_output_durations[0]
        for index in range(1, len(clips)):
            transition = clips[index - 1]["cut"]["transition"]
            transition_type = transition.get("type", "fade")
            if transition_type == "hard_cut":
                transition_type = "fade"
            transition_duration = max(0.001, float(transition.get("duration", 0.18) or 0.18))
            next_video = f"[{video_labels[index]}]"
            next_audio = f"[{audio_labels[index]}]"
            video_out = f"vx{index}"
            audio_out = f"ax{index}"
            offset = max(0.0, elapsed - transition_duration)
            filter_parts.append(
                f"{current_video}{next_video}xfade=transition={transition_type}:duration={transition_duration:.3f}:offset={offset:.3f}[{video_out}]"
            )
            filter_parts.append(
                f"{current_audio}{next_audio}acrossfade=d={transition_duration:.3f}:c1=tri:c2=tri[{audio_out}]"
            )
            current_video = f"[{video_out}]"
            current_audio = f"[{audio_out}]"
            elapsed += clip_output_durations[index] - transition_duration
        filter_parts.append(f"{current_video}null[vtmp]")
        filter_parts.append(f"{current_audio}anull[aout]")
        filter_parts.append("[vtmp]null[vout]")

    active_video_label = "[vout]"
    if captions_path:
        escaped = captions_path.replace("\\", "\\\\").replace(":", "\\:")
        filter_parts.append(f"{active_video_label}ass='{escaped}'[vcap]")
        active_video_label = "[vcap]"

    overlay_counter = 0
    for clip in clips:
        overlay = clip["cut"].get("text_overlay")
        if not overlay or not overlay.get("text"):
            continue
        next_label = f"vtxt{overlay_counter}"
        text = escape_drawtext(str(overlay["text"]))
        start = float(overlay.get("start", clip["cut"]["start"]))
        end = float(overlay.get("end", clip["cut"]["end"]))
        x = overlay.get("x", "(w-text_w)/2")
        y = overlay.get("y", "h*0.14")
        font_size = int(overlay.get("font_size", 52))
        color = overlay.get("color", "white")
        border_color = overlay.get("border_color", "black")
        borderw = int(overlay.get("borderw", 3))
        filter_parts.append(
            f"{active_video_label}drawtext=text='{text}':fontsize={font_size}:"
            f"fontcolor={color}:bordercolor={border_color}:borderw={borderw}:x={x}:y={y}:"
            f"enable='between(t,{start:.3f},{end:.3f})'[{next_label}]"
        )
        active_video_label = f"[{next_label}]"
        overlay_counter += 1

    if active_video_label != "[vfinal]":
        filter_parts.append(f"{active_video_label}null[vfinal]")

    ffmpeg_cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vfinal]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-b:v",
            "4M",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            output_path,
        ]
    )
    log_step(step, f"Completed in {now() - started:.1f}s")
    return ffmpeg_cmd


def render_output(ffmpeg_cmd, output_path):
    step = "render"
    started = now()
    log_step(step, "Starting")
    log_step(step, f"FFmpeg cmd length: {sum(len(part) for part in ffmpeg_cmd)} chars")
    log_step(step, f"cmd first 300 chars: {' '.join(ffmpeg_cmd)[:300]}")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    elapsed = now() - started
    if result.stderr:
        stderr_lines = result.stderr.strip().split("\n")
        tail = stderr_lines[-30:] if len(stderr_lines) > 30 else stderr_lines
        for line in tail:
            print(f"[ffmpeg] {line}")
    if result.returncode != 0:
        error_tail = "\n".join((result.stderr or "").strip().split("\n")[-20:])
        raise PipelineStepError(step, f"FFmpeg failed (exit {result.returncode}): {error_tail}")
    if not os.path.exists(output_path):
        raise PipelineStepError(step, "No output file")

    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    fps_match = re.findall(r"fps=\s*([0-9.]+)", result.stderr or "")
    rendered_fps = fps_match[-1] if fps_match else "unknown"
    log_step(step, f"Completed in {elapsed:.1f}s at fps={rendered_fps}")
    log_step(step, f"Output: {output_size_mb:.1f}MB")
    return round(elapsed, 1), round(output_size_mb, 1)


def upload_output(upload_url, output_path):
    step = "upload"
    started = now()
    log_step(step, "Starting")
    with open(output_path, "rb") as handle:
        response = requests.put(upload_url, data=handle, headers={"Content-Type": "video/mp4"}, timeout=300)
    response.raise_for_status()
    elapsed = now() - started
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log_step(step, f"Uploaded {size_mb:.1f}MB in {elapsed:.1f}s")


def merge_analysis_with_tightening(analysis, tightened_segments):
    merged = dict(analysis or {})
    merged["tightened_timeline"] = tightened_segments
    return merged


def validate_job_input(job_input):
    required = ["job_id", "video_url", "vibe", "user_id", "upload_url"]
    missing = [field for field in required if not job_input.get(field)]
    if missing:
        raise PipelineStepError("input", f"Missing required input fields: {', '.join(missing)}")


def log_ffmpeg_version():
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    first_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
    log_step("worker", f"FFmpeg: {first_line}")


def check_job_timeout(job_start):
    if time.time() - job_start > MAX_JOB_SECONDS:
        raise PipelineStepError("timeout_guard", "Job timeout")


def handler(job):
    work_dir = tempfile.mkdtemp(prefix="promptly-")
    total_started = now()
    job_start = time.time()
    try:
        job_input = job["input"]
        validate_job_input(job_input)
        log_step("worker", f"Work dir: {work_dir}")
        log_step("worker", f"job_id={job_input.get('job_id')}")
        log_ffmpeg_version()
        check_job_timeout(job_start)

        source_path = os.path.join(work_dir, "source.mp4")
        step_started = now()
        log_step("download", "Starting")
        download_file(job_input["video_url"], source_path)
        log_step("download", f"Completed in {now() - step_started:.1f}s")
        check_job_timeout(job_start)

        normalized_path, profile, _ = normalize_source(source_path, work_dir)
        check_job_timeout(job_start)

        wave_started = now()
        log_step("parallel_wave", "Starting")
        with ThreadPoolExecutor(max_workers=5) as executor:
            gemini_future = executor.submit(analyze_with_gemini, normalized_path, job_input.get("cached_analysis"))
            deepgram_future = executor.submit(transcribe_with_deepgram, normalized_path, work_dir)
            scdet_future = executor.submit(detect_scene_cuts, normalized_path)
            vibe_future = executor.submit(expand_vibe, job_input.get("vibe", ""))
            keyframe_future = executor.submit(
                lambda: encode_keyframed_source(normalized_path, deepgram_future.result(), work_dir)
            )

            analysis = gemini_future.result()
            transcript = deepgram_future.result()
            scene_cuts = scdet_future.result()
            expanded_vibe = vibe_future.result()
            keyframed_source_path = keyframe_future.result()

        log_step("parallel_wave", f"Completed in {now() - wave_started:.1f}s")
        check_job_timeout(job_start)

        tightened_segments, _ = tighten_transcript(transcript, profile["duration"])
        analysis = merge_analysis_with_tightening(analysis, tightened_segments)
        check_job_timeout(job_start)
        scene_frames = extract_scene_frames(normalized_path, scene_cuts, work_dir)
        check_job_timeout(job_start)
        recipe = request_edit_recipe(
            job_input,
            expanded_vibe,
            analysis,
            transcript,
            tightened_segments,
            scene_frames,
            scene_cuts,
        )
        check_job_timeout(job_start)
        clips = extract_stream_copy_clips(keyframed_source_path, recipe, work_dir)
        check_job_timeout(job_start)
        captions_path = build_ass_captions(transcript, recipe, work_dir)
        output_path = os.path.join(work_dir, "output.mp4")
        ffmpeg_cmd = build_render_command(clips, recipe, captions_path, output_path)
        render_time, output_size_mb = render_output(ffmpeg_cmd, output_path)
        check_job_timeout(job_start)
        upload_output(job_input["upload_url"], output_path)

        total_time = round(now() - total_started, 1)
        return {
            "status": "success",
            "render_time": render_time,
            "total_time": total_time,
            "output_size_mb": output_size_mb,
            "edit_recipe": recipe,
            "analysis": analysis,
        }
    except PipelineStepError as exc:
        print(f"[error] step={exc.step} message={exc.message}")
        return {"error": exc.message, "step": exc.step}
    except Exception as exc:
        traceback.print_exc()
        return {"error": str(exc), "step": "unknown"}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


runpod.serverless.start({"handler": handler})
