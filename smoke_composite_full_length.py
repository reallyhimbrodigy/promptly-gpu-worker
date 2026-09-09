#!/usr/bin/env python3
"""The composite output is as long as the BASE, whatever the overlay's length.

THE DEFECT, round 43, one flag:

    [0:v][cap]overlay=0:0:shortest=1[outv]

`shortest=1` ends the output when the shortest input ends. The overlay .mov is
only as long as the material it carries, so any job whose overlay was shorter
than its video ended the VIDEO there — while `-map 0:a?` carried the full audio
through. screen_recording shipped 9.267s of video against 30.960s of audio.

THIS RUNS THE SHIPPED FILTERGRAPH THROUGH REAL FFMPEG. A string assertion would
pass on `eof_action=endall`, which is the same truncation by another name, and
would also pass on the default `repeat`, which freezes the last caption frame
for the rest of the video. Only running it separates the three.

  python3 smoke_composite_full_length.py     exit 0 = base length preserved
"""
import os
import shutil
import subprocess
import sys
import tempfile

import agentic_editor_app as app

fails = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(label)


def dur(path, stream):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream,
                        "-show_entries", "stream=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float((r.stdout or "").strip().split("\n")[0])
    except Exception:
        return None


if not shutil.which("ffmpeg"):
    print("  [FAIL] ffmpeg not present — this check cannot be run, which is NOT a pass")
    sys.exit(1)
if not hasattr(app, "alpha_composite_filter"):
    print("  [FAIL] alpha_composite_filter does not exist — the filtergraph is "
          "inline where no test can run it")
    sys.exit(1)

tmp = tempfile.mkdtemp(prefix="composite-")
base = os.path.join(tmp, "base.mp4")
ov = os.path.join(tmp, "ov.mov")
out = os.path.join(tmp, "out.mp4")

# A 10s base WITH AUDIO (the audio is what made the container look correct), and
# a 3s transparent overlay — the real shape: overlay much shorter than base.
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "testsrc=size=320x568:rate=30:duration=10", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=10", "-c:v", "libx264", "-crf", "28",
                "-c:a", "aac", "-shortest", base], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "color=c=red@0.5:size=320x568:rate=30:duration=3,format=yuva420p",
                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                ov], check=True)
check("premise: base is 10s, overlay is 3s",
      abs(dur(base, "v") - 10.0) < 0.2 and abs(dur(ov, "v") - 3.0) < 0.2,
      f"base {dur(base,'v')}, overlay {dur(ov,'v')}")

r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", base, "-i", ov,
                    "-filter_complex", app.alpha_composite_filter(30),
                    "-map", "[outv]", "-map", "0:a?", "-c:v", "libx264",
                    "-crf", "28", "-preset", "veryfast", "-c:a", "copy", out],
                   capture_output=True, text=True)
check("the shipped filtergraph runs", r.returncode == 0, (r.stderr or "")[-120:])
if r.returncode != 0:
    print("\n1 failure(s)")
    sys.exit(1)

v, a = dur(out, "v"), dur(out, "a")
check("output VIDEO is the base's length, not the overlay's",
      v is not None and abs(v - 10.0) < 0.2, f"video {v}s (overlay was 3s)")
check("output AUDIO matches the video", a is not None and abs(a - v) < 0.1,
      f"audio {a}s vs video {v}s")
# The verdict function must agree — the two checks must not disagree about the
# same file, which is how a fixed pipeline keeps failing a stale gate.
st, det = app.stream_length_verdict(v, a, 10.0)
check("stream_length_verdict says OK on the composited file", st == "OK", det[:70])

# AND THE OVERLAY MUST NOT FREEZE — MEASURED AS TWO ARMS, NOT AGAINST A GUESS.
#
# eof_action=repeat holds the last overlay frame for the remaining 7s. My first
# version of this leg compared out@8s to base@8s and demanded >35 dB, which
# FAILED at 30.85 — and the 35 was a number I invented. The base is crf-28
# testsrc re-encoded twice, so 30.85 is double-compression, not a freeze. That is
# the same mistake as the three fitted bars in this lane, made while fixing one
# of them.
#
# The honest form renders BOTH arms on identical content and requires the correct
# one to separate from the defective one. Content cancels because it is the same
# content, so there is no population constant to mis-fit.
def _arm(action, dst):
    filt = (f"[1:v]fps=30,format=yuva444p[cap];"
            f"[0:v][cap]overlay=0:0:eof_action={action}[outv]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", base, "-i", ov,
                    "-filter_complex", filt, "-map", "[outv]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
                    "-c:a", "copy", dst], check=True)
    return dst


def _psnr(a_path, b_path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", a_path, "-i", b_path,
                        "-lavfi", "psnr=stats_file=-", "-f", "null", "-"],
                       capture_output=True, text=True)
    blob = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"psnr_avg:([0-9.]+|inf)", blob)
    if not m:
        return None
    return float("inf") if m.group(1) == "inf" else float(m.group(1))


def frame(path, t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", path,
                    "-frames:v", "1", dst], check=True)
    return dst


import re
out_repeat = _arm("repeat", os.path.join(tmp, "repeat.mp4"))
base_late = frame(base, 8.0, os.path.join(tmp, "blate.png"))
pass_late = frame(out, 8.0, os.path.join(tmp, "plate.png"))
rept_late = frame(out_repeat, 8.0, os.path.join(tmp, "rlate.png"))

p_pass = _psnr(pass_late, base_late)      # shipped arm vs the untouched base
p_rept = _psnr(rept_late, base_late)      # frozen-overlay arm vs the same base
print("\n  two arms at t=8s, both against the untouched base:")
print(f"    eof_action=pass   (shipped) : {p_pass} dB")
print(f"    eof_action=repeat (defect)  : {p_rept} dB")
check("the shipped arm is CLOSER to the untouched base than the frozen arm",
      p_pass is not None and p_rept is not None and p_pass > p_rept + 3.0,
      f"pass {p_pass} vs repeat {p_rept} — separation "
      f"{(p_pass - p_rept) if (p_pass and p_rept) else '?'} dB, need >3.0")

shutil.rmtree(tmp, ignore_errors=True)
print()
if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("the composite preserves the base length and stops overlaying cleanly")
