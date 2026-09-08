#!/usr/bin/env python3
"""SMOKE: an alpha layer that painted NOTHING is refused, and props are numbers.

FOUND BY LOOKING, WHICH IS THE POINT. Round 35 declared four StatCards on
talking_head. Every effect measurement passed them — psnr 59-61 dB against their
control windows, all four "moved", EFFECT COVERAGE said ALL MEASURED. The frames
show no card at all. The reel painted 300 real frames of nothing, the composite
re-encoded the video, and every instrument agreed.

WHY NO INSTRUMENT COULD SEE IT. Compositing an EMPTY alpha layer still
re-encodes, still changes the file, still clears a relative threshold against a
control window. `placement_inert` asks "did the picture change" and the honest
answer is yes. The only question with a different answer is asked of the LAYER:
what do you contain?

    MEASURED, alpha plane YMAX per frame, rendered locally:
        empty layer            256 on every frame
        one StatCard           256 .. 3760
    There is no overlap. 260 is the bar.

THE ROOT CAUSE, measured the same way — alpha composited over white, non-white
pixels counted:
        value "10,000"  (string)          0 pixels
        value 10000     (number)    204,953 pixels
        value "three"   (word)            0 pixels
StatCard counts up digit-by-digit to a TARGET. A string is not a smaller number;
it is not a number. All four of round 35's cards passed `card_hero` verbatim.

AND "three" IS NOT A COERCION FAILURE. It is a beat with no quoted figure, and
production's own teach says a StatCard without one is the wrong component. The
build refuses rather than rendering an empty card.
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
_ep = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)

# ── 1. PROPS COERCION ───────────────────────────────────────────────────────
check("coerce_mg_props is importable", callable(getattr(A, "coerce_mg_props", None)))
for _raw, _want in (("10,000", 10000), ("62", 62), ("$1.2M", 1200000),
                    ("30000", 30000), ("12.5%", 12.5), (7, 7)):
    _p, _bad = A.coerce_mg_props({"value": _raw})
    check(f"{_raw!r} becomes {_want!r}", _p["value"] == _want and not _bad,
          f"got {_p['value']!r} unusable={_bad}")
for _raw in ("three", "", None, "a lot"):
    _p, _bad = A.coerce_mg_props({"value": _raw})
    check(f"{_raw!r} is reported UNUSABLE, not forced",
          _bad == ["value"],
          f"got {_p.get('value')!r} unusable={_bad} — forcing it to 0 would "
          f"render a card counting up to nothing")
check("every numeric prop the components take is covered",
      A._MG_NUMERIC_PROPS == {"value", "total", "fromValue"},
      f"got {A._MG_NUMERIC_PROPS}; ProgressBar reads total, StatCard reads "
      f"fromValue, and a string in either renders blank the same way")
_p, _ = A.coerce_mg_props({"value": "47,000", "total": "100,000", "label": "GOAL"})
check("non-numeric props are left alone",
      _p == {"value": 47000, "total": 100000, "label": "GOAL"}, str(_p))
check("a missing prop is not invented",
      A.coerce_mg_props({"label": "X"}) == ({"label": "X"}, []))

# ── 2. THE BUILD USES IT AND REFUSES WHAT IT CANNOT USE ─────────────────────
_calls = {n.func.id for n in ast.walk(_ep) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name)} if _ep else set()
check("coerce_mg_props is CALLED in the build", "coerce_mg_props" in _calls)
check("an unusable prop skips the card", "_bad_props" in src and
      "needs a number for" in src)
check("the skip names the alternative rather than only the rule",
      "05_motion_graphics" in src.split("needs a number for")[1][:600],
      "a refusal that does not say what to do instead just costs a turn")

# ── 3. THE ALPHA LAYER IS ASKED WHAT IT CONTAINS ────────────────────────────
check("alpha_layer_max is importable", callable(getattr(A, "alpha_layer_max", None)))
check("the empty bar is the measured one",
      A._ALPHA_EMPTY_YMAX == 260.0,
      f"is {A._ALPHA_EMPTY_YMAX}; empty planes sit at 256 and a StatCard "
      f"reaches 3760")
check("an unreadable layer is None, never a pass",
      A.alpha_layer_max("/nonexistent-layer.mov") is None,
      "the same law every other instrument here carries")
check("the REEL layer is checked before it is composited",
      "_reel_alpha = alpha_layer_max(" in src
      and src.index("_reel_alpha = alpha_layer_max(") < src.index("reel-filter.txt"),
      "checking after the composite tells you what you already shipped")
check("the CAPTION layer is checked too",
      "_cap_alpha = alpha_layer_max(" in src,
      "this is the pass that rendered 600 frames of an empty default for two "
      "whole rounds while reporting composited=True")
check("an empty layer FAILS the round",
      "alpha_layer_empty" in A.CONTRACT_FAILURES)


def _guarded_by(marker):
    out, stack = set(), [(tree, [])]
    while stack:
        node, guards = stack.pop()
        for child in ast.iter_child_nodes(node):
            g = guards + [node.test] if isinstance(node, ast.If) and child in node.body else guards
            if (isinstance(child, ast.Constant) and isinstance(child.value, str)
                    and marker in child.value):
                for t in g:
                    out |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}
            stack.append((child, g))
    return out


# The raise must be reachable only when the MEASUREMENT says empty — `if False:`
# leaves the string in the file and a substring test cannot tell.
check("the reel raise is guarded by the measured alpha",
      "_reel_alpha" in _guarded_by("the components painted NOTHING"),
      f"guarded by {sorted(_guarded_by('the components painted NOTHING'))}")
check("the caption raise is guarded by the measured alpha",
      "_cap_alpha" in _guarded_by("the styles painted NOTHING"),
      f"guarded by {sorted(_guarded_by('the styles painted NOTHING'))}")
check("both measurements are RECORDED, not only tested",
      'led["reel_alpha_max"]' in src and 'led["caption_alpha_max"]' in src,
      "a layer that was checked and passed should be readable as such")

if fails:
    print(f"ALPHA-NOT-EMPTY: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALPHA-NOT-EMPTY: PASS")
