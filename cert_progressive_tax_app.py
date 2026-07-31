"""PROGRESSIVE TAX PROBE (Zac 2026-07-26): does publishing a preview slow the
render? The preview is a separate libx264 encode of each composite chunk running
in a background thread on the SAME container as the render. Measure the render
wall-clock with supports_progressive OFF vs ON on the SAME durable source.
Ephemeral (`modal run`), never deployed. Reports render/total delta."""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-progressive-tax", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("promptly-lang-flags")]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
FACE_KEY = "multilingual-cert/_face/face.mp4"; AUDIO_KEY = "multilingual-cert/_bridge_regression/en.m4a"

@app.function(secrets=SECRETS, timeout=4800, cpu=64, memory=131072)
def run_leg(progressive: bool, dur: float = 75.0, ts: str = "0") -> dict:
    import uuid, subprocess, boto3, time, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_PROGRESSIVE", None)
    import handler as H
    out = {"progressive": progressive, "ok": False}
    try:
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
        bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
        work = f"/tmp/tax/{uuid.uuid4().hex[:8]}"; os.makedirs(work, exist_ok=True)
        face = f"{work}/face.mp4"; aud = f"{work}/en.m4a"; src = f"{work}/src.mp4"
        s3.download_file(bucket, FACE_KEY, face); s3.download_file(bucket, AUDIO_KEY, aud)
        subprocess.run(["ffmpeg","-y","-loglevel","error","-stream_loop","-1","-i",face,
            "-stream_loop","-1","-i",aud,"-map","0:v:0","-map","1:a:0","-t",f"{dur:.1f}",
            "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-ar","44100","-shortest",src],
            check=True, capture_output=True, text=True)
        jid = f"certtax-{uuid.uuid4().hex[:10]}"; base = f"cert/tax/{jid}"
        s3.upload_file(src, bucket, f"{base}/source.mp4", ExtraArgs={"ContentType":"video/mp4"})
        vurl = s3.generate_presigned_url("get_object", Params={"Bucket":bucket,"Key":f"{base}/source.mp4"}, ExpiresIn=7200)
        uurl = s3.generate_presigned_url("put_object", Params={"Bucket":bucket,"Key":f"{base}/out.mp4","ContentType":"video/mp4"}, ExpiresIn=7200)
        turl = s3.generate_presigned_url("put_object", Params={"Bucket":bucket,"Key":f"{base}/thumb.jpg","ContentType":"image/jpeg"}, ExpiresIn=7200)
        body = {"job_id": jid, "user_id": "cert-progressive-tax", "vibe": "clean confident",
                "video_url": vurl, "upload_url": uurl, "upload_url_thumb": turl,
                "public_url": f"{CDN}{base}/out.mp4", "mode": "full",
                "supports_progressive": bool(progressive)}
        t0 = time.time()
        res = H.handler({"input": body})
        wall = time.time() - t0
        st = res.get("stage_timings") or {}
        out.update({"ok": res.get("status") == "success", "status": res.get("status"),
                    "handler_wall_s": round(wall, 1), "total": st.get("total"),
                    "render": st.get("render"), "edit_plan": st.get("edit_plan"),
                    "upload_export": st.get("upload_export")})
        return out
    except Exception as e:
        out["exc"] = f"{type(e).__name__}: {e}"; out["tb"] = traceback.format_exc()[-1200:]; return out

@app.local_entrypoint()
def main():
    import json, time
    ts = str(int(1000))
    # run OFF then ON on identical sources (Gemini nondeterminism affects plan, not the render-encode tax we isolate via render/total)
    off = run_leg.remote(False, 75.0, ts)
    on = run_leg.remote(True, 75.0, ts)
    print("\n===== PROGRESSIVE TAX (75s source) =====")
    print("OFF:", json.dumps(off)); print("ON :", json.dumps(on))
    if off.get("render") and on.get("render"):
        dr = on["render"] - off["render"]; dt = (on.get("total") or 0) - (off.get("total") or 0)
        print(f"\nDELTA render: {dr:+.1f}s ({100*dr/off['render']:+.0f}%)  |  total: {dt:+.1f}s")
        print(f"OFF render={off['render']}s total={off.get('total')}s | ON render={on['render']}s total={on.get('total')}s")
    print("========================================")
