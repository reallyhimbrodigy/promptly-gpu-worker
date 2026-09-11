#!/usr/bin/env python3
"""A cutaway across sources names WHICH source, and is refused when it cannot.

WHY THE ADDRESS CHANGES SHAPE. With one source a cutaway is a timestamp:
`cutaway_from_s: 12.4` means 12.4s into the only footage there is. With ten it
is ambiguous — and an ambiguous address resolved by a DEFAULT is the
silent-wrong-moment class: the picture cuts to the right second of the wrong
clip, the video plays, and nothing reports it.

THE RULE. A bare number stays legal and means source 0, so every single-source
ruling keeps working unchanged — but ONLY while there is one source. With
several, a bare number is REFUSED rather than defaulted.

BOUNDS ARE PER SOURCE. Clip 3 being 40s long says nothing about clip 7, and a
timestamp valid in one is routinely past the end of another. The duration
checked is the duration OF THE NAMED SOURCE.

AND AN UNKNOWN DURATION IS NOT A ZERO DURATION — the same rule as
source_duration_state. A bound that could not be read must not become a bound of
0, which would reject every timestamp in that clip while looking like a content
decision.

RED-proven by red_proof_cutaway_across_sources.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "").startswith("CUTAWAY_REF")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name == "cutaway_source_ref":
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("cutaway_source_ref is module-level and pure", "cutaway_source_ref" in _ns)
if "cutaway_source_ref" not in _ns:
    print("\nCUTAWAY-ACROSS-SOURCES: FAIL"); sys.exit(1)
f = _ns["cutaway_source_ref"]
OK = _ns.get("CUTAWAY_REF_OK", "OK")
BAD = _ns.get("CUTAWAY_REF_BAD", "BAD_REF")

ONE, MANY = ["a.mp4"], ["a.mp4", "b.mp4", "c.mp4"]
D1, D3 = {0: 20.0}, {0: 20.0, 1: 8.0, 2: 40.0}

# ── BACKWARD COMPATIBILITY ──────────────────────────────────────────────────
_s, _i, _t, _w = f(12.4, ONE, D1)
check("a bare timestamp still works when there is ONE source",
      (_s, _i, _t) == (OK, 0, 12.4), f"{_s} {_i} {_t} {_w}")

# ── THE AMBIGUITY IS REFUSED, NOT DEFAULTED ─────────────────────────────────
_s2, _i2, _t2, _w2 = f(12.4, MANY, D3)
check("a bare timestamp across MANY sources is REFUSED", _s2 == BAD, _w2)
check("and the refusal says how to fix it", "source" in _w2 and "t" in _w2, _w2)
check("it does NOT quietly resolve to source 0", _i2 is None,
      "defaulting here cuts to the right second of the wrong clip and nothing "
      "reports it")

# ── THE QUALIFIED FORM ──────────────────────────────────────────────────────
check("{source, t} resolves", f({"source": 2, "t": 12.4}, MANY, D3)[:3]
      == (OK, 2, 12.4))
check("a ref missing either half is refused",
      f({"t": 1.0}, MANY, D3)[0] == BAD
      and f({"source": 1}, MANY, D3)[0] == BAD)
check("a non-numeric source or t is refused, not coerced",
      f({"source": "two", "t": 1.0}, MANY, D3)[0] == BAD)
check("a string ref is refused", f("12.4", MANY, D3)[0] == BAD)
check("True is not a timestamp", f(True, ONE, D1)[0] == BAD,
      "bool is a subclass of int and would otherwise read as t=1.0")

# ── BOUNDS ARE PER SOURCE ───────────────────────────────────────────────────
check("12.4s is INSIDE source 2 (40s)", f({"source": 2, "t": 12.4}, MANY, D3)[0] == OK)
check("the SAME 12.4s is OUTSIDE source 1 (8s)",
      f({"source": 1, "t": 12.4}, MANY, D3)[0] == BAD,
      "a timestamp valid in one clip is routinely past the end of another")
check("a source index that does not exist is refused and says how many there are",
      f({"source": 9, "t": 1.0}, MANY, D3)[0] == BAD
      and "3 uploaded" in f({"source": 9, "t": 1.0}, MANY, D3)[3])
check("a negative t is refused", f({"source": 0, "t": -1.0}, MANY, D3)[0] == BAD)
check("t exactly at the end is refused (the last frame is before it)",
      f({"source": 1, "t": 8.0}, MANY, D3)[0] == BAD)

# ── UNKNOWN DURATION IS NOT ZERO DURATION ───────────────────────────────────
_s3, _, _, _w3 = f({"source": 2, "t": 1.0}, MANY, {0: 20.0, 1: 8.0})
check("a source with no measured duration REFUSES rather than bounding at 0",
      _s3 == BAD and "no measured duration" in _w3, _w3)
check("and it is not reported as an out-of-range timestamp",
      "outside source" not in _w3,
      "an unreadable bound and a real overrun are different findings")

# ── list durations too, since callers have both shapes ──────────────────────
check("durations may be a list as well as a dict",
      f({"source": 1, "t": 3.0}, MANY, [20.0, 8.0, 40.0])[:3] == (OK, 1, 3.0))
check("no sources at all is refused", f(1.0, [], {})[0] == BAD)

print()
if fails:
    print("CUTAWAY-ACROSS-SOURCES: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("CUTAWAY-ACROSS-SOURCES: PASS — bare timestamps still work on one source "
      "and are refused on many, bounds are per source, unknown duration refuses "
      "rather than bounding at zero")
