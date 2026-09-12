#!/usr/bin/env python3
"""The 2 fps corpus against the 5 fps re-read, scored on the REGISTERED predictions.

Reads the shipped reference_index.json (the 153-beat, 2 fps, six-name corpus)
and the new records directory, and prints the diff per family plus a verdict on
each of the eight predictions in PREREG_reference_reread.md.

SCHEMA AND RATE MOVED TOGETHER and this says so rather than attributing the
delta to either: the annotator gained a `transition` slot in the same change
that raised the sample rate, because a re-read at any rate against the old
closed enum would have reproduced transition: 0 of 153.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = sys.argv[1] if len(sys.argv) > 1 else "/tmp/refcorpus_5fps"

old = json.load(open(os.path.join(HERE, "reference_index.json")))
old_beats = old["beats"]

new_beats, used, skipped = [], [], []
for fn in sorted(os.listdir(NEW)):
    if not fn.endswith(".mp4.json"):
        continue
    d = json.load(open(os.path.join(NEW, fn)))
    if d.get("state") != "MEASURED" or not (d.get("record") or {}).get("beats"):
        skipped.append((d.get("video", fn), d.get("state")))
        continue
    used.append(d["video"])
    new_beats.extend(d["record"]["beats"])

# ONE VOCABULARY. The old corpus wrote overlay_text, the new annotator writes
# text_placement, and they are the same family — comparing them as two names
# would report a 124 -> 0 collapse that is pure renaming.
ALIAS = {"overlay_text": "text_placement"}


def fams(beats, key):
    c = collections.Counter()
    bare = 0
    for b in beats:
        t = [ALIAS.get(x, x) for x in (b.get(key) or [])]
        if not t:
            bare += 1
        for x in t:
            c[x] += 1
    return c, bare


oc, obare = fams(old_beats, "treat")
nc, nbare = fams(new_beats, "treatment")
on, nn = len(old_beats), len(new_beats)

print(f"  OLD  reference_index.json   {on} beats, 2 fps, six-name enum")
print(f"  NEW  {NEW}   {nn} beats over {len(used)} video(s), 5 fps, "
      f"seven-name enum")
for v, st in skipped:
    print(f"       EXCLUDED {v}: {st}")
print()
print(f"  {'family':16} {'2 fps':>14} {'5 fps':>14}   move")
for f in sorted(set(oc) | set(nc)):
    o, n = oc.get(f, 0), nc.get(f, 0)
    op, np_ = 100.0 * o / on, 100.0 * n / nn if nn else 0.0
    print(f"  {f:16} {o:5d} ({op:5.1f}%) {n:5d} ({np_:5.1f}%)   "
          f"{np_ - op:+6.1f}pp")
print(f"  {'(bare)':16} {obare:5d} ({100.0*obare/on:5.1f}%) "
      f"{nbare:5d} ({100.0*nbare/nn if nn else 0:5.1f}%)   "
      f"{(100.0*nbare/nn if nn else 0) - 100.0*obare/on:+6.1f}pp")

# GROUNDING: a transition that cannot say what it does is not a transition.
tk = [b.get("transition_kind") for b in new_beats
      if "transition" in (b.get("treatment") or [])]
named = [x for x in tk if x]
print()
print(f"  transition grounding: {len(named)} of {len(tk)} carry a "
      f"transition_kind")
if len(named) != len(tk):
    print(f"  *** {len(tk) - len(named)} transition(s) name no kind — those "
          f"are cuts, and the slot is inflating to justify itself")

# THE REGISTERED PREDICTIONS, scored.
tr = nc.get("transition", 0)
txt_o = 100.0 * oc.get("text_placement", 0) / on
txt_n = 100.0 * nc.get("text_placement", 0) / nn if nn else 0.0
cut_o = 100.0 * oc.get("cutaway", 0) / on
cut_n = 100.0 * nc.get("cutaway", 0) / nn if nn else 0.0
preds = [
    ("P1", "transition > 0", tr > 0, f"{tr}"),
    ("P2", "transition in 8-30", 8 <= tr <= 30, f"{tr}"),
    ("P3", "text family falls below 50%", txt_n < 50.0,
     f"{txt_o:.1f}% -> {txt_n:.1f}%"),
    ("P4", "bare beats >= 15", nbare >= 15, f"{obare} -> {nbare}"),
    ("P5", "punch_in rises above 6", nc.get("punch_in", 0) > 6,
     f"{oc.get('punch_in', 0)} -> {nc.get('punch_in', 0)}"),
    ("P6", "cutaway within 10pp", abs(cut_n - cut_o) <= 10.0,
     f"{cut_o:.1f}% -> {cut_n:.1f}% ({cut_n-cut_o:+.1f}pp)"),
    ("P7", "beat count 115-191", 115 <= nn <= 191, f"{on} -> {nn}"),
]
print("\n  REGISTERED PREDICTIONS (P8 is scored on the rebuilt surface)")
for tag, txt, ok, detail in preds:
    print(f"   {tag} {'HELD    ' if ok else 'REFUTED '} {txt:32} {detail}")
held = sum(1 for _, _, ok, _ in preds if ok)
print(f"\n  {held} of {len(preds)} held")
