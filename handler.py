import sys
print(f"[startup] Python {sys.version}", flush=True)

try:
    import runpod
    print("[startup] runpod OK", flush=True)
except Exception as e:
    print(f"[startup] runpod FAILED: {e}", flush=True)

try:
    from deepgram import DeepgramClient, PrerecordedOptions
    print("[startup] deepgram OK", flush=True)
except Exception as e:
    print(f"[startup] deepgram FAILED: {e}", flush=True)

try:
    import google.generativeai as genai
    print("[startup] google.generativeai OK", flush=True)
except Exception as e:
    print(f"[startup] google.generativeai FAILED: {e}", flush=True)

try:
    import anthropic
    print("[startup] anthropic OK", flush=True)
except Exception as e:
    print(f"[startup] anthropic FAILED: {e}", flush=True)

print("[startup] all import checks done", flush=True)
import subprocess
import os
import requests
import tempfile
import time
import shutil
import json
import re


def measure_video(source_path):
    import subprocess, json, re

    measurements = {}

    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", source_path
    ], capture_output=True, text=True)
    probe_data = json.loads(probe.stdout)
    video_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), {})
    measurements["width"] = video_stream.get("width", 1080)
    measurements["height"] = video_stream.get("height", 1920)
    measurements["fps"] = eval(video_stream.get("r_frame_rate", "30/1"))
    measurements["duration"] = float(probe_data["format"].get("duration", 0))
    measurements["bitrate_kbps"] = int(probe_data["format"].get("bit_rate", 0)) // 1000

    luma = subprocess.run([
        "ffmpeg", "-i", source_path, "-vf",
        "scale=320:-1,signalstats=stat=tout+brng+vrep",
        "-frames:v", "30", "-f", "null", "-"
    ], capture_output=True, text=True)
    yavg_values = re.findall(r"YAVG=(\d+\.?\d*)", luma.stderr)
    if yavg_values:
        mean_luma = sum(float(v) for v in yavg_values) / len(yavg_values)
        measurements["mean_luma"] = round(mean_luma, 1)
        measurements["luma_min"] = round(min(float(v) for v in yavg_values), 1)
        measurements["luma_max"] = round(max(float(v) for v in yavg_values), 1)
        measurements["contrast_ratio"] = round(measurements["luma_max"] / max(measurements["luma_min"], 1), 2)
    else:
        measurements["mean_luma"] = 128.0
        measurements["contrast_ratio"] = 1.0

    subprocess.run([
        "ffmpeg", "-i", source_path,
        "-vf", "scale=160:-1,extractplanes=y+u+v,split=3[y][u][v];"
               "[y]signalstats[ys];[u]signalstats[us];[v]signalstats[vs]",
        "-frames:v", "30", "-f", "null", "-"
    ], capture_output=True, text=True)
    subprocess.run([
        "ffmpeg", "-i", source_path,
        "-vf", "scale=160:-1,signalstats=stat=tout",
        "-frames:v", "1", "-f", "null", "-"
    ], capture_output=True, text=True)

    noise = subprocess.run([
        "ffmpeg", "-i", source_path,
        "-vf", "scale=320:-1,noise=alls=0,signalstats",
        "-frames:v", "10", "-f", "null", "-"
    ], capture_output=True, text=True)
    vrep_values = re.findall(r"VREP=(\d+\.?\d*)", noise.stderr)
    measurements["noise_level"] = round(sum(float(v) for v in vrep_values) / len(vrep_values), 2) if vrep_values else 0.0

    sharp = subprocess.run([
        "ffmpeg", "-i", source_path,
        "-vf", "scale=320:-1,signalstats=stat=brng",
        "-frames:v", "10", "-f", "null", "-"
    ], capture_output=True, text=True)
    brng_values = re.findall(r"BRNG=(\d+\.?\d*)", sharp.stderr)
    measurements["out_of_range_pct"] = round(sum(float(v) for v in brng_values) / len(brng_values), 3) if brng_values else 0.0

    subprocess.run([
        "ffmpeg", "-i", source_path,
        "-vf", "scale=320:-1,mestimate,metadata=print:file=-",
        "-frames:v", "30", "-f", "null", "-"
    ], capture_output=True, text=True)
    measurements["has_motion"] = measurements["bitrate_kbps"] > 3000

    return measurements


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
            dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
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

        print(f"[pipeline] step=measure_video")
        t = time.time()
        video_measurements = measure_video(source_path)
        print(f"[pipeline] measurements complete in {time.time()-t:.1f}s: {json.dumps(video_measurements)}")

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
        duration = video_measurements["duration"]
        recipe_prompt = f"""You are a professional video colorist and editor. Generate a precise edit recipe based on real video measurements.

VIDEO MEASUREMENTS (from actual pixel analysis):
- Duration: {video_measurements['duration']}s
- Resolution: {video_measurements['width']}x{video_measurements['height']}
- Mean luma (brightness): {video_measurements['mean_luma']} / 255 (128 = perfect exposure)
- Contrast ratio: {video_measurements['contrast_ratio']} (1.0 = flat, 3.0+ = punchy)
- Noise level (VREP): {video_measurements['noise_level']} (0 = clean, higher = noisy/compressed)
- Out-of-range pixels: {video_measurements['out_of_range_pct']}% (>5% means blown highlights or crushed blacks)
- Has significant motion: {video_measurements['has_motion']}
- Bitrate: {video_measurements['bitrate_kbps']} kbps

VIBE: {expanded_vibe}
TRANSCRIPT: {transcript_text[:2000] if transcript_text else "No speech detected"}
ANALYSIS: {json.dumps(analysis, indent=2)[:2000]}

Based on the measurements above, decide which enhancements this specific video needs and at what precise strength. Do NOT apply filters the video doesn't need.

AVAILABLE FILTERS (include only what's needed, omit the rest):

color_grade (FFmpeg eq filter — all values are multipliers/offsets, not 0-255):
  brightness: -1.0 to 1.0 (0 = no change. If mean_luma=100, video is dark; if mean_luma=160, video is bright)
  contrast: 0.5 to 2.0 (1.0 = no change)
  saturation: 0.5 to 2.0 (1.0 = no change)
  gamma: 0.5 to 2.0 (1.0 = no change, lower lifts shadows)

sharpen (FFmpeg unsharp filter, omit if video is already sharp):
  luma_amount: 0.0 to 2.0 (0.5 = subtle, 1.0 = moderate, 2.0 = strong)
  luma_size: 3 or 5 (kernel size, use 5 for most cases)

denoise (FFmpeg hqdn3d filter, only if noise_level > 2 or video looks grainy):
  spatial: 0.5 to 4.0 (strength of spatial denoising)
  temporal: 3.0 to 10.0 (strength of temporal denoising, higher = smoother)

stabilize: true or false (only if has_motion=true AND vibe calls for smooth/cinematic look)

color_temperature (FFmpeg colortemperature filter, omit if color looks neutral):
  temperature: 1000 to 40000 (6500 = neutral, lower = warmer, higher = cooler)

vignette (FFmpeg vignette filter, omit if not cinematic vibe):
  angle: 0.1 to 0.8 (strength, 0.3 = subtle, 0.6 = strong)

Return ONLY a JSON object:
{{
  "clips": [{{"source_start": <float>, "source_end": <float>, "speed": 1.0}}],
  "overlays": [{{"type": "text", "text": "<ascii only>", "start_time": <float>, "end_time": <float>, "x": "(w-text_w)/2", "y": "h*0.15", "fontsize": 52, "fontcolor": "white", "bordercolor": "black", "borderw": 3}}],
  "color_grade": {{"brightness": <float>, "contrast": <float>, "saturation": <float>, "gamma": <float>}},
  "sharpen": {{"luma_amount": <float>, "luma_size": <int>}},
  "denoise": {{"spatial": <float>, "temporal": <float>}},
  "stabilize": <bool>,
  "color_temperature": {{"temperature": <int>}},
  "vignette": {{"angle": <float>}},
  "audio": {{"original_volume": <float 0-1>}},
  "notes": "<50 words, explain what you applied and why based on the measurements>"
}}

Rules:
- Omit any filter key you are not applying (don't include it with null or 0)
- color_grade brightness is NOT 0-255, it is -1.0 to 1.0
- Clips must be sequential, total duration <= {video_measurements['duration']}s
- overlay text must be ASCII only, no emojis
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
            clips = [{"source_start": 0, "source_end": video_measurements['duration'], "speed": 1.0}]

        cmd = ["ffmpeg", "-y"]

        do_stabilize = recipe.get("stabilize", False)
        if do_stabilize:
            stab_vectors = os.path.join(work_dir, "stab.trf")
            detect_cmd = [
                "ffmpeg", "-i", source_path,
                "-vf", f"vidstabdetect=stepsize=6:shakiness=8:accuracy=9:result={stab_vectors}",
                "-f", "null", "-"
            ]
            subprocess.run(detect_cmd, capture_output=True)
            print(f"[pipeline] stabilization detect complete")

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
        last_v = "vconcat"

        if do_stabilize and os.path.exists(stab_vectors):
            filter_parts.append(f"[{last_v}]vidstabtransform=input={stab_vectors}:smoothing=10[vstab]")
            last_v = "vstab"

        cb = recipe.get("color_grade", {})
        if cb:
            brightness = max(-1.0, min(1.0, float(cb.get("brightness", 0))))
            contrast = max(0.5, min(2.0, float(cb.get("contrast", 1))))
            saturation = max(0.5, min(2.0, float(cb.get("saturation", 1))))
            gamma = max(0.5, min(2.0, float(cb.get("gamma", 1))))
            filter_parts.append(
                f"[{last_v}]eq=brightness={brightness}:contrast={contrast}"
                f":saturation={saturation}:gamma={gamma}[vgraded]"
            )
            last_v = "vgraded"

        ct = recipe.get("color_temperature", {})
        if ct and ct.get("temperature"):
            temp = max(1000, min(40000, int(ct["temperature"])))
            filter_parts.append(f"[{last_v}]colortemperature=temperature={temp}[vtemp]")
            last_v = "vtemp"

        sh = recipe.get("sharpen", {})
        if sh and sh.get("luma_amount"):
            amount = max(0.0, min(2.0, float(sh["luma_amount"])))
            size = int(sh.get("luma_size", 5))
            if size % 2 == 0:
                size += 1
            filter_parts.append(f"[{last_v}]unsharp={size}:{size}:{amount}:3:3:0[vsharp]")
            last_v = "vsharp"

        dn = recipe.get("denoise", {})
        if dn and dn.get("spatial"):
            spatial = max(0.5, min(4.0, float(dn["spatial"])))
            temporal = max(3.0, min(10.0, float(dn.get("temporal", 6.0))))
            filter_parts.append(f"[{last_v}]hqdn3d={spatial}:{spatial}:{temporal}:{temporal}[vdenoise]")
            last_v = "vdenoise"

        vg = recipe.get("vignette", {})
        if vg and vg.get("angle"):
            angle = max(0.1, min(0.8, float(vg["angle"])))
            filter_parts.append(f"[{last_v}]vignette=angle={angle}[vvignette]")
            last_v = "vvignette"

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
