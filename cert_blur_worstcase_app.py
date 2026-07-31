"""BLUR GUARD (Zac 2026-07-27): verify motion-blur samples on the WORST CASE, not the
showcase. Failure mode is a per-chunk render TIMEOUT (_PLAIN_CHUNK_TIMEOUT=300s per
overlay chunk; samples-10/360 tripped it on the 20s showcase). A long source has more
chunks AND more moving elements per chunk, so blur cost per chunk is higher. Render a
2-3min source at control / s3 / s6 (shutter 180) and report per-arm wall-clock. A
'completed' status = no chunk exceeded 300s; a degrade = it did. Ship with headroom
BELOW the failure point.

Uses a component-heavy long clip (viral vibe maximizes zooms/MG → worst blur load)."""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-blur-worstcase", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
# 84a1d4df — 143s (2.4min), 152 words → dense captions + many zooms = high blur load. Renders.
LONG_SRC = "https://d1iax8jos987n3.cloudfront.net/sources/42354e24-96bd-4b94-b9e8-d3157748f192/1785049174706-1A405575-F62C-41C6-8279-FC959EFD13C8_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=3300)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_COVERAGE_GATE"] = ""  # isolate the render-perf test from the gate
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/blur-worstcase/{arm['label']}-{jid}/render.mp4"
    body = {"job_id": jid, "video_url": arm["src"], "vibe": "High energy viral edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url, "public_url": url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    if arm.get("blur"):
        body["motion_blur_test"] = True
        body["motion_blur_samples"] = arm["samples"]
        body["motion_blur_shutter"] = arm["shutter"]
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"label": arm["label"], "error": f"{type(e).__name__}: {str(e)[:200]}",
                "tb": traceback.format_exc()[-400:], "wall_s": round(time.time() - t0, 1)}
    r = res if isinstance(res, dict) else {}
    return {"label": arm["label"], "status": r.get("status"), "video_url": r.get("video_url"),
            "wall_s": round(time.time() - t0, 1)}


@app.local_entrypoint()
def main():
    assert "XXReplaceXX" not in LONG_SRC, "set LONG_SRC to the real 84a1d4df source URL before running"
    arms = [{"label": "control", "blur": False, "src": LONG_SRC}]
    for s in (3, 6):
        arms.append({"label": f"s{s}_sh180", "blur": True, "samples": s, "shutter": 180, "src": LONG_SRC})
    for i, a in enumerate(arms):
        a["stagger_s"] = i * 20
    print(f"=== BLUR WORST-CASE ({len(arms)} arms, long clip; per-chunk timeout=300s, reaper=3300s) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement produced"
    for r in out:
        if r.get("error"):
            print(f"  {r['label']}: ERROR {r['error']}  (wall {r.get('wall_s')}s)")
        else:
            hd = 300  # per-chunk budget; a 'completed' status means every chunk fit under it
            print(f"  {r['label']}: {r.get('status')} wall={r.get('wall_s')}s "
                  f"({'no chunk hit 300s' if r.get('status') else 'DEGRADED — a chunk hit the wall'})  "
                  f"{r.get('video_url')}")
    print("READ: control gives the no-blur baseline; s3/s6 must complete with margin. "
          "If s6 degrades or runs long, ship s3.")
