#!/usr/bin/env python3
"""Re-derive the density rubric FROM the corpus. Never hand-written.

Every number in REFERENCE_PER_25S came from the six-word reading:

    text       7.28/25s   from "overlay_text, 124 beats"
    cut        4.75       from 81
    card       2.35       from 40
    sfx        0.82       from 14
    zoom       0.35       from "punch_in, 6"
    cutaway    4.22       from 72
    transition 0.00       from "ZERO in the corpus — not a gap, an absence"

Two of those are not what they say.

`text 7.28` rests on 124 of 153 beats carrying overlay_text — and the annotator
prompt that SUPERSEDED the one which produced it names that exact count as the
bug it was written to fix: running captions recorded as a per-beat treatment,
making every beat non-bare and restraint unmeasurable. The shipped index has 0
bare beats of 153.

`transition 0.00` is not an absence. The annotator's treatment field was a
CLOSED ENUM of six with no transition in it, so the word could not be written if
every beat had one. A rate of 0.00 and a question never asked are different
things and the rubric printed them the same.

EVERY FAMILY CARRIES ITS VIDEO COUNT, and that is the headline number, not the
rate. One video whip-cutting forty times is a HABIT; four videos whip-cutting
twice is a FAMILY. Counting occurrences ranks the habit above the family, which
is what these rates did — a per-25s target derived from one editor's tics grades
every other edit against them. A family present in fewer than HABIT_FLOOR of the
videos is labelled HABIT and must not be used as a target.

THE RATES GRADE; THEY NEVER INSTRUCT. Standing rule, unchanged. This writes a
grading instrument, and nothing here may reach the agent as a floor or a target.

    python3 derive_reference_rates.py /tmp/refcorpus_open
"""
import collections
import json
import os
import sys

HABIT_FLOOR = 4          # of 10 videos — below this it is one editor's habit


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "/tmp/refcorpus_open"
    vp = os.path.join(d, "vocabulary.json")
    fam_of = {}
    if os.path.exists(vp):
        v = json.load(open(vp, encoding="utf-8"))
        for f in v.get("families") or []:
            for m in f.get("members") or []:
                fam_of[m] = f["family"]
        for s in v.get("singletons") or []:
            fam_of[s] = s
    else:
        print("  NO vocabulary.json — rates would be computed over RAW names, "
              "which are one-off observations, not families. Run "
              "cluster_reference_vocabulary.py first.")
        return 2

    occ = collections.Counter()
    beats_with = collections.Counter()
    vids = collections.defaultdict(set)
    total_s, n_beats, n_bare, n_videos, skipped = 0.0, 0, 0, 0, []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".mp4.json"):
            continue
        r = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        if r.get("state") != "MEASURED":
            skipped.append((r.get("video", fn), r.get("state")))
            continue
        n_videos += 1
        rec = r.get("record") or {}
        total_s += float((rec.get("provenance") or {}).get("duration_s") or 0.0)
        for b in rec.get("beats") or []:
            n_beats += 1
            names = [t.get("name") for t in (b.get("treatment") or [])
                     if isinstance(t, dict) and t.get("name")]
            if not names:
                n_bare += 1
            fams = {fam_of.get(x, x) for x in names}
            for f in fams:
                beats_with[f] += 1
                vids[f].add(r["video"])
            for x in names:
                occ[fam_of.get(x, x)] += 1
    if skipped:
        print("  NOT MEASURED — excluded, so the denominator is smaller:")
        for v, st in skipped:
            print(f"    {st}: {v}")
        print("  *** PARTIAL. These rates do not describe the corpus.")
        return 2

    print(f"  {n_videos} videos, {total_s:.1f}s, {n_beats} beats, "
          f"{n_bare} BARE ({100.0*n_bare/n_beats:.1f}%)")
    print(f"\n  {'family':38} {'vids':>6} {'beats':>6} {'occ':>5} {'/25s':>7}  kind")
    rows = []
    for f in sorted(occ, key=lambda x: -len(vids[x])):
        nv = len(vids[f])
        rate = occ[f] / total_s * 25.0
        kind = "FAMILY" if nv >= HABIT_FLOOR else "habit"
        rows.append({"family": f, "videos": nv, "beats": beats_with[f],
                     "occurrences": occ[f], "per_25s": round(rate, 2),
                     "kind": kind})
        print(f"  {f[:38]:38} {nv:>3}/{n_videos} {beats_with[f]:>6} "
              f"{occ[f]:>5} {rate:>7.2f}  {kind}")
    doc = {"n_videos": n_videos, "corpus_s": round(total_s, 1),
           "n_beats": n_beats, "n_bare": n_bare,
           "habit_floor_videos": HABIT_FLOOR,
           "derived_from": os.path.abspath(d),
           "families": rows}
    outp = os.path.join(d, "rates.json")
    json.dump(doc, open(outp, "w"), ensure_ascii=False, indent=1)
    nf = sum(1 for r in rows if r["kind"] == "FAMILY")
    print(f"\n  {nf} FAMILY, {len(rows)-nf} habit "
          f"(floor: present in {HABIT_FLOOR}+ of {n_videos} videos)")
    print(f"  written {outp}")
    print("\n  THE RATES GRADE; THEY NEVER INSTRUCT. Nothing here may reach the "
          "agent as a floor or a target.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
