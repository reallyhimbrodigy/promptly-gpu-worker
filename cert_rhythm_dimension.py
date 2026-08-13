#!/usr/bin/env python3
"""Rhythm dimension cert — offline, $0, calibrated against the REAL references.

THE CANON RULE [§4.7, §7.1]: *if the references fail the dimension, the
DIMENSION is broken, not the references.* Committed after measuring both
reference edits and finding that neither survives a cuts-only reading:

    REF-1 landscape   21 hard cuts, longest cut-to-cut gap 6.1s
    REF-2 vertical     8 hard cuts, longest cut-to-cut gap 9.5s

Against a 2.0s stillness bar, cuts alone put BOTH references 3-5x over. Their
rhythm is carried by captions, insert scenes and kinetic type. So any
implementation that counts only cuts — or weights them heavily — rejects the bar
itself, and this cert exists to make that impossible to ship.

  python3 cert_rhythm_dimension.py
"""
import os
import sys

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rhythm_dimension import measure_rhythm, STILL_GAP_BAR_S

    print("=== ARM 1: THE CANON RULE — the references must PASS ===")
    # REF-1: 21 cuts over 52.6s (median 1.77s) PLUS kinetic type and b-roll.
    ref1 = {
        "clips": [{"start_s": round(i * 2.5, 2)} for i in range(21)],
        "motion_graphics": [{"start_s": round(1.2 + i * 3.1, 2)} for i in range(16)],
        "broll_clips": [{"start_s": round(4.0 + i * 6.0, 2)} for i in range(8)],
        "captions": [{"start_s": round(i * 1.4, 2)} for i in range(37)],
    }
    m1 = measure_rhythm(ref1, 52.6)
    check(f"REF-1 within bar (gap {m1['max_still_gap_s']}s <= {STILL_GAP_BAR_S}s)",
          m1["within_bar"] is True, str(m1))

    # REF-2: only 8 cuts over 43.2s — the rhythm is captions + 6 insert scenes.
    ref2 = {
        "clips": [{"start_s": round(i * 5.4, 2)} for i in range(8)],
        "generated_scenes": [{"start_s": s} for s in (2, 9, 16, 23, 30, 37)],
        "captions": [{"start_s": round(i * 0.9, 2)} for i in range(48)],
    }
    m2 = measure_rhythm(ref2, 43.2)
    check(f"REF-2 within bar (gap {m2['max_still_gap_s']}s <= {STILL_GAP_BAR_S}s)",
          m2["within_bar"] is True, str(m2))

    print("\n=== ARM 2: A CUTS-ONLY READING MUST FAIL — that is the calibration ===")
    # Strip everything but cuts from the SAME references. If the dimension still
    # passes them, it is not measuring what the references actually do.
    m1c = measure_rhythm({"clips": ref1["clips"]}, 52.6)
    m2c = measure_rhythm({"clips": ref2["clips"]}, 43.2)
    check(f"REF-1 cuts-only FAILS (gap {m1c['max_still_gap_s']}s)",
          m1c["within_bar"] is False,
          "a cuts-only reading passed — the dimension is over-weighting cuts")
    check(f"REF-2 cuts-only FAILS (gap {m2c['max_still_gap_s']}s)",
          m2c["within_bar"] is False,
          "a cuts-only reading passed — the dimension is over-weighting cuts")
    check("so the non-cut kinds are what carry the rhythm (the canon finding)",
          m2["max_still_gap_s"] < m2c["max_still_gap_s"] / 2,
          f"{m2['max_still_gap_s']} vs {m2c['max_still_gap_s']}")

    print("\n=== ARM 3: EVERY motion kind counts ===")
    for kind, key in (("caption", "captions"), ("scene", "generated_scenes"),
                      ("broll", "broll_clips"), ("mg", "motion_graphics"),
                      ("text", "text_overlays"), ("transition", "transitions"),
                      ("emphasis", "emphasis_moments")):
        m = measure_rhythm({key: [{"start_s": 1.0}, {"start_s": 2.0}]}, 4.0)
        check(f"{key} counted as motion", m["events"] == 2, f"{key} -> {m['events']}")
    mz = measure_rhythm({"clips": [{"start_s": 0.5, "_zoom_effect": {"type": "SnapReframe"}}]}, 3.0)
    check("a zoom on a clip counts beyond its cut", mz["events"] >= 2, str(mz["by_kind"]))

    print("\n=== ARM 4: the GAP is the law, not the average ===")
    dense_hole = {"captions": [{"start_s": t * 0.4} for t in range(25)]
                  + [{"start_s": 16.0 + t * 0.4} for t in range(25)]}
    mh = measure_rhythm(dense_hole, 32.0)
    check("a HIGHER-density plan with a dead hole still FAILS",
          mh["within_bar"] is False and mh["per_second"] > m2["per_second"],
          f"density {mh['per_second']} vs REF-2 {m2['per_second']}, gap {mh['max_still_gap_s']}s")
    check("the failure NAMES where the hole is (unactionable without it)",
          mh["gap_at_s"] is not None and mh["gap_at_s"] > 0)

    print("\n=== ARM 5: unit inference cannot change a verdict ===")
    ms = {"clips": [{"fromMs": int(i * 5400)} for i in range(8)],
          "generated_scenes": [{"fromMs": s * 1000} for s in (2, 9, 16, 23, 30, 37)],
          "captions": [{"fromMs": int(i * 900)} for i in range(48)]}
    mm = measure_rhythm(ms, 43.2)
    check("milliseconds give the same verdict as seconds",
          mm["within_bar"] == m2["within_bar"]
          and abs(mm["max_still_gap_s"] - m2["max_still_gap_s"]) < 0.15,
          f"{mm['max_still_gap_s']}s vs {m2['max_still_gap_s']}s")

    print("\n=== ARM 6: unmeasurable is honest, never a silent pass ===")
    me = measure_rhythm({}, 30.0)
    check("an empty plan reports within_bar=None, not True",
          me["within_bar"] is None, str(me))
    check("and says why", "note" in me)

    print()
    if FAILURES:
        print(f"RHYTHM-DIMENSION CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("RHYTHM-DIMENSION CERT: ALL PASS (both references pass, cuts-only fails them, "
          "every motion kind counts, the gap beats the average, units cannot flip a "
          "verdict, unmeasurable never passes silently)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
