#!/usr/bin/env python3
"""The cutaway composite must build a filter graph ffmpeg can actually run.

ROUND 65, motion: five failures, every cutaway lost, ruled_vs_built cutaway
2 -> 0.

    [cutaway] cutaway composite failed: [AVFilterGraph] Too many inputs
              specified for the "scale" filter.

`geometry_normalise_filter` returns a semicolon-separated, LABELLED GRAPH
carrying {IN}/{OUT}/{i} placeholders. The cutaway path comma-appended it onto a
filter chain and never substituted them:

    [cs0]trim=...,setpts=...,[{IN}]scale=1080:1920:...[{OUT}]

so ffmpeg reads the literal `[{IN}]` as a SECOND INPUT PAD to scale. The sibling
call site in build_cut has always done it correctly — .format() the labels and
append the graph as its own part.

WHY IT HID ON FOUR OF FIVE FIXTURES. The fragment comes back EMPTY when the
source needs no normalising, so `if _cgeo:` never fires. talking_head, car_short,
car_mid and screen_recording are already 1080x1920; only motion (540x960) took
the branch. A bug invisible on 80% of the corpus that takes the family to zero
on the rest — and the family is 47% of Zac's reference beats.

THIS CHECK RUNS FFMPEG. A string comparison would have passed the broken form
too: it is well-formed text, and the only thing that knows it is invalid is the
filter-graph parser. Every prior version of this class in the repo was caught by
a render, never by a reader.

FOUR PROPERTIES:
  1. the graph parses and runs for a source that NEEDS normalising — the case
     that was broken;
  2. it parses for a source that needs none — the case that hid it;
  3. TWO cutaways do not collide on an intermediate label;
  4. the code no longer comma-appends the fragment, asked of the source, so the
     old form cannot come back under a passing run.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0


def graph(geo, plans):
    """THE SHIPPED BUILDER, not a restatement of it.

    The first version of this smoke assembled the graph itself — so mutating
    the real builder could not change its verdict, and three properties were
    passing against a copy. Proven: colliding the {i} label in
    agentic_editor_app.py left this green. The builder is now module-level and
    this calls it, which is the only arrangement where a RED proof means
    anything.
    """
    return A.cutaway_filter_graph(
        [{"src_t0": p[0], "src_t1": p[1], "out_t0": p[2], "out_t1": p[3]}
         for p in plans], geo)


def runs(geo, plans, size):
    fg, last = graph(geo, plans)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30:duration=8",
         "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration=8",
         "-filter_complex", fg, "-map", f"[{last}]", "-frames:v", "30",
         "-f", "null", "-"], capture_output=True, text=True)
    return r.returncode, (r.stderr or "").strip()[:150]


P1 = [(2.0, 4.0, 1.0, 3.0)]
P2 = [(2.0, 4.0, 1.0, 3.0), (6.0, 7.5, 5.0, 6.5)]

# 1. the case that was BROKEN: a source that needs normalising.
geo, mode, _ = A.geometry_normalise_filter(540, 960)
if not geo:
    print("  *** 540x960 needs no normalisation on this build, so property 1 "
          "cannot exercise the branch that failed — this check is ABSENT here")
    fail += 1
else:
    rc, err = runs(geo, P1, "540x960")
    if rc != 0:
        print(f"  *** one cutaway on a source needing normalisation ({mode}) "
              f"does not run: {err}")
        fail += 1
    rc, err = runs(geo, P2, "540x960")
    if rc != 0:
        print(f"  *** TWO cutaways on a scaled source do not run: {err}")
        fail += 1

# 3. LABEL COLLISION, TESTED WHERE LABELS EXIST. The first version ran this on
#    540x960, whose fragment is mode='scale':
#      [{IN}]scale=...,crop=...,setsar=1[{OUT}]
#    — it contains NO {i} at all, so colliding {i} across cutaways changed the
#    file and could not change the result. A mutation aimed at a population the
#    target is not in, which is the fifth way a mutation stops mutating and the
#    one with no generic guard. Only blur_fill uses {i}, for its [_bg{i}] and
#    [_fg{i}] intermediates, so the collision has to be tested on a source that
#    produces it.
_geo_blur, _mblur, _ = A.geometry_normalise_filter(1920, 1080)
if "{i}" not in (_geo_blur or ""):
    print(f"  *** the {_mblur!r} fragment carries no {{i}}, so nothing in this "
          f"corpus exercises per-cutaway label uniqueness — that property is "
          f"ABSENT, not passing")
    fail += 1
else:
    rc, err = runs(_geo_blur, P2, "1920x1080")
    if rc != 0:
        print(f"  *** TWO cutaways on a {_mblur} source do not run — the {{i}} "
              f"placeholder is not unique per cutaway and the intermediate "
              f"labels collide: {err}")
        fail += 1

# 2. the case that HID it: a source needing no normalisation.
geo0, _m0, _ = A.geometry_normalise_filter(1080, 1920)
rc, err = runs(geo0, P2, "1080x1920")
if rc != 0:
    print(f"  *** the no-normalisation path does not run: {err}")
    fail += 1

# 4. THE OLD FORM CANNOT COME BACK. Asked of the source: the fragment must
#    never be comma-appended, and must be .format()ed.
# ASKED OF THE AST, NOT THE TEXT, AND THE FIRST VERSION PROVED WHY. It matched
# the literal `_ch += f",{_cgeo}"` and fired immediately — on the COMMENT in
# agentic_editor_app.py that documents the defect. Writing the bug down
# re-targeted the check that hunts it; the repo has a rule for this
# (`_match_is_prose`) and a string test walks straight into it.
import ast  # noqa: E402
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
tree = ast.parse(src)
# SCOPED TO THE BUILDER, not to a variable name. The first version keyed on
# `_cgeo`, the name the fragment had while the code was inline — hoisting it
# renamed the parameter to `geo` and the leg went looking for something that no
# longer existed. A check pinned to a local's spelling is pinned to nothing.
_fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            and n.name == "cutaway_filter_graph"), None)
if _fn is None:
    print("  *** cutaway_filter_graph is gone — the graph is inline again and "
          "no check can reach it without restating it")
    fail += 1
    formatted = []
else:
    # the geo fragment is the function's SECOND parameter, whatever it is called
    _geo_name = _fn.args.args[1].arg if len(_fn.args.args) > 1 else "geo"
    bad_append = [n.lineno for n in ast.walk(_fn)
                  if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add)
                  and any(getattr(x, "id", "") == _geo_name
                          for x in ast.walk(n.value))]
    if bad_append:
        print(f"  *** the fragment is comma-appended onto the chain again at "
              f"line(s) {bad_append} — that is what produced 'Too many inputs "
              f"specified for the scale filter' and lost every cutaway on motion")
        fail += 1
    formatted = [n for n in ast.walk(_fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", "") == "format"
                 and getattr(getattr(n.func, "value", None), "id", "") == _geo_name]
    if not formatted:
        print(f"  *** {_geo_name}.format(...) is never called — the "
              f"{{IN}}/{{OUT}}/{{i}} placeholders reach ffmpeg literally and "
              f"[{{IN}}] parses as an input pad")
        fail += 1

print(f"smoke_cutaway_graph_parses: mode={mode!r}, "
      f"{len(formatted)} format() site(s), {fail} wrong")
sys.exit(1 if fail else 0)
