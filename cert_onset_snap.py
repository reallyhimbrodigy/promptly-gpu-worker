#!/usr/bin/env python3
"""cert_onset_snap.py — A SNAPPED CUT NEVER CROSSES A WORD BOUNDARY.

The lever moves cuts onto audio onsets. The one way it can do harm is by moving
a cut into the middle of a spoken word: that clips a syllable AND produces a time
no word index can express — the second clock this repo has paid for twice.

An onset mid-word is a real drum hit and a catastrophic cut point. Detecting it
correctly and then refusing to use it is the whole design.

    python3 cert_onset_snap.py
"""
import sys

import onset_snap as S

# words at 0.5s intervals, 0.35s spoken then 0.15s gap
WORDS = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.35} for i in range(20)]


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    spans = S._word_spans(WORDS)

    # ── 1. THE CONSTRAINT ───────────────────────────────────────────────────
    # An onset 30ms from the cut but INSIDE a word must be refused.
    r = S.snap_cuts([2.50], [2.53], WORDS)          # 2.53 is inside w5 (2.50-2.85)
    check("an onset INSIDE a word is refused, however close",
          r["cuts"] == [2.50] and r["moved"] == 0 and r["ledger"]["skipped_in_word"] == 1,
          f"cut moved to {r['cuts']}")

    # and the same distance in the GAP is taken
    r = S.snap_cuts([2.90], [2.93], WORDS)          # 2.93 is in the gap (2.85-3.00)
    check("an onset in the GAP at the same distance IS taken",
          r["moved"] == 1 and abs(r["cuts"][0] - 2.93) < 1e-6,
          f"got {r['cuts']}")

    # ── 2. TOLERANCE ────────────────────────────────────────────────────────
    r = S.snap_cuts([2.90], [3.40], WORDS)          # 500ms away
    check("an onset beyond TOL is refused",
          r["moved"] == 0 and r["ledger"]["skipped_beyond_tol"] == 1)
    r = S.snap_cuts([2.90], [2.90 + S.DEFAULT_TOL_S + 0.001], WORDS)
    check("TOL is a real edge, not approximate", r["moved"] == 0)

    # ── 3. SHAPE PRESERVED ──────────────────────────────────────────────────
    # This moves cuts. It must never add, drop or reorder them — a caller that
    # validated cut count keeps that guarantee.
    cuts = [0.90, 2.90, 4.90, 6.90]
    r = S.snap_cuts(cuts, [0.92, 2.93, 9.9], WORDS)
    check("length and order preserved",
          len(r["cuts"]) == len(cuts) and r["cuts"] == sorted(r["cuts"]),
          f"got {r['cuts']}")

    # ── 4. UNMEASURED IS NOT ZERO ───────────────────────────────────────────
    r = S.snap_cuts([2.90], [], WORDS)
    check("no onsets -> every cut untouched", r["cuts"] == [2.90] and r["moved"] == 0)
    check("onsets_from_audio returns None on probe failure, not []",
          S.onsets_from_audio("/nonexistent/x.mp4") is None,
          "a failed probe would read as a silent track")

    # ── 5. LEDGERED WITH ITS DELTA ──────────────────────────────────────────
    # "Snapping fires" must be answerable from production, not a harness. Nine
    # features here shipped and did nothing; a silent improvement is
    # indistinguishable from a no-op.
    r = S.snap_cuts([0.90, 2.90, 4.90], [0.92, 2.93, 4.99], WORDS)
    lg = r["ledger"]
    check("every move carries a signed delta in ms",
          all("delta_ms" in m and "from" in m and "to" in m for m in lg["moves"]),
          str(lg["moves"])[:120])
    check("the ledger reports a RATE, not just a count",
          "moved_frac" in lg and "median_delta_ms" in lg and "n_cuts" in lg)
    check("refusals are counted separately by REASON",
          "skipped_in_word" in lg and "skipped_beyond_tol" in lg,
          "a refused snap must say which rule refused it")

    # ── 6. WORD-EDGE IS LEGAL ───────────────────────────────────────────────
    # A cut exactly on a word boundary is the normal case and must stay allowed.
    check("a time exactly on a word edge is NOT 'inside' the word",
          not S.in_word(2.50, spans) and not S.in_word(2.85, spans))
    check("a time strictly inside IS inside", S.in_word(2.60, spans))

    print()
    if fails:
        print(f"  CERT ONSET-SNAP: FAIL ({len(fails)})")
        return 1
    print("  NOTE: asserts the TRANSFORM. That snapping FIRES on real traffic is")
    print("  proven by the production counter, not by this file.")
    print("  CERT ONSET-SNAP: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
