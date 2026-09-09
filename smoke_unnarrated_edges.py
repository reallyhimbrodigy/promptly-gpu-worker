#!/usr/bin/env python3
"""A stretch of source that is not a beat can never be kept.

THE DEFECT. segment_beats derives beats from WORDS. Round 42's car_short is a
10.0s car clip carrying TWO incidental Russian words at 5.68-6.64s; Deepgram
found them, it took the transcript route, beats covered 0.96s, and the delivered
file was 0.975 SECONDS. The agent kept every beat it was shown — cuts ACTUAL
{'keep': 1, 'cut': 0} — so this was never a cutting decision. 9.04s of footage
was invisible to it. That is a rejection wearing a delivery's clothes, and
zero-reject permits exactly two: under 2.0s and over 300s.

  python3 smoke_unnarrated_edges.py     exit 0 = the edges are offered
"""
import ast
import os
import sys

import agentic_editor_app as app

HERE = os.path.dirname(os.path.abspath(__file__))
fails = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(label)


if not hasattr(app, "cover_unnarrated_edges"):
    print("  [FAIL] cover_unnarrated_edges does not exist")
    sys.exit(1)
f = app.cover_unnarrated_edges

# THE REAL CASE, with the real numbers off round 42's log.
car = [{"i": 0, "t_start": 5.68, "t_end": 6.64, "text": "ой что", "role": "hook"}]
r = f(car, 10.0)
cov = sum(b["t_end"] - b["t_start"] for b in r)
check("car_short: 1 beat becomes 3", len(r) == 3, f"{len(r)}")
check("car_short: coverage is the WHOLE source", abs(cov - 10.0) < 0.01,
      f"{cov:.2f}s of 10.0s")
check("the head beat starts at 0", r[0]["t_start"] == 0.0)
check("the tail beat ends at the duration", r[-1]["t_end"] == 10.0)
check("no gap is left between beats",
      all(abs(a["t_end"] - b["t_start"]) < 0.01 for a, b in zip(r, r[1:])))

# hook/close must MOVE — leaving them on the old first beat puts the hook in the
# middle of the timeline, and 64% of corpus sfx land on one of those two roles.
check("hook moved to the new first beat", r[0].get("role") == "hook")
check("close moved to the new last beat", r[-1].get("role") == "close")
check("exactly one hook and one close",
      sum(1 for b in r if b.get("role") == "hook") == 1
      and sum(1 for b in r if b.get("role") == "close") == 1)
check("beats are re-indexed contiguously from 0",
      [b["i"] for b in r] == list(range(len(r))))

# DEAD AIR IS UNTOUCHED. A talking head whose speech starts 0.3s in must gain
# nothing — covering every gap would break "cut the filler and dead air hard".
th = [{"i": 0, "t_start": 0.3, "t_end": 20.1, "text": "...", "role": "hook"}]
check("a 0.3s head gap adds NOTHING (dead air stays cuttable)",
      len(f(th, 20.36)) == 1)
# An INTERIOR gap is dead air and must not be covered either.
two = [{"i": 0, "t_start": 0.0, "t_end": 4.0, "text": "a"},
       {"i": 1, "t_start": 9.0, "t_end": 12.0, "text": "b"}]
check("a 5s INTERIOR gap is NOT covered (only edges are)", len(f(two, 12.0)) == 2)

# Degenerate inputs must not invent beats.
check("no beats in, no beats out", f([], 10.0) == [])
check("zero duration returns the input unchanged", f(car, 0) == car)

# WIRING: the transcript path must call it, and bind the result.
tree = ast.parse(open(os.path.join(HERE, "agentic_editor_app.py"),
                      encoding="utf-8").read())
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and getattr(n.func, "id", "") == "cover_unnarrated_edges"]
check("the pipeline CALLS cover_unnarrated_edges", len(calls) == 1, f"{len(calls)}")
bound = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
         and any(isinstance(v, ast.Call)
                 and getattr(v.func, "id", "") == "cover_unnarrated_edges"
                 for v in ast.walk(n))]
check("its result is BOUND to the beats it returns, not discarded", len(bound) == 1)

print()
if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("the un-narrated edges are offered to the agent")
