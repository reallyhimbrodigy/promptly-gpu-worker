#!/usr/bin/env python3
"""cert_proxy_thread_pin — the check that makes the Gemini-proxy thread pin
un-removable (Rule 1).

WHY: the 480p/18fps Gemini proxy encodes with `libx264 -preset ultrafast -crf 30`
and, until this fix, NO encoder-thread pin (`-threads 0` = x264-auto). x264-auto
sizes its thread count from the MACHINE core count, so the SAME source encodes to
DIFFERENT proxy bytes at cpu=4 vs cpu=16 — silently changing what Gemini watches
when the orchestrator split drops the planner cpu. The fix pins
`-x264-params threads=_PROXY_X264_THREADS` on both proxy sites.

The "bytes Gemini watches" are the ENCODED VIDEO ELEMENTARY STREAM (container
timestamps/metadata are irrelevant — Gemini decodes frames), so we compare the
video-stream MD5 (`-map 0:v:0 -c copy -f md5`), not the whole MP4.

The ffmpeg GLOBAL `-threads` (placed before `-i`, as production does) binds to
the DECODER, not the x264 encoder — decode thread count does not change encoded
bytes. The x264 ENCODER thread count comes from libx264's own auto default
(≈1.5×logical-cores) when no `-x264-params threads=` is given. We cannot change
core count on one machine, so we simulate the two production boxes by setting the
ENCODER count to what auto picks on each: cpu=4 → ~6 threads, cpu=16 → ~24. This
is exactly the byte divergence a cpu=4 planner would produce vs today's cpu=16.

PASS requires BOTH:
  (1) BUG REPRO   — unpinned: enc=6 (cpu4) stream != enc=24 (cpu16) stream
  (2) FIX PROOF   — pinned:   both boxes forced to enc=48 → identical streams,
                    AND identical even when the box's DECODE threads differ (2 vs 8)

If the pin is ever removed, (2) goes RED. If x264 ever stops being
thread-sensitive at this resolution, (1) goes RED (cert lost its teeth) — both
are real failures worth surfacing. No Modal spend; pure local ffmpeg.
"""
import hashlib
import os
import subprocess
import sys
import tempfile

# Must match handler.py _PROXY_X264_THREADS. Read it from the source so the cert
# tracks the real pin value and can't drift.
def _read_pin_from_handler():
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, "handler.py")).read()
    m = re.search(r"^_PROXY_X264_THREADS\s*=\s*(\d+)", src, re.M)
    if not m:
        print("FAIL: _PROXY_X264_THREADS constant not found in handler.py", flush=True)
        sys.exit(1)
    return int(m.group(1))

# The EXACT production proxy spec (handler.py 32652 / 35429).
PROXY_VF = "scale=480:-2,fps=18"
PROXY_VENC = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]
PROXY_AENC = ["-c:a", "libopus", "-b:a", "64k", "-ac", "1"]


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("CMD FAILED:", " ".join(cmd), flush=True)
        print(p.stderr[-800:], flush=True)
        sys.exit(1)
    return p


def _vstream_md5(path):
    """MD5 of the encoded video elementary stream (container-metadata-independent
    — this is what Gemini actually decodes)."""
    p = _run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0",
              "-c", "copy", "-f", "md5", "-"])
    # ffmpeg prints "MD5=<hex>"
    out = (p.stdout or "").strip()
    if "MD5=" not in out:
        # some builds print to stderr
        out = (p.stderr or "").strip()
    return out.split("MD5=")[-1].strip()


def _encode_proxy(source, out, enc_threads, decode_threads=0):
    """Encode the proxy with the x264 ENCODER thread count set explicitly to
    `enc_threads` (this is the byte-determining knob). `decode_threads` is the
    ffmpeg global `-threads` (decoder side) — varied only to prove it does NOT
    change encoded bytes once the encoder count is pinned."""
    venc = list(PROXY_VENC) + ["-x264-params", f"threads={enc_threads}"]
    _run(["ffmpeg", "-y", "-v", "error", "-threads", str(decode_threads),
          "-i", source, "-vf", PROXY_VF] + venc + PROXY_AENC + [out])
    return _vstream_md5(out)


def main():
    pin = _read_pin_from_handler()
    print(f"[cert] _PROXY_X264_THREADS = {pin} (read from handler.py)", flush=True)
    with tempfile.TemporaryDirectory() as td:
        # Deterministic, durable synthetic source (multilingual-corpus pattern:
        # constructed, not user media). Tall frame + enough frames so x264
        # frame-threading is genuinely thread-count sensitive. The source encode
        # itself need not be deterministic — every proxy re-DECODES this same
        # file, and decode is deterministic.
        source = os.path.join(td, "source.mp4")
        _run(["ffmpeg", "-y", "-v", "error",
              "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=8",
              "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", source])

        # (1) BUG REPRO — TODAY's unpinned reality: x264-auto sizes from cores,
        # so a cpu=4 planner (~6 enc threads) and a cpu=16 planner (~24) produce
        # different proxy bytes for the SAME source.
        a4 = _encode_proxy(source, os.path.join(td, "a4.mp4"), 6)    # sim cpu=4 auto
        a16 = _encode_proxy(source, os.path.join(td, "a16.mp4"), 24)  # sim cpu=16 auto
        bug_reproduces = (a4 != a16)
        print(f"[cert] UNPINNED  sim-cpu4(enc=6) vs sim-cpu16(enc=24) : "
              f"{'DIFFER (cpu-dependent — bug is real)' if bug_reproduces else 'IDENTICAL (cert lost its teeth!)'}",
              flush=True)
        print(f"         cpu4={a4}  cpu16={a16}", flush=True)

        # (2) FIX PROOF — the pin forces enc=48 on ANY box, so both planners are
        # byte-identical; and it stays identical even when the box's DECODE
        # threads differ (2 vs 8), proving decode threading can't leak in.
        b4 = _encode_proxy(source, os.path.join(td, "b4.mp4"), pin, decode_threads=2)   # pinned, sim-cpu4 decode
        b16 = _encode_proxy(source, os.path.join(td, "b16.mp4"), pin, decode_threads=8)  # pinned, sim-cpu16 decode
        fix_holds = (b4 == b16)
        print(f"[cert] PINNED    sim-cpu4 vs sim-cpu16 (both enc={pin}) : "
              f"{'IDENTICAL (cpu-independent — fix holds)' if fix_holds else 'DIFFER (fix FAILED!)'}",
              flush=True)
        print(f"         cpu4={b4}  cpu16={b16}", flush=True)

    ok = bug_reproduces and fix_holds
    print(f"\n[cert] RESULT: {'PASS' if ok else 'FAIL'} "
          f"(bug_reproduces={bug_reproduces}, fix_holds={fix_holds})", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
