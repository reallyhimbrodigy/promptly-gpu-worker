#!/usr/bin/env python3
"""SMOKE: cards DERIVE from the claim; the agent no longer picks from 29 names.

ZAC'S RULING, 2026-09-09, from watching the videos against his references.
Three moments wanted a card and got text, on the one fixture that had them:

    10 TIMES A DAY      HOURS TO EDIT      5 MINUTES

against reference hooks built on escalating counters and dollar-figure cards.
The agent identified each as a stat IN ITS OWN RATIONALE and chose text.

THE MECHANISM, from round 42's own control group — same round, same cached
prefix, same model: zoom placed THREE distinct types, cards placed ONE of 29.
The difference is who chooses. The agent NEVER NAMES A ZOOM TYPE; it rules
zoom_arc and ZOOM_ARC_HOMES looks up the move. Cards asked the model to do the
one thing the zoom design deliberately refuses to ask.

So the agent now supplies the JUDGEMENT — this beat carries a claim worth
stamping, and card_hero is the phrase — and the harness derives WHICH component.
The 29-name enum is retired, and it was the incumbency mechanism itself.

RENDERED, both derived shapes, PromptlyOverlay frame 30:
    StatCard  {value: 10, label: "TIMES A DAY"}   139,780 bytes — 10 over the
              accent rule with TIMES A DAY beneath, the counter-hook shape
    PullQuote {text: "HOURS TO EDIT"}             176,329 bytes — the phrase whole
An empty StatCard was 48,138 bytes, so both paint.
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

# ── 1. THE THREE MISSED MOMENTS ─────────────────────────────────────────────
for _hero, _want in (("10 TIMES A DAY", "StatCard"),
                     ("5 MINUTES", "StatCard"),
                     ("HOURS TO EDIT", "PullQuote")):
    _t, _w = A.derive_card_type(_hero)
    check(f"{_hero!r} derives {_want}", _t == _want, f"got {_t} ({_w})")
# A DIGITS-ONLY RULE CATCHES TWO OF THE THREE. "HOURS TO EDIT" has no numeral,
# and leaving it as text is the defect — so a claim without a figure is still a
# claim, and PullQuote reads `text`.
check("a claim with no figure still gets a card",
      A.derive_card_type("HOURS TO EDIT")[0] is not None,
      "a digits-only rule leaves this one as text, which is the miss")

# ── 2. REFUSING IS A REAL ANSWER ────────────────────────────────────────────
check("no phrase means no card", A.derive_card_type("")[0] is None)
check("a sentence is not a card",
      A.derive_card_type("a phrase that runs on well past what a card can "
                         "hold at reading size")[0] is None,
      "a card is a few words at size, not a sentence")
for _bad in ("", "a phrase that runs on well past what a card can hold at size"):
    check(f"and it says why for {_bad[:18]!r}", len(A.derive_card_type(_bad)[1]) > 20)

# ── 3. THE PROPS DERIVE FROM THE DERIVED TYPE ───────────────────────────────
# I introduced this defect while fixing the other half: the old shorthand built
# {value, label} — StatCard's shape — so a derived PullQuote would have been
# handed props it reads NEITHER of and painted a transparent frame. The blank
# card class, reintroduced by the fix for a different half of it.
_p, _ = A.derive_card_props("PullQuote", "HOURS TO EDIT")
check("PullQuote gets text, not value", _p == {"text": "HOURS TO EDIT"}, str(_p))
_p2, _ = A.derive_card_props("StatCard", "10 TIMES A DAY")
check("StatCard gets a figure and the rest as its label",
      _p2.get("value") == "10" and _p2.get("label") == "TIMES A DAY", str(_p2))

# THE SUFFIX MUST BE ATTACHED TO THE DIGITS. `[0-9][0-9,.]*\s?[kKmMxX]?` matched
# "5 M" in "5 MINUTES" and coerce_mg_props read it as FIVE MILLION.
_p3, _ = A.derive_card_props("StatCard", "5 MINUTES")
_c3, _bad3 = A.coerce_mg_props(dict(_p3))
check("'5 MINUTES' is five, not five million",
      _c3.get("value") == 5, f"{_c3} — the M of MINUTES is not a mega suffix")
# AND THE LOOKAHEAD EARNS ITS PLACE. Removing `(?![A-Za-z])` is harmless on
# "5 MINUTES" — the space already stops it — so the case that justifies the
# lookahead is a suffix letter followed by MORE letters: "30KG OF GEAR" is
# thirty kilograms, not thirty thousand. Without this leg the lookahead could
# be deleted and every other leg stays green, which is a check that guards
# nothing.
check("a suffix letter inside a word does not multiply",
      A.coerce_mg_props(A.derive_card_props("StatCard", "30KG OF GEAR")[0])[0]
      .get("value") == 30,
      f"{A.derive_card_props('StatCard', '30KG OF GEAR')[0]} — KG is a unit, "
      f"not a kilo-multiplier")

check("a real attached suffix still multiplies",
      A.coerce_mg_props(A.derive_card_props("StatCard", "30K FOLLOWERS")[0])[0]
      .get("value") == 30000)
check("a decimal percentage survives",
      A.coerce_mg_props(A.derive_card_props("StatCard", "12.5% GROWTH")[0])[0]
      .get("value") == 12.5)

# THE SPLIT HAPPENS BEFORE ANY PROP IS FILLED. Filling in the interface's own
# alphabetical order put `label` before `value`, so the label took the WHOLE
# phrase and the remainder was computed too late.
check("the label is the remainder, never the whole phrase",
      A.derive_card_props("StatCard", "5 MINUTES")[0].get("label") == "MINUTES")
check("an explicit label still wins",
      A.derive_card_props("StatCard", "10,000", "FOLLOWERS")[0].get("label")
      == "FOLLOWERS")

# ── 4. END TO END: DERIVED PROPS SURVIVE EVERY DOWNSTREAM GATE ──────────────
for _hero in ("10 TIMES A DAY", "HOURS TO EDIT", "5 MINUTES", "$400", "10,000"):
    _t, _ = A.derive_card_type(_hero)
    _pp, _ = A.derive_card_props(_t, _hero)
    _cc, _unusable = A.coerce_mg_props(dict(_pp))
    check(f"{_hero!r} coerces with nothing unusable", not _unusable, str(_unusable))
    check(f"{_hero!r} passes mg_props_mismatch",
          A.mg_props_mismatch(_t, _cc) == "",
          A.mg_props_mismatch(_t, _cc))

# ── 5. THE AGENT NO LONGER PICKS ────────────────────────────────────────────
_schema = __import__("json").dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
check("card_type is gone from the agent's schema", '"card_type"' not in _schema,
      "a 29-name enum is what produced 1 distinct of 29 for five rounds")
check("card_props is gone too", '"card_props"' not in _schema,
      "the agent cannot supply a component's props when it does not choose the "
      "component")
check("card_hero survives — the judgement is still the agent's",
      '"card_hero"' in _schema,
      "WHICH phrase is worth stamping cannot be derived; that is the zoom_arc "
      "half of the contract")

_ep = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)
_calls = {n.func.id for n in ast.walk(_ep) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name)} if _ep else set()
check("the build DERIVES the type", "derive_card_type" in _calls)
check("the build DERIVES the props", "derive_card_props" in _calls)
check("and the derivation is recorded",
      'led.setdefault("card_type_derived"' in src,
      "the reason a component was chosen has to be readable afterwards")

if fails:
    print(f"CARD-DERIVED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CARD-DERIVED: PASS — the three missed moments derive StatCard/PullQuote, "
      "props follow the type, and the 29-name enum is gone")
