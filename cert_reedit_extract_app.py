"""Extract frames around a target timestamp from the ALREADY-rendered re-edit E2E video
(no re-render). Confirms visually whether the folded caption override 'SPENDINGZ' rendered
where the word 'spending' (10.22-10.54s) is spoken."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-reedit-extract", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront")]
RENDER_URL = "https://thisismybucketagainwooo.s3.amazonaws.com/reedit-e2e/a73f7b93-87b0-4aab-9778-bbb2dffaa9b0/render.mp4"
TIMESTAMPS = [9.9, 10.2, 10.35, 10.5, 10.7]


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=600)
def extract() -> dict:
    import tempfile, subprocess, base64
    sys.path.insert(0, "/")
    import handler as H
    b, k = H._parse_aws_s3_url(RENDER_URL)
    d = tempfile.mkdtemp(); src = os.path.join(d, "r.mp4")
    H._aws_s3_client.download_file(b, k, src)
    out = {}
    for ts in TIMESTAMPS:
        fp = os.path.join(d, f"f{ts}.png")
        subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", f"{ts:.2f}",
            "-i", src, "-frames:v", "1", "-vf", "scale=540:960", fp, "-y"], check=False)
        if os.path.exists(fp):
            out[f"t{ts}"] = base64.b64encode(open(fp, "rb").read()).decode()
    return out


@app.local_entrypoint()
def main():
    res = extract.remote()
    assert res, "no frames extracted"
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/reedit_e2e_frames"
    os.makedirs(SCR, exist_ok=True)
    import base64
    for ts, b in res.items():
        open(os.path.join(SCR, f"target_{ts}.png"), "wb").write(base64.b64decode(b))
    print(f"extracted {len(res)} frames around 'spending' (10.3s) → {SCR}/target_*.png")
