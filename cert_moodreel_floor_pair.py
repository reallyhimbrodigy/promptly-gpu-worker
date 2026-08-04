"""THE 3-8s FLOOR PAIR (Zac approved ~$0.25, 2026-08-04).

Validates a change ALREADY LIVE on 371 jobs / 355 users that shipped on a ruling
rather than on measured quality: the mood-reel duration floor dropped 8.0s -> 3.0s,
so silent clips in the 3-8s band now get a MODEL-COMPOSED cut instead of the
deterministic minimal edit.

The static-silent worry turned out to be moot (a still clip yields a curve of
zeros, which is truthy, so static footage always reached moodreel). The 3-8s band
is the ONLY genuinely new population, so it is the only thing worth paying to
watch.

ONE VARIABLE. Same source bytes, same container image, same secrets; the only
difference is `moodreel_test`, which is exactly the gate the floor change opened:
    arm A  moodreel_test=True   -> moodreel  (NEW behaviour for this band)
    arm B  moodreel_test absent -> minimal   (OLD behaviour)

Run:  modal run cert_moodreel_floor_pair.py
"""
import os

import modal
import modal_app

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("/tmp/pair_src_5s.mp4", "/pair_src_5s.mp4"))
app = modal.App("cert-moodreel-floor-pair", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"


@app.function(secrets=SECRETS, timeout=2400, cpu=8.0, memory=32768)
def run_arm(arm: dict) -> dict:
    import json
    import sys
    import boto3
    sys.path.insert(0, "/")
    import handler as H

    name = arm["name"]
    jid = f"floorpair-{name}"
    out = {"arm": name}
    s3 = boto3.client("s3")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    base = f"cert/moodreel-floor-pair/{jid}"

    src_key = f"{base}/source.mp4"
    s3.upload_file("/pair_src_5s.mp4", bucket, src_key,
                   ExtraArgs={"ContentType": "video/mp4"})
    video_url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": src_key}, ExpiresIn=7200)
    out_key = f"{base}/output.mp4"
    upload_url = s3.generate_presigned_url(
        "put_object", Params={"Bucket": bucket, "Key": out_key,
                              "ContentType": "video/mp4"}, ExpiresIn=7200)
    thumb_key = f"{base}/thumb.jpg"
    upload_url_thumb = s3.generate_presigned_url(
        "put_object", Params={"Bucket": bucket, "Key": thumb_key,
                              "ContentType": "image/jpeg"}, ExpiresIn=7200)

    input_data = {
        "job_id": jid,
        "user_id": "cert-moodreel-floor-pair",
        # ONE vibe for both arms — the pair tests the ROUTE, not the vibe.
        "vibe": "cinematic and calm",
        "video_url": video_url,
        "upload_url": upload_url,
        "upload_url_thumb": upload_url_thumb,
        "public_url": f"{CDN}{out_key}",
        "mode": "full",
        "zero_reject_test": True,
    }
    if arm.get("moodreel"):
        input_data["moodreel_test"] = True

    res = H.handler({"input": input_data})
    out["status"] = res.get("status")
    out["route"] = res.get("route")
    out["route_reason"] = res.get("route_reason")
    out["error"] = str(res.get("error"))[:200] if res.get("error") else None
    out["video_url"] = res.get("video_url")
    out["public_url"] = f"{CDN}{out_key}"
    out["edit_rationale"] = res.get("edit_rationale")
    er = res.get("edit_recipe") or {}
    plan = (er.get("plan") or er) if isinstance(er, dict) else {}
    out["clips"] = len(plan.get("clips") or plan.get("cuts") or [])
    out["transitions"] = len(plan.get("transitions") or [])
    out["motion_graphics"] = len(plan.get("motion_graphics") or [])
    # the headline the floor change is supposed to move
    out["editorial_events"] = (max(0, out["clips"] - 1)
                               + out["transitions"] + out["motion_graphics"])
    print(f"[floor-pair] {name}: route={out['route']} events={out['editorial_events']} "
          f"clips={out['clips']} trans={out['transitions']}", flush=True)
    return out


@app.local_entrypoint()
def main():
    import json
    arms = [{"name": "A_moodreel", "moodreel": True},
            {"name": "B_minimal", "moodreel": False}]
    results = list(run_arm.map(arms))
    print("\n============ 3-8s FLOOR PAIR ============")
    for r in results:
        print(json.dumps(r, indent=2, default=str))
    ok = [r for r in results if r.get("status") == "success"]
    print(f"\n{len(ok)}/2 arms rendered")
    if len(ok) == 2:
        a = next(r for r in results if r["arm"] == "A_moodreel")
        b = next(r for r in results if r["arm"] == "B_minimal")
        print(f"routes:  A={a['route']}  B={b['route']}")
        print(f"events:  A={a['editorial_events']}  B={b['editorial_events']}")
        if a["route"] == b["route"]:
            print("⚠️  ARMS DID NOT DIVERGE — same route. The pair proves nothing; "
                  "do NOT send it to Zac.")
