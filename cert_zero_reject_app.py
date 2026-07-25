"""ZERO-REJECT Modal cert — proves the minimal route end-to-end BEFORE any deploy.

Ephemeral (`modal run cert_zero_reject_app.py` only, never deployed). Runs the
CURRENT LOCAL handler.py on the production worker image + secrets, calling
handler() directly with constructed jobs (crypto-random job ids — every DB
side-effect no-ops on nonexistent rows; APP_URL is blanked in-container so no
progress POSTs reach the prod server; S3 artifacts land under cert/zero-reject/).

CASES (the cert bar per path):
  1. no_audio      — 12s video-only source, flag-on override → routed, completed,
                     MP4 delivered + mechanically sound (A/V, no stray black).
  2. no_speech     — 12s video + tone audio (Deepgram → 0 words; exercises the
                     FULL path through transcription) → routed, completed.
  3. too_short_3s  — 3.2s source → routed (>= the 2.0s floor), completed.
  4. floor_reject  — 1.5s source → CLIP_TOO_SHORT, the ONE honest rejection.
  5. off_control   — 12s no-speech source with the flag OFF → today's NO_SPEECH
                     rejection, byte-identical live behavior preserved.
"""
import os
import sys
sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-zero-reject", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"


def _synth(path, dur_s, with_audio, audio_kind="tone"):
    import subprocess
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"testsrc2=size=720x1280:rate=30:duration={dur_s}"]
    if with_audio:
        src = ("sine=frequency=440" if audio_kind == "tone" else "anullsrc")
        cmd += ["-f", "lavfi", "-i", f"{src}:duration={dur_s}:sample_rate=44100",
                "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-map", "0:v", "-an"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return path


@app.function(secrets=SECRETS, timeout=2400, cpu=8.0, memory=32768)
def run_case(case: dict) -> dict:
    import json, uuid, subprocess, traceback
    import boto3
    sys.path.insert(0, "/")
    # Kill server POSTs BEFORE importing handler (handler reads APP_URL at call
    # time, but belt: blank it first so no cert traffic touches prod).
    os.environ["APP_URL"] = ""
    import handler as H

    name = case["name"]
    out = {"case": name, "ok": False}
    try:
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
        bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
        jid = str(uuid.uuid4())
        base = f"cert/zero-reject/{jid}"
        # source
        src_local = f"/tmp/{jid}_src.mp4"
        _synth(src_local, case["dur"], case["audio"])
        src_key = f"{base}/source.mp4"
        s3.upload_file(src_local, bucket, src_key, ExtraArgs={"ContentType": "video/mp4"})
        video_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": src_key}, ExpiresIn=3600)
        out_key = f"{base}/output.mp4"
        upload_url = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": out_key,
                                  "ContentType": "video/mp4"}, ExpiresIn=3600)
        thumb_key = f"{base}/thumb.jpg"
        upload_url_thumb = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": thumb_key,
                                  "ContentType": "image/jpeg"}, ExpiresIn=3600)
        input_data = {
            # vibe must be non-empty (the required-fields check is falsy-based)
            "job_id": jid, "user_id": "cert-zero-reject", "vibe": "cert probe",
            "video_url": video_url, "upload_url": upload_url,
            "upload_url_thumb": upload_url_thumb,
            "public_url": f"{CDN}{out_key}",
            "mode": "full",
        }
        if case.get("flag_on", True):
            input_data["zero_reject_test"] = True
        res = H.handler({"input": input_data})
        out["result_keys"] = sorted(res.keys())[:20]
        out["status"] = res.get("status")
        out["error_text"] = (str(res.get("error"))[:200] if res.get("error") else None)
        out["error_code"] = res.get("error_code")
        out["route"] = res.get("route")
        out["route_reason"] = res.get("route_reason")
        out["edit_rationale"] = res.get("edit_rationale")
        expect = case["expect"]
        if expect == "minimal_complete":
            ok = (res.get("status") == "success" and res.get("route") == "minimal"
                  and bool(res.get("video_url")))
            # mechanical: pull the delivered MP4 back and probe it
            if ok:
                dl = f"/tmp/{jid}_check.mp4"
                s3.download_file(bucket, out_key, dl)
                def _probe(sel):
                    r = subprocess.run(
                        ["ffprobe", "-v", "error", "-select_streams", sel,
                         "-show_entries", "stream=duration", "-of", "csv=p=0", dl],
                        capture_output=True, text=True)
                    return float((r.stdout or "0").strip().splitlines()[0] or 0)
                vd, ad = _probe("v:0"), _probe("a:0")
                blk = subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", dl, "-vf",
                     "blackdetect=d=0.2:pic_th=0.98", "-an", "-f", "null", "-"],
                    capture_output=True, text=True)
                nblack = (blk.stderr or "").count("black_start")
                out["mech"] = {"v_dur": round(vd, 3), "a_dur": round(ad, 3),
                               "av_skew_ms": round(abs(vd - ad) * 1000),
                               "black_spans": nblack}
                ok = ok and abs(vd - ad) * 1000 <= 80 and nblack == 0 and vd > 1.0
                ok = ok and bool(res.get("edit_rationale"))
            out["ok"] = bool(ok)
        elif expect == "reject_too_short":
            out["ok"] = (res.get("error_code") == "CLIP_TOO_SHORT"
                         and res.get("designed_rejection") is True)
        elif expect == "reject_no_speech":
            # A faceless synthetic clip legitimately trips the fast-check
            # NOT_TALKING_HEAD BEFORE transcription with the flag off — any of
            # these codes proves today's rejection behavior is preserved.
            out["ok"] = (res.get("error_code") in
                         ("NO_SPEECH", "NO_SPEECH_FACE", "NOT_TALKING_HEAD")
                         and res.get("designed_rejection") is True)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-2000:]
        return out


@app.local_entrypoint()
def main():
    import json
    cases = [
        {"name": "no_audio", "dur": 12.0, "audio": False, "flag_on": True,
         "expect": "minimal_complete"},
        {"name": "no_speech", "dur": 12.0, "audio": True, "flag_on": True,
         "expect": "minimal_complete"},
        {"name": "too_short_3s", "dur": 3.2, "audio": True, "flag_on": True,
         "expect": "minimal_complete"},
        {"name": "floor_reject_1_5s", "dur": 1.5, "audio": True, "flag_on": True,
         "expect": "reject_too_short"},
        {"name": "off_control_no_speech", "dur": 12.0, "audio": True,
         "flag_on": False, "expect": "reject_no_speech"},
    ]
    results = list(run_case.map(cases))
    print("\n================ ZERO-REJECT CERT ================")
    npass = 0
    for r in results:
        npass += 1 if r.get("ok") else 0
        print(json.dumps(r, indent=2, default=str))
    print(f"==================== {npass}/{len(cases)} PASS ====================")
