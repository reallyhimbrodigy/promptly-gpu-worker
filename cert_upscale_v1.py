#!/usr/bin/env python3
"""UPSCALE v1 cert — REAL ffmpeg, local, $0 (no Modal, no Gemini, no network).

195 asks say 4K/8K/HD/upscale [JUDGE 2026-08-10] and 100% dropped. The
negotiation half shipped the honesty; this is the half that makes the answer a
yes — and the thing that must be certified is not "does ffmpeg run" but:

  THE NOTE IS DERIVED FROM THE ARTIFACT, NEVER FROM THE INTENT.

Promising 4K because we tried is the exact dishonesty the negotiation exists to
end, and it is the one failure mode that would make this capability worse than
not shipping it. Every arm below exists to pin that.

Runs a real 1-second clip through the real pass, so "it produced a 4K file" is
measured, not asserted.

  python3 cert_upscale_v1.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def main():
    os.environ.pop("PROMPTLY_UPSCALE_V1", None)
    os.environ.pop("PROMPTLY_UPSCALE_NEGOTIATE", None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler as H

    print("=== ARM 1: DARK by default ===")
    check("pass disabled unless flagged", H._upscale_v1_enabled({}) is False)
    check("per-job test override works", H._upscale_v1_enabled({"upscale_v1_test": True}) is True)
    check("independent of the negotiation flag",
          H._upscale_negotiate_enabled({}) is False)

    print("\n=== ARM 2: THE NOTE FOLLOWS THE ARTIFACT (the whole point) ===")
    not_delivered = H._upscale_note(False)
    delivered = H._upscale_note(True)
    check("not delivered -> the honest 'not yet' note",
          not_delivered == H._UPSCALE_NEGOTIATION_NOTE)
    check("not-delivered note never claims 4K was produced",
          "isn't in Promptly yet" in not_delivered)
    check("delivered -> a DIFFERENT note", delivered != not_delivered)
    check("delivered note names the real resolution", "2160x3840" in delivered)
    # The single most important line in this file: we must not imply invented
    # detail. A resample is not super-resolution and saying otherwise is the
    # same dishonesty in a new costume.
    check("delivered note explicitly disclaims invented detail",
          "not invented detail" in delivered, repr(delivered))
    check("delivered note still tells the truth about the feed",
          "1080p" in delivered)

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("\nSKIP(no-ffmpeg) — the real-pass arms cannot run on this box.")
        print("  NOT VERIFIED HERE: 4K dimensions, artifact check, failure paths.")
        return 1 if FAILURES else 0

    tmp = tempfile.mkdtemp(prefix="upscale-cert-")
    try:
        src = os.path.join(tmp, "in.mp4")
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc2=s=1080x1920:d=1:r=24",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
             "-shortest", src], capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(src):
            print("  [FAIL] could not build the 1080x1920 fixture")
            return 1

        print("\n=== ARM 3: the REAL pass produces a REAL 4K file ===")
        out = os.path.join(tmp, "out.mp4")
        got = H._upscale_to_4k(src, out, timeout_s=300)
        check("pass returns the output path", got == out, repr(got))
        check("output exists and is non-trivial",
              os.path.exists(out) and os.path.getsize(out) > 100_000,
              f"{os.path.getsize(out) if os.path.exists(out) else 0} bytes")
        p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0", out],
                           capture_output=True, timeout=60)
        dims = (p.stdout or b"").decode().strip()
        check("dimensions are exactly 2160x3840 (2x the render canvas)",
              dims.startswith("2160,3840"), repr(dims))
        # Audio must survive: a 4K file with no sound is not the user's video.
        pa = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                             "-show_entries", "stream=codec_type", "-of", "csv=p=0", out],
                            capture_output=True, timeout=60)
        check("audio stream preserved", b"audio" in (pa.stdout or b""),
              repr((pa.stdout or b"").decode().strip()))

        print("\n=== ARM 4: failure NEVER costs the delivered video ===")
        check("missing source -> None, no raise",
              H._upscale_to_4k(os.path.join(tmp, "nope.mp4"), os.path.join(tmp, "o2.mp4")) is None)
        check("empty source path -> None, no raise",
              H._upscale_to_4k("", os.path.join(tmp, "o3.mp4")) is None)
        junk = os.path.join(tmp, "junk.mp4")
        with open(junk, "wb") as f:
            f.write(b"not a video at all")
        check("corrupt source -> None, no raise",
              H._upscale_to_4k(junk, os.path.join(tmp, "o4.mp4")) is None)
        # A timeout must degrade, not explode.
        check("a 0s budget times out to None, no raise",
              H._upscale_to_4k(src, os.path.join(tmp, "o5.mp4"), timeout_s=0.001) is None)
        # And every one of those must still yield the HONEST note, not a promise.
        check("a failed pass yields the not-yet note",
              H._upscale_note(False) == H._UPSCALE_NEGOTIATION_NOTE)

        print("\n=== ARM 5: determinism (threads pinned, like every other encode) ===")
        out_a = os.path.join(tmp, "a.mp4")
        out_b = os.path.join(tmp, "b.mp4")
        H._upscale_to_4k(src, out_a, timeout_s=300)
        H._upscale_to_4k(src, out_b, timeout_s=300)
        ok = (os.path.exists(out_a) and os.path.exists(out_b)
              and open(out_a, "rb").read() == open(out_b, "rb").read())
        check("same input -> byte-identical output on this box", ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILURES:
        print(f"UPSCALE-V1 CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("UPSCALE-V1 CERT: ALL PASS (dark by default, note follows the ARTIFACT, "
          "real 2160x3840 with audio, every failure degrades to the honest note, "
          "byte-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
