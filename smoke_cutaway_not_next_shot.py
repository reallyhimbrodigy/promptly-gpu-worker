#!/usr/bin/env python3
"""A cutaway must not show the footage that plays right after the beat.

FOUND BY WATCHING round 54. motion: beat 2 is 4.5-10.5s, cutaway_from_s=10.5,
so output 4.5-8.5 showed source 10.5-14.5 and then the timeline reached 10.5
and showed it again. car_short: beat 1 ends 6.64, cutaway to 6.64. Both were
"ruled 1, planned 1, built 1" and both were a stutter dressed as a cutaway.

Through the REAL cutaway_plan, with the real round-54 beats: the two shipped
plans must now be rejected BY NAME, and a cutaway to footage that is not about
to play (the end of the clip) must still be accepted — a guard that rejects
everything is not a guard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
beats = [{"i": 0, "t_start": 0.0, "t_end": 1.5}, {"i": 1, "t_start": 1.5, "t_end": 4.5},
         {"i": 2, "t_start": 4.5, "t_end": 10.5}, {"i": 3, "t_start": 10.5, "t_end": 12.5},
         {"i": 4, "t_start": 12.5, "t_end": 15.5}, {"i": 5, "t_start": 15.5, "t_end": 19.5},
         {"i": 6, "t_start": 19.5, "t_end": 20.8}, {"i": 7, "t_start": 20.8, "t_end": 24.3},
         {"i": 8, "t_start": 24.3, "t_end": 27.9}]
spans = [[0.0, 27.9]]

def plan(from_s, beat=2):
    rulings = [{"beat": beat, "treatment": ["cutaway"], "cutaway_from_s": from_s}]
    return A.cutaway_plan(rulings, spans, 27.9, beats=beats)

# RED 1: the shipped motion plan — the next shot
p, r = plan(10.5)
if p or not any("plays right after" in x.get("why", "") for x in r):
    print(f"  *** the round-54 motion cutaway (beat 2 -> 10.5s) is still accepted: plans={p} rejects={r}")
    fail += 1
# RED 2: one second into the next beat is still "about to play"
p, r = plan(11.5)
if p:
    print(f"  *** 11.5s (inside the replay window) accepted: {p}")
    fail += 1
# GREEN: footage well ahead is a real cutaway
p, r = plan(22.0)
if not p or r:
    print(f"  *** a legitimate cutaway to 22.0s was refused: rejects={r}")
    fail += 1
# GREEN: footage BEFORE the beat is a real cutaway (a callback)
p, r = plan(0.5, beat=5)
if not p or r:
    print(f"  *** a callback cutaway (beat 5 -> 0.5s) was refused: rejects={r}")
    fail += 1

print(f"smoke_cutaway_not_next_shot: {fail} wrong")
sys.exit(1 if fail else 0)
