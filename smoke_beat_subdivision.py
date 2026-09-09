#!/usr/bin/env python3
"""Beats subdivide at REAL seams, and a beat with no seam is left whole.

WHY. A beat is a speech gap >= 0.35s or a 6s cap, so cuts — which can only land
on beat boundaries — were capped BELOW Zac's reference median (0.253 cuts/s,
range 0.140-0.689 across ten videos):

    fixture         out_s  beats  max_cuts  ceiling
    talking_head     20.3      4         3    0.148   <-- cannot reach 0.253
    car_short        10.0      3         2    0.199   <-- cannot reach it
    car_mid          13.2      4         3    0.227   <-- cannot reach it

Round 45 came in 5.7x under the reference median. Two causes: the agent
under-used the boundaries it had (0 of 3 on talking_head), AND the surface could
not express the rate. Prompting alone tops out at 0.148 there.

THE PROPERTY THIS PINS IS THE ABSENCE OF A FALLBACK. Cutting every 3 seconds on
a metronome is worse than not cutting, so a beat with no internal seam must come
back WHOLE. A midpoint fallback would satisfy every rate check and produce worse
edits, which is the shape of every false green in this repo.

  python3 smoke_beat_subdivision.py     exit 0
"""
import sys
import agentic_editor_app as app

fails = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(label)


for n in ("subdivide_beats", "beat_split_candidates"):
    if not hasattr(app, n):
        print(f"  [FAIL] {n} does not exist")
        sys.exit(1)
sub, cand = app.subdivide_beats, app.beat_split_candidates

# ── THE CORE PROPERTY: NO SEAM, NO SPLIT ────────────────────────────────────
print("no seam means no split — there is no midpoint fallback:")
long_beat = [{"i": 0, "t_start": 0.0, "t_end": 9.0, "text": "x"}]
check("a 9s beat with NO signals stays ONE beat", len(sub(long_beat)) == 1)
check("a 9s beat with only sub-threshold word gaps stays ONE beat",
      len(sub(long_beat, words=[{"s": i * 0.4, "e": i * 0.4 + 0.35}
                                for i in range(23)])) == 1,
      "0.05s gaps are diction, not seams")
check("a 9s beat whose only shot change is inside the min-length margin stays ONE",
      len(sub(long_beat, shot_changes=[0.4, 8.7])) == 1,
      "a split there would make a sub-minimum segment")
check("candidates are EMPTY for a beat with no signals",
      cand(0.0, 9.0) == [])

# ── IT DOES SPLIT ON REAL SEAMS ─────────────────────────────────────────────
print("\nreal seams do split, strongest first:")
r = sub(long_beat, shot_changes=[4.5])
check("a shot change inside splits the beat", len(r) == 2)
check("the boundary lands ON the shot change",
      len(r) == 2 and abs(r[0]["t_end"] - 4.5) < 1e-6, f"{r[0]['t_end']}")
# A shot change must outrank a word pause when both are available.
r2 = sub([{"i": 0, "t_start": 0.0, "t_end": 5.0, "text": "x"}],
         words=[{"s": 1.8, "e": 2.0}, {"s": 2.6, "e": 2.9}], shot_changes=[3.0])
check("a shot change OUTRANKS a word pause when ONE split is needed",
      len(r2) == 2 and "shot" in (r2[1].get("split_at") or ""),
      f"{len(r2)} segments, boundary from {r2[1].get('split_at') if len(r2) > 1 else '-'}")
r3 = sub([{"i": 0, "t_start": 0.0, "t_end": 7.0, "text": "x"}],
         words=[{"s": 3.0, "e": 3.2}, {"s": 3.9, "e": 4.2}])
check("a real 0.7s pause splits when no shot change exists",
      len(r3) == 2, f"{len(r3)} beat(s)")
_tr = sub([{"i": 0, "t_start": 0.0, "t_end": 8.0, "text": "x"}],
          motion_curve=[0.9, 0.8, 0.2, 0.7, 0.9, 0.8, 0.9, 0.9])
check("motion troughs are usable as seams", len(_tr) > 1, f"{len(_tr)} segments")
check("every trough split lands on a trough",
      all("trough" in (b.get("split_at") or "") for b in _tr[1:]))

# ── LEGAL SHAPE ─────────────────────────────────────────────────────────────
print("\nshape and legality:")
big = sub([{"i": 0, "t_start": 0.0, "t_end": 20.3, "text": "a"}],
          words=[{"s": i * 0.5, "e": i * 0.5 + 0.33} for i in range(41)],
          shot_changes=[3.2, 8.4, 13.1, 17.9])
check("no segment is shorter than min_beat_s",
      all(b["t_end"] - b["t_start"] >= 1.2 - 1e-6 for b in big),
      f"min {min(b['t_end'] - b['t_start'] for b in big):.3f}s")
check("segments are contiguous and cover the original span",
      abs(big[0]["t_start"] - 0.0) < 1e-6 and abs(big[-1]["t_end"] - 20.3) < 1e-6
      and all(abs(a["t_end"] - b["t_start"]) < 1e-6 for a, b in zip(big, big[1:])))
check("the beat contract keys survive",
      all(app._BEAT_CORE_KEYS <= set(b) for b in big))
check("re-indexed contiguously from 0", [b["i"] for b in big] == list(range(len(big))))
check("exactly one hook and one close",
      sum(1 for b in big if b.get("role") == "hook") == 1
      and sum(1 for b in big if b.get("role") == "close") == 1
      and big[0].get("role") == "hook" and big[-1].get("role") == "close")
check("a beat already under target is untouched",
      len(sub([{"i": 0, "t_start": 0.0, "t_end": 2.4, "text": "x"}],
              shot_changes=[1.2])) == 1)

# ── THE CEILING IT BUYS, on talking_head's real shape ───────────────────────
print("\nthe ceiling, on talking_head's real numbers (20.3s, 4 beats):")
th = [{"i": i, "t_start": i * 5.075, "t_end": (i + 1) * 5.075, "text": "b"}
      for i in range(4)]
for label, kw in (("shot changes only", {"shot_changes": [3.2, 8.4, 13.1, 17.9]}),
                  ("word pauses only",
                   {"words": [{"s": i * 0.6, "e": i * 0.6 + 0.4} for i in range(34)]}),
                  ("both", {"shot_changes": [3.2, 8.4, 13.1, 17.9],
                            "words": [{"s": i * 0.6, "e": i * 0.6 + 0.4}
                                      for i in range(34)]})):
    got = sub(list(th), **kw)
    ceil = (len(got) - 1) / 20.3
    print(f"    {label:20} {len(th)} -> {len(got):>2} beats   ceiling {ceil:.3f}/s"
          + ("   REACHES the 0.253 median" if ceil >= 0.253 else "   still under"))
check("with real seams the ceiling clears the reference median",
      (len(sub(list(th), shot_changes=[3.2, 8.4, 13.1, 17.9])) - 1) / 20.3 >= 0.253)

print()
if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("beats subdivide at real seams; a beat with no seam is left whole")
