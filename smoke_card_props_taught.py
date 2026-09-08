#!/usr/bin/env python3
"""SMOKE: the agent is TOLD each component's props, from the same table that enforces them.

WHY. Round 40 built ZERO cards. The agent sent a camel-cased hero key where
StatCard reads `value`; my refusal correctly skipped all three; MG CATALOGUE had
nothing to measure for the third round running. The refusal was right and it was
not the fix.

    educate rather than validate — standing law

Until this, the agent was never told ANY component's props. card_props said only
"in the shape its catalogue entry shows", and reading the catalogue costs a
read_knowledge turn the agent does not spend. So it invented key names, which is
the only thing left to do.

ONE CHAIN, CERTED AT BOTH JOINTS:
    component types.ts  --cert_mg_prop_keys-->  MG_PROP_KEYS  --this smoke-->
    the card_props description the agent reads
A hand-written third copy would rot against the other two; this asserts the
description is DERIVED, by regenerating it and comparing.

STYLING PROPS EXCLUDED for types that require nothing. Alphabetical order put
`accentColor` first for BarRace, which reads `bars` — teaching that would produce
a styled EMPTY component, a new way to render nothing rather than a fix for the
old one.
"""
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


# THE DESCRIPTION AS THE AGENT RECEIVES IT — walked out of the real schemas, not
# read from the source. rule_all_beats lives in KNOWLEDGE_TOOLS, not TOOLS; a
# probe that searched only TOOLS reported card_props ABSENT and was wrong about
# the code rather than the code being wrong.
_found = []


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "card_props" and isinstance(v, dict):
                _found.append(v)
            _walk(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _walk(v)


_walk(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
check("card_props is reachable in the schemas the agent gets", len(_found) == 1,
      f"found {len(_found)} — searching only TOOLS finds ZERO, because "
      f"rule_all_beats is in KNOWLEDGE_TOOLS")
DESC = _found[0].get("description", "") if _found else ""

# ── 1. IT IS DERIVED, NOT TYPED ─────────────────────────────────────────────
check("the taught text is exactly what the table generates",
      A.MG_PROPS_TEACH == A._mg_props_teach(),
      "MG_PROPS_TEACH has drifted from its own generator")
check("and the description carries it verbatim",
      A.MG_PROPS_TEACH and A.MG_PROPS_TEACH in DESC,
      "the description was hand-edited — a third copy that rots against the "
      "table and the components")

# ── 2. EVERY REQUIRED PROP IS ACTUALLY TAUGHT ───────────────────────────────
# The specific failure: StatCard needs `value`, the agent was never told, and it
# guessed. Every type with required props must name them.
_taught = 0
for _t, _v in sorted(A.MG_PROP_KEYS.items()):
    if not _v["required"]:
        continue
    _taught += 1
    check(f"{_t}'s required props are taught",
          f"{_t}: {'+'.join(_v['required'])}" in DESC,
          f"the agent cannot supply {_v['required']} it has never been shown")
check("this leg is not vacuous", _taught >= 10,
      f"only {_taught} types have required props — check the table loaded")
check("StatCard specifically teaches value", "StatCard: label+value" in DESC,
      "this is the exact key round 40 guessed wrong")

# ── 3. NO TYPE IS TAUGHT A STYLING PROP AS ITS SHAPE ────────────────────────
# BarRace reads `bars`; alphabetical order offered `accentColor`. A component
# styled and empty is not better than a component that is merely empty.
for _t, _v in sorted(A.MG_PROP_KEYS.items()):
    if _v["required"] or f"{_t}: " not in DESC:
        continue
    _shown = DESC.split(f"{_t}: ", 1)[1].split(";")[0].split(" (")[0].split("+")
    check(f"{_t} is not taught a styling prop as its shape",
          not any(A._MG_STYLE_PROP.search(p) for p in _shown),
          f"teaches {_shown} — a styled EMPTY component is a new way to render "
          f"nothing, not a fix for the old one")

# ── 4. THE SHORTHAND STAYS OFFERED ──────────────────────────────────────────
# It is the path that always worked, and the one that rendered round 36's card.
check("the StatCard shorthand is still offered",
      "card_hero" in DESC and "card_label" in DESC,
      "omitting card_props is the simplest correct answer and must stay stated")
check("and it says the hero must be a real figure",
      "figure the speaker actually said" in DESC,
      "a hero that is not a number renders a blank card counting up to nothing")

# ── 5. THE COST IS BOUNDED ──────────────────────────────────────────────────
# This rides in the CACHED PREFIX on every call of every run.
check("the taught text stays small", len(DESC) < 2000,
      f"{len(DESC)} chars — it is in the cached prefix on every call")

if fails:
    print(f"CARD-PROPS-TAUGHT: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"CARD-PROPS-TAUGHT: PASS — {_taught} types teach their required props, "
      f"{len(DESC)} chars in the cached prefix")
