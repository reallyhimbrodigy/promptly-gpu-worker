import runpod
import subprocess
import os
import requests
import tempfile
import time
import shutil
import shlex


def download_file(url, dest):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"[download] {os.path.basename(dest)}: {size_mb:.1f}MB")


def replace_placeholders(value, clip_paths, sfx_paths, watermark_path, font_path, captions_path, output_path):
    """Replace {CLIP_0}, {FONT_PATH}, etc. in a string."""
    for i, path in enumerate(clip_paths):
        value = value.replace(f"{{CLIP_{i}}}", path)
    for i, path in enumerate(sfx_paths):
        value = value.replace(f"{{SFX_{i}}}", path)
    if watermark_path:
        value = value.replace("{WATERMARK}", watermark_path)
    if font_path:
        value = value.replace("{FONT_PATH}", font_path)
    if captions_path:
        value = value.replace("{CAPTIONS_PATH}", captions_path)
    value = value.replace("{OUTPUT}", output_path)
    return value


def handler(job):
    try:
        input_data = job["input"]
        clip_urls = input_data.get("clip_urls", [])
        ffmpeg_args_input = input_data.get("ffmpeg_args", "")
        upload_url = input_data.get("upload_url", "")
        sfx_urls = input_data.get("sfx_urls", [])
        watermark_url = input_data.get("watermark_url", None)
        font_url = input_data.get("font_url", None)
        captions_url = input_data.get("captions_url", None)

        work_dir = tempfile.mkdtemp(prefix="promptly-")
        print(f"[worker] Work dir: {work_dir}")
        print(f"[worker] Clips: {len(clip_urls)}, SFX: {len(sfx_urls)}")

        # Download clips
        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(work_dir, f"clip_{i}.mp4")
            download_file(url, path)
            clip_paths.append(path)

        # Download SFX
        sfx_paths = []
        for i, url in enumerate(sfx_urls):
            ext = url.split(".")[-1].split("?")[0][:4]
            path = os.path.join(work_dir, f"sfx_{i}.{ext}")
            download_file(url, path)
            sfx_paths.append(path)

        # Download watermark
        watermark_path = None
        if watermark_url:
            watermark_path = os.path.join(work_dir, "watermark.png")
            download_file(watermark_url, watermark_path)

        # Download font
        font_path = None
        if font_url:
            font_path = os.path.join(work_dir, "Montserrat-Black.ttf")
            download_file(font_url, font_path)
            print(f"[worker] Font downloaded: {font_path}")
            print(f"[worker] font_url={font_url}")
            print(f"[worker] font_path={font_path}")
            print(f"[worker] font exists={os.path.exists(font_path)}")

        # Download captions file
        captions_path = None
        if captions_url:
            captions_path = os.path.join(work_dir, "captions.ass")
            download_file(captions_url, captions_path)
            print(f"[download] captions.ass: {os.path.getsize(captions_path) / 1024:.1f}KB")

        output_path = os.path.join(work_dir, "output.mp4")

        # Check FFmpeg version
        ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        first_line = ver.stdout.split("\n")[0] if ver.stdout else "unknown"
        print(f"[worker] FFmpeg: {first_line}")

        # Probe each clip before render
        for i, path in enumerate(clip_paths):
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
            )
            print(f"[probe] clip_{i}: {probe.stdout.strip()}")

        # Build FFmpeg command — handle both array (new) and string (legacy) formats
        if isinstance(ffmpeg_args_input, list):
            # NEW FORMAT: args as JSON array — no shell escaping needed
            print(f"[worker] FFmpeg args format: array ({len(ffmpeg_args_input)} elements)")
            ffmpeg_cmd_list = [
                replace_placeholders(arg, clip_paths, sfx_paths, watermark_path, font_path, captions_path, output_path)
                for arg in ffmpeg_args_input
            ]
            print(f"[worker] FONT_PATH still in cmd: {any('{FONT_PATH}' in a for a in ffmpeg_cmd_list)}")
            print(f"[worker] cmd first 300 chars: {' '.join(ffmpeg_cmd_list)[:300]}")
            print(f"[worker] FFmpeg cmd length: {sum(len(a) for a in ffmpeg_cmd_list)} chars")

            print(f"[ffmpeg] Running...")
            start_time = time.time()
            result = subprocess.run(ffmpeg_cmd_list, capture_output=True, text=True)

        else:
            # LEGACY FORMAT: string command — use shlex.split for parsing
            print(f"[worker] FFmpeg args format: string ({len(ffmpeg_args_input)} chars)")
            ffmpeg_cmd = replace_placeholders(ffmpeg_args_input, clip_paths, sfx_paths, watermark_path, font_path, captions_path, output_path)
            print(f"[worker] FONT_PATH still in cmd: {'{FONT_PATH}' in ffmpeg_cmd}")
            print(f"[worker] cmd first 300 chars: {ffmpeg_cmd[:300]}")
            print(f"[worker] FFmpeg cmd length: {len(ffmpeg_cmd)} chars")

            print(f"[ffmpeg] Running...")
            start_time = time.time()
            result = subprocess.run(shlex.split(ffmpeg_cmd), capture_output=True, text=True)

        elapsed = time.time() - start_time
        print(f"[ffmpeg] Exit: {result.returncode}, Time: {elapsed:.1f}s")

        # Log stderr tail for diagnostics
        if result.stderr:
            stderr_lines = result.stderr.strip().split("\n")
            tail = stderr_lines[-30:] if len(stderr_lines) > 30 else stderr_lines
            for line in tail:
                print(f"[ffmpeg] {line}")

        if result.returncode != 0:
            error_tail = ""
            if result.stderr:
                error_tail = "\n".join(result.stderr.strip().split("\n")[-20:])
            return {"error": f"FFmpeg failed (exit {result.returncode}): {error_tail}"}

        if not os.path.exists(output_path):
            return {"error": "No output file"}

        output_size = os.path.getsize(output_path)
        output_size_mb = output_size / (1024 * 1024)
        print(f"[ffmpeg] Output: {output_size_mb:.1f}MB")

        # Upload
        with open(output_path, 'rb') as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"})
            resp.raise_for_status()
        print(f"[upload] Done")

        shutil.rmtree(work_dir, ignore_errors=True)
        return {"status": "success", "render_time": round(elapsed, 1), "output_size_mb": round(output_size_mb, 1)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


runpod.serverless.start({"handler": handler})
