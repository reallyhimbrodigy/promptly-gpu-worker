#!/usr/bin/env python3
"""SMOKE: props that do not address the component are refused before the render.

THE REGRESSION, round 36 -> round 39. Round 36's frames show a StatCard: "10,000"
in display numerals, the accent rule, the label. Round 39, same fixture and same
brief, shows NO CARD ANYWHERE — and the reel's alpha never exceeded 0.0, meaning
300 frames of a fully transparent layer, rendered and composited and reported
successful.

WHAT CHANGED BETWEEN THEM, and it is mine: 6073850 made card_props reach the
builder. Before it, the field was dropped at the boundary, so `_cprops` always
fell back to the StatCard shorthand {value: hero, label: card_label} — which
always carries `value`, and always renders. After it, whatever the agent sends is
used verbatim.

MEASURED, one still per arm, PromptlyOverlay frame 20, rendered locally:
    {"value": 10000, "label": "FOLLOWERS"}    184,920 bytes   the number draws
    {"stat": 10000, "caption": "FOLLOWERS"}    48,138 bytes   BLANK
Both exit 0. Both report a successful render. One is a transparent frame.

WHY NO EXISTING GATE CAUGHT IT. coerce_mg_props only fixes keys that are
PRESENT — a missing prop is never invented, which is correct and was tested. So
coerce_mg_props({"stat": 10000}) reports nothing wrong. The card_props schema
description says "A type whose props do not match renders empty", which is a
warning with no consequence attached. And the alpha check fires only AFTER the
reel has been painted, which is the most expensive stage in the run.
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

# ── 1. THE TWO FAILURE SHAPES ───────────────────────────────────────────────
_foreign = A.mg_props_mismatch("StatCard", {"stat": 10000, "caption": "X"})
check("props addressing another component are REFUSED", bool(_foreign),
      "this is round 39's shape and it rendered a transparent frame")
check("and the refusal names what the component does read",
      "value" in _foreign and "label" in _foreign, _foreign)
# ISOLATE THE FOREIGN BRANCH. The leg above does NOT prove it: {"stat":...} is
# also MISSING value and label, so the missing branch refuses it either way —
# disabling the foreign branch entirely left this smoke green (RED proof 2).
# A component with NO required props can only be caught by the foreign branch.
_nr = [t for t, v in A.MG_PROP_KEYS.items() if not v["required"] and v["declared"]]
check("there is a component with no required props to test with", bool(_nr),
      "without one, the foreign branch cannot be isolated and this smoke would "
      "pass with it deleted")
for _t in _nr[:3]:
    check(f"foreign props are refused for {_t}, which requires nothing",
          bool(A.mg_props_mismatch(_t, {"zzz": 1})),
          f"{_t} requires no props, so ONLY the foreign check can catch this — "
          f"if it passes, the foreign branch is dead and the leg above was "
          f"being satisfied by the missing-prop branch instead")
    check(f"and correct props still pass for {_t}",
          A.mg_props_mismatch(_t, {A.MG_PROP_KEYS[_t]["declared"][0]: 1}) == "")

check("a missing required prop is REFUSED",
      bool(A.mg_props_mismatch("StatCard", {"label": "X"})),
      "StatCard with no `value` has nothing to count up to")
check("correct props pass",
      A.mg_props_mismatch("StatCard", {"value": 1, "label": "X"}) == "")
check("extra props alongside correct ones pass",
      A.mg_props_mismatch("StatCard", {"value": 1, "label": "X", "suffix": "%"}) == "",
      "components take optional props; only FOREIGN or MISSING are defects")

# EMPTY props are not this check's business: the shorthand fills them upstream.
check("empty props are left to the shorthand",
      A.mg_props_mismatch("StatCard", {}) == "")
# UNDERIVABLE types are NOT VALIDATED — never assumed to require nothing.
for _u in A.MG_PROPS_UNDERIVABLE:
    check(f"{_u} is not validated rather than assumed fine",
          A.mg_props_mismatch(_u, {"zzz": 1}) == "",
          "calling an underivable component 'requires nothing' would wave "
          "through the exact blank render this check exists to stop")

# ── 2. IT IS ASKED BEFORE THE RENDER, NOT AFTER ─────────────────────────────
# The alpha check already catches a blank reel — after paying for the paint,
# which is the most expensive stage in the run. This one is worth having only if
# it runs first.
_ep = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)
check("execute_plan is present", _ep is not None)
if _ep:
    _calls = [n for n in ast.walk(_ep) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name)]
    _names = [n.func.id for n in _calls]
    check("the build CALLS mg_props_mismatch", "mg_props_mismatch" in _names,
          "the function exists and nothing runs it")
    check("it is asked BEFORE render_components",
          "mg_props_mismatch" in _names and "render_components" in _names
          and _names.index("mg_props_mismatch") < _names.index("render_components"),
          "checking after the paint is what the alpha gate already does")
    check("it is asked BEFORE coerce_mg_props",
          "mg_props_mismatch" in _names and "coerce_mg_props" in _names
          and _names.index("mg_props_mismatch") < _names.index("coerce_mg_props"),
          "coercion only fixes keys that are present, so a foreign props object "
          "passes it clean — asking after would read a green that means nothing")

# ── 3. THE TABLE IS REAL ────────────────────────────────────────────────────
check("every derivable selectable type has an entry",
      set(A.MG_PROP_KEYS) | set(A.MG_PROPS_UNDERIVABLE) == set(A.MG_SELECTABLE_TYPES),
      f"unaccounted "
      f"{sorted(set(A.MG_SELECTABLE_TYPES) - set(A.MG_PROP_KEYS) - set(A.MG_PROPS_UNDERIVABLE))}")
check("StatCard's requirements are the ones the component states",
      A.MG_PROP_KEYS["StatCard"]["required"] == ["label", "value"],
      f"{A.MG_PROP_KEYS['StatCard']['required']}")
check("the table is not empty of requirements everywhere",
      sum(1 for v in A.MG_PROP_KEYS.values() if v["required"]) >= 10,
      "a table whose every entry requires nothing validates nothing")
# ── 4. THE NAME THAT CAN FAIL A ROUND IS ACTUALLY EMITTED ───────────────────
# THIS LEG WAS A TAUTOLOGY AND COST A ROUND. It read
#
#     "card_props_mismatch" in A.CONTRACT_FAILURES or "mg_props_mismatch" in src
#
# and the second clause is ALWAYS true, because the function is named in the
# file being searched. So it passed while card_props_mismatch had one consumer
# and NO PRODUCER: round 40 dropped 3 of 3 cards to the refusal, emitted only
# execute_plan_skip and ruled_not_built — neither of which fails a round — and
# scored GREEN. Worse than round 39, where the cards rendered blank and
# alpha_layer_empty caught them. Builder-1 found it by checking every fail()
# literal in the module. Thirteenth substring trap this session, and the first
# one that made a real round lie.
#
# READ THE CALL, NOT THE TEXT. A fail() whose first argument is the literal.
_emitted = {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "fail" and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)}
check("this smoke can see the module's fail() calls", len(_emitted) > 15,
      f"only {len(_emitted)} — the walk is not finding them and the leg below "
      f"would pass vacuously")
check("card_props_mismatch can fail a round",
      "card_props_mismatch" in A.CONTRACT_FAILURES)
check("card_props_mismatch is actually EMITTED",
      "card_props_mismatch" in _emitted,
      "it is in CONTRACT_FAILURES with no producer — a name that can fail a "
      "round and never does is a green that means nothing")
check("it is emitted from the mismatch refusal itself",
      any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == "fail" and n.args
          and isinstance(n.args[0], ast.Constant)
          and n.args[0].value == "card_props_mismatch"
          for n in ast.walk(_ep or tree)),
      "emitted somewhere else entirely would not answer for this refusal")

# ── THE TWO COUNTERS THAT SAY WHETHER 15 COMPONENTS GOT REACHED ──────────────
# Round 63 could not answer that, and I reported both as `null` when the honest
# answer was KEY ABSENT. Three separate defects, one class:
#   * both are written with `led.setdefault(k, []).append(...)`, so a run that
#     rules no card never creates the key — and an absent key is
#     indistinguishable from a tree with none of the wiring;
#   * `card_conditions_named` was written and NEVER PRINTED;
#   * `card_props_seen`'s print was guarded by `if _cps:`, so zero printed
#     nothing and "zero cards" read exactly like "no instrumentation".
#
# NOTE ON THE SCAN ITSELF: my first AST pass for these looked only for `Assign`
# to a Subscript and reported BOTH as "assigned NOWHERE" — it does not model
# `setdefault().append()`. Same family as the out-parameter an AST scan of a
# closure body cannot see: enumerate the MUTATIONS, not just the assignments.
_CARD_COUNTERS = ("card_conditions_named", "card_props_seen")

_init_empty = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.List) and not n.value.elts:
        for t in n.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                    and t.slice.value in _CARD_COUNTERS):
                _init_empty.add(t.slice.value)
for _k in _CARD_COUNTERS:
    check(f"`{_k}` is INITIALISED to [], so wired-and-zero is not ABSENT",
          _k in _init_empty,
          "only setdefault-written: on a run with no cards the key never "
          "exists, and nobody can tell that from an unwired tree")

# PRINTED IN BOTH STATES. The property is an if/else where BOTH arms print, not
# merely that a print mentions the counter — `if _cps:` with no else satisfied
# that weaker reading for months.
_both_arms = set()
for n in ast.walk(tree):
    if not isinstance(n, ast.If) or not n.orelse:
        continue
    _seg = ast.get_source_segment(src, n) or ""
    def _has_print(body):
        return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                   and c.func.id == "print"
                   for b in body for c in ast.walk(b))
    if _has_print(n.body) and _has_print(n.orelse):
        for _k in _CARD_COUNTERS:
            if _k in _seg or _k.split("_")[1][:4].upper() in _seg.upper():
                _both_arms.add(_k)
for _k in _CARD_COUNTERS:
    check(f"`{_k}` is printed in BOTH states (an if/else, both arms printing)",
          _k in _both_arms,
          "a guarded print makes a zero silent, which is the ambiguity the "
          "counter exists to resolve")

check("the ABSENT word reaches the card-counter output, so a missing key is "
      "named rather than shown as 0",
      src.count('"MEASURED 0" if isinstance(_ccn, list) else "ABSENT"') == 1
      and src.count('"MEASURED 0" if isinstance(_cps, list) else "ABSENT"') == 1,
      "the three-state distinction has to be in the printed text, not only in "
      "the ledger")

if fails:
    print(f"CARD-PROPS-MATCH: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CARD-PROPS-MATCH: PASS")
