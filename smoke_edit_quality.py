#!/usr/bin/env python3
"""SMOKE: the composite cannot truncate, and the mechanical edit-quality measures.

TWO THINGS, and the first is above the second (Zac, 2026-09-09).

1. THE COMPOSITE CANNOT TRUNCATE. The caption composite carried
   `overlay=0:0:shortest=1`, which ends the OUTPUT when the shortest input ends
   — and the caption layer is shorter than the video whenever speech does not
   run to the last frame. Round 43: three of five fixtures truncated,
   screen_recording delivering 9.267s of video against 30.960s of audio. Every
   corpus before that hid it, because it appears precisely when the overlay is
   SHORTER than the base.

   AND DROPPING `shortest` IS NOT THE FIX. overlay's default eof_action is
   REPEAT, which freezes the last caption frame over the rest of the video —
   same cause, a different defect, and a length check passes it happily. Only
   eof_action=pass is correct, so the check asserts the CURE and not merely the
   absence of the symptom.

2. THE MECHANICAL EDIT-QUALITY MEASURES. Zac: nobody has judged an edit as an
   edit. These are the cheap proxy for what "bad edit" means mechanically. They
   are MEASURED AND PRINTED, NOT VERDICTS — every one is a threshold on a
   distribution nobody has measured, and this lane set four thresholds from the
   wrong measurement in a week. The smoke pins their ARITHMETIC, not a bar.
"""
import ast
import pathlib
import sys
import types

_m = types.ModuleType("modal")


class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f


for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True
_m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)

# ── 1. NO COMPOSITE MAY TRUNCATE ────────────────────────────────────────────
# READ THE FILTER STRINGS, not the file text — a comment explaining the defect
# names `shortest=1` and would satisfy a substring search. Fifteenth instance.
# DOCSTRINGS EXCLUDED, and this is the SIXTEENTH instance of the same class.
#
# The comment above says "read the filter strings, not the file text" — and a
# DOCSTRING is a string constant, so it was read as one. alpha_composite_filter's
# docstring documents the defect it cures by quoting it:
#
#     [1:v]fps=30,...[cap];[0:v][cap]overlay=0:0:shortest=1[outv]
#
# so this check failed on the FIXED tree and named prose as the defect. Moving
# from file text to string constants was the right direction and one step short:
# a docstring is prose that happens to be a string, which is exactly the thing
# "a check that reads SOURCE cannot tell code from string content" warns about.
_DOCSTRINGS = set()
for _n in ast.walk(tree):
    if isinstance(_n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                       ast.ClassDef)):
        _b = getattr(_n, "body", None) or []
        if (_b and isinstance(_b[0], ast.Expr)
                and isinstance(_b[0].value, ast.Constant)
                and isinstance(_b[0].value.value, str)):
            _DOCSTRINGS.add(id(_b[0].value))
_STRINGS = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in _DOCSTRINGS]
check("this smoke can see the module's strings", len(_STRINGS) > 500,
      f"only {len(_STRINGS)}")
# AN ACTUAL FILTER GRAPH, not any string containing the word. The first version
# matched a bare 'overlay=' fragment and an ERROR MESSAGE that mentions the
# filter — a check that flags prose is a check someone deletes.
import re as _re                                                  # noqa: E402
_overlays = [t for t in _STRINGS if _re.search(r"overlay=\d+:\d+", t)]
check("there are overlay filters to check", len(_overlays) >= 3,
      f"{len(_overlays)} — the legs below would be vacuous")
_short = [t[:70] for t in _overlays if "shortest=1" in t or "shortest=true" in t]
check("no overlay filter uses shortest", not _short,
      f"{_short} — shortest ends the OUTPUT when the overlay ends, which is "
      f"three of five fixtures truncated in round 43")
# The cure, asserted positively. An overlay that spans the whole base without
# `enable` must say what happens at the overlay's EOF; `enable` gates the draw
# off outside its window, so those are safe with the default.
_ungated = [t for t in _overlays if "enable=" not in t]
check("every ungated overlay declares eof_action=pass",
      all("eof_action=pass" in t for t in _ungated),
      f"{[t[:70] for t in _ungated if 'eof_action=pass' not in t]} — without it "
      f"overlay REPEATS its last frame for the rest of the video, which a "
      f"length check passes happily")

# ── 2a. CUTS THAT LAND INSIDE A WORD ────────────────────────────────────────
W = [{"s": 0.0, "e": 0.40, "w": "ten"}, {"s": 0.40, "e": 0.90, "w": "times"},
     {"s": 1.00, "e": 1.60, "w": "a"}, {"s": 1.60, "e": 2.00, "w": "day"}]
check("a cut on a word boundary is not an intrusion",
      A.cut_word_intrusions([[0.40, 1.60]], W) == [])
check("a cut in the GAP between words is not an intrusion",
      A.cut_word_intrusions([[0.95, 1.60]], W) == [],
      "silence between words is where a cut belongs")
_mid = A.cut_word_intrusions([[0.60, 1.60]], W)
check("a cut inside a word IS an intrusion", len(_mid) == 1, str(_mid))
if _mid:
    check("it names the word it severed", _mid[0]["word"] == "times", str(_mid[0]))
    check("and how far in it landed",
          _mid[0]["intrusion_ms"] == 200,
          f"{_mid[0].get('intrusion_ms')} — 0.60 is 200ms past 0.40 and 300ms "
          f"short of 0.90, so the nearer edge is 200")
# ISOLATES "NEARER EDGE". The case above cannot: 0.60 in [0.40, 0.90] is 200ms
# from the start AND 200ms from the nearer edge, so a mutant measuring from the
# start stayed green. A cut PAST the midpoint separates them — 0.80 is 400ms
# from the start and 100ms from the nearer edge, and 100 is the honest number:
# only a tenth of a second of that word is left dangling.
_late = A.cut_word_intrusions([[0.80, 1.60]], W)
check("a late cut measures to the NEARER edge, not from the word start",
      _late and _late[0]["intrusion_ms"] == 100,
      f"{_late[0]['intrusion_ms'] if _late else None} — measuring from the "
      f"start would say 400 and overstate every late cut")

check("both edges of a span are checked",
      len(A.cut_word_intrusions([[0.60, 1.80]], W)) == 2,
      "a cut OUT mid-word severs a word exactly as a cut IN does")
check("no threshold is applied", not any(
    isinstance(n, ast.Constant) and isinstance(n.value, float) and 0 < n.value < 1
    for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
    and f.name == "cut_word_intrusions" for n in ast.walk(f)),
    "it reports intrusion_ms and the distribution decides — a constant invented "
    "now is the fourth threshold from an unmeasured distribution")

# ── 2b. CARDS ON THE BEAT THEY NAME ─────────────────────────────────────────
_beat = {"t_start": 1.0, "t_end": 3.0, "text": "we hit 10,000 followers"}
_r = A.card_beat_alignment({"anchor_s": 2.0, "hero": "10,000"}, _beat)
check("a card on its beat, naming what the beat says, is aligned",
      _r["on_beat"] is True and _r["grounded"] is True, str(_r))
_r2 = A.card_beat_alignment({"anchor_s": 5.0, "hero": "10,000"}, _beat)
check("a card landing outside its beat is flagged", _r2["on_beat"] is False, str(_r2))
_r3 = A.card_beat_alignment({"anchor_s": 2.0, "hero": "30,000"}, _beat)
check("a card naming a figure the beat never says is flagged",
      _r3["grounded"] is False, str(_r3))
_r4 = A.card_beat_alignment({"anchor_s": 2.0, "hero": "GROWTH"}, _beat)
check("a hero with no digits is NOT APPLICABLE, not ungrounded",
      _r4["grounded"] is None,
      "None must never read as False — 'we could not compare' is a different "
      "fact from 'it does not match'")

# ── 2c. OVERLAYS COLLIDING, BY PAINTED PIXELS ───────────────────────────────
check("disjoint boxes do not overlap",
      A.boxes_overlap((0, 0, 100, 100), (200, 200, 50, 50)) == 0)
check("touching edges do not overlap",
      A.boxes_overlap((0, 0, 100, 100), (100, 0, 50, 50)) == 0)
check("overlap is reported as AREA, not a boolean",
      A.boxes_overlap((0, 0, 100, 100), (50, 50, 100, 100)) == 2500,
      "4 pixels of anti-aliasing and 200,000 pixels are both 'True'")
_pl = [{"family": "card", "t0": 1.0, "t1": 3.0, "box": (0, 600, 1000, 400)},
       {"family": "text", "t0": 2.0, "t1": 4.0, "box": (100, 900, 300, 200)},
       {"family": "text", "t0": 9.0, "t1": 9.5, "box": (100, 900, 300, 200)}]
_col = A.placement_collisions(_pl)
check("placements overlapping in time AND pixels collide", len(_col) == 1, str(_col))
if _col:
    check("the collision names both families",
          _col[0]["families"] == ["card", "text"], str(_col[0]))
    check("and reports the fraction of the SMALLER box",
          0 < _col[0]["overlap_frac_of_smaller"] <= 1.0,
          "a caption swallowed by a card is a collision; a card clipping the "
          "corner of a full-frame wash is not")
check("a placement with no measured box is skipped, not guessed",
      A.placement_collisions([{"family": "a", "t0": 0, "t1": 9, "box": None},
                              {"family": "b", "t0": 0, "t1": 9, "box": (0, 0, 9, 9)}]) == [],
      "an unmeasured box must not be treated as a rectangle at the origin")

# ── 3. AND SOMETHING ACTUALLY CALLS THEM ────────────────────────────────────
# THE DEFECT THIS EXISTS FOR. All three measures were written, smoke-tested
# directly, and CALLED NOWHERE. The smoke passed because it invoked them itself;
# a round would have produced no distribution at all, and I would have found out
# when round 44 collected and there was nothing to report. Tenth instance of
# this repo's "shipped gate-green and did nothing" — and the first I caught
# before the round rather than after.
#
# A pure function plus a smoke that calls it is not wiring. Ask the MODULE who
# calls it, not the test.
_defs = {n.name: n.lineno for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
_calls = {}
for _n in ast.walk(tree):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name):
        _calls.setdefault(_n.func.id, []).append(_n.lineno)
for _fn in ("cut_word_intrusions", "card_beat_alignment", "placement_collisions"):
    _sites = [l for l in _calls.get(_fn, []) if abs(l - _defs.get(_fn, -999)) > 3]
    check(f"{_fn} is CALLED by the pipeline, not only by this smoke",
          bool(_sites),
          "defined and invoked nowhere — a round produces no distribution and "
          "the smoke still passes, because the smoke calls it itself")

# AND ITS RESULT REACHES THE LEDGER AND THE OUTPUT. Ledgering is not observing:
# a counter that reaches the ledger and no output answered nothing in round 29.
for _key, _label in (("cut_word_intrusions", "CUT INTRUSIONS"),
                     ("card_beat_alignment", "CARD ALIGNMENT"),
                     ("placement_collisions", "COLLISIONS")):
    check(f"{_key} reaches the ledger", f'led["{_key}"]' in src
          or f'led.setdefault("{_key}"' in src)
    # INSIDE A print() CALL, not merely present in the file. The first version
    # asked whether the label string existed, and a mutant that changed
    # `print(f"  CUT INTRUSIONS ...")` to `_unprinted = (f"  CUT INTRUSIONS ...")`
    # kept the string and stayed green. Seventeenth instance of the class: the
    # label is evidence of intent, the print CALL is evidence of output.
    _printed = False
    for _n in ast.walk(tree):
        if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "print"):
            continue
        for _sub in ast.walk(_n):
            if isinstance(_sub, ast.Constant) and isinstance(_sub.value, str) \
                    and _label in _sub.value:
                _printed = True
    check(f"{_label} is PRINTED", _printed,
          "the label exists somewhere but no print() call carries it — a "
          "measure nobody prints is a measure nobody reads")

if fails:
    print(f"EDIT-QUALITY: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("EDIT-QUALITY: PASS — composite cannot truncate; cuts/cards/collisions "
      "measured, no thresholds")
