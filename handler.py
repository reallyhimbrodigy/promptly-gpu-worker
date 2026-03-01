import runpod
import subprocess
import os
import requests
import tempfile
import time
import shutil


def download_file(url, dest):
    """Download a file from URL to dest path."""
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"[download] {os.path.basename(dest)}: {size_mb:.1f}MB")


def handler(job):
    """
    RunPod serverless handler for FFmpeg rendering.
    
    Receives clip URLs, an FFmpeg command with placeholders, 
    and a signed upload URL. Downloads clips, runs FFmpeg, 
    uploads the result.
    """
    try:
        input_data = job["input"]
        clip_urls = input_data.get("clip_urls", [])
        ffmpeg_args_str = input_data.get("ffmpeg_args", "")
        upload_url = input_data.get("upload_url", "")
        sfx_urls = input_data.get("sfx_urls", [])
        watermark_url = input_data.get("watermark_url", None)

        work_dir = tempfile.mkdtemp(prefix="promptly-render-")
        print(f"[worker] Work dir: {work_dir}")
        print(f"[worker] Clips: {len(clip_urls)}, SFX: {len(sfx_urls)}, Watermark: {watermark_url is not None}")

        # Download all clip files
        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(work_dir, f"clip_{i}.mp4")
            download_file(url, path)
            clip_paths.append(path)

        # Download SFX files
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

        output_path = os.path.join(work_dir, "output.mp4")

        # Replace placeholders with local paths
        ffmpeg_cmd = ffmpeg_args_str
        for i, path in enumerate(clip_paths):
            ffmpeg_cmd = ffmpeg_cmd.replace(f"{{CLIP_{i}}}", path)
        for i, path in enumerate(sfx_paths):
            ffmpeg_cmd = ffmpeg_cmd.replace(f"{{SFX_{i}}}", path)
        if watermark_path:
            ffmpeg_cmd = ffmpeg_cmd.replace("{WATERMARK}", watermark_path)
        ffmpeg_cmd = ffmpeg_cmd.replace("{OUTPUT}", output_path)

        print(f"[ffmpeg] Command (first 300 chars): {ffmpeg_cmd[:300]}")
        start_time = time.time()

        result = subprocess.run(
            ffmpeg_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=240
        )

        elapsed = time.time() - start_time
        print(f"[ffmpeg] Exit code: {result.returncode}, Time: {elapsed:.1f}s")

        if result.returncode != 0:
            stderr_tail = result.stderr[-1000:] if result.stderr else "no stderr"
            print(f"[ffmpeg] STDERR: {stderr_tail}")
            return {"error": f"FFmpeg failed (code {result.returncode})", "stderr": stderr_tail}

        if not os.path.exists(output_path):
            return {"error": "FFmpeg produced no output file"}

        output_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[ffmpeg] Output: {output_size:.1f}MB")

        # Upload to Supabase
        print(f"[upload] Uploading {output_size:.1f}MB to Supabase...")
        with open(output_path, 'rb') as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"})
            resp.raise_for_status()
        print(f"[upload] Done (status {resp.status_code})")

        # Cleanup
        shutil.rmtree(work_dir, ignore_errors=True)

        return {
            "status": "success",
            "render_time": round(elapsed, 1),
            "output_size_mb": round(output_size, 1)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


runpod.serverless.start({"handler": handler})