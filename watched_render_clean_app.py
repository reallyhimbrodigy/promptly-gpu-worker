"""WATCHED RENDER v2 (deploy canary payload, 2026-07-31) — CLEAN long clip.

v1 (watched_render_app.py) accidentally hit a Malayalam clip → coverage REJECT →
minimal_speech_uncut route (no captions, no Remotion, NO fanout). It proved gate #5
+ option(a) live, but measured the wrong path for the cost decision.

v2 CONSTRUCTS a durable clean English talking-head ~93s (concat of the two GOODEN
clips, per the durable-sources law) so the STANDARD decorated render runs and
fanout (≥60s output) engages. psutil added so the per-stage CPU sampler works.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")  # psutil installed at runtime (base image ends with local files)
app = modal.App("watched-render-clean", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

# Clean English GOODEN clips (coverage-PASS in cert_coverage_broad_app.py).
G1 = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"  # 35s
G2 = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782599246881-AB653DB0-BCCF-4C67-9910-0355686EC183_L0_001.mp4"  # 23s
SRC_KEY = "sources/watched-clean/goodEN_93s.mp4"
SRC_BUCKET = "thisismybucketagainwooo"
SRC_URL = f"https://d1iax8jos987n3.cloudfront.net/{SRC_KEY}"


@app.function(secrets=SECRETS, cpu=16.0, memory=131072, region="us", timeout=2400)
def run() -> dict:
    import time, uuid, traceback, threading, tempfile, subprocess, requests
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    try:
        import psutil
    except Exception:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "psutil"], check=False, timeout=120)
            import psutil
        except Exception:
            psutil = None

    # ── build the clean ~93s source (concat G1+G2+G1, re-encode to normalize) ──
    wd = tempfile.mkdtemp()
    p1 = os.path.join(wd, "g1.mp4"); p2 = os.path.join(wd, "g2.mp4")
    for u, p in ((G1, p1), (G2, p2)):
        r = requests.get(u, timeout=120); open(p, "wb").write(r.content)
    concat_list = os.path.join(wd, "list.txt")
    # normalize each to a common format first (so concat demuxer is safe)
    norm = []
    for i, p in enumerate([p1, p2, p1]):
        np_ = os.path.join(wd, f"n{i}.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30",
                        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "48000", np_], check=True)
        norm.append(np_)
    with open(concat_list, "w") as f:
        for np_ in norm:
            f.write(f"file '{np_}'\n")
    src_local = os.path.join(wd, "clean93.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", src_local], check=True)
    src_dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src_local],
                                   capture_output=True, text=True).stdout.strip() or 0)
    # upload to S3 so the handler's source-poll finds it
    H._aws_s3_client.upload_file(src_local, SRC_BUCKET, SRC_KEY, ExtraArgs={"ContentType": "video/mp4"})

    jid = str(uuid.uuid4())
    out_url = f"https://{SRC_BUCKET}.s3.amazonaws.com/watched-render/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SRC_URL, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": out_url, "public_url": out_url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}

    # ── per-stage CPU sampler ──
    samples = []; stop = threading.Event()
    def _sampler():
        if psutil: psutil.cpu_percent(interval=None)
        while not stop.is_set():
            try: stg = H._CPU_STAGE[0]
            except Exception: stg = "?"
            samples.append((round(time.time(), 2), stg, psutil.cpu_percent(interval=None) if psutil else None))
            stop.wait(0.5)
    th = threading.Thread(target=_sampler, daemon=True); th.start()

    t0 = time.time(); err = None
    try:
        res = H.handler({"input": body})
    except Exception as e:
        err = {"error": f"{type(e).__name__}: {str(e)[:200]}", "tb": traceback.format_exc()[-800:]}; res = {}
    finally:
        stop.set(); th.join(timeout=2)
    wall = round(time.time() - t0, 1)
    r = res if isinstance(res, dict) else {}
    per_stage = {}
    for _t, stg, cpu in samples:
        if cpu is None: continue
        d = per_stage.setdefault(stg, {"peak": 0.0, "sum": 0.0, "n": 0})
        d["peak"] = max(d["peak"], cpu); d["sum"] += cpu; d["n"] += 1
    for stg, d in per_stage.items():
        d["mean"] = round(d["sum"] / d["n"], 1) if d["n"] else None; d["peak"] = round(d["peak"], 1); d.pop("sum")
    out = {"wall_s": wall, "status": r.get("status"), "route": r.get("route"), "route_reason": r.get("route_reason"),
           "stage_timings": r.get("stage_timings"), "video_url": r.get("video_url"),
           "cpu_per_stage": per_stage, "n_samples": len(samples), "src_dur_s": round(src_dur, 1),
           "psutil": bool(psutil), "cpu_cores": 16}
    if err: out.update(err)
    return out


@app.local_entrypoint()
def main():
    print("=== WATCHED RENDER v2 (CLEAN ~93s): cpu=16 + fanout=1, STANDARD render ===")
    print(json.dumps(run.remote(), indent=2, default=str)[:4000])
