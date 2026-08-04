"""Re-run the saved 26a05f5d source and CAPTURE THE PLAN.

The job died before edit_recipe persisted, so the DB cannot say where its clips
landed. The source is ordinary — 15.02s, 1080x1920, h264, 30fps — which makes
whatever produced out-of-range clips MORE likely to recur, not less.

Captures the plan whether the render succeeds or fails: the point is the clip
ranges relative to a 15.02s source, not the outcome.
"""
import os
import sys

sys.path.insert(0, "/")
import modal  # noqa: E402
import modal_app  # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-repro-26a05f5d", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

BUCKET = "thisismybucketagainwooo"
SRC = f"https://{BUCKET}.s3.amazonaws.com/failure-corpus/RENDER_FATAL/26a05f5d-596b-42cf-8f01-6b89bbc25985.mp4"
SOURCE_DURATION = 15.019002


@app.function(secrets=SECRETS, cpu=16.0, memory=12288, timeout=3000)
def repro() -> dict:
    import contextlib
    import io
    import json
    import re
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    job_id = str(uuid.uuid4())
    key = f"repro/26a05f5d/{job_id}.mp4"
    url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    body = {
        "job_id": job_id, "video_url": SRC,
        "vibe": "Clean and engaging edit",
        "user_id": "00000000-0000-0000-0000-0000000000ee",
        "upload_url": url, "public_url": url,
        "model": "flare", "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }

    buf = io.StringIO()
    res, err = None, None
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf):
            res = H.handler({"input": body})
    except Exception as e:                                   # noqa: BLE001
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
    log = buf.getvalue()
    print(log[-6000:], flush=True)

    # THE PLAN, however we can get it. The recipe is the answer; the log is the
    # fallback when the job dies before the recipe is returned.
    recipe = (res or {}).get("edit_recipe") or {}
    clips = []

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("cuts", "clips") and isinstance(v, list):
                    for c in v:
                        if isinstance(c, dict):
                            clips.append({
                                "start": c.get("start", c.get("start_s")),
                                "end": c.get("end", c.get("end_s")),
                                "src_start": c.get("source_start", c.get("src_start")),
                            })
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)
    _walk(recipe)

    out_of_range = [c for c in clips
                    if isinstance(c.get("start"), (int, float))
                    and c["start"] >= SOURCE_DURATION]

    return {
        "job_id": job_id,
        "completed": bool(res) and not (res or {}).get("error") and not err,
        "seconds": round(time.time() - t0, 1),
        "error_cause": (res or {}).get("error_cause"),
        "error_detail": str((res or {}).get("error_detail") or err or "")[:500],
        "source_duration": SOURCE_DURATION,
        "n_clips": len(clips),
        "clips": clips[:12],
        "out_of_range": out_of_range,
        # Log lines that name the plan's extent even when the recipe is lost.
        "plan_lines": [ln for ln in log.splitlines()
                       if re.search(r"\[plan\]|\[cuts\]|clip.*start|trim|out of range|past", ln, re.I)][:25],
        "probe_budget_lines": [ln for ln in log.splitlines() if "[probe budget]" in ln][:5],
    }


@app.local_entrypoint()
def main():
    import json
    r = repro.remote()
    print("\n" + "=" * 80)
    print(f"source duration : {r['source_duration']}s")
    print(f"completed       : {r['completed']}  ({r['seconds']}s)")
    print(f"error_cause     : {r['error_cause']}")
    print(f"error_detail    : {r['error_detail'][:300]}")
    print(f"clips in plan   : {r['n_clips']}")
    for c in r["clips"]:
        print(f"   {c}")
    print(f"OUT OF RANGE    : {len(r['out_of_range'])} -> {r['out_of_range']}")
    for ln in r["probe_budget_lines"]:
        print(f"   {ln}")
    print("--- plan lines ---")
    for ln in r["plan_lines"]:
        print(f"   {ln[:170]}")
    print("=" * 80)
    print("RESULT " + json.dumps(r, default=str)[:4000])
