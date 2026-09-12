#!/usr/bin/env python3
"""A beat-line signal that cannot fire is worse than none — it reads as absence.

I SHIPPED ONE. `stall_note`'s silence arm fires at `max_gap_s >= 0.35`, and
`segment_beats` splits on `gap >= 0.35` — so a gap that large INSIDE a beat
cannot exist; it would have become a beat boundary. Measured on round 65: the
largest intra-beat gap across every beat is 0.16s. The arm could never fire
once, and a run where it never fired was indistinguishable from a corpus with no
stalls.

And beats are defined BY word boundaries — t_start is the first word's start,
t_end is the last word's end — so there is no head or tail silence either.
THERE IS NO SILENCE INSIDE A BEAT TO TRIM, by construction. A within-beat trim
can only remove SPEECH: a stumble, a restart, a repeated word.

THE THRESHOLD IS COUPLED TO A CONSTANT IT NEVER NAMED, which is why this needs a
check rather than a fix. `stall_note`'s floor and `segment_beats`' gap_s are the
same number in two places; the arm is dead while they are equal and becomes
reachable the moment they diverge. Nothing said so.

FOUR PROPERTIES:
  1. every arm of stall_note is reachable on SOME input, or is named as coupled
     to the constant that makes it unreachable;
  2. the repeat arm fires on a real restart;
  3. the note is EMPTY on a clean beat — a line that says something on every
     beat trains the reader to skip it on the beat that matters;
  4. the coupling is asserted: if segment_beats' gap_s rises above the silence
     floor, the arm becomes live and this check says so rather than leaving a
     reader to wonder.
"""
import inspect
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0


def note(words, t0, t1):
    b = [{"i": 0, "t_start": t0, "t_end": t1, "text": " ".join(w["w"] for w in words)}]
    return A.stall_note(b[0], A.beat_stalls(words, b))


# 2. THE REPEAT ARM FIRES on a real restart.
w_rep = [{"w": "so", "s": 0.0, "e": 0.2}, {"w": "the", "s": 0.25, "e": 0.4},
         {"w": "the", "s": 0.45, "e": 0.6}, {"w": "thing", "s": 0.65, "e": 0.9}]
n = note(w_rep, 0.0, 0.9)
if "repeat" not in n:
    print(f"  *** a repeated word produced no signal: {n!r}")
    fail += 1

# 3. EMPTY ON A CLEAN BEAT.
w_ok = [{"w": w, "s": i * 0.25, "e": i * 0.25 + 0.2}
        for i, w in enumerate(["this", "one", "is", "clean", "enough"])]
n_ok = note(w_ok, 0.0, 1.45)
if n_ok:
    print(f"  *** a clean beat produced a note: {n_ok!r} — a line that says "
          f"something on every beat is a line nobody reads")
    fail += 1

# 1 & 4. THE COUPLING, ASSERTED. Read both constants and say which way it is.
sig = inspect.signature(A.segment_beats)
gap_s = sig.parameters["gap_s"].default
src_note = inspect.getsource(A.stall_note)
m = re.search(r'max_gap_s",\s*0\)\s*>=\s*([0-9.]+)', src_note)
if not m:
    print("  *** the silence floor could not be read out of stall_note — this "
          "coupling check is ABSENT, not passing")
    fail += 1
else:
    floor = float(m.group(1))
    reachable = gap_s > floor
    if not reachable:
        # dead — it MUST be named as such, or a future reader reads its silence
        # as evidence there are no stalls
        if "dead by construction" not in inspect.getsource(A.stall_note).lower() \
                and "unreachable" not in inspect.getsource(A.stall_note).lower():
            print(f"  *** the silence arm fires at >= {floor} while "
                  f"segment_beats splits at >= {gap_s}, so it can never fire — "
                  f"and nothing in stall_note says so. Its silence would read "
                  f"as 'no stalls in this corpus'")
            fail += 1
    else:
        # live — then it must actually fire on an input segment_beats permits
        big = (gap_s + floor) / 2.0
        w_gap = [{"w": "a", "s": 0.0, "e": 0.2},
                 {"w": "b", "s": 0.2 + big, "e": 0.4 + big}]
        if "silence" not in note(w_gap, 0.0, 0.4 + big):
            print(f"  *** gap_s={gap_s} exceeds the floor {floor}, so the "
                  f"silence arm should be reachable, and it did not fire")
            fail += 1

print(f"smoke_stall_signal_reachable: segment gap_s={gap_s}, silence floor="
      f"{m.group(1) if m else '?'}, silence arm "
      f"{'LIVE' if (m and gap_s > float(m.group(1))) else 'dead-and-named'}, "
      f"{fail} wrong")
sys.exit(1 if fail else 0)
