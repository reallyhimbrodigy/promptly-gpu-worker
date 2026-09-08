"""SMOKE — a chained builder never writes to the file it is reading.

THE DEFECT. execute_plan threads one file through the families: each step reads
`cur` and writes a new artifact, then `cur` becomes that artifact. Two steps
passed a FIXED output name inside a loop, so the second iteration handed ffmpeg
the same path as input and output:

    zr = build_zoom(a2, z2, 1.12, cur, "zoomed.mp4")   # then cur = "zoomed.mp4"

Round 15 measured it as `zoom 2->1` with
`build_zoom_failed: Output /work/zoomed.mp4 same as Input #0 - exiting`. The
family silently lost every placement after its first, and the run still scored
green because one zoom did build.

sfx carried the identical defect UNFIRED — the corpus rate is 0.82/25s so runs
place one sound. A second sound on a longer video would have lost it the same
way, which is the kind of bug that ships because the fixture is too short.

This asserts the SHAPE rather than the two known sites: any builder called with
`cur` as input inside a loop must write a name derived from a counter.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

# The chained builders: (function, input-arg index, output-arg index)
CHAINED = {"build_zoom": (3, 4), "place_sfx": (3, 4)}

_ep = next((n for n in ast.walk(TREE)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)
ok(_ep is not None, "execute_plan not found")

_checked = 0
if _ep:
    for node in ast.walk(_ep):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") in CHAINED):
            continue
        name = node.func.id
        i_in, i_out = CHAINED[name]
        if len(node.args) <= max(i_in, i_out):
            continue
        a_in, a_out = node.args[i_in], node.args[i_out]
        # input is the threaded `cur`?
        if getattr(a_in, "id", "") != "cur":
            continue
        _checked += 1
        # RESOLVE THROUGH THE VARIABLE. This used to test only the expression AT
        # the call site, so `_sout = "with_sfx.mp4"` one line above and
        # `place_sfx(..., _sout)` at the call passed cleanly: the argument is a
        # Name, not a Constant, and the constant was invisible. RED-proving
        # found it — binding a literal to a variable first defeated the whole
        # check. Scope is not text, and one hop of indirection is still scope.
        _resolved = [a_out]
        if isinstance(a_out, ast.Name) and _ep is not None:
            _bindings = [n2.value for n2 in ast.walk(_ep)
                         if isinstance(n2, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == a_out.id
                                 for t in n2.targets)]
            if _bindings:
                _resolved = _bindings
        for _rv in _resolved:
            # THE OUTPUT MUST NOT BE A CONSTANT. A constant is reused on the
            # next iteration, by which time `cur` IS that constant.
            ok(not isinstance(_rv, ast.Constant),
               f"{name} at line {node.lineno} reads `cur` and writes the "
               f"CONSTANT {getattr(_rv, 'value', '?')!r} — on the next "
               f"iteration `cur` is that same file and ffmpeg exits with "
               f"'Output ... same as Input #0'")
            # and it must vary with something that changes per iteration
            if isinstance(_rv, ast.JoinedStr):
                ok(any(isinstance(v, ast.FormattedValue) for v in _rv.values),
                   f"{name} at line {node.lineno} writes an f-string with no "
                   f"interpolated counter — it is a constant in disguise")

# ZOOM LEFT THIS SHAPE, and that is a fix rather than a gap. It no longer calls
# a chained builder per ruling: every zoom renders in ONE Remotion batch and the
# whole family composites ONCE, outside the loop, so there is no per-iteration
# ffmpeg write to collide. The guard does not disappear with the shape — it
# moves into the composite as an explicit refusal, because "cannot recur by
# construction" is exactly what was believed about the fixed "zoomed.mp4" before
# round 15 measured zoom 2->1.
ok("chain_writes_its_own_input" in SRC,
   "the zoom composite no longer uses a chained builder, and nothing refuses "
   "the case where it would read and write the same file")
ok('if cur == "zoomed.mp4":' in SRC,
   "the zoom composite's input==output guard is missing")

ok(_checked >= 1,
   f"only {_checked} chained builder call(s) inspected — sfx is still one, so "
   f"the walk should reach it; at zero every assertion above is vacuous")

# `cur` must be advanced to the SAME name that was written, not the old constant.
for fam, var in (("sfx", "_sout"),):
    ok(f"cur = {var}" in SRC,
       f"after a successful {fam} build, `cur` is not advanced to {var} — the "
       f"chain would keep reading the pre-{fam} file and silently discard it")
# The batch-rendered family advances to the name its composite wrote.
ok('cur = "zoomed.mp4"' in SRC,
   "after the zoom composite, `cur` is not advanced to zoomed.mp4 — the chain "
   "would keep reading the pre-zoom file and silently discard every zoom")

if FAIL:
    print("FAIL smoke_chain_paths:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print(f"ok smoke_chain_paths — {_checked} chained builders inspected, none "
      f"writes a constant over its own input, cur advances to the written name")
