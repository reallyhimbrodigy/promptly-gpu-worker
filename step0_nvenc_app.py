"""STEP 0 (Zac cleared 2026-08-01): does OUR current image's ffmpeg carry nvenc/cuvid?
ONE L4 container, prints the encoder/decoder greps verbatim. Price: L4 $0.000222/s x
~30s ~= $0.01 (image cached, no build). If absent -> build the CUDA/NVENC image."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("step0-nvenc", image=image)
@app.function(gpu="L4", timeout=180)
def check():
    import subprocess
    def run(a): return subprocess.run(a, capture_output=True, text=True)
    smi = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    enc = run(["ffmpeg", "-hide_banner", "-encoders"])
    dec = run(["ffmpeg", "-hide_banner", "-decoders"])
    ver = run(["ffmpeg", "-hide_banner", "-version"])
    nvenc = [l.strip() for l in enc.stdout.splitlines() if "nvenc" in l.lower()]
    cuvid = [l.strip() for l in dec.stdout.splitlines() if ("cuvid" in l.lower() or "nvdec" in l.lower())]
    return {"gpu": (smi.stdout or smi.stderr).strip()[:80],
            "ffmpeg": (ver.stdout.splitlines()[0] if ver.stdout else "")[:90],
            "nvenc_encoders": nvenc, "cuvid_decoders": cuvid}
@app.local_entrypoint()
def main():
    print("STEP0 " + json.dumps(check.remote(), indent=2))
