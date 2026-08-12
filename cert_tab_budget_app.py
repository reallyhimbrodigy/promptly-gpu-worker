"""48-TAB CONTENTION measurement (Zac 2026-08-02): the overlay render fans out a
Chromium-tab budget (historically 32) across parallel chunks, but the container
is cpu=16 — so 32 tabs / 16 vCPU = 2x oversubscription, the leading suspect for a
micro chunk crawling at 0.3 fps into the 600s RENDER_FATAL floor (2f07c37b).

Renders the SAME durable clip at PROMPTLY_OVERLAY_TAB_BUDGET = 32 (current) / 16
(scaled to cores) / 8, on cpu=16 (production render size), and reports render_s
per arm. If a smaller budget is FASTER, the oversubscription is real and it is
free latency on EVERY chunked render.

Ephemeral (`modal run cert_tab_budget_app.py`). Full deployed secret set so the
render flags match production. Priced ~$0.6-0.9 (3 chunked renders @ cpu=16)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-tab-budget", image=image)
SECRETS = [modal.Secret.from_name(s) for s in
           ("promptly-secrets", "promptly-lang-flags", "gemini-vertex", "promptly-cloudfront")]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
FACE_KEY = "multilingual-cert/_face/face.mp4"
AUDIO_KEY = "multilingual-cert/_bridge_regression/en.m4a"


@app.function(secrets=SECRETS, timeout=5400, cpu=16, memory=65536)
def run(dur: float = 45.0, budgets: str = "32,16,8") -> dict:
    import subprocess, tempfile, time, uuid, boto3
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "thisismybucketagainwooo"
    work = tempfile.mkdtemp(prefix="tabm_")
    face = os.path.join(work, "f.mp4"); aud = os.path.join(work, "a.m4a"); src = os.path.join(work, "s.mp4")
    s3.download_file(bucket, FACE_KEY, face); s3.download_file(bucket, AUDIO_KEY, aud)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", face,
                    "-stream_loop", "-1", "-i", aud, "-map", "0:v:0", "-map", "1:a:0",
                    "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-shortest", src], check=True, capture_output=True)
    out = {"dur_s": dur, "cpu": 16, "arms": {}}

    def _render(budget):
        import handler as H
        os.environ["PROMPTLY_OVERLAY_TAB_BUDGET"] = str(budget)
        jid = f"tabm-{budget}-{uuid.uuid4().hex[:8]}"; key = f"cert/tabm/{jid}.mp4"
        vurl = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": f"cert/tabm/{jid}_s.mp4"}, ExpiresIn=7200)
        s3.upload_file(src, bucket, f"cert/tabm/{jid}_s.mp4", ExtraArgs={"ContentType": "video/mp4"})
        uurl = s3.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": key, "ContentType": "video/mp4"}, ExpiresIn=7200)
        turl = s3.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": f"cert/tabm/{jid}_t.jpg", "ContentType": "image/jpeg"}, ExpiresIn=7200)
        body = {"job_id": jid, "user_id": "cert-tabm", "vibe": "viral", "video_url": vurl,
                "upload_url": uurl, "upload_url_thumb": turl, "public_url": f"{CDN}{key}", "mode": "full"}
        t = time.time()
        res = H.handler({"input": body})
        st = (res or {}).get("stage_timings") or {}
        return {"budget": budget, "status": res.get("status"), "wall_s": round(time.time() - t, 1),
                "render_s": st.get("render"), "err": str(res.get("error"))[:120] if res.get("error") else None}

    for b in [int(x) for x in budgets.split(",") if x.strip()]:
        out["arms"][str(b)] = _render(b)
    import shutil; shutil.rmtree(work, ignore_errors=True)
    return out


@app.local_entrypoint()
def main(dur: float = 45.0, budgets: str = "32,16,8"):
    r = run.remote(dur, budgets)
    print("\n" + "=" * 60 + "\n48-TAB CONTENTION — overlay tab budget vs cpu=16\n" + "=" * 60)
    print(json.dumps(r, indent=2))
    a = r.get("arms", {})
    base = a.get("32", {}).get("render_s")
    print(f"\nrender_s by tab budget (cpu=16, dur={dur}s):")
    for b in sorted(a, key=int, reverse=True):
        rs = a[b].get("render_s")
        delta = f"  ({rs - base:+.1f}s vs 32)" if (rs and base) else ""
        print(f"  budget={b:>2} → render {rs}s  status={a[b].get('status')}{delta}")
    print("\n→ if 16/8 is FASTER than 32, the 48-tab oversubscription is real: reduce "
          "PROMPTLY_OVERLAY_TAB_BUDGET to the core count — free latency on every chunked render.")
