#!/usr/bin/env python3
"""SMOKE: placement effect is measured where the placement PAINTED.

THE DEFECT. _record_effect compared whole-frame PSNR at the placement against
whole-frame PSNR at a control window, bar 3.0 dB. Round 42, Zac's real footage:
THREE FALSE placement_inert failures on text that rendered correctly and legibly
("10 TIMES A DAY", "RECORD 10 - UPLOAD ALL", "5 MINUTES - ZERO WORK"). Had they
been reported as measured, someone would have gone to edit a component that
works — the exact cost that made Zac rule zoom geometry UNMEASURED.

WHY, MEASURED RATHER THAN ARGUED — the painted fraction of a 1080x1920 frame:
    text overlay    0.9%
    StatCard       23.1%
A whole-frame average cannot see a 0.9% change. It is not a constant to nudge;
it is the wrong measurement, and this is the FOURTH threshold in this lane
fitted to one.

REPRODUCED under production-like accumulated loss (every pipeline step
re-encodes the whole video, so the CONTROL window degrades too):
    v3 text   GLOBAL delta  3.14 dB against a 3.0 bar   margin 0.14 dB
    v3 text   REGION delta 19.98 dB                     margin 13.98 dB
The verdict turned on a seventh of a decibel.

VALIDATED ON BOTH CORPORA BEFORE SHIPPING, criteria registered in advance in
FALSIFIER_localised_effect.md:
    arm            v1 (synthetic)   v3 (Zac real)     required
    card                 49.55           33.00        CHANGED
    text                 72.62           28.86        CHANGED
    text (lossy)         50.68           19.98        CHANGED
    null region          -2.50            0.24        INERT
    empty alpha          EMPTY           EMPTY        EMPTY
    worst CHANGED 19.98 | best INERT 0.24 | window 19.74 dB
One bar serves both corpora, which is the criterion all three previous bars
failed.
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
INF = float("inf")

# ── 1. THE THREE BOX STATES ─────────────────────────────────────────────────
check("alpha_paint_box is importable", callable(getattr(A, "alpha_paint_box", None)))
_st, _bx, _why = A.alpha_paint_box("/nonexistent-layer.mov", 1.0)
check("a missing layer is UNMEASURED, not empty and not a box",
      _st == A.ALPHA_BOX_UNMEASURED and _bx is None,
      f"({_st}, {_bx}) — an unread layer must not read as 'painted nothing'")
check("the three states are distinct values",
      len({A.ALPHA_BOX_MEASURED, A.ALPHA_BOX_EMPTY, A.ALPHA_BOX_UNMEASURED}) == 3)

# ── 2. crop TAKES w:h:x:y, AND THE BOX IS (x,y,w,h) ─────────────────────────
# Passing the box straight through measured a region with nothing to do with the
# placement: it read 44.85 dB on a card whose real region PSNR was 9.45. The
# order is the bug most likely to come back, so it is asserted on the AST rather
# than on a comment.
_rp = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "region_psnr"), None)
check("region_psnr exists", _rp is not None)
if _rp:
    _crops = [n for n in ast.walk(_rp)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value.startswith("crop=")]
    check("the crop format string is present", len(_crops) == 1, str(_crops))
    _bin = next((n for n in ast.walk(_rp) if isinstance(n, ast.BinOp)
                 and isinstance(n.left, ast.Constant)
                 and str(n.left.value).startswith("crop=")), None)
    check("crop is fed w, h, x, y — not the box order",
          _bin is not None and isinstance(_bin.right, ast.Tuple)
          and [getattr(e, "id", "") for e in _bin.right.elts] == ["_w", "_h", "_x", "_y"],
          "crop=%d:%d:%d:%d is w:h:x:y; the box is (x,y,w,h) and passing it "
          "through measures the wrong rectangle entirely")

# ── 3. inf IS A RESULT, NOT A GAP ───────────────────────────────────────────
# An identical region gives psnr_avg:inf. A regex matching only [0-9.] drops it
# silently, so the CLEANEST case — a control window that did not move at all —
# came back unmeasurable.
check("region_psnr parses inf", "inf|[0-9.]" in src,
      "the control window of a static source is identical and reports inf")
check("both-inf is 'nothing moved anywhere', not a change",
      A.region_effect_delta(INF, INF) == 0.0)
check("a pristine control with a moved placement is unambiguous",
      A.region_effect_delta(10.0, INF) == INF)
check("a pristine PLACEMENT region is inert",
      A.region_effect_delta(INF, 10.0) == -INF)
check("a missing reading is None, never a number",
      A.region_effect_delta(None, 10.0) is None
      and A.region_effect_delta(10.0, None) is None)
check("the ordinary case is control minus placement",
      A.region_effect_delta(10.0, 40.0) == 30.0,
      "the region moved 30 dB MORE at the placement than at the control")

# ── 4. THE BAR, AND THE MEASURED ARMS IT SITS BETWEEN ───────────────────────
WORST_CHANGED, BEST_INERT = 19.98, 0.24
check("the bar separates every measured arm",
      BEST_INERT < A._REGION_EFFECT_BAR_DB < WORST_CHANGED,
      f"{A._REGION_EFFECT_BAR_DB} is outside ({BEST_INERT}, {WORST_CHANGED})")
check("it clears the 2.0 dB margin registered BEFORE the arms existed",
      (WORST_CHANGED - A._REGION_EFFECT_BAR_DB) >= 2.0
      and (A._REGION_EFFECT_BAR_DB - BEST_INERT) >= 2.0,
      f"margins {WORST_CHANGED - A._REGION_EFFECT_BAR_DB:.2f} / "
      f"{A._REGION_EFFECT_BAR_DB - BEST_INERT:.2f}")
check("it is biased LOW within the window, not centred",
      A._REGION_EFFECT_BAR_DB < (WORST_CHANGED + BEST_INERT) / 2.0,
      "the two errors are not symmetric: a false INERT sends someone to edit a "
      "working component (round 42, three times); a false CHANGED misses one "
      "inert placement. The tolerable error is the missed defect.")

# ── 5. THE GLOBAL BAR NO LONGER JUDGES AN OVERLAY ───────────────────────────
_re = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_record_effect"), None)
check("_record_effect exists", _re is not None)
if _re:
    _kw = [a.arg for a in _re.args.args] + [a.arg for a in _re.args.kwonlyargs]
    check("it takes a layer", "layer" in _kw)
    _calls = {n.func.id for n in ast.walk(_re)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check("it asks the layer for the box", "alpha_paint_box" in _calls)
    check("and measures the region", "region_psnr" in _calls)
# The families that paint a LOCAL overlay must pass a layer. zoom and transition
# replace the whole frame and correctly keep the global measure.
for _fam in ('"text"', '"caption"', '"card"'):
    _i = src.find(f"_record_effect({_fam}")
    check(f"the {_fam} placement passes its alpha layer",
          _i > 0 and "layer=" in src[_i:_i + 700],
          "without a layer it falls back to the whole-frame average that "
          "produced the false failures")

# ── 6. EMPTY AND UNMEASURED ARE NOT VERDICTS ────────────────────────────────
# The case that started all of this: an empty alpha layer composites,
# re-encodes, changes the file and passes a global check. It must not now be
# reported as INERT either — that would be a different wrong answer.
# READ THE ASSIGNMENTS. The first version greped for '_rec["changed"] = None'
# and a mutant that changed THIS branch to False stayed green, because a SECOND
# branch further down still carried the string. Fourteenth substring trap this
# session; the file it is checking has to be read as code.
_assigns_false = []
for _n in ast.walk(_re) if _re else []:
    if not isinstance(_n, ast.Assign):
        continue
    _t = _n.targets[0]
    if (isinstance(_t, ast.Subscript) and getattr(_t.value, "id", "") == "_rec"
            and getattr(getattr(_t, "slice", None), "value", None) == "changed"
            and isinstance(_n.value, ast.Constant) and _n.value.value is False):
        _assigns_false.append(_n.lineno)
check("no branch reports an unanswered box as INERT", not _assigns_false,
      f"_rec['changed'] is set to False at line(s) {_assigns_false} — False "
      f"fails the round as placement_inert on a question nobody answered")
check("this leg can see the assignments at all",
      _re is not None and any(
          isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript)
          and getattr(n.targets[0].value, "id", "") == "_rec"
          for n in ast.walk(_re)),
      "the walk is not reaching _rec assignments and the leg is vacuous")
check("the non-measured branch exists",
      "if _bx_st != ALPHA_BOX_MEASURED" in src)
check("the state is recorded on the placement",
      '_rec["region_verdict"]' in src and '_rec["box_state"]' in src)
check("and counted on the ledger",
      'led["region_effect_" + _bx_st] += 1' in src)

if fails:
    print(f"LOCALISED-EFFECT: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"LOCALISED-EFFECT: PASS — bar {A._REGION_EFFECT_BAR_DB} dB inside "
      f"({BEST_INERT}, {WORST_CHANGED}), margins "
      f"{WORST_CHANGED - A._REGION_EFFECT_BAR_DB:.2f}/"
      f"{A._REGION_EFFECT_BAR_DB - BEST_INERT:.2f} dB on both corpora")
