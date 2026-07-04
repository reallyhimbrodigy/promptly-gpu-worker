# promptly-matting — SIBLING Modal app (behind-layer Phase 1).
# Freeze-legal by construction: nothing in the frozen worker (v193) calls this.
# GPU person-matting built on Robust Video Matting (PeterL1n), weights BAKED
# into the image (no runtime downloads). Per window: ~1s lead-in so the
# recurrent state settles before the window opens; auto downsample_ratio per
# RVM guidance; windows process independently (parallelize across calls).
#
# NOTE: this file is parsed by the local modal CLI (Python 3.9) — no X|Y
# unions, no 3.10+ syntax at module level.
import os

import modal

RVM_REPO = "https://github.com/PeterL1n/RobustVideoMatting"
W_BASE = RVM_REPO + "/releases/download/v1.0.0"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git", "wget")
    .pip_install("torch==2.4.1", "torchvision==0.19.1", "numpy", "boto3", "requests")
    .run_commands(
        "git clone --depth 1 " + RVM_REPO + " /rvm",
        "mkdir -p /weights",
        "wget -q " + W_BASE + "/rvm_mobilenetv3.pth -O /weights/rvm_mobilenetv3.pth",
        "wget -q " + W_BASE + "/rvm_resnet50.pth -O /weights/rvm_resnet50.pth",
        "test -s /weights/rvm_mobilenetv3.pth && test -s /weights/rvm_resnet50.pth",
    )
)

app = modal.App(
    "promptly-matting",
    image=image,
    secrets=[modal.Secret.from_name("promptly-secrets")],
)

_DEPLOYER = os.environ.get("PROMPTLY_DEPLOYER", "claude-code")

LEAD_IN_S = 1.0  # recurrent-state settle time before each window opens
# RVM guidance: downsample so the matting backbone sees ~256-512px on the
# short side. Portrait 1080x1920: 0.25 => 270x480 (fast), 0.375 => 405x720.
QUALITY_RATIO = {"fast": 0.25, "best": 0.375, "full": 1.0}

# ── The keying finish (Phase 1.5 R3) — alpha post-chain, constants named ────
# Applied to the raw per-frame mattes BEFORE composing/encoding. Bias: a
# hair-thin dark bite (erode) reads better than a bright un-dimmed halo —
# the wash shot is the worst case and the tiebreak.
ALPHA_TEMPORAL_WINDOW = 3   # median over t-1, t, t+1 (odd; 1 disables)
ALPHA_ERODE_PX = 1          # min-filter radius, px (0 disables)
ALPHA_FEATHER_PX = 1.0      # gaussian sigma, px (0 disables)


def _matte_impl(video_url, windows, quality, model_name, formats, gpu_label, post=None):
    import json
    import subprocess
    import time

    import boto3
    import numpy as np
    import torch

    t_all = time.time()
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3 = boto3.client("s3", region_name=region)
    print("BUILD app=promptly-matting deployer=" + _DEPLOYER
          + " gpu=" + gpu_label + " model=" + model_name, flush=True)

    # source download (once per call)
    t0 = time.time()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video_url,
                    "-c", "copy", "/tmp/src.mp4"], check=True, timeout=600)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:stream_side_data=rotation",
         "-of", "json", "/tmp/src.mp4"], capture_output=True, text=True)
    st = json.loads(probe.stdout)["streams"][0]
    W, H = int(st["width"]), int(st["height"])
    # Phone portrait sources store landscape + a rotation side-data; ffmpeg's
    # raw decode AUTO-ROTATES, so the pipe delivers DISPLAY-oriented frames.
    # Reshaping with coded dims transposed every frame into garbage (the
    # all-zero-alpha bug) — swap to display dims when rotation is +/-90.
    _rot = 0
    for _sd in (st.get("side_data_list") or []):
        if "rotation" in _sd:
            _rot = int(_sd["rotation"])
    if abs(_rot) % 180 == 90:
        W, H = H, W
    num, den = st["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    dl_s = time.time() - t0

    # model load
    t0 = time.time()
    model = torch.hub.load("/rvm", model_name, source="local", pretrained=False)
    sd = torch.load("/weights/rvm_" + model_name + ".pth", map_location="cuda")
    model.load_state_dict(sd)
    model = model.cuda().eval().half()
    ratio = QUALITY_RATIO.get(quality, QUALITY_RATIO["fast"])
    load_s = time.time() - t0

    results = []
    for wi, win in enumerate(windows):
        w_start = float(win["start"])
        w_end = float(win["end"])
        lead = min(LEAD_IN_S, w_start)
        dec_start = w_start - lead
        n_lead = int(round(lead * fps))
        n_frames = int(round((w_end - w_start) * fps))

        # decode lead-in + window as raw RGB
        t0 = time.time()
        dec = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", str(dec_start), "-i", "/tmp/src.mp4",
             "-frames:v", str(n_lead + n_frames), "-f", "rawvideo",
             "-pix_fmt", "rgb24", "pipe:1"],
            stdout=subprocess.PIPE)
        frame_bytes = W * H * 3
        fgr_frames = []  # window frames only (lead-in discarded post-inference)
        pha_frames = []
        rec = [None] * 4
        infer_s = 0.0
        idx = 0
        with torch.no_grad():
            while True:
                buf = dec.stdout.read(frame_bytes)
                if not buf or len(buf) < frame_bytes:
                    break
                src = torch.frombuffer(bytearray(buf), dtype=torch.uint8)
                src = src.reshape(1, H, W, 3).permute(0, 3, 1, 2).cuda().half() / 255.0
                ti = time.time()
                fgr, pha, *rec = model(src, *rec, downsample_ratio=ratio)
                torch.cuda.synchronize()
                infer_s += time.time() - ti
                if idx >= n_lead:
                    fgr_frames.append(
                        (fgr.clamp(0, 1)[0].permute(1, 2, 0) * 255)
                        .byte().cpu().numpy().astype(np.uint8))
                    pha_frames.append(
                        (pha.clamp(0, 1)[0, 0] * 255)
                        .byte().cpu().numpy().astype(np.uint8))
                idx += 1
        dec.stdout.close()
        dec.wait()
        decode_s = time.time() - t0 - infer_s

        # ── R3 keying finish: temporal median → erode → feather ────────────
        post_s = 0.0
        if post:
            import torch.nn.functional as Fnn
            ti = time.time()
            tw = int(post.get("temporal", ALPHA_TEMPORAL_WINDOW))
            er = int(post.get("erode", ALPHA_ERODE_PX))
            fe = float(post.get("feather", ALPHA_FEATHER_PX))
            ph = torch.from_numpy(np.stack(pha_frames)).cuda().half() / 255.0
            ph = ph.unsqueeze(1)  # T,1,H,W
            if tw >= 3:
                pad = tw // 2
                idxs = [torch.clamp(torch.arange(len(pha_frames)) + o, 0,
                                    len(pha_frames) - 1) for o in range(-pad, pad + 1)]
                ph = torch.median(torch.stack([ph[i] for i in idxs]), dim=0).values
            if er > 0:
                k = 2 * er + 1
                ph = -Fnn.max_pool2d(-ph, k, stride=1, padding=er)
            if fe > 0:
                rad = max(1, int(round(3 * fe)))
                x = torch.arange(-rad, rad + 1, dtype=torch.half, device="cuda")
                g = torch.exp(-(x ** 2) / (2 * fe * fe))
                g = (g / g.sum()).reshape(1, 1, 1, -1)
                ph = Fnn.conv2d(ph, g, padding=(0, rad))
                ph = Fnn.conv2d(ph, g.reshape(1, 1, -1, 1), padding=(rad, 0))
            ph = (ph.clamp(0, 1)[:, 0] * 255).byte().cpu().numpy()
            pha_frames = [ph[i] for i in range(ph.shape[0])]
            torch.cuda.synchronize()
            post_s = time.time() - ti

        rgba_frames = [
            np.dstack([fgr_frames[i], pha_frames[i]]) for i in range(len(fgr_frames))
        ]
        del fgr_frames, pha_frames

        # encode each requested alpha format from the buffered RGBA frames
        enc_out = {}
        for fmt in formats:
            t0 = time.time()
            key = ("matting-tests/%s/win%d_%s_%s_%s"
                   % (win.get("tag", "w"), wi, model_name, quality, fmt))
            if fmt == "webm":
                out, args = "/tmp/out.webm", [
                    "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                    "-b:v", "0", "-crf", "28", "-row-mt", "1", "-speed", "6"]
                key += ".webm"
            elif fmt == "webm_hq":  # R4 encode-isolation rung: near-lossless VP9
                out, args = "/tmp/out_hq.webm", [
                    "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                    "-b:v", "0", "-crf", "10", "-row-mt", "1", "-speed", "4"]
                key += "_hq.webm"
            elif fmt == "prores":
                out, args = "/tmp/out.mov", [
                    "-c:v", "prores_ks", "-profile:v", "4444",
                    "-pix_fmt", "yuva444p10le"]
                key += ".mov"
            elif fmt == "png":
                out, args = "/tmp/png/%06d.png", []
                subprocess.run(["rm", "-rf", "/tmp/png"], check=False)
                os.makedirs("/tmp/png", exist_ok=True)
                key += ".tar"
            else:
                continue
            enc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo",
                 "-pix_fmt", "rgba", "-s", "%dx%d" % (W, H),
                 "-r", str(fps), "-i", "pipe:0"] + args + [out],
                stdin=subprocess.PIPE)
            for fr in rgba_frames:
                enc.stdin.write(fr.tobytes())
            enc.stdin.close()
            enc.wait()
            if fmt == "png":
                subprocess.run(["tar", "-cf", "/tmp/out.tar", "-C", "/tmp", "png"],
                               check=True)
                out = "/tmp/out.tar"
            size_mb = round(os.path.getsize(out) / 1048576.0, 2)
            s3.upload_file(out, bucket, key)
            url = s3.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": key},
                ExpiresIn=604800)
            enc_out[fmt] = {"encode_s": round(time.time() - t0, 2),
                            "size_mb": size_mb, "url": url}

        results.append({
            "window": [w_start, w_end], "frames": len(rgba_frames),
            "post_s": round(post_s, 2),
            "decode_s": round(decode_s, 2), "infer_s": round(infer_s, 2),
            "infer_fps": round(len(rgba_frames) / infer_s, 1) if infer_s else None,
            "encodes": enc_out,
        })
        del rgba_frames

    return {
        "gpu": gpu_label, "model": model_name, "quality": quality,
        "ratio": ratio, "resolution": [W, H], "fps": fps,
        "download_s": round(dl_s, 2), "model_load_s": round(load_s, 2),
        "total_s": round(time.time() - t_all, 2), "windows": results,
    }


@app.function(gpu="T4", memory=16384, timeout=1200)
def matte_windows_t4(video_url, windows, quality="fast",
                     model_name="mobilenetv3", formats=("webm",), post=None):
    return _matte_impl(video_url, windows, quality, model_name,
                       list(formats), "T4", post=post)


@app.function(gpu="L4", memory=16384, timeout=1200)
def matte_windows_l4(video_url, windows, quality="fast",
                     model_name="mobilenetv3", formats=("webm",), post=None):
    return _matte_impl(video_url, windows, quality, model_name,
                       list(formats), "L4", post=post)
