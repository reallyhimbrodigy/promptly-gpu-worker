"""THINKING-BUDGET A/B (Zac 2026-07-31): Call-2 thinking_budget is a dial. Test
whether quality holds at a LOWER budget — a 30-60s win with zero prompt work, and
(per the r=0.59 output-vs-wallclock finding) a possible bound on the degen class.

Two arms on ONE clean real English talking-head (GOODEN, coverage-pass, no degen
artifact): CONTROL thinking_budget=24576 vs LOW thinking_budget=8192 (the minimal
route's budget). Each a full standard render. Reports gemini_call (thinking time),
edit_plan, gemini_wasted_degen, e2e, and the rendered video URL for Zac's eye.
Same prompt → same Vertex cache (thinking_budget is a per-call config, not cached),
so the arms differ ONLY in the dial.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("thinking-budget-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

# Clean 35s real English talking-head (GOODEN_233ef734, coverage-PASS, no repeats).
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=131072, region="us", timeout=2400)
def run(budget: int) -> dict:
    import time, uuid, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_POST_THINKING_BUDGET"] = str(budget)   # THE DIAL
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    out_url = f"https://thisismybucketagainwooo.s3.amazonaws.com/thinking-ab/tb{budget}/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": out_url, "public_url": out_url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    t0 = time.time(); err = None
    try:
        res = H.handler({"input": body})
    except Exception as e:
        err = {"error": f"{type(e).__name__}: {str(e)[:200]}", "tb": traceback.format_exc()[-600:]}; res = {}
    r = res if isinstance(res, dict) else {}
    st = r.get("stage_timings") or {}
    out = {
        "thinking_budget": budget,
        "wall_s": round(time.time() - t0, 1),
        "status": r.get("status"),
        "route": r.get("route"),
        "gemini_call_s": st.get("gemini_call"),          # thinking/deliberation time
        "gemini_wasted_degen_s": st.get("gemini_wasted_degen"),
        "edit_plan_s": st.get("edit_plan"),              # whole editorial stage incl re-rolls
        "fps_normalize_s": st.get("fps_normalize"),
        "render_s": st.get("render"),
        "total_s": st.get("total"),
        "video_url": r.get("video_url"),
    }
    if err: out.update(err)
    return out


@app.local_entrypoint()
def main():
    print("=== THINKING-BUDGET A/B: 24576 (control) vs 8192 (low), clean 35s clip ===")
    control = run.remote(24576)
    print("CONTROL(24576):", json.dumps(control, default=str))
    low = run.remote(8192)
    print("LOW(8192):", json.dumps(low, default=str))
    print("\n=== DELTA ===")
    for k in ("gemini_call_s", "edit_plan_s", "gemini_wasted_degen_s", "total_s", "wall_s"):
        c, l = control.get(k), low.get(k)
        if isinstance(c, (int, float)) and isinstance(l, (int, float)):
            print(f"  {k:24} 24576={c:7.1f}  8192={l:7.1f}  Δ={c - l:+7.1f}s")
    print(f"\n  control video: {control.get('video_url')}")
    print(f"  low     video: {low.get('video_url')}")
