#!/usr/bin/env python3
"""The one moment the catalogue provably cannot serve a beat ROUTES to authoring.

WHY SKILLS NEVER FIRED. `search_skills` has zero calls across every round and no
component has ever been authored. Three independent structural reasons, all
found by reading the ruling surface rather than the prompt:

  1  THE RULING SURFACE CANNOT EXPRESS THE TRIGGER. Both treatment enums —
     rule_all_beats and beat_verdict — are card|text|sfx|zoom|transition|none.
     Every value has a harness builder. There is NO value meaning "the catalogue
     has none", so the decision point author_component exists for never arises
     from a ruling.

  2  THE TOOL'S ONLY WORKED EXAMPLE WAS OBSOLETE. It said "Zoom is the case:
     there is no PunchIn component, so author one." Zoom is now IN the enum,
     derived through ZOOM_ARC_HOMES and built mechanically by build_zoom. The
     one illustration the tool offered pointed at a case the harness had taken
     over — so an agent that read it correctly would conclude authoring was for
     something it must not do.

  3  THE SYSTEM PROMPT NEVER ROUTES TO IT. `author_component` appears zero times
     in SYSTEM. `search_skills` appears, but as the Remotion API reference — the
     manual for a task nobody is ever told to begin.

WHAT MAKES IT REACHABLE, and it is derived rather than invented. The harness
ALREADY computes the moment: `derive_card_type` returns (None, why) when a
ruled card's hero is neither a figure nor a short claim — no StatCard, no
PullQuote, nothing in the 25 fits. That determination was absorbed into a skip
and reported afterwards as a count. It is now a NAMED CODE with the hero and a
remedy, so the agent learns the catalogue failed on THIS beat, with the material
in hand, at the moment `execute_plan` reports back.

This does not invite authoring anywhere else. The signal is proven, not offered:
the agent ruled a card, the harness tried every catalogue type, and none fit.

RED-proven by red_proof_authoring_reachable.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# ── the three reasons, asserted as facts about the tree ─────────────────────
_enums = []
for _n in ast.walk(tree):
    if isinstance(_n, ast.Dict):
        for _k, _v in zip(_n.keys, _n.values):
            if isinstance(_k, ast.Constant) and _k.value == "enum" \
                    and isinstance(_v, ast.List):
                _vals = [c.value for c in _v.elts if isinstance(c, ast.Constant)]
                if "card" in _vals and "text" in _vals:
                    _enums.append((_k.lineno, _vals))
check(f"the treatment enums were found ({len(_enums)}) — non-vacuity",
      len(_enums) >= 2, f"{_enums}")
check("no treatment value means 'the catalogue has none'",
      all(not any(v in ("author", "custom", "new_component") for v in vals)
          for _ln, vals in _enums),
      "if one is added, the trigger becomes a ruling and this file's reasoning "
      "changes — that would be a product decision, not a fix")

# ── the fix: the skip carries a CODE, the hero and a remedy ─────────────────
check("a card the catalogue cannot serve is coded, not just counted",
      '"code": "no_catalogue_component"' in src,
      "a skip with only a `why` is a count; the agent needs the name of the "
      "condition to act on it")
check("the report carries the HERO, so the agent has the material",
      '"hero": str(hero)[:60]' in src)
check("and a remedy naming author_component",
      "author_component is how this" in src)
check("the beats are ledgered so the round can count them",
      'led.setdefault("authorable_beats"' in src,
      "a signal that reaches the agent and not the ledger cannot be measured "
      "afterwards; one that reaches the ledger and not the agent cannot be "
      "acted on. This needs both.")

# ── the obsolete example is gone ────────────────────────────────────────────
check("author_component no longer offers ZOOM as its worked example",
      "there is no PunchIn component, so author one" not in src,
      "zoom is in the treatment enum and built by build_zoom — an agent "
      "following that example would author something it must not")
check("its example is now the case that actually reaches it",
      "no_catalogue_component" in src and "THE CASE IS A CARD" in src)

# ── it is wired where the determination happens ─────────────────────────────
_dc = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
       and getattr(n.func, "id", "") == "derive_card_type"]
check(f"derive_card_type is called ({len(_dc)}) — the determination exists",
      len(_dc) >= 1)
check("the routing sits on the None branch of that call",
      src.index('"code": "no_catalogue_component"') > src.index("if not _ctype:"),
      "the remedy must attach to the proven failure, not to every card")

print()
if fails:
    print("AUTHORING-REACHABLE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("AUTHORING-REACHABLE: PASS — the catalogue's own failure is now named, "
      "carries the hero and a remedy, and is ledgered for counting")
