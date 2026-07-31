"""Caption STYLE comparison — same showcase clip rendered as CleanCut (current) vs
TwoTone vs Pulse vs Cove. Measures caption-band change-energy per arm (CleanCut baselines
~5.4; references 11.7-28.2) so the session yields a NUMBER, plus frames for Zac's eye.
Decides RE-ROUTE (bias selection) vs RAISE-THE-DEFAULT (give CleanCut phrase+keyword).
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-caption-style", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SHOWCASE = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


def _cap_energy(src, cap_lo=0.60, cap_hi=0.98):
    """Caption-band change-energy: rate + energy/event (same method as change_energy.py)."""
    import subprocess, numpy as np
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "json", src], capture_output=True, text=True)
    s = json.loads(p.stdout)["streams"][0]; W, H = int(s["width"]), int(s["height"])
    w = 160; h = int(round(H * w / W / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-i", src,
        "-vf", f"fps=15,scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    n = len(raw) // (w * h)
    arr = np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.int16)
    diff = np.abs(arr[1:] - arr[:-1]).astype(np.float32)
    y0, y1 = int(h * cap_lo), int(h * cap_hi)
    cap = diff[:, y0:y1, :].mean(axis=1).mean(axis=1)
    dur = (n - 1) / 15.0
    def count(sig, T, mg):
        pk, last = [], -10**9
        for i in range(1, len(sig) - 1):
            if sig[i] >= T and sig[i] >= sig[i-1] and sig[i] > sig[i+1] and i - last >= mg:
                pk.append(float(sig[i])); last = i
        return len(pk), (round(float(np.mean(pk)), 2) if pk else 0.0)
    c2, e2 = count(cap, 2, 2)
    return {"cap_rate": round(c2 / dur, 3), "cap_energy_per_event": e2,
            "cap_mean_energy": round(float(cap.mean()), 2)}


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=1800)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback, base64, tempfile, subprocess
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/caption-style-cert/{arm['style']}-{jid}/render.mp4"
    body = {"job_id": jid, "video_url": SHOWCASE, "vibe": "Clean and engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url, "public_url": url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False,
            "caption_style_test": arm["style"]}
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"style": arm["style"], "error": f"{type(e).__name__}: {str(e)[:200]}",
                "tb": traceback.format_exc()[-400:], "wall_s": round(time.time()-t0, 1)}
    r = res if isinstance(res, dict) else {}
    vurl = r.get("video_url"); energy = None; frames = {}
    if vurl:
        try:
            b, k = H._parse_aws_s3_url(vurl); src = os.path.join(tempfile.mkdtemp(), "r.mp4")
            H._aws_s3_client.download_file(b, k, src)
            energy = _cap_energy(src)
            for ts in (5, 11, 17):
                fp = os.path.join(tempfile.mkdtemp(), "f.png")
                subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", str(ts), "-i", src,
                    "-frames:v", "1", "-vf", "scale=337:600", fp, "-y"], check=False)
                if os.path.exists(fp):
                    frames[f"t{ts}"] = base64.b64encode(open(fp, "rb").read()).decode()
        except Exception as e:
            energy = {"measure_error": str(e)[:150]}
    return {"style": arm["style"], "status": r.get("status"), "video_url": vurl,
            "energy": energy, "frames_b64": frames, "wall_s": round(time.time()-t0, 1)}


@app.local_entrypoint()
def main():
    styles = ["CleanCut", "TwoTone", "Pulse", "Cove"]
    arms = [{"style": s, "stagger_s": i * 15} for i, s in enumerate(styles)]
    print("=== CAPTION STYLE COMPARISON (CleanCut baseline 5.4; refs 11.7-28.2) ===")
    out = list(run_arm.map(arms))
    import base64
    outdir = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/style_frames"
    os.makedirs(outdir, exist_ok=True)
    for r in out:
        print(f"\n--- {r['style']} (wall {r.get('wall_s')}s) ---")
        if r.get("error"):
            print("  ERROR:", r["error"]); continue
        print("  status:", r.get("status"), "| ENERGY:", json.dumps(r.get("energy")))
        print("  video:", r.get("video_url"))
        for ts, b in (r.get("frames_b64") or {}).items():
            open(os.path.join(outdir, f"{r['style']}_{ts}.png"), "wb").write(base64.b64decode(b))
    print(f"\n=== CAPTION ENERGY/EVENT SUMMARY (vs CleanCut 5.4 / refs 11.7-28.2) ===")
    for r in out:
        e = r.get("energy") or {}
        print(f"  {r['style']}: energy/event={e.get('cap_energy_per_event')} rate={e.get('cap_rate')} mean={e.get('cap_mean_energy')}")
    print(f"frames → {outdir}")
