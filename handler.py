import runpod
import subprocess
import os
import requests
import tempfile
import time
import shutil


def download_file(url, dest):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"[download] {os.path.basename(dest)}: {size_mb:.1f}MB")


def handler(job):
    try:
        input_data = job["input"]
        clip_urls = input_data.get("clip_urls", [])
        ffmpeg_args_str = input_data.get("ffmpeg_args", "")
        upload_url = input_data.get("upload_url", "")
        sfx_urls = input_data.get("sfx_urls", [])
        watermark_url = input_data.get("watermark_url", None)

        work_dir = tempfile.mkdtemp(prefix="promptly-")
        print(f"[worker] Clips: {len(clip_urls)}, SFX: {len(sfx_urls)}")

        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(work_dir, f"clip_{i}.mp4")
            download_file(url, path)
            clip_paths.append(path)

        sfx_paths = []
        for i, url in enumerate(sfx_urls):
            ext = url.split(".")[-1].split("?")[0][:4]
            path = os.path.join(work_dir, f"sfx_{i}.{ext}")
            download_file(url, path)
            sfx_paths.append(path)

        watermark_path = None
        if watermark_url:
            watermark_path = os.path.join(work_dir, "watermark.png")
            download_file(watermark_url, watermark_path)

        output_path = os.path.join(work_dir, "output.mp4")

        ffmpeg_cmd = ffmpeg_args_str
        for i, path in enumerate(clip_paths):
            ffmpeg_cmd = ffmpeg_cmd.replace(f"{{CLIP_{i}}}", path)
        for i, path in enumerate(sfx_paths):
            ffmpeg_cmd = ffmpeg_cmd.replace(f"{{SFX_{i}}}", path)
        if watermark_path:
            ffmpeg_cmd = ffmpeg_cmd.replace("{WATERMARK}", watermark_path)
        ffmpeg_cmd = ffmpeg_cmd.replace("{OUTPUT}", output_path)

        print(f"[ffmpeg] Running...")
        start_time = time.time()

        result = subprocess.run(ffmpeg_cmd, shell=True, capture_output=True, text=True, timeout=240)

        elapsed = time.time() - start_time
        print(f"[ffmpeg] Exit: {result.returncode}, Time: {elapsed:.1f}s")

        if result.returncode != 0:
            print(f"[ffmpeg] STDERR: {(result.stderr or '')[-500:]}")
            return {"error": f"FFmpeg failed (code {result.returncode})", "stderr": (result.stderr or "")[-500:]}

        if not os.path.exists(output_path):
            return {"error": "No output file"}

        output_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[ffmpeg] Output: {output_size:.1f}MB")

        with open(output_path, 'rb') as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"})
            resp.raise_for_status()
        print(f"[upload] Done")

        shutil.rmtree(work_dir, ignore_errors=True)
        return {"status": "success", "render_time": round(elapsed, 1), "output_size_mb": round(output_size, 1)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


runpod.serverless.start({"handler": handler})