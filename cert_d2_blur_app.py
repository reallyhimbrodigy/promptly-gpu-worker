"""D2 motion-blur render batch — same clip, control vs samples {3,6,10} x shutter {180,360}.
Blur is only visible during MOTION (zoom/transition/MG), so the VIDEO is the deliverable
(not frames). Returns render URLs to drop in the Review Queue for Zac's eye.
"""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-d2-blur", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SHOWCASE = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=1800)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/d2-blur-cert/{arm['label']}-{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SHOWCASE, "vibe": "Clean and engaging edit",
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
                "tb": traceback.format_exc()[-400:], "wall_s": round(time.time()-t0, 1)}
    r = res if isinstance(res, dict) else {}
    return {"label": arm["label"], "status": r.get("status"),
            "video_url": r.get("video_url"), "wall_s": round(time.time()-t0, 1)}


@app.local_entrypoint()
def main():
    arms = [{"label": "control", "blur": False}]
    i = 1
    for s in (3, 6, 10):
        arms.append({"label": f"s{s}_sh180", "blur": True, "samples": s, "shutter": 180})
    arms.append({"label": "s6_sh360", "blur": True, "samples": 6, "shutter": 360})
    for a in arms:
        a["stagger_s"] = i * 15; i += 1
    print(f"=== D2 BLUR BATCH ({len(arms)} arms) ===")
    for r in run_arm.map(arms):
        if r.get("error"):
            print(f"  {r['label']}: ERROR {r['error']}")
        else:
            print(f"  {r['label']}: {r.get('status')} wall={r.get('wall_s')}s  {r.get('video_url')}")
