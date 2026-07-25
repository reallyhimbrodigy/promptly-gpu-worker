"""A/B PAIR PROBE — Zac's phone-judged pairs for the two staged latency levers.

Ephemeral (`modal run ab_pair_probe_app.py`), never deployed. Constructed durable
source (the multilingual-cert pattern: _face/face.mp4 + en TTS audio — never
user media). Produces, via the REAL pipeline (handler() with the per-job
overrides staged in 5011882):

  PAIR 1 (Cause #3): the same talking-head clip delivered at 60fps vs 30fps.
  PAIR 2 (A-L2):     the same borderline-handheld clip (synthetic wobble)
                     delivered stabilized vs unstabilized.
  EVAL  (A-L2b):     vidstab detection-on-proxy speedup — full-res detect vs
                     480p-proxy detect (trf x/y rescaled), SSIM + wall-clock.

Nothing here flips anything — pairs go to S3/CloudFront for Zac's eye.
"""
import os
import sys
sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("ab-pair-probe", image=image)
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
BUCKET_DEFAULT = "promptly-video-storage"


def _s3():
    import boto3
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1"), \
        (os.environ.get("S3_BUCKET_NAME") or BUCKET_DEFAULT)


def _build_th_source(work, wobble=False):
    """face.mp4 looped over the en TTS track = a constructed durable talking-head.
    wobble=True overlays a deterministic handheld-style jitter (sin-driven crop
    pan + slight rotation) so the vidstab pair judges realistic borderline shake."""
    import subprocess
    s3, bucket = _s3()
    face = os.path.join(work, "face.mp4")
    voice = os.path.join(work, "voice.m4a")
    s3.download_file(bucket, "multilingual-cert/_face/face.mp4", face)
    s3.download_file(bucket, "multilingual-cert/_bridge_regression/en.m4a", voice)
    out = os.path.join(work, "th_source.mp4")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if wobble:
        # deterministic pseudo-handheld: ±14px pan @ ~2.3Hz/1.7Hz + ±0.6° roll.
        vf = ("scale=1188:2112:force_original_aspect_ratio=increase,"
              "crop=1080:1920:x='54+14*sin(2.3*t*2*PI)':y='96+11*sin(1.7*t*2*PI+1.1)',"
              "rotate='0.010*sin(2.9*t*2*PI)':fillcolor=black")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", face,
         "-i", voice, "-map", "0:v", "-map", "1:a", "-vf", vf,
         "-r", "60", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out],
        check=True, capture_output=True, text=True)
    return out


@app.function(secrets=SECRETS, timeout=2400, cpu=16.0, memory=65536)
def run_pair_case(case: dict) -> dict:
    import uuid, traceback, subprocess
    sys.path.insert(0, "/")
    os.environ["APP_URL"] = ""      # no cert traffic reaches the prod server
    import handler as H
    out = {"case": case["name"], "ok": False}
    try:
        s3, bucket = _s3()
        work = f"/tmp/ab/{case['name']}"
        os.makedirs(work, exist_ok=True)
        src = _build_th_source(work, wobble=case.get("wobble", False))
        jid = str(uuid.uuid4())
        base = f"hype-samples/ab-pairs/{case['name']}_{case['ts']}"
        src_key = f"cert/ab-src/{jid}.mp4"
        s3.upload_file(src, bucket, src_key, ExtraArgs={"ContentType": "video/mp4"})
        input_data = {
            "job_id": jid, "user_id": "ab-pair-probe", "vibe": "clean, confident pacing",
            "video_url": s3.generate_presigned_url("get_object",
                Params={"Bucket": bucket, "Key": src_key}, ExpiresIn=3600),
            "upload_url": s3.generate_presigned_url("put_object",
                Params={"Bucket": bucket, "Key": f"{base}.mp4",
                        "ContentType": "video/mp4"}, ExpiresIn=3600),
            "upload_url_thumb": s3.generate_presigned_url("put_object",
                Params={"Bucket": bucket, "Key": f"{base}.jpg",
                        "ContentType": "image/jpeg"}, ExpiresIn=3600),
            "public_url": f"{CDN}{base}.mp4",
            "mode": "full",
        }
        input_data.update(case.get("overrides", {}))
        res = H.handler({"input": input_data})
        out["status"] = res.get("status")
        out["error"] = res.get("error_code") or res.get("error")
        out["url"] = f"{CDN}{base}.mp4" if res.get("status") == "success" else None
        st = (res.get("stage_timings") or {})
        out["stage_timings"] = {k: st.get(k) for k in
                                ("total", "render", "fps_normalize", "edit_plan",
                                 "gemini_call", "target_fps", "shake_score", "source_fps")
                                if k in st}
        out["ok"] = res.get("status") == "success"
        return out
    except Exception as e:
        out["exc"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1500:]
        return out


@app.function(secrets=SECRETS, timeout=1800, cpu=16.0, memory=32768)
def proxy_detect_eval() -> dict:
    """A-L2b: vidstab detection-on-proxy — full-res detect vs 480p-proxy detect
    (trf x/y rescaled by the resolution ratio; angle/zoom are scale-invariant).
    Pixel evidence = SSIM between the two stabilized outputs + both wall-clocks."""
    import subprocess, time, re, traceback
    out = {"ok": False}
    try:
        work = "/tmp/ab/proxyeval"
        os.makedirs(work, exist_ok=True)
        src = _build_th_source(work, wobble=True)

        def _detect(path, height, trf):
            t0 = time.time()
            vf = (f"scale=-2:{height}," if height else "") + \
                 f"vidstabdetect=result={trf}:shakiness=5:accuracy=9"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", vf,
                            "-f", "null", "-"], check=True, capture_output=True, text=True)
            return time.time() - t0

        t_full = _detect(src, None, f"{work}/full.trf")
        t_proxy = _detect(src, 480, f"{work}/proxy.trf")
        # rescale proxy trf x/y to full res (1920-tall source → factor 1920/480)
        factor = 1920.0 / 480.0
        with open(f"{work}/proxy.trf") as f:
            lines = f.read().splitlines()
        scaled = []
        for ln in lines:
            # vidstab trf v1 lines: "Frame N (List [(LM x y ...),...])" — scale
            # every "x y" pair inside LM tuples; header/comment lines pass through
            if ln.startswith("#") or "LM" not in ln:
                scaled.append(ln)
                continue
            def _sc(m):
                vals = m.group(0).split()
                try:
                    vals[1] = str(int(round(float(vals[1]) * factor)))
                    vals[2] = str(int(round(float(vals[2]) * factor)))
                    vals[3] = str(int(round(float(vals[3]) * factor)))
                    vals[4] = str(int(round(float(vals[4]) * factor)))
                except (ValueError, IndexError):
                    pass
                return " ".join(vals)
            scaled.append(re.sub(r"LM \S+ \S+ \S+ \S+ \S+ \S+ \S+", _sc, ln))
        with open(f"{work}/proxy_scaled.trf", "w") as f:
            f.write("\n".join(scaled))

        def _transform(trf, outp):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", src, "-vf",
                 f"vidstabtransform=input={trf}:smoothing=30:optzoom=1,unsharp=5:5:0.8:3:3:0.4",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an", outp],
                check=True, capture_output=True, text=True)
        _transform(f"{work}/full.trf", f"{work}/out_full.mp4")
        _transform(f"{work}/proxy_scaled.trf", f"{work}/out_proxy.mp4")
        r = subprocess.run(
            ["ffmpeg", "-i", f"{work}/out_full.mp4", "-i", f"{work}/out_proxy.mp4",
             "-lavfi", "ssim", "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"All:([\d.]+)", r.stderr or "")
        out.update({
            "ok": True,
            "detect_full_s": round(t_full, 1), "detect_proxy_s": round(t_proxy, 1),
            "speedup": round(t_full / max(t_proxy, 0.01), 1),
            "ssim_full_vs_proxy": float(m.group(1)) if m else None,
        })
        return out
    except Exception as e:
        out["exc"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1200:]
        return out


@app.local_entrypoint()
def main():
    import json, time
    ts = str(int(time.time()))
    pairs = [
        {"name": "fps60", "ts": ts, "overrides": {"delivery_fps_test": "60"}},
        {"name": "fps30", "ts": ts, "overrides": {"delivery_fps_test": "30"}},
        {"name": "stab_on", "ts": ts, "wobble": True, "overrides": {"vidstab_test": "on"}},
        {"name": "stab_off", "ts": ts, "wobble": True, "overrides": {"vidstab_test": "off"}},
    ]
    fut = proxy_detect_eval.spawn()
    results = list(run_pair_case.map(pairs))
    results.append(fut.get())
    print("\n================ A/B PAIR RESULTS ================")
    for r in results:
        print(json.dumps(r, indent=2, default=str))
    print("==================================================")
