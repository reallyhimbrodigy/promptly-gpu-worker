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
        # REF-1's lower-third phrases animate per keyword, not per line.
        "captions": [{"start_s": round(i * 0.36, 2)} for i in range(145)],
    }
    m1 = measure_rhythm(ref1, 52.6)
    check(f"REF-1 within bar (gap {m1['max_still_gap_s']}s <= {STILL_GAP_BAR_S}s)",
          m1["within_bar"] is True, str(m1))

    # REF-2: only 8 cuts over 43.2s — the rhythm is captions + 6 insert scenes.
    # Caption cadence corrected 2026-08-14: JUDGE measured ~3.5 moving
    # samples/s on the REAL references, and my first fixture used ~1.1
    # captions/s — an approximation of REF-2's PER-WORD centre-frame captions
    # that undercounted them by ~3x. Left uncorrected it would have indicted
    # JUDGE's target instead of my fixture, which is the canon rule pointed the
    # wrong way. REF-2 is 43.2s of near-continuous per-word captioning.
    ref2 = {
        "clips": [{"start_s": round(i * 5.4, 2)} for i in range(8)],
        "generated_scenes": [{"start_s": s} for s in (2, 9, 16, 23, 30, 37)],
        "captions": [{"start_s": round(i * 0.30, 2)} for i in range(140)],
    }
    m2 = measure_rhythm(ref2, 43.2)
    check(f"REF-2 within bar (gap {m2['max_still_gap_s']}s <= {STILL_GAP_BAR_S}s)",
          m2["within_bar"] is True, str(m2))

    check(f"REF-1 meets the PRIMARY density target ({m1['per_second']}/s)",
          m1.get("meets_density") is True, str(m1))
    check(f"REF-2 meets the PRIMARY density target ({m2['per_second']}/s)",
          m2.get("meets_density") is True, str(m2))

    print("\n=== ARM 2: A CUTS-ONLY READING MUST FAIL — that is the calibration ===")
    # Strip everything but cuts from the SAME references. If the dimension still
    # passes them, it is not measuring what the references actually do.
    # Re-aimed 2026-08-14 at JUDGE's PRIMARY. It used to assert cuts-only breaks
    # the GAP bar, which was true only while that bar was 2.0s — REF-1's cuts sit
    # 2.5s apart and would now slip under a 3.5s gap. The density target is what
    # rejects a cuts-only reading decisively and at every duration: 21 cuts over
    # 52.6s is 0.4/s against a 3.5/s bar, an 8x miss that no gap tuning can hide.
    # This is the ordering earning its keep, not a fixture rescue.
    m1c = measure_rhythm({"clips": ref1["clips"]}, 52.6)
    m2c = measure_rhythm({"clips": ref2["clips"]}, 43.2)
    check(f"REF-1 cuts-only FAILS the PRIMARY ({m1c['per_second']}/s vs 3.5)",
          m1c["meets_density"] is False,
          "a cuts-only reading passed — the dimension is over-weighting cuts")
    check(f"REF-2 cuts-only FAILS the PRIMARY ({m2c['per_second']}/s vs 3.5)",
          m2c["meets_density"] is False,
          "a cuts-only reading passed — the dimension is over-weighting cuts")
    check("REF-2 cuts-only ALSO breaks the stillness bar (both targets agree here)",
          m2c["within_bar"] is False, str(m2c))
    check("cuts-only is ~an order of magnitude off the bar, not a near miss",
          m1c["density_ratio"] < 0.2 and m2c["density_ratio"] < 0.2,
          f"{m1c['density_ratio']} / {m2c['density_ratio']}")
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
    # Density raised with the reference fixture: the decoy has to BEAT REF-2 on
    # the primary target for "density cannot buy your way past a hole" to be a
    # real claim. 120 events / 32s = 3.75/s, clear of REF-2's 3.52.
    dense_hole = {"captions": [{"start_s": round(t * 0.13, 2)} for t in range(60)]
                  + [{"start_s": round(24.0 + t * 0.13, 2)} for t in range(60)]}
    mh = measure_rhythm(dense_hole, 32.0)
    check("a plan that MEETS the primary target still FAILS on the hole",
          mh["within_bar"] is False and mh["meets_density"] is True
          and mh["per_second"] > m2["per_second"],
          f"density {mh['per_second']} vs REF-2 {m2['per_second']}, gap {mh['max_still_gap_s']}s")
    check("the failure NAMES where the hole is (unactionable without it)",
          mh["gap_at_s"] is not None and mh["gap_at_s"] > 0)

    print("\n=== ARM 5: unit inference cannot change a verdict ===")
    ms = {"clips": [{"fromMs": int(i * 5400)} for i in range(8)],
          "generated_scenes": [{"fromMs": s * 1000} for s in (2, 9, 16, 23, 30, 37)],
          "captions": [{"fromMs": int(i * 300)} for i in range(140)]}
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
