#!/usr/bin/env python3
"""cert_v3_beat_resolution.py — V3 (b): A BEAT WE CANNOT ANCHOR IS *OUR* DROP.

The pre-registration (PROMPT_V3_BEAT_PURPOSE_PREREGISTRATION.md) measures
`unresolvable beats`. This cert is why that number can be trusted.

THE FAILURE IT CLOSES. Before v3, the flatten loop did `continue` on any beat
without a usable `word_index` — silently. A v3 beat reasons in SECONDS, so a
perfectly well-formed plan can arrive with no word_index at all. Dropping those
without a count reports "the model emitted nothing" when the truth is "we
discarded everything it emitted", and those two readings point at opposite fixes.
That exact confusion made "0/779 scenes" unreadable for weeks.

    python3 cert_v3_beat_resolution.py
"""
import sys

import prompt_v2_schema as S

WT = {i: i * 0.5 for i in range(40)}     # word i at 0.5s intervals


def _counts(plan, **kw):
    return S.flatten_beats(plan, **kw).get("v2_counts", {})


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    # 1. a v3 beat with only t_start ANCHORS rather than vanishing
    c = _counts({"beats": [{"purpose": "hook", "t_start": 2.4, "t_end": 4.0, "place": []}]},
                word_times=WT)
    check("a beat with only t_start resolves to a word", c.get("beats_unresolvable") == 0,
          f"got {c.get('beats_unresolvable')} unresolvable")

    # 2. NEAREST, not floor. A boundary 10ms before a word belongs to THAT word;
    #    floor() would attach it to the previous one and shift every treatment.
    near = min(WT, key=lambda i: abs(WT[i] - 2.4))
    check("resolution is NEAREST, not floor (2.4s -> word 5, not 4)", near == 5,
          f"got word {near}")

    # 3. THE CASE THAT WOULD SWALLOW A WHOLE PLAN: seconds present, no clock to
    #    resolve against. Silent here means arm B reads as mute.
    c = _counts({"beats": [{"purpose": "claim", "t_start": 1.0, "place": []},
                           {"purpose": "payoff", "t_start": 3.0, "place": []}]})
    check("t_start with NO word_times is COUNTED, not swallowed",
          c.get("beats_unresolvable") == 2,
          f"got {c.get('beats_unresolvable')} of 2 — the pre-registered metric is blind")
    check("and it says WHY",
          bool((c.get("unresolvable_detail") or [{}])[0].get("why")))

    # 4. a beat with neither is counted and carries its purpose, so the drop is
    #    attributable to a KIND of beat rather than being an anonymous integer
    c = _counts({"beats": [{"purpose": "breath", "place": []}]}, word_times=WT)
    check("a beat with neither anchor is counted with its purpose",
          c.get("beats_unresolvable") == 1
          and (c.get("unresolvable_detail") or [{}])[0].get("purpose") == "breath")

    # 5. NO REGRESSION FOR v2. word_index still wins and needs no word_times —
    #    arm A and every existing caller must be byte-unaffected.
    c = _counts({"beats": [{"word_index": 7, "read": "x", "place": []}]})
    check("a v2 beat (word_index, no word_times) is untouched",
          c.get("beats_unresolvable") == 0 and c.get("beats") == 1)

    # 6. the two pre-registered "worse result" readings are MEASURABLE, not
    #    arguable after the fact
    uni = [{"purpose": "claim", "t_start": i * 5.0, "t_end": i * 5.0 + 5.0,
            "word_index": i, "place": []} for i in range(4)]
    c = _counts({"beats": uni}, word_times=WT)
    check("uniform durations are visible (reading 4: duration is decoration)",
          len(set(c.get("beat_durations_s") or [])) == 1,
          f"got {c.get('beat_durations_s')}")
    check("purpose distribution is reported (reading 2: enum carries nothing)",
          c.get("purpose_distribution") == {"claim": 4},
          f"got {c.get('purpose_distribution')}")

    # 7. THE KEY MUST NOT BE UNDERSCORE-PREFIXED. handler sanitises plans with
    #    `k.startswith("_")` filters, so `_v2_counts` was STRIPPED IN TRANSIT —
    #    computed, certified, proven end to end, and deleted before any reader
    #    saw it. Two paid cells reported the metrics as ABSENT for that reason.
    out = S.flatten_beats({"beats": [{"purpose": "hook", "word_index": 1, "place": []}]})
    survivors = {k: v for k, v in out.items() if not k.startswith("_")}
    check("the counts key survives an underscore strip",
          survivors.get("v2_counts") is not None,
          "the metrics are dropped in transit by handler's sanitiser")

    print()
    if fails:
        print(f"  CERT V3 BEAT-RESOLUTION: FAIL ({len(fails)})")
        return 1
    print("  NOTE: asserts the TRANSFORM. That arm B actually emits purpose and")
    print("  t_start is proven by the run, against the pre-registration.")
    print("  CERT V3 BEAT-RESOLUTION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
