#!/usr/bin/env python3
"""RE-GRADE THE EVIDENCE CORPUS AT 11 FRAMES, NOT ONE.

WHY: the first grading of this corpus looked at ONE frame per source (the 50%
mark) and produced "1 YES, 2 MARGINAL, 3 NO of 6". Watching 11 keyframes of
127d3c07 overturned its grade outright — the creator inserts a transient
PICTURE-IN-PICTURE close-up of the exact control being discussed, present at the
claim and absent otherwise. That is EvidenceCard, hand-built by a real user, and
a single mid-point frame could not see it because the inset is TRANSIENT BY
CONSTRUCTION: it exists only for the moment the claim is spoken.

That is a general property, not a quirk of one video. Any component whose
trigger is a MOMENT cannot be graded by a sample that is not that moment. So
one-frame grading is retired for this corpus.

LOCAL ONLY. --no-whisper: these are real users' videos and their audio does not
go to a third-party transcription API to answer a question about pixels.

Prints the frame paths for each source; the grading is done by READING them.
This script does not decide anything — it refuses to guess a verdict from
metadata, which is how the previous grade went wrong.

    python3 repass_evidence_corpus.py --skip 127d3c07
"""
import argparse
import json
import os
import subprocess
import sys

WATCH = os.path.expanduser("~/.claude/skills/watch/scripts/watch.py")
MAN = "evidence_corpus_manifest.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="comma-separated id prefixes already re-graded")
    ap.add_argument("--frames", type=int, default=11)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}

    if not os.path.exists(WATCH):
        print(f"  watch skill not found at {WATCH} — install it first")
        return 2
    man = json.load(open(MAN))
    out_root = a.out or os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "evidence_repass")
    os.makedirs(out_root, exist_ok=True)

    for src in man["sources"]:
        sid = src["id"][:8]
        if any(sid.startswith(s) for s in skip):
            print(f"\n  === {sid}  SKIPPED (already re-graded) ===")
            continue
        print(f"\n  === {sid}   cuts={src['shot_changes']}  "
              f"dur={src['duration_s']}s   prior grade: {src.get('visual_trigger')} ===")
        d = os.path.join(out_root, sid)
        r = subprocess.run(
            [sys.executable, WATCH, src["video_url"], "--no-whisper",
             "--detail", "efficient", "--max-frames", str(a.frames),
             "--out-dir", d],
            capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            # A FAILED EXTRACTION IS NOT A GRADE. Say so and move on.
            print(f"    EXTRACTION FAILED (rc={r.returncode}) — NOT gradable, "
                  f"NOT a 'NO'. {(r.stderr or '')[-200:]}")
            continue
        frames = sorted(
            os.path.join(d, "frames", f)
            for f in os.listdir(os.path.join(d, "frames"))
            if f.endswith(".jpg")) if os.path.isdir(os.path.join(d, "frames")) else []
        print(f"    {len(frames)} frame(s):")
        for f in frames:
            print(f"      {f}")
    print(f"\n  READ the frames above to grade. Frames live under {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
