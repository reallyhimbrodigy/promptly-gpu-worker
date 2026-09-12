#!/usr/bin/env python3
"""What the references DO with a placement — derived, with denominators.

Zac, 2026-09-12: "stop taking my three items as prompt rules. Extract them from
the corpus instead... If the answer is 'zero of ten place a graphic over a face'
and 'case varies by role,' those become derived facts with a denominator,
exactly like the arc rules."

THE STANDING RULE THIS COMES FROM: when the output is wrong in a way the
references are right about, the first question is WHAT THE ANNOTATOR WAS NEVER
ASKED — not what rule to add. Three defects were about to become three prompt
rules on somebody's say-so:

    an opaque numeral centred on the speaker's face   -> over_subject
    every overlay full-size and ALL CAPS              -> size, case

None of the three was answerable from the corpus, because the corpus had never
been asked. `transition: 0 of 153` all over again: a question never put, read as
an answer.

COUNTED ACROSS VIDEOS, NOT OCCURRENCES, for the same reason family discovery is
— one editor stamping forty ALL-CAPS overlays is a habit; six of ten doing it is
a convention. Occurrence counts appear beside, never as the headline.

AND A DENOMINATOR PER FIELD, because the fields are nullable by design: `case`
is null on anything that is not text, `colour` on a sound. A constraint derived
over "all placements" when only half answered is a rate over a population that
does not exist.
"""
import collections
import json
import os
import sys

PF = ("where", "over_subject", "size", "case", "colour", "hold_s")


def load(d, arm):
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn.startswith(
                ("manifest", "clusters", "vocabulary", "rates")):
            continue
        try:
            r = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            continue
        if r.get("state") != "MEASURED":
            continue
        vid = (r.get("video") or r.get("label") or fn).replace(".mp4.json", "")
        for b in (r.get("record") or {}).get("beats") or []:
            for t in (b.get("treatment") or []):
                if isinstance(t, dict) and t.get("name"):
                    out.append({"arm": arm, "video": vid, "beat": b.get("beat_index"),
                                "purpose": b.get("purpose"), **t})
    return out


def report(rows, field, label):
    """Videos first, occurrences second, and the denominator stated."""
    answered = [r for r in rows if r.get(field) not in (None, "", "null")]
    if not answered:
        print(f"\n  {label}: NO PLACEMENT ANSWERED — nothing derived, and that "
              f"is a fact about the annotator, not the editors")
        return {}
    vids = {r["video"] for r in rows}
    byval = collections.defaultdict(lambda: {"vids": set(), "n": 0})
    for r in answered:
        v = str(r[field]).strip().lower()
        byval[v]["vids"].add(r["video"])
        byval[v]["n"] += 1
    print(f"\n  {label}   ({len(answered)} of {len(rows)} placements answered, "
          f"{len(vids)} videos)")
    for v, d in sorted(byval.items(), key=lambda x: (-len(x[1]["vids"]), -x[1]["n"])):
        print(f"    {len(d['vids']):>2}/{len(vids)} videos  {d['n']:>3} placements   {v}")
    return byval


def main():
    rows = (load(sys.argv[1] if len(sys.argv) > 1 else "/tmp/refcorpus_pf", "frames")
            + load(sys.argv[2] if len(sys.argv) > 2 else "/tmp/refcorpus_pf_listen",
                   "heard"))
    if not rows:
        print("  no MEASURED records — nothing to derive")
        return 2
    vids = {r["video"] for r in rows}
    print(f"  {len(rows)} placements over {len(vids)} video(s), "
          f"{len({r['arm'] for r in rows})} reading(s)")

    over = report(rows, "over_subject", "OVER THE SUBJECT")
    report(rows, "size", "SIZE, share of frame height")
    case = report(rows, "case", "CASE")
    report(rows, "where", "WHERE IN THE FRAME")
    report(rows, "colour", "COLOUR")

    # hold is numeric — quantiles, not categories
    holds = sorted(float(r["hold_s"]) for r in rows
                   if isinstance(r.get("hold_s"), (int, float)))
    if holds:
        q = lambda p: holds[min(len(holds) - 1, int(len(holds) * p))]
        print(f"\n  HOLD ON SCREEN   ({len(holds)} of {len(rows)} answered)")
        print(f"    min {holds[0]:.2f}s  p25 {q(.25):.2f}s  median {q(.5):.2f}s  "
              f"p75 {q(.75):.2f}s  max {holds[-1]:.2f}s")

    # CASE BY PURPOSE — the specific question Zac raised ("case varies by role")
    if case:
        print("\n  CASE BY BEAT PURPOSE")
        bypur = collections.defaultdict(collections.Counter)
        for r in rows:
            if r.get("case") not in (None, "", "null"):
                bypur[str(r.get("purpose"))][str(r["case"]).lower()] += 1
        for p, c in sorted(bypur.items(), key=lambda x: -sum(x[1].values())):
            print(f"    {p:10} {dict(c)}")

    # THE HEADLINE, stated as a derived fact with its denominator
    if over:
        face = over.get("over_face", {"vids": set(), "n": 0})
        print(f"\n  DERIVED: {len(face['vids'])} of {len(vids)} videos place a "
              f"graphic over the subject's FACE ({face['n']} placements of "
              f"{sum(d['n'] for d in over.values())} answered).")
    json.dump({"placements": len(rows), "videos": sorted(vids)},
              open("placement_constraints.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
