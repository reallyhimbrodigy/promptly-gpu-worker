#!/usr/bin/env python3
"""RIFE-based video frame-rate normalization.

Runs Practical-RIFE 4.6 frame interpolation on the H100 GPU to produce
truly motion-compensated intermediate frames — much higher quality than
FFmpeg's `minterpolate` filter and ~30× faster on this hardware.

Pipeline:
  1. ffmpeg decodes source frames to raw rgb24 over stdin pipe
  2. RIFE generates intermediate frames between every adjacent pair
     using optical-flow + multi-scale neural network on CUDA
  3. ffmpeg encodes the interpolated stream + muxes audio from the
     original source in a single libx264 ultrafast pass

Usage:
  python rife_normalize.py --input SOURCE.mp4 --output OUT.mp4 --target-fps 60

For 30fps source → 60fps output: 1 intermediate per pair (2× multiplier).
For arbitrary src/target ratios: integer multiplier (rounded), with RIFE's
`inference(t0, t1, timestep)` supporting fractional timesteps.

Requires:
  * CUDA-capable PyTorch (`torch.cuda.is_available()` == True)
  * Practical-RIFE checkout at /opt/rife with v4.6 model in train_log/
  * ffmpeg with libx264 + audio codec available
"""
import argparse
import os
import subprocess
import sys
import time

import numpy as np
import torch


def _probe_video(path):
    """Return (width, height, src_fps, n_frames) or raise."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
            "-of", "default=noprint_wrappers=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    fields = {}
    for line in out.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()
    width = int(fields.get("width", 0))
    height = int(fields.get("height", 0))
    rate_str = fields.get("r_frame_rate", "0/1")
    if "/" in rate_str:
        n, d = rate_str.split("/")
        src_fps = float(n) / float(d) if float(d) > 0 else 0.0
    else:
        src_fps = float(rate_str)
    return width, height, src_fps


def _load_rife_model(rife_dir):
    """Load Practical-RIFE v4.6 model from rife_dir/train_log/."""
    sys.path.insert(0, rife_dir)
    from train_log.RIFE_HDv3 import Model  # type: ignore

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA not available — RIFE requires GPU. "
            "Check container nvidia driver mount and torch CUDA build."
        )

    torch.set_grad_enabled(False)
    device = torch.device("cuda")
    torch.cuda.set_device(device)

    model = Model()
    model.load_model(os.path.join(rife_dir, "train_log"), -1)
    model.eval()
    model.device()
    return model, device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--target-fps", type=float, required=True)
    ap.add_argument("--rife-dir", default="/opt/rife")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(args.input)

    width, height, src_fps = _probe_video(args.input)
    if width <= 0 or height <= 0 or src_fps <= 0:
        raise RuntimeError(
            f"ffprobe returned invalid stream metadata: "
            f"{width}x{height} @ {src_fps}fps"
        )

    target_fps = float(args.target_fps)
    multiplier = target_fps / src_fps
    int_mult = int(round(multiplier))
    if int_mult < 2:
        raise RuntimeError(
            f"RIFE only used for upscaling; target {target_fps} ≤ src {src_fps:.3f}. "
            f"Use plain `ffmpeg fps={target_fps}` instead."
        )

    print(
        f"[rife] {args.input} → {args.output}: "
        f"{width}×{height} {src_fps:.3f}fps → {target_fps:.3f}fps "
        f"({int_mult}× multiplier)",
        flush=True,
    )

    # Load RIFE model
    t0 = time.time()
    model, device = _load_rife_model(args.rife_dir)
    print(f"[rife] model loaded in {time.time() - t0:.1f}s on {device}", flush=True)

    # RIFE 4.x requires input dimensions to be multiples of 32
    pad_w = ((width + 31) // 32) * 32
    pad_h = ((height + 31) // 32) * 32
    pad_right = pad_w - width
    pad_bottom = pad_h - height

    # Decode source via ffmpeg → stdin pipe
    decoder = subprocess.Popen(
        [
            "ffmpeg", "-v", "error", "-i", args.input,
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-",
        ],
        stdout=subprocess.PIPE,
        bufsize=10 * 1024 * 1024,
    )

    # Encode interpolated stream + mux audio in one ffmpeg invocation.
    # Input 0: rawvideo from stdin (interpolated frames at target_fps)
    # Input 1: original source (for audio passthrough)
    encoder = subprocess.Popen(
        [
            "ffmpeg", "-y", "-v", "error", "-threads", "0",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{width}x{height}",
            "-r", f"{target_fps:.6f}",
            "-i", "-",
            "-i", args.input,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-g", str(int(round(target_fps))),
            "-keyint_min", str(int(round(target_fps))),
            "-sc_threshold", "0",
            "-c:a", "copy",
            "-video_track_timescale", "90000",
            args.output,
        ],
        stdin=subprocess.PIPE,
        bufsize=10 * 1024 * 1024,
    )

    frame_bytes = width * height * 3

    def to_tensor(frame_np):
        """rgb24 numpy → padded float tensor on CUDA."""
        t = torch.from_numpy(frame_np).to(device, non_blocking=True)
        t = t.permute(2, 0, 1).float() / 255.0
        if pad_right > 0 or pad_bottom > 0:
            # Reflection pad for edge artifacts; bottom-right padding.
            t = torch.nn.functional.pad(
                t.unsqueeze(0), (0, pad_right, 0, pad_bottom), mode="replicate"
            ).squeeze(0)
        return t.unsqueeze(0)

    def from_tensor(tensor):
        """padded float tensor → rgb24 numpy (cropped to original size)."""
        t = tensor[0]
        if pad_right > 0 or pad_bottom > 0:
            t = t[:, :height, :width]
        t = (t.clamp(0, 1) * 255.0).byte()
        # CPU + numpy
        return t.permute(1, 2, 0).contiguous().cpu().numpy()

    prev_np = None
    prev_t = None
    n_input = 0
    n_emitted = 0
    proc_t0 = time.time()
    last_log = proc_t0

    while True:
        raw = decoder.stdout.read(frame_bytes)
        if len(raw) < frame_bytes:
            break
        n_input += 1
        curr_np = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
        curr_t = to_tensor(curr_np)

        if prev_np is None:
            # First frame: emit as-is
            encoder.stdin.write(curr_np.tobytes())
            n_emitted += 1
        else:
            # Emit (int_mult - 1) intermediate frames between prev and curr
            for k in range(1, int_mult):
                timestep = k / int_mult
                mid_t = model.inference(prev_t, curr_t, timestep)
                mid_np = from_tensor(mid_t)
                encoder.stdin.write(mid_np.tobytes())
                n_emitted += 1
            # Then emit curr
            encoder.stdin.write(curr_np.tobytes())
            n_emitted += 1

        prev_np = curr_np
        prev_t = curr_t

        # Periodic progress log every ~3 seconds wall time
        now = time.time()
        if now - last_log > 3.0:
            elapsed = now - proc_t0
            in_fps = n_input / elapsed if elapsed > 0 else 0
            print(
                f"[rife] processed {n_input} input frames "
                f"({in_fps:.1f} fps), emitted {n_emitted}",
                flush=True,
            )
            last_log = now

    # Flush + finalize
    decoder.wait()
    encoder.stdin.close()
    encoder.wait()

    elapsed = time.time() - proc_t0
    in_fps = n_input / elapsed if elapsed > 0 else 0
    print(
        f"[rife] DONE: {n_input} input → {n_emitted} output frames "
        f"in {elapsed:.1f}s ({in_fps:.1f} input fps)",
        flush=True,
    )

    if encoder.returncode != 0:
        raise RuntimeError(
            f"ffmpeg encoder exited with rc={encoder.returncode}"
        )
    if decoder.returncode != 0:
        raise RuntimeError(
            f"ffmpeg decoder exited with rc={decoder.returncode}"
        )
    if not os.path.exists(args.output) or os.path.getsize(args.output) < 1024:
        raise RuntimeError(
            f"output {args.output} missing or too small after encode"
        )


if __name__ == "__main__":
    main()
