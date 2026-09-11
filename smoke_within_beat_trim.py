#!/usr/bin/env python3
"""A trim shortens the BEAT, not just the span — one window per beat.

ZAC RULED IT: the standard says trim every breath, and the pipeline placed
ZERO cuts on a 20-second talking head because a beat is keep-or-cut whole.
car_short kept 5.7s of a static puddle for the same reason.

BUILDER-2 FOUND THE DEFECT IN MY FIRST DESIGN and it is the laundering shape:
intersecting keep_spans while leaving beats[i] alone gives TWO WINDOWS for one
beat, and every beat-indexed consumer reads the wrong one — a card anchored in
the trimmed-away part reports on_beat=True over footage that is gone, figure_t
resolves to an instant not in the output, split_beat_text claims words the
viewer never hears, and a kept-but-head-trimmed beat records the skip reason
"beat was cut". So the trim is applied TO THE BEAT and the original bounds are
kept as provenance that nothing reads.

FIVE PROPERTIES:
  1. the fields are OFFERED on both ruling surfaces (a builder for a field
     nobody can rule is dead code);
  2. absent fields mean the whole beat — byte-identical to today;
  3. a window outside the beat, or under the 0.6s floor, is REFUSED and named,
     never clamped — a clamp is a no-op on exactly the beat being tightened;
  4. a boundary inside a spoken word is refused, and on a source with NO
     SPEECH that check says ABSENT rather than passing (46.5% of traffic);
  5. the beat itself is rewritten, with t_start_untrimmed kept.
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
sch = json.dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
for f in ("keep_from_s", "keep_to_s"):
    if sch.count(f'"{f}"') != 2:
        print(f"  *** {f} is on {sch.count(chr(34)+f+chr(34))} ruling "
              f"surface(s), needs both")
        fail += 1

if A._trim_window({}, 1.0, 5.0) != (1.0, 5.0):
    print("  *** no trim fields must mean the whole beat, unchanged")
    fail += 1
if A._trim_window({"keep_from_s": 2.0}, 1.0, 5.0) != (2.0, 5.0):
    print("  *** a head trim did not take")
    fail += 1
if A._trim_window({"keep_to_s": 4.0}, 1.0, 5.0) != (1.0, 4.0):
    print("  *** a tail trim did not take")
    fail += 1
for bad, what in (({"keep_from_s": 4.6}, "under the floor"),
                  ({"keep_to_s": 9.0}, "outside the beat"),
                  ({"keep_from_s": 0.1}, "before the beat"),
                  ({"keep_from_s": "x"}, "not a number")):
    got, why = A._trim_window(bad, 1.0, 5.0)
    if got is not None:
        print(f"  *** {what} was ACCEPTED: {bad} -> {got}")
        fail += 1
    elif not why:
        print(f"  *** {what} was refused with no reason")
        fail += 1
# a clamp would have returned a window instead of a refusal
if "clamp" not in (A._trim_window({"keep_from_s": 4.6}, 1.0, 5.0)[1] or ""):
    print("  *** the floor refusal does not say it refuses rather than clamps")
    fail += 1

W = [{"w": "hello", "s": 1.8, "e": 2.4}]
if not A._word_split_by(W, 2.0, 5.0):
    print("  *** a trim inside a spoken word was allowed")
    fail += 1
if A._word_split_by(W, 2.5, 5.0):
    print("  *** a trim between words was refused")
    fail += 1
if A._word_split_by([], 2.0, 5.0) is not None:
    print("  *** with NO word table the check must be ABSENT, not a pass")
    fail += 1

src = open(os.path.join(HERE, "agentic_editor_app.py")).read()
for need, why in (("t_start_untrimmed", "the original bounds are not kept"),
                  ('led.setdefault("trims"', "the trim is not ledgered"),
                  ('b["t_start"], b["t_end"] = _ka, _kz',
                   "the BEAT is not rewritten — two windows for one beat")):
    if need not in src:
        print(f"  *** {why}")
        fail += 1
# and nothing may read the provenance bounds
tree = ast.parse(src)
reads = [n for n in ast.walk(tree)
         if isinstance(n, ast.Constant) and n.value == "t_start_untrimmed"]
if len(reads) > 1:
    print(f"  *** t_start_untrimmed appears {len(reads)}x — provenance must be "
          f"written once and read by nothing")
    fail += 1

print(f"smoke_within_beat_trim: {fail} wrong")
sys.exit(1 if fail else 0)
