"""TIER-1 STAGE A HINDI GRADUATION E2E: render the Hindi failure clip (bb30ffb8, multi 27%-short)
through the FULL handler with Stage A ON. Confirms the clip RECOVERS (Gemini-ID hi → Deepgram hi)
and RENDERS native Devanagari captions (no tofu) instead of rejecting. Extracts frames for the
frontend's per-script eye (tofu / caption fit / timing)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-tier1-tamil-e2e", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/400e9c2f-83da-43fa-a299-00b3fb51475e/1785192532742-5706C3FE-1AD9-45D6-8011-C44F877454B9_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def run() -> dict:
    import time, uuid, traceback, tempfile, subprocess, base64
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"; os.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
    os.environ["PROMPTLY_LANG_ROUTING"] = "1"; os.environ["PROMPTLY_ROUTE_LANGS"] = "hi,bn,ta,te"
    os.environ["PROMPTLY_COVERAGE_GATE"] = "1"
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/tier1-hindi-e2e/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url, "public_url": url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}", "tb": traceback.format_exc()[-500:],
                "wall_s": round(time.time() - t0, 1)}
    r = res if isinstance(res, dict) else {}
    out = {"status": r.get("status"), "video_url": r.get("video_url"), "wall_s": round(time.time() - t0, 1)}
    vurl = r.get("video_url")
    if vurl:
        try:
            b, k = H._parse_aws_s3_url(vurl); src = os.path.join(tempfile.mkdtemp(), "r.mp4")
            H._aws_s3_client.download_file(b, k, src)
            p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",src],
                               capture_output=True, text=True)
            dur = float(json.loads(p.stdout)["format"]["duration"]); out["dur"] = round(dur, 1)
            frames = {}
            for i in range(8):
                ts = dur * (i + 0.5) / 8
                fp = os.path.join(tempfile.mkdtemp(), "f.png")
                subprocess.run(["ffmpeg","-nostats","-loglevel","error","-ss",f"{ts:.2f}","-i",src,
                    "-frames:v","1","-vf","scale=337:600",fp,"-y"], check=False)
                if os.path.exists(fp):
                    frames[f"t{ts:.1f}"] = base64.b64encode(open(fp,"rb").read()).decode()
            out["frames_b64"] = frames
        except Exception as e:
            out["measure_error"] = str(e)[:150]
    return out


@app.local_entrypoint()
def main():
    print("=== TIER-1 TAMIL/TELUGU GRADUATION E2E (bb30ffb8: multi 27%-short → Stage A hi) ===")
    o = run.remote()
    assert o, "no result"
    if o.get("error"):
        print("RENDER ERROR:", o["error"]); print("tb:", o.get("tb")); raise SystemExit("hindi recovery render failed")
    print(f"status={o.get('status')} dur={o.get('dur')}s wall={o.get('wall_s')}s")
    print(f"video={o.get('video_url')}")
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/tamil_e2e_frames"
    os.makedirs(SCR, exist_ok=True)
    import base64
    for ts, b in (o.get("frames_b64") or {}).items():
        open(os.path.join(SCR, f"hindi_{ts}.png"), "wb").write(base64.b64decode(b))
    print(f"frames → {SCR} (inspect for native Devanagari captions, no tofu)")
    assert o.get("status") == "success", f"expected success (recovery), got {o.get('status')}"
    print("\n✅ GRADUATION SAMPLE E2E: rendered (was a TRANSCRIPTION_INCOMPLETE reject before Stage A).")
