#!/usr/bin/env python3
"""A duration is MEASURED, ABSENT or FAILED — never a fabricated 0.0.

THE DEFECT THIS CLOSES (traced 2026-09-09). Five sites read the source's
duration as `float(x.get("format", {}).get("duration") or 0)`. That idiom is
LAUNDERING: it converts *absent* into a present, well-typed 0.0 and hands it
downstream, after which no consumer-side check can tell it from a measurement —
the key is there, the type is right, and there is nothing left to test. My own
`source_duration_s` pin in smoke_no_absent_as_zero.py was the print at the END
of that chain; removing its `or 0` would have changed nothing and closed the
item.

`probe()` returns `{}` when ffprobe fails or its JSON will not parse, so the
absent path is reachable, not theoretical. What a zero cost, per route:

    visual      segment_beats_visual(src, 0.0) divides a 0-second video
    transcript  cover_unnarrated_edges(beats, 0.0) covers nothing — the
                car_short regression (10.0s delivered 0.975s) returning
                SILENTLY, with beats still present from the word list
    both        _ceil = (len - 1) / _vdur if _vdur else 0.0 — a fabricated
                cut-rate ceiling of 0.000 against a reference median of 0.253
    the tool    `s[1] > dur + 0.05` is true for EVERY span when dur is 0.0, so
                cut_command refuses the agent's entire cut as out of bounds

THE BAN IS UNIVERSAL AND HAS NO PIN TABLE, deliberately. An exception list is a
population fitted to today's call sites and rots the first time someone adds a
sixth. `.get("duration") or 0` is wrong on the source, wrong on the output, and
wrong in a tool.

AST, NOT GREP. The docstrings above and in agentic_editor_app.py QUOTE the
banned idiom, which is exactly the substring trap this repo has now hit 21
times. A comment is invisible to an AST walk; that is the whole reason for it.

RED-proven by red_proof_source_duration_state.py.
"""
import ast
import pathlib
import sys

SRC = pathlib.Path("agentic_editor_app.py")
src = SRC.read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# ---------------------------------------------------------------- the function
_fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "source_duration_state"), None)
check("source_duration_state exists at module level (a test can drive it)",
      _fn is not None)
if _fn is None:
    print("\nSOURCE-DURATION: FAIL — nothing to check"); sys.exit(1)

_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(t, "id", "") == "SRC_DUR_MEASURED" for t in ast.walk(_n)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
exec(compile(ast.Module([_fn], []), "<c>", "exec"), _ns)
f = _ns["source_duration_state"]

# ------------------------------------------------- 1. all three states REACHED
# Not "does it return a number" — the guard that only checks the value is the
# rule this whole family exists under.
_cases = [
    ("format.duration present", {"format": {"duration": "12.5"}}, "MEASURED", 12.5),
    ("video stream fallback",
     {"streams": [{"codec_type": "video", "duration": "9.0"}]}, "MEASURED", 9.0),
    ("probe returned {}", {}, "ABSENT", None),
    ("duration unparseable", {"format": {"duration": "N/A"}}, "FAILED", None),
    ("duration is zero", {"format": {"duration": "0"}}, "FAILED", None),
    ("meta is not a dict", None, "FAILED", None),
]
for _label, _meta, _want, _wantv in _cases:
    _st, _v, _why = f(_meta)
    check(f"{_label} -> {_want}", _st == _want and _v == _wantv,
          f"got {_st} value={_v!r} ({_why})")
check("every non-MEASURED state returns None, never a number",
      all(f(m)[1] is None for _l, m, w, _v in _cases if w != "MEASURED"),
      "a state that carries a number is a number that will be reported")
_states = {f(m)[0] for _l, m, _w, _v in _cases}
check("the three states are all reachable (non-vacuity)",
      _states == {"MEASURED", "ABSENT", "FAILED"}, f"reached {sorted(_states)}")
# AST, NOT SUBSTRING — AND I TRIPPED MY OWN TRAP WRITING IT. The first version
# was `"r_frame_rate" not in ast.get_source_segment(src, _fn)`, which failed on
# the DOCSTRING explaining why the field is not used. A check against a comment
# quoting the thing it bans is trap 22 in this repo, and it was in the check
# whose own docstring warns about trap 21.
_rfr = [n for n in ast.walk(_fn)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
        and n.args and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "r_frame_rate"]
check("a declared frame rate is NOT read to derive a duration",
      not _rfr, f"lines {[n.lineno for n in _rfr]} — fps_verdict exists because "
                f"that number lies on VFR (motion declares 59.94, runs 35.94); "
                f"deriving the unknown from it rebuilds the defect one layer up")


# ------------------------------------------ 2. the laundering idiom is BANNED
def _is_duration_or_zero(n):
    """`<anything>.get("duration") or 0`, at any depth of wrapping."""
    return (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
            and len(n.values) == 2
            and isinstance(n.values[-1], ast.Constant) and n.values[-1].value == 0
            and isinstance(n.values[0], ast.Call)
            and getattr(n.values[0].func, "attr", "") == "get"
            and n.values[0].args
            and isinstance(n.values[0].args[0], ast.Constant)
            and n.values[0].args[0].value == "duration")


# WALK EVERY NODE, not the top of each expression. Both mutations in the last
# red proof were defeated by a str(...) wrapper, which is the thinnest disguise
# a defect has worn in this repo.
_laundered = [n.lineno for n in ast.walk(tree) if _is_duration_or_zero(n)]
check("no `.get(\"duration\") or 0` anywhere in the file",
      not _laundered, f"lines {_laundered} — absence becomes a present 0.0 "
                      f"and no downstream check can see it again")
check("the scan can see this shape at all (non-vacuity)",
      _is_duration_or_zero(ast.parse('float(m.get("format",{}).get("duration") or 0)'
                                     ).body[0].value.args[0]),
      "the matcher does not recognise the idiom it is built to ban")

# ------------------------------------- 3. the single read RAISES before it is used
_edit = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "edit"), None)
check("edit() found", _edit is not None)
if _edit is not None:
    _assign, _guard, _first_use = None, None, None
    for _n in ast.walk(_edit):
        if isinstance(_n, ast.Assign) and any(
                isinstance(t, ast.Tuple) and any(getattr(e, "id", "") == "_vdur"
                                                 for e in t.elts)
                for t in _n.targets):
            if any(isinstance(c, ast.Call)
                   and getattr(c.func, "id", "") == "source_duration_state"
                   for c in ast.walk(_n.value)):
                _assign = _n.lineno
        if isinstance(_n, ast.If) and any(
                getattr(x, "id", "") == "SRC_DUR_MEASURED" for x in ast.walk(_n.test)):
            if any(isinstance(b, ast.Raise) for b in ast.walk(_n)):
                _guard = _guard or _n.lineno
    for _n in ast.walk(_edit):
        if isinstance(_n, ast.Name) and _n.id == "_vdur" \
                and _assign and _n.lineno > _assign:
            _first_use = min(_first_use or 10**9, _n.lineno)
    check("_vdur comes from source_duration_state, not a float() of a get()",
          _assign is not None)
    check("a raise on non-MEASURED guards it", _guard is not None)
    check("the guard dominates the first use of _vdur",
          bool(_assign and _guard and _first_use and _assign < _guard < _first_use),
          f"assign={_assign} guard={_guard} first_use={_first_use}")

# ---------------------------- 4. NO CALLER SILENTLY CONTINUES ON NON-MEASURED
_callers = {}
for _fnode in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    for _n in ast.walk(_fnode):
        if isinstance(_n, ast.Call) and getattr(_n.func, "id", "") == "source_duration_state":
            _callers.setdefault(_fnode.name, []).append(_n.lineno)
check("source_duration_state has callers (non-vacuity)", bool(_callers),
      "the function is defined and nothing uses it")
_silent = []
for _name, _lines in _callers.items():
    _fnode = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == _name)
    _handled = False
    for _n in ast.walk(_fnode):
        if isinstance(_n, ast.If) and any(
                getattr(x, "id", "") == "SRC_DUR_MEASURED" for x in ast.walk(_n.test)):
            # the branch must LEAVE or SHOUT — raise, return, or fail()
            if any(isinstance(b, (ast.Raise, ast.Return)) for b in ast.walk(_n)) or \
               any(isinstance(b, ast.Call) and getattr(b.func, "id", "") == "fail"
                   for b in ast.walk(_n)):
                _handled = True
        # a conditional expression that reports the state is handling it too
        if isinstance(_n, ast.IfExp) and any(
                getattr(x, "id", "") == "SRC_DUR_MEASURED" for x in ast.walk(_n.test)):
            _handled = True
    if not _handled:
        _silent.append((_name, _lines))
check("every caller raises, returns or fails on non-MEASURED", not _silent,
      f"{_silent} — a caller that continues has re-created the 0.0 by hand")

print()
if fails:
    print("SOURCE-DURATION: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"SOURCE-DURATION: PASS — 3 states driven, {len(_callers)} caller(s) all "
      f"handling non-MEASURED, 0 laundering sites left")
