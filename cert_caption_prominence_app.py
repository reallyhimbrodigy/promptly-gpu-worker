"""CAPTION PROMINENCE frames (Zac: frames not metrics). One clip (showcase), 4 variants:
CleanCut(control) / CleanCut phrase-chunked / TwoTone(larger-bolder two-tone) / Cove(keyword-
coloured). Extract frames at caption moments to place BESIDE REF_C. Energy reported as context only."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-caption-prominence", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SHOWCASE = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"
VARIANTS = [
    {"label": "1_CleanCut_control", "style": "CleanCut", "mw": 2},
    {"label": "2_CleanCut_phrasechunk", "style": "CleanCut", "mw": 4},
    {"label": "3_TwoTone_bold", "style": "TwoTone", "mw": 3},
    {"label": "4_Cove_keywordcolour", "style": "Cove", "mw": 2},
]


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=1800)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback, tempfile, subprocess, base64
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/caption-prominence/{arm['label']}-{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SHOWCASE, "vibe": "Clean and engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url, "public_url": url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False,
            "caption_style_test": arm["style"], "caption_max_words": arm["mw"]}
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"label": arm["label"], "error": f"{type(e).__name__}: {str(e)[:180]}", "wall": round(time.time()-t0,1)}
    r = res if isinstance(res, dict) else {}
    out = {"label": arm["label"], "status": r.get("status"), "video_url": r.get("video_url"), "wall": round(time.time()-t0,1)}
    vurl = r.get("video_url")
    if vurl:
        try:
            b, k = H._parse_aws_s3_url(vurl); src = os.path.join(tempfile.mkdtemp(), "r.mp4")
            H._aws_s3_client.download_file(b, k, src)
            p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",src], capture_output=True, text=True)
            dur = float(json.loads(p.stdout)["format"]["duration"])
            frames = {}
            for ts in (dur*0.30, dur*0.55, dur*0.80):
                fp = os.path.join(tempfile.mkdtemp(), "f.png")
                subprocess.run(["ffmpeg","-nostats","-loglevel","error","-ss",f"{ts:.2f}","-i",src,"-frames:v","1","-vf","scale=360:640",fp,"-y"], check=False)
                if os.path.exists(fp):
                    frames[f"t{ts:.0f}"] = base64.b64encode(open(fp,"rb").read()).decode()
            out["frames_b64"] = frames
        except Exception as e:
            out["measure_error"] = str(e)[:120]
    return out


@app.local_entrypoint()
def main():
    arms = [{**v, "stagger_s": i*15} for i, v in enumerate(VARIANTS)]
    print("=== CAPTION PROMINENCE (4 variants; frames beside REF_C, Zac's eye) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement"
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/prominence_frames"
    os.makedirs(SCR, exist_ok=True)
    import base64
    for r in out:
        print(f"\n--- {r['label']} (wall {r.get('wall')}s) status={r.get('status')} ---")
        if r.get("error"): print("  ERROR:", r["error"]); continue
        print("  video:", r.get("video_url"))
        for ts, bdata in (r.get("frames_b64") or {}).items():
            open(os.path.join(SCR, f"{r['label']}_{ts}.png"), "wb").write(base64.b64decode(bdata))
    print(f"\nframes → {SCR} (place beside REF_C_flare_fuckhooks_*.png in refframes/)")
