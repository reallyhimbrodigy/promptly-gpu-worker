#!/usr/bin/env python3
"""CERT — render's three sub-timers must reach the one clock.

WHY THIS EXISTS. `render` was a single opaque number for the whole life of the
pipeline. The three internal timers (remotion / audio / composite) were computed,
printed to stdout, and discarded — so production's own timeline reported

    render   671.1s
      unaccounted   671.1s   <- gap

on 160 of 160 jobs carrying a timeline: render was 100% blind by construction,
and the speed campaign spent a full round attributing a 45.3s "startup" cost
that the instrument could never have confirmed or refuted.

WHAT THIS GUARDS. That the sub-spans are attached AND that attaching them
actually collapses `unaccounted`. Presence alone is not enough — a call with the
wrong parent name is silently DROPPED by the timeline (finalize() walks down
from "job", so an orphan never appears), which would look exactly like success
in the diff and exactly like blindness in production.

RED-PROVEN: check 4 re-runs the identical timeline with the calls removed and
requires it to go back to ~100% unaccounted.

Runs offline. No modal, no network, no spend.
"""
import ast
import os
import re
import sys

HANDLER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")

# name -> parent it MUST be attached to. A child whose parent span does not
# exist is dropped without error, so the parent is part of the contract.
REQUIRED = {
    "render_remotion":  "render",
    "render_audio":     "render",
    "render_composite": "render",
    "render_audio_mux": "render_composite",
}

fails = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        fails.append(label)
    return ok


src = open(HANDLER, encoding="utf-8").read()

print("CERT render sub-timers")
print()

# ── 1. handler.py still parses ────────────────────────────────────────────
try:
    tree = ast.parse(src)
    check("handler.py parses", True)
except SyntaxError as e:
    check("handler.py parses", False, str(e))
    print("\nRESULT: FAIL")
    sys.exit(1)

# ── 2. the helper exists and no-ops without a timeline ────────────────────
helper = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "_tl_add_done"]
check("_tl_add_done is defined", len(helper) == 1)
if helper:
    body = ast.unparse(helper[0])
    check("_tl_add_done no-ops when _TL is None",
          "_TL is None" in body and "return" in body,
          "a probe/unit-test call must not raise")

# ── 3. every required span is attached, to the RIGHT parent ───────────────
found = {}
for node in ast.walk(tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "_tl_add_done" and node.args):
        try:
            nm = ast.literal_eval(node.args[0])
        except (ValueError, SyntaxError):
            continue
        parent = None
        if len(node.args) >= 3:
            try:
                parent = ast.literal_eval(node.args[2])
            except (ValueError, SyntaxError):
                parent = None
        for kw in node.keywords:
            if kw.arg == "parent":
                try:
                    parent = ast.literal_eval(kw.value)
                except (ValueError, SyntaxError):
                    pass
        found[nm] = parent

for nm, parent in REQUIRED.items():
    got = found.get(nm, "<MISSING>")
    check(f"span {nm!r} attached to parent {parent!r}", got == parent,
          f"found parent={got!r}")

# the parent span every render child hangs off must itself be created
check("the 'render' parent span is created",
      bool(re.search(r'_tl_start\(\s*["\']render["\']', src)))

# ── 4. BEHAVIOURAL + RED: attaching must collapse `unaccounted` ───────────
# Lift the real _JobTimeline out of handler.py rather than reimplementing it,
# so this tests the shipped coverage maths and not a copy that can drift.
cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_JobTimeline"]
if not check("_JobTimeline class found", len(cls) == 1):
    print("\nRESULT: FAIL")
    sys.exit(1)

ns = {"time": __import__("time")}
exec(compile(ast.Module(body=cls, type_ignores=[]), "<jt>", "exec"), ns)
JT = ns["_JobTimeline"]


def render_node(tl):
    for c in tl.finalize()["children"]:
        if c["name"] == "render":
            return c
    return None


def build(attach):
    """A job whose render span covers 100s of real work, timed the way the
    pipeline times it. `attach` toggles the sub-timer calls."""
    tl = JT()
    r = tl.start("render", "job")
    t = tl.now()
    # remotion 70s, audio 10s, composite 20s — sequential, covering the span
    tl._spans[-1]["start"] = t  # anchor
    if attach:
        tl.add("render_remotion", t, t + 70.0, "render")
        tl.add("render_audio", t + 70.0, t + 80.0, "render")
        tl.add("render_composite", t + 80.0, t + 100.0, "render")
        tl.add("render_audio_mux", t + 95.0, t + 100.0, "render_composite")
    r["end"] = t + 100.0
    return render_node(tl)

after = build(True)
before = build(False)

check("WITHOUT the sub-timers, render is ~100% unaccounted",
      before["unaccounted"] >= before["dur"] * 0.95,
      f"unaccounted={before['unaccounted']}s of {before['dur']}s  [RED proof]")

check("WITH the sub-timers, unaccounted collapses to ~0",
      after["unaccounted"] <= max(1.0, after["dur"] * 0.02),
      f"unaccounted={after['unaccounted']}s of {after['dur']}s")

check("the three children are visible on the render node",
      {c["name"] for c in after["children"]} ==
      {"render_remotion", "render_audio", "render_composite"},
      str(sorted(c["name"] for c in after["children"])))

check("audio_mux nests UNDER composite, not under render",
      any(c["name"] == "render_composite"
          and [k["name"] for k in c["children"]] == ["render_audio_mux"]
          for c in after["children"]))

print()
print(f"RESULT: {'FAIL — ' + ', '.join(fails) if fails else 'PASS'}")
sys.exit(1 if fails else 0)
