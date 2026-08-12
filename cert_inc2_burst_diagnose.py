"""inc2 render_burst CANARY DIAGNOSIS (Zac 2026-08-02, cost P0): the burst closes
$0.41→~$0.06 by paying cpu=48/64GiB only for the ~50s render window. It was built,
the canary failed, and it was never diagnosed. This forces the burst on ONE durable
coverage-passing source (render_burst_test=1) and captures the ACTUAL error — the
burst raises/dies and _fn.remote() propagates it into handler's terminal, so the
handler exception carries the container's real traceback.

Priced: 1 orchestrator (cpu16/64Gi ~200s) + 1 burst (cpu48/64Gi ~50-120s) + 1 Gemini
plan ≈ $0.35-0.50 (Zac-authorised inc2 canary spend).

  modal run cert_inc2_burst_diagnose.py"""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-inc2-burst-diagnose", image=image)
SECRETS = [modal.Secret.from_name(s) for s in
           ("promptly-secrets", "promptly-cloudfront", "gemini-vertex", "promptly-lang-flags")]
# one durable coverage-passing TH clip (plan_ab corpus)
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/11d10886-8e7d-479d-b313-3007b22004d0/1785553314588-B557ABA6-09CD-47B4-BB56-7D3A59BFADF0_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16, memory=65536, region="us", timeout=1800,
              volumes={"/prewarm": modal_app.prewarm_volume})
def run_canary(src):
    import uuid, traceback, time
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # DO NOT set PROMPTLY_RENDER_BURST globally — the per-job render_burst_test=1
    # forces JUST this job through the burst, proving the seam on real traffic shape.
    import handler as H
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": src, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/inc2-canary/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/inc2-canary/{jid}.mp4",
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False,
            "render_burst_test": 1}
    t0 = time.time()
    out = {"job_id": jid}
    try:
        res = H.handler({"input": body})
        out["ok"] = True
        out["elapsed_s"] = round(time.time() - t0, 1)
        out["status"] = (res or {}).get("status")
        out["error_detail"] = (res or {}).get("error_detail") or (res or {}).get("error")
        out["has_video"] = bool((res or {}).get("edit_plan", {}).get("_rendered_video_url")
                                or (res or {}).get("video_url"))
    except Exception as e:
        out["ok"] = False
        out["elapsed_s"] = round(time.time() - t0, 1)
        out["error"] = f"{type(e).__name__}: {str(e)[:600]}"
        out["traceback"] = traceback.format_exc()[-4000:]
    return out


@app.local_entrypoint()
def main():
    print("=== inc2 render_burst canary diagnosis (1 forced-burst job) ===")
    r = run_canary.remote(SRC)
    print("\n--- RESULT ---")
    for k in ("job_id", "ok", "elapsed_s", "status", "has_video", "error", "error_detail"):
        if k in r:
            print(f"  {k}: {r[k]}")
    if r.get("traceback"):
        print("\n--- TRACEBACK (last 4000 chars — the container's actual error) ---")
        print(r["traceback"])
