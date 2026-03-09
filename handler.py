import runpod
import subprocess
import os
import requests
import tempfile
import time
import shutil
import json
import re
import anthropic
import google.generativeai as genai
from deepgram import DeepgramClient, PrerecordedOptions


def handler(job):
    input_data = job["input"]
    work_dir = None
    try:
        # Step 1 — Validate input
        required = ["job_id", "video_url", "vibe", "user_id", "upload_url"]
        missing = [f for f in required if not input_data.get(f)]
        if missing:
            return {"error": f"Missing required input fields: {', '.join(missing)}"}

        job_id = input_data["job_id"]
        video_url = input_data["video_url"]
        vibe = input_data["vibe"]
        upload_url = input_data["upload_url"]
        cached_analysis = input_data.get("cached_analysis")

        work_dir = tempfile.mkdtemp(prefix=f"promptly-{job_id}-")
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")

        # Step 2 — Download source video
        t = time.time()
        print(f"[pipeline] step=download")
        r = requests.get(video_url, stream=True)
        r.raise_for_status()
        with open(source_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        size_mb = os.path.getsize(source_path) / (1024 * 1024)
        print(f"[pipeline] download complete: {size_mb:.1f}MB in {time.time()-t:.1f}s")

        # Step 3 — Gemini visual analysis
        if cached_analysis:
            print(f"[pipeline] step=analysis (cache HIT)")
            analysis = cached_analysis
        else:
            print(f"[pipeline] step=analysis (Gemini)")
            t = time.time()
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            gemini_file = genai.upload_file(source_path)
            deadline = time.time() + 60
            while gemini_file.state.name != "ACTIVE":
                if time.time() > deadline:
                    return {"error": "Gemini file upload timed out"}
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)
            model = genai.GenerativeModel("gemini-2.0-flash")
            system_prompt = """You are a professional video editor analyzing footage for social media editing.

Analyze this video and return a JSON object with this exact structure:
{
  "duration": <float seconds>,
  "shots": [{"start":<float>,"end":<float>,"description":"<str>","action":"<str>","visual":"<str>","energy":<0-1>,"score":<0-1>,"editing_value":"essential|strong|moderate|weak"}],
  "speech": {"has_speech":<bool>,"segments":[],"sentence_boundaries":[]},
  "audio": {"music":"none|background|prominent"},
  "peak_moments": [],
  "safe_cut_points": [],
  "color_baseline": {"brightness":<-1 to 1>,"contrast":<0.5-2>,"saturation":<0.5-2>,"gamma":<0.5-2>,"color_temperature":"cool|neutral|warm","assessment":"<str>"},
  "frame_layout": {"subject_position":"<str>","free_zones":"<str>","existing_overlays":{"has_burned_captions":<bool>,"has_text_graphics":<bool>,"overlay_locations":"<str>"}},
  "video_profile": {"content_type":"<str>","visual_character":"<str>","strongest_moments":[],"weakest_moments":"<str>","editing_brief":"<str>"},
  "metadata": {}
}
Return only valid JSON. No markdown, no explanation."""
            response = model.generate_content([gemini_file, system_prompt])
            raw = response.text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"```$", "", raw)
            analysis = json.loads(raw.strip())
            print(f"[pipeline] Gemini complete in {time.time()-t:.1f}s")

        # Step 4 — Deepgram transcription
        print(f"[pipeline] step=transcription")
        t = time.time()
        transcript_text = ""
        sentence_boundaries = []
        try:
            dg = DeepgramClient(os.environ["DEEPGRAM_API_KEY"])
            with open(source_path, "rb") as f:
                payload = {"buffer": f.read()}
            options = PrerecordedOptions(model="nova-3", smart_format=True, utterances=True, punctuate=True, diarize=False)
            dg_response = dg.listen.prerecorded.v("1").transcribe_file(payload, options)
            alt = dg_response.results.channels[0].alternatives[0]
            transcript_text = alt.transcript
            words = alt.words or []
            for w in words:
                if hasattr(w, "word") and w.word.rstrip().endswith((".", "?", "!")):
                    sentence_boundaries.append({"time": w.start})
            print(f"[pipeline] transcription complete in {time.time()-t:.1f}s: {len(transcript_text)} chars")
        except Exception as e:
            print(f"[pipeline] transcription failed (non-fatal): {e}")

        # Step 5 — Expand vibe with Claude Haiku
        print(f"[pipeline] step=vibe_expansion")
        t = time.time()
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        haiku_resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="You are a creative video editor. Expand the user's vibe description into a concrete editing intention in 2-3 sentences. Focus on pacing, mood, and visual style. Be specific and actionable.",
            messages=[{"role": "user", "content": f"Vibe: {vibe}"}]
        )
        expanded_vibe = haiku_resp.content[0].text
        print(f"[pipeline] vibe expanded in {time.time()-t:.1f}s")

        # Step 6 — Generate edit recipe with Claude Sonnet
        print(f"[pipeline] step=edit_recipe")
        t = time.time()
        duration = analysis.get("duration", 30)
        recipe_prompt = f"""You are a professional video editor. Generate an edit recipe for this video.

VIDEO DURATION: {duration}s
VIBE: {expanded_vibe}
TRANSCRIPT: {transcript_text[:2000] if transcript_text else "No speech detected"}
ANALYSIS: {json.dumps(analysis, indent=2)[:3000]}

Return ONLY a JSON object with this exact structure:
{{
  "clips": [
    {{"source_start": <float>, "source_end": <float>, "speed": 1.0}}
  ],
  "overlays": [
    {{"type": "text", "text": "<ascii only, no emojis>", "start_time": <float>, "end_time": <float>, "x": "(w-text_w)/2", "y": "h*0.15", "fontsize": 52, "fontcolor": "white", "bordercolor": "black", "borderw": 3}}
  ],
  "color_grade": {{"brightness": 0, "contrast": 1.0, "saturation": 1.0, "gamma": 1.0}},
  "audio": {{"original_volume": 1.0}},
  "notes": "<50 words max>"
}}

Rules:
- Clips must be sequential, no overlaps, total duration <= {duration}s
- overlay text must be ASCII only — no emojis, no special characters
- Return only JSON, no markdown"""

        sonnet_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": recipe_prompt}]
        )
        raw_recipe = sonnet_resp.content[0].text.strip()
        raw_recipe = re.sub(r"^```json\s*", "", raw_recipe)
        raw_recipe = re.sub(r"```$", "", raw_recipe)
        recipe = json.loads(raw_recipe.strip())
        print(f"[pipeline] edit recipe generated in {time.time()-t:.1f}s, {len(recipe.get('clips',[]))} clips, {len(recipe.get('overlays',[]))} overlays")

        # Step 7 — Build and run FFmpeg
        print(f"[pipeline] step=ffmpeg_render")
        t = time.time()
        clips = recipe.get("clips", [])
        if not clips:
            clips = [{"source_start": 0, "source_end": duration, "speed": 1.0}]

        cmd = ["ffmpeg", "-y"]
        for clip in clips:
            cmd += ["-ss", str(clip["source_start"]), "-to", str(clip["source_end"]), "-i", source_path]

        filter_parts = []
        n = len(clips)

        for i in range(n):
            filter_parts.append(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v{i}]")

        v_inputs = "".join(f"[v{i}]" for i in range(n))
        a_inputs = "".join(f"[{i}:a]" for i in range(n))
        filter_parts.append(f"{v_inputs}concat=n={n}:v=1:a=0[vconcat]")
        filter_parts.append(f"{a_inputs}concat=n={n}:v=0:a=1[aconcat]")

        cb = recipe.get("color_grade", {})
        eq = f"eq=brightness={cb.get('brightness',0)}:contrast={cb.get('contrast',1)}:saturation={cb.get('saturation',1)}:gamma={cb.get('gamma',1)}"
        filter_parts.append(f"[vconcat]{eq}[vgraded]")
        last_v = "vgraded"

        for i, overlay in enumerate(recipe.get("overlays", [])):
            raw_text = overlay.get("text", "")
            # Strip to ASCII only, remove problematic chars
            text = raw_text.encode("ascii", "ignore").decode("ascii")
            text = text.replace("'", "").replace('"', "").replace("\\", "")
            text = text.replace(":", "\\:").replace(",", "\\,")
            text = text.strip()
            if not text:
                continue
            start = float(overlay.get("start_time", 0))
            end = float(overlay.get("end_time", 3))
            x = overlay.get("x", "(w-text_w)/2")
            y = overlay.get("y", "h*0.15")
            fs = overlay.get("fontsize", 52)
            fc = overlay.get("fontcolor", "white")
            bc = overlay.get("bordercolor", "black")
            bw = overlay.get("borderw", 3)
            filter_parts.append(
                f"[{last_v}]drawtext=text={text}:fontsize={fs}:fontcolor={fc}"
                f":bordercolor={bc}:borderw={bw}:x={x}:y={y}"
                f":enable='between(t\\,{start}\\,{end})'[vtxt{i}]"
            )
            last_v = f"vtxt{i}"

        vol = recipe.get("audio", {}).get("original_volume", 1.0)
        filter_parts.append(f"[aconcat]volume={vol}[afinal]")

        filter_complex = ";".join(filter_parts)
        cmd += ["-filter_complex", filter_complex]
        cmd += ["-map", f"[{last_v}]", "-map", "[afinal]"]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "128k"]
        cmd += [output_path]

        print(f"[pipeline] FFmpeg cmd: {len(cmd)} args, filter_complex: {len(filter_complex)} chars")
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed_ffmpeg = time.time() - t
        print(f"[pipeline] FFmpeg exit={result.returncode} in {elapsed_ffmpeg:.1f}s")

        if result.stderr:
            for line in result.stderr.strip().split("\n")[-30:]:
                print(f"[ffmpeg] {line}")

        if result.returncode != 0:
            error_tail = "\n".join(result.stderr.strip().split("\n")[-20:])
            return {"error": f"FFmpeg failed (exit {result.returncode}): {error_tail}"}

        if not os.path.exists(output_path):
            return {"error": "No output file produced"}

        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[pipeline] output: {output_size_mb:.1f}MB")

        # Step 8 — Upload
        print(f"[pipeline] step=upload")
        with open(output_path, "rb") as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"})
            resp.raise_for_status()
        print(f"[pipeline] upload complete")

        return {
            "status": "success",
            "job_id": job_id,
            "render_time": round(elapsed_ffmpeg, 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": recipe,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


runpod.serverless.start({"handler": handler})
