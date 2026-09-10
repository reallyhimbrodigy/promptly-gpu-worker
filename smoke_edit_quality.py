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

import modal_stub                                         # noqa: E402
modal_stub.install()
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

# ── 2a-ii. THE FLOOR IS UNMEASURED OR REAL, NEVER A DEFAULT ─────────────────
# The first version read float(led.get("source_fps") or 30.0). Nothing ever set
# source_fps, so EVERY fixture silently took 30 — and on a 59.94 source that is
# wrong by 2x in the direction that HIDES intrusions: a floor twice too large
# excuses cuts that really did sever a word. A default that fails toward
# "nothing to see" is the worst direction a default can fail.
check("a missing frame rate is UNMEASURED, not 30",
      A.cut_intrusion_floor_ms(None, None)[0] is None
      and A.cut_intrusion_floor_ms(None, None)[1] == "UNMEASURED")
check("a CFR source gets half a frame",
      A.cut_intrusion_floor_ms("30/1", "30/1")[0] == 16.67,
      str(A.cut_intrusion_floor_ms("30/1", "30/1")))
check("29.97 is not rounded to 30",
      A.cut_intrusion_floor_ms("30000/1001", "30000/1001")[0] == 16.68)
# A VFR SOURCE HAS NO FLOOR AT ALL — the floor is half a frame duration, so it
# exists only if frames have ONE duration. This is what excludes motion from
# pooled numbers, DERIVED from the source rather than hand-listed, so the next
# VFR fixture excludes itself without anyone remembering.
_vfr = A.cut_intrusion_floor_ms("60000/1001", "35.94")
check("a VFR source has NO floor", _vfr[0] is None and _vfr[1] == "UNMEASURED",
      str(_vfr))
check("and says which two rates disagree",
      "59.94" in _vfr[2] and "35.94" in _vfr[2], _vfr[2])
check("the VFR tolerance is an equality check, not a fitted threshold",
      A._CUT_FLOOR_VFR_TOLERANCE == 0.02,
      "a CFR source agrees to rounding; this is slack on 'these should be "
      "equal', not a bar chosen from a distribution")
check("the floor STATE reaches the ledger",
      'led["cut_floor_state"]' in src and 'led["cut_floor_detail"]' in src)

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
# ── 2c-ii. THE SCALE IS VALIDATED; THE THRESHOLD IS NOT AVAILABLE ───────────
# I registered collisions as "the one I can construct ground truth for". The
# construction shows why that was half right, and the correction is recorded
# BEFORE round 45 rather than after.
#
# MEASURED by sliding the REAL text paint (208x88) through the REAL card paint
# (852x416) — both measured component rectangles, only the offset constructed:
#     clear            0.000
#     straddling       0.091  0.182  0.545  0.636
#     fully inside     1.000
# The metric is CONTINUOUS BY CONSTRUCTION. There is no gap between a touch and
# a swallow, so picking two constructed points and calling them separated proves
# nothing — it is the smooth-distribution trap with arms instead of a round.
#
# WHAT CONSTRUCTION DOES ESTABLISH, and it is what these legs pin: the SCALE is
# correct, ordered and interpretable. 0 means clear, 1 means one component is
# entirely inside the other, and the middle is the fraction of the smaller box
# covered. Whether 0.3 is a defect is a QUALITY judgement — Zac's eye — exactly
# as whether a 90ms intrusion is audible is a question about hearing.
_CARD, _TEXT = (120, 652, 852, 416), (436, 920, 208, 88)


def _frac(dy):
    _t = (_TEXT[0], _TEXT[1] + dy, _TEXT[2], _TEXT[3])
    _c = A.placement_collisions([{"family": "card", "t0": 0, "t1": 2, "box": _CARD},
                                 {"family": "text", "t0": 1, "t1": 3, "box": _t}])
    return _c[0]["overlap_frac_of_smaller"] if _c else 0.0


check("a fully-contained overlay reads exactly 1.0", _frac(0) == 1.0,
      f"{_frac(0)} — the text box sits entirely inside the card box")
check("a clear overlay reads exactly 0.0", _frac(-500) == 0.0 and _frac(500) == 0.0)
# The card spans y 652..1068 and the text is 88 tall, so it straddles the top
# edge for dy in (-356, -268) and the bottom edge for dy in (60, 148). Offsets
# picked from the measured sweep rather than guessed — my first attempt used
# dy=340, which puts the text clear of the card entirely and reads 0.0.
check("the scale is MONOTONIC through the straddle",
      _frac(-348) < _frac(-308) < _frac(-268),
      f"{_frac(-348)}, {_frac(-308)}, {_frac(-268)} — a measure that is not "
      f"ordered in the thing it measures cannot be read at any bar")
check("the straddle is CONTINUOUS — no gap to put a bar in",
      0.0 < _frac(-348) < 1.0 and 0.0 < _frac(132) < 1.0,
      "recorded so nobody later reads the constructed arms as a validated "
      "separation; the bar has to come from the real population being bimodal, "
      "which round 45 answers and construction cannot")

# ── 2c-iii. ONE PLACEMENT SEEN TWICE IS NOT A COLLISION ─────────────────────
# Round 45 reported four text+text collisions at exactly 1.00 on four text
# placements at DISJOINT times (1.25-1.75, 7.09-7.59, 12.85-13.35, 18.64-19.14).
# Every placement was recorded twice — the harness answers a second identical
# execute_plan and only refuses the third — so each row met itself.
#
# AND IT LANDED EXACTLY WHERE A THRESHOLD WOULD HAVE COME FROM. I registered
# that a bar could come from the real population being bimodal; {0.000 x N,
# 1.000 x 4} IS bimodal, and read at face value it is the strongest possible
# argument for a bar at 0.5 — manufactured entirely by a duplicate record.
_B = (436, 920, 208, 88)
_dbl = [{"family": "text", "t0": 1.25, "t1": 1.75, "box": _B},
        {"family": "text", "t0": 1.25, "t1": 1.75, "box": _B}]
check("the same placement recorded twice is NOT a collision",
      A.placement_collisions(_dbl) == [],
      "identical family, window and painted box is one placement seen twice")
# EXACT, not a threshold: a different window or a different box is a real pair.
check("a duplicate at a DIFFERENT time is still compared",
      len(A.placement_collisions(
          [{"family": "text", "t0": 1.0, "t1": 3.0, "box": _B},
           {"family": "text", "t0": 2.0, "t1": 4.0, "box": _B}])) == 1,
      "same box, overlapping but different windows — two placements, not one")
check("a duplicate window with a DIFFERENT box is still compared",
      len(A.placement_collisions(
          [{"family": "text", "t0": 1.0, "t1": 3.0, "box": _B},
           {"family": "text", "t0": 1.0, "t1": 3.0, "box": (400, 900, 300, 150)}])) == 1)
# AND 1.00 IS NOT THE SIGNATURE. A small overlay fully inside a large one reads
# exactly 1.00 legitimately — the diagnostic for round 45 was the DISJOINT
# TIMES, not the value. Anyone using "1.00 means duplicate" as a heuristic would
# discard real collisions.
check("a genuine containment still reads 1.00 and still collides",
      A.placement_collisions(
          [{"family": "card", "t0": 1.0, "t1": 3.0, "box": (120, 652, 852, 416)},
           {"family": "text", "t0": 2.0, "t1": 4.0, "box": _B}]
      )[0]["overlap_frac_of_smaller"] == 1.0,
      "1.00 is what full containment MEANS; it is not evidence of duplication")
check("duplicates are counted, not silently collapsed",
      'led["painted_boxes_duplicate"]' in src,
      "a number that quietly disappears is how this inflated every "
      "per-placement count since round 41 without anyone noticing")

check("a placement with no measured box is skipped, not guessed",
      A.placement_collisions([{"family": "a", "t0": 0, "t1": 9, "box": None},
                              {"family": "b", "t0": 0, "t1": 9, "box": (0, 0, 9, 9)}]) == [],
      "an unmeasured box must not be treated as a rectangle at the origin")

# ── 2b-ii. NO CARDS IS NOT "NO CARD COULD HAVE FAILED" ──────────────────────
# Round 45 placed no cards, so `if _cba:` skipped the line and CARD ALIGNMENT
# appeared ZERO times in four logs. An absence rendered as silence — and worse,
# I had registered UNEXERCISED for "every card passed both legs", which is a
# DIFFERENT fact wearing the same label.
# READ THE print() CALLS, not the file text. My first version asked whether the
# phrase EXISTED, so `_unprinted = (f"... NO CARDS PLACED"` kept it and stayed
# green. Eighteenth instance, and the third time in this one file.
def _in_print(phrase):
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                and _n.func.id == "print":
            for _sub in ast.walk(_n):
                if isinstance(_sub, ast.Constant) and isinstance(_sub.value, str) \
                        and phrase in _sub.value:
                    return True
    return False


check("the no-cards case is PRINTED, not skipped", _in_print("NO CARDS PLACED"),
      "with no cards the line vanished entirely, which reads as 'not measured' "
      "and 'nothing wrong' at the same time")
check("the two states print differently",
      _in_print("NO CARDS PLACED") and _in_print("UNEXERCISED"),
      "'no cards existed' and 'no card could have failed' are different facts")
# UNEXERCISED must key on cards that COULD have failed, not on the absence of
# failures — a set of all-not-applicable cards has not exercised the check
# either, and reporting it as passing is the same error one step in. Asserted
# on the CONDITION that yields the word, not on the name appearing somewhere.
_unex_tests = [n.test for n in ast.walk(tree) if isinstance(n, ast.IfExp)
               and any(isinstance(c, ast.Constant) and isinstance(c.value, str)
                       and "UNEXERCISED" in c.value for c in ast.walk(n))]
check("the UNEXERCISED condition exists", len(_unex_tests) == 1, str(len(_unex_tests)))
check("UNEXERCISED keys on cards that could have failed",
      _unex_tests and "_could_fail" in {n.id for t in _unex_tests
                                        for n in ast.walk(t) if isinstance(n, ast.Name)},
      "all-not-applicable cards exercise nothing; counting them as passing is "
      "the same mistake as counting zero cards as passing")

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

# ── 4. A NEVER-RECORDED VALUE MUST NOT PRINT AS A MEASURED ZERO ─────────────
# Builder-1 found paint_ms printing 0.0s for six rounds against 458s of real
# wall, because the key was never written and the printer said `or 0`. I had the
# same idiom in three places — and in the exact lines Zac asked me to report
# distributions from, where "0 of 0 boundaries land inside a word" reads as a
# clean edit rather than as an unrecorded denominator.
#
# READ THE PRINT EXPRESSIONS, not the file text: the denominator must come from
# a value that can say it is absent.
check("the cut denominator can report ABSENT",
      "_tot_s" in src and '"?" if _tot is None' in src,
      "`or 0` turns a key nobody wrote into a measurement")
check("the collision denominator can report ABSENT",
      "_nb_s" in src and "NOT RECORDED" in src)
_bad = [n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
        and len(n.values) == 2
        and isinstance(n.values[1], ast.Constant) and n.values[1].value == 0
        and isinstance(n.values[0], ast.Call)
        and getattr(n.values[0].func, "attr", "") == "get"
        and n.values[0].args
        and isinstance(n.values[0].args[0], ast.Constant)
        and str(n.values[0].args[0].value) in (
            "cut_boundaries_total", "painted_boxes_measured",
            "cut_quantisation_floor_ms")]
check("no measure I report uses `.get(...) or 0` for a denominator",
      not _bad, f"line(s) {_bad} — a never-written key becomes a zero and the "
                f"zero becomes a finding")

if fails:
    print(f"EDIT-QUALITY: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("EDIT-QUALITY: PASS — composite cannot truncate; cuts/cards/collisions "
      "measured, no thresholds")
