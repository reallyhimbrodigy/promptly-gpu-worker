"""FORCE THE SCRIBE PROOF (Zac 2026-08-02): run one Deepgram-zero clip through the
REAL pipeline and convert Scribe from 'armed' to 'working'.

The bake-off proved Scribe transcribes these clips (27b02576: deepgram 0 -> scribe
152 words). This proves the PIPELINE INTEGRATION: the asr_upgrade_scribe divergence
fires, the coverage gate passes on the Scribe transcript, and a REAL edit comes out
where a minimal passthrough / TRANSCRIPTION_INCOMPLETE would have.

Give it the S3 key of a staged Deepgram-zero clip (audio OR video). Audio is muxed
onto the durable face so it's a talking-head the pipeline will edit. Scribe is armed
in-container (promptly-elevenlabs key + PROMPTLY_ASR_SCRIBE=1) and routing is forced
open (PROMPTLY_SCRIBE_LANGS='*') so the clip's language cannot gate it out.

  modal run cert_scribe_proof_app.py --key scribe-proof/27b02576.wav

Priced: cpu=16/64GiB, one full pipeline (~$0.30-0.45). Ephemeral. Full deployed
secret set so render flags match production."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-scribe-proof", image=image)
SECRETS = [modal.Secret.from_name(s) for s in
           ("promptly-secrets", "promptly-lang-flags", "gemini-vertex",
            "promptly-cloudfront", "promptly-elevenlabs")]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
FACE_KEY = "multilingual-cert/_face/face.mp4"


@app.function(secrets=SECRETS, timeout=5400, cpu=16, memory=65536)
def run(key: str) -> dict:
    import subprocess, tempfile, time, uuid, boto3, re
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # Arm Scribe for this run regardless of the deployed flag state, and force
    # the language allowlist open so a matching clip in ANY language routes.
    os.environ["PROMPTLY_ASR_SCRIBE"] = "1"
    os.environ["PROMPTLY_SCRIBE_LANGS"] = "*"
    # BURST REPRO (Zac 2026-08-03): force the burst path (as the live secret does)
    # so we capture WHY the RENDER_BURST=1 dispatch failed — a reproducible case
    # beats the silent absence on real traffic. The render_burst error propagates
    # here; its container log is in the DEPLOYED promptly-gpu-worker app.
    os.environ["PROMPTLY_RENDER_BURST"] = "1"
    import handler as H
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "thisismybucketagainwooo"
    work = tempfile.mkdtemp(prefix="scribeproof_")
    clip = os.path.join(work, os.path.basename(key))
    s3.download_file(bucket, key, clip)
    ext = os.path.splitext(key)[1].lower()

    # Build a talking-head source: video clips pass straight through; an audio
    # clip is muxed onto the durable face (loop to the audio length).
    src = os.path.join(work, "source.mp4")
    if ext in (".mp4", ".mov", ".m4v", ".webm"):
        # normalise container/codecs so the pipeline treats it like an upload
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip,
                        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", src], check=True, capture_output=True)
    else:
        face = os.path.join(work, "face.mp4"); s3.download_file(bucket, FACE_KEY, face)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-stream_loop", "-1", "-i", face, "-i", clip,
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
                        "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                        "-shortest", src], check=True, capture_output=True)

    jid = f"scribeproof-{uuid.uuid4().hex[:10]}"
    base = f"cert/scribe-proof/{jid}"
    s3.upload_file(src, bucket, f"{base}/src.mp4", ExtraArgs={"ContentType": "video/mp4"})
    vurl = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": f"{base}/src.mp4"}, ExpiresIn=14400)
    uurl = s3.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": f"{base}/out.mp4", "ContentType": "video/mp4"}, ExpiresIn=14400)
    turl = s3.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": f"{base}/t.jpg", "ContentType": "image/jpeg"}, ExpiresIn=14400)
    body = {"job_id": jid, "user_id": "cert-scribe-proof", "vibe": "viral",
            "video_url": vurl, "upload_url": uurl, "upload_url_thumb": turl,
            "public_url": f"{CDN}{base}/out.mp4", "mode": "full"}
    t0 = time.time()
    res = H.handler({"input": body})
    ep = (res or {}).get("edit_recipe") or (res or {}).get("edit_plan") or {}
    # count the real-edit signal the same way the silent detector does
    n_cuts = len(ep.get("cuts") or ep.get("clips") or [])
    plan = ep.get("plan") if isinstance(ep.get("plan"), dict) else {}
    n_plan_clips = len(plan.get("clips") or [])
    out = {
        "job_id": jid, "status": res.get("status"), "wall_s": round(time.time() - t0, 1),
        "route": res.get("route"), "detected_language": res.get("detected_language"),
        "asr_engine": (res.get("stage_timings") or {}).get("asr_engine"),
        "n_cuts": n_cuts, "n_plan_clips": n_plan_clips,
        "error": str(res.get("error"))[:200] if res.get("error") else None,
        "out_url": s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": f"{base}/out.mp4"}, ExpiresIn=86400),
    }
    import shutil; shutil.rmtree(work, ignore_errors=True)
    return out


@app.local_entrypoint()
def main(key: str = ""):
    if not key:
        print("PASS --key <s3-key-of-staged-clip> (e.g. scribe-proof/27b02576.wav)"); return
    r = run.remote(key)
    print("\n" + "=" * 66 + "\nSCRIBE PROOF — one Deepgram-zero clip through the real pipeline\n" + "=" * 66)
    print(json.dumps(r, indent=2))
    print("\nProof signals to grep the worker logs for this job_id:")
    print(f"  [asr-upgrade] ... => SCRIBE     (Scribe beat Deepgram)")
    print(f"  divergence asr_upgrade_scribe   (recorded)")
    print(f"  status={r.get('status')} route={r.get('route')} cuts={r.get('n_cuts')}"
          f" plan_clips={r.get('n_plan_clips')}  ← non-zero cuts + status=completed = a REAL edit, not minimal")
