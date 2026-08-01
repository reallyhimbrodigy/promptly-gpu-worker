"""WATCHED RENDER (deploy canary payload, 2026-07-31): measure the deployed
cpu=16 + PROMPTLY_RENDER_FANOUT=1 config on a LONG clip.

Runs H.handler IN-PROCESS inside a cpu=16 / 128GB container that mirrors the
deployed run_pipeline_bg container, with the LIVE promptly-lang-flags secret
attached (fanout=1). The render's fanout stage still spawns the DEPLOYED
render_chunk_fanout containers, so this exercises the real offload path.

Captures:
  • wall_s (E2E) — compare to the ~458s long-clip baseline
  • stage_timings (from the result payload)
  • per-stage CPU saturation — an in-harness sampler thread reads
    psutil.cpu_percent + handler._CPU_STAGE[0] every 0.5s (the deployed
    run_pipeline_bg sampler is bypassed by the in-process call, so we replicate
    it here) → per-stage peak/mean %CPU across the 16 cores
  • route / route_reason — so a clip that coverage-routes to minimal is not
    silently mis-measured as a full decorated render
  • output duration + whether fanout engaged

Read-only w.r.t. the repo; costs one real render (the canary Zac authorized).
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("watched-render-canary", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

# Longest in-range durable source (112s). Labeled BIGGAP in the coverage corpus,
# so the harness reports the ACTUAL route rather than assuming a full render.
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/02b3c741-e34e-427e-b924-a585a360e0bf/1784674125091-F5F0A7AE-620B-45AB-83C4-1BC329310A7A_L0_001.mp4"


# MATCH the deployed container: cpu=16, memory=131072 (128GB), region us.
@app.function(secrets=SECRETS, cpu=16.0, memory=131072, region="us", timeout=2400)
def run() -> dict:
    import time, uuid, traceback, threading
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    try:
        import psutil
    except Exception:
        psutil = None

    jid = str(uuid.uuid4())
    out_url = f"https://thisismybucketagainwooo.s3.amazonaws.com/watched-render/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": out_url, "public_url": out_url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}

    # ── per-stage CPU sampler thread (replicates run_pipeline_bg's sampler) ──
    samples = []  # (t, stage, cpu_pct)
    stop = threading.Event()
    def _sampler():
        if psutil:
            psutil.cpu_percent(interval=None)  # prime
        while not stop.is_set():
            stage = None
            try:
                stage = H._CPU_STAGE[0]
            except Exception:
                stage = "?"
            cpu = psutil.cpu_percent(interval=None) if psutil else None
            samples.append((round(time.time(), 2), stage, cpu))
            stop.wait(0.5)
    th = threading.Thread(target=_sampler, daemon=True); th.start()

    t0 = time.time()
    err = None
    try:
        res = H.handler({"input": body})
    except Exception as e:
        err = {"error": f"{type(e).__name__}: {str(e)[:200]}", "tb": traceback.format_exc()[-800:]}
        res = {}
    finally:
        stop.set(); th.join(timeout=2)
    wall = round(time.time() - t0, 1)

    r = res if isinstance(res, dict) else {}
    # aggregate CPU per stage (peak + mean), cores=16 so 100% == 1 core, 1600% == all 16
    per_stage = {}
    for _t, stg, cpu in samples:
        if cpu is None:
            continue
        d = per_stage.setdefault(stg, {"peak": 0.0, "sum": 0.0, "n": 0})
        d["peak"] = max(d["peak"], cpu); d["sum"] += cpu; d["n"] += 1
    for stg, d in per_stage.items():
        d["mean"] = round(d["sum"] / d["n"], 1) if d["n"] else None
        d["peak"] = round(d["peak"], 1); d.pop("sum");
    out = {
        "wall_s": wall,
        "status": r.get("status"),
        "route": r.get("route"),
        "route_reason": r.get("route_reason"),
        "stage_timings": r.get("stage_timings"),
        "stage_manifest": r.get("stage_manifest"),
        "video_url": r.get("video_url"),
        "cpu_per_stage": per_stage,      # {stage: {peak%, mean%, n}}  (1600% = all 16 cores)
        "n_samples": len(samples),
        "src_dur_s": 112.1,
        "cpu_cores": 16,
    }
    if err:
        out.update(err)
    return out


@app.local_entrypoint()
def main():
    print("=== WATCHED RENDER CANARY: cpu=16 + fanout=1 on a 112s clip ===")
    o = run.remote()
    print(json.dumps(o, indent=2, default=str)[:4000])
