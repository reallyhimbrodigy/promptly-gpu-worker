"""Integrity-gate battery (CUT_STACK_REFORM Part 1) — drives the REAL
handler functions: _integrity_gate, _build_integrity_masks, _ig_source_echo,
classify_error, and the rescue deny-list.

Fixture classes mirror the field calibration (2026-07-05, 45-file battery):
freeze ≥0.80s trips (dde5945d=0.883s), sub-trip freeze passes (field max
0.75s), black trips, both-stream hole trips (TIMELINE_HOLES class), duration
delta trips (PC2=0.993s), designed windows mask per-check, content-stillness
downgrades via the source echo.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}"
          + (f"   :: {detail}" if (detail and not cond) else ""))


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True,
                   capture_output=True)


def build_fixtures(d):
    """Motion + tone segments, spliced with defect segments per class."""
    _ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", f"{d}/seg_a.mp4")
    _ff("-ss", "2.9", "-i", f"{d}/seg_a.mp4", "-frames:v", "1",
        f"{d}/still.png")
    _ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", f"{d}/seg_b.mp4")

    def seg_still(name, dur, audio):
        _ff("-loop", "1", "-i", f"{d}/still.png", "-f", "lavfi", "-i", audio,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-r", "30", "-t", str(dur),
            "-c:a", "aac", f"{d}/{name}")

    def concat(name, mids):
        with open(f"{d}/cc.txt", "w") as f:
            f.write(f"file '{d}/seg_a.mp4'\n")
            for m in mids:
                f.write(f"file '{d}/{m}'\n")
            f.write(f"file '{d}/seg_b.mp4'\n")
        _ff("-f", "concat", "-safe", "0", "-i", f"{d}/cc.txt",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", f"{d}/{name}")

    _ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=8",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", f"{d}/clean.mp4")
    seg_still("still_12.mp4", 1.2, "sine=frequency=440:duration=1.2")
    concat("freeze_trip.mp4", ["still_12.mp4"])
    seg_still("still_06.mp4", 0.6, "sine=frequency=440:duration=0.6")
    concat("freeze_subtrip.mp4", ["still_06.mp4"])
    _ff("-f", "lavfi", "-i", "color=black:size=320x568:rate=30:duration=0.6",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=0.6",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-c:a", "aac", f"{d}/seg_black.mp4")
    concat("black_trip.mp4", ["seg_black.mp4"])
    seg_still("hole.mp4", 0.8, "anullsrc=r=44100:cl=stereo:duration=0.8")
    concat("hole_trip.mp4", ["hole.mp4"])
    _ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=8",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=7.4",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", f"{d}/delta.mp4")
    # source-echo pair: a STILL source (content stillness), 8s
    seg_still("still_source.mp4", 8.0, "sine=frequency=440:duration=8")


def gate(d, name, masks=None, **kw):
    path = f"{d}/{name}"
    meta = H._probe_full(path)
    v = next((s for s in meta.get("streams", [])
              if s.get("codec_type") == "video"), {})
    a = next((s for s in meta.get("streams", [])
              if s.get("codec_type") == "audio"), {})
    return H._integrity_gate(path, float(v.get("duration") or 0),
                             float(a.get("duration") or 0), 0,
                             int(v.get("nb_frames") or 0), 30.0,
                             masks or {}, **kw)


def main():
    d = tempfile.mkdtemp(prefix="ig_battery_")
    try:
        build_fixtures(d)

        print("=== T1: every trip class fires; clean and sub-trip pass ===")
        v = gate(d, "clean.mp4")
        check("clean file passes", v["clean"], str(v["trips"]))
        v = gate(d, "freeze_trip.mp4")
        check("1.2s freeze trips",
              any(t["check"] == "freeze" for t in v["trips"]), str(v["trips"]))
        v = gate(d, "freeze_subtrip.mp4")
        check("0.6s freeze passes (trip floor 0.80s)", v["clean"],
              str(v["trips"]))
        v = gate(d, "black_trip.mp4")
        check("0.6s black trips",
              any(t["check"] == "black" for t in v["trips"]), str(v["trips"]))
        v = gate(d, "hole_trip.mp4")
        check("frozen+silent 0.8s trips both_stream_hole",
              any(t["check"] == "both_stream_hole" for t in v["trips"]),
              str(v["trips"]))
        v = gate(d, "delta.mp4")
        check("0.6s A/V duration delta trips",
              any(t["check"] == "av_duration_delta" for t in v["trips"]),
              str(v["trips"]))

        print("=== T2: per-check masks excuse designed windows ===")
        v = gate(d, "freeze_trip.mp4", masks={"freeze": [(2.8, 4.5)]})
        check("designed-still window masks the freeze", v["clean"],
              str(v["trips"]))
        v = gate(d, "black_trip.mp4",
                 masks={"black": [(2.8, 3.9)], "hole": [(2.8, 3.9)]})
        check("designed dip masks the black", v["clean"], str(v["trips"]))
        v = gate(d, "black_trip.mp4", masks={"freeze": [(2.8, 3.9)]})
        check("freeze mask does NOT excuse black (per-check bounding)",
              not v["clean"], str(v["trips"]))

        print("=== T3: mask assembly from the post-safeguard plan stash ===")
        plan = {
            "_render_fps": 60.0,
            "_integrity_slot_ranges": [
                {"start": 5.0, "end": 5.6, "type": "CardSwipe"},
                {"start": 9.0, "end": 9.5, "type": "DipToBlack"},
            ],
            "_integrity_fullmg_ranges": [(12.0, 14.0)],
            "_broll_output_ranges": [(20.0, 23.0)],
            "_rendered_generated_scenes": [
                {"fromFrame": 1800, "durationInFrames": 120}],
        }
        m = H._build_integrity_masks(plan)
        check("freeze mask = slots + fullMG + broll + genscenes",
              len(m["freeze"]) == 5, str(m["freeze"]))
        check("black mask = DipToBlack slots only",
              len(m["black"]) == 1 and abs(m["black"][0][0] - 8.75) < 1e-6,
              str(m["black"]))
        check("hole mask = all slots", len(m["hole"]) == 2, str(m["hole"]))
        check("mask pad applied (±0.25s)",
              abs(m["freeze"][0][0] - 4.75) < 1e-6
              and abs(m["freeze"][0][1] - 5.85) < 1e-6, str(m["freeze"][0]))
        check("genscene frames→seconds via fps",
              abs(m["freeze"][4][0] - 29.75) < 1e-6, str(m["freeze"][4]))

        print("=== T4: source-echo content-stillness discriminator ===")
        defects, down = H._ig_source_echo(
            f"{d}/still_source.mp4", [(3.0, 4.2)], lambda t: t)
        check("still source downgrades the freeze (content stillness)",
              not defects and len(down) == 1, f"{defects} {down}")
        defects, down = H._ig_source_echo(
            f"{d}/clean.mp4", [(3.0, 4.2)], lambda t: t)
        check("moving source keeps the freeze (render defect)",
              defects == [(3.0, 4.2)] and not down, f"{defects} {down}")

        print("=== T5: trip routing — envelope + no auto-retry ===")
        env = H.classify_error(RuntimeError(
            "INTEGRITY_TRIP: freeze=[[7.0, 7.88]]"))
        check("classify_error → INTEGRITY_TRIP",
              env.get("error_code") == "INTEGRITY_TRIP", str(env))
        check("honest user copy (refund named)",
              "credit was returned" in str(env.get("user_message")))
        check("retryable=True", env.get("retryable") is True)
        check("INTEGRITY_TRIP in _OUTER_RESCUE_DENY (no auto-retry)",
              "INTEGRITY_TRIP" in H._OUTER_RESCUE_DENY)

        print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
        if FAIL:
            print("FAILURES:", FAIL)
            sys.exit(1)
        print("ALL INTEGRITY GATE CASES PASS")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
