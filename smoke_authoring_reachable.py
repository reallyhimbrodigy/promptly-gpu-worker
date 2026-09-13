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
# THE KEY AND ITS VALUE, NOT THE LITERAL PAIR. Same correction as the branch
# leg above: `code` is now computed (hero_too_long vs no_catalogue_component),
# so the exact string `"code": "no_catalogue_component"` no longer appears and
# the leg failed on a change that added a distinction.
_skip_emits = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "append"
               and getattr(n.func.value, "id", "") == "_skips"
               and n.args and isinstance(n.args[0], ast.Dict)]
_coded = [n for n in _skip_emits
          if any(isinstance(k, ast.Constant) and k.value == "code"
                 and "no_catalogue_component" in ast.unparse(v)
                 for k, v in zip(n.args[0].keys, n.args[0].values))]
check("a card the catalogue cannot serve is coded, not just counted",
      bool(_coded),
      "a skip with only a `why` is a count; the agent needs the name of the "
      "condition to act on it")
check("the report carries the HERO, so the agent has the material",
      '"hero": str(hero)[:60]' in src)
check("and a remedy naming author_component",
      "author_component is how this" in src)
check("the beats are ledgered so the round can count them",
      'led.setdefault("catalogue_gap_beats"' in src,
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
# THE BRANCH, NOT THE SPELLING. This compared the byte offsets of the literal
# `"code": "no_catalogue_component"` against `if not _ctype:`. The code now
# emits that value from a CONDITIONAL — `"code": ("hero_too_long" if _too_long
# else "no_catalogue_component")` — because derive_card_type returns None for
# two different reasons and only one is a catalogue gap. The literal vanished
# and this leg crashed with ValueError: substring not found, on a change that
# made the routing MORE precise. An offset comparison over source text is not
# a structural claim; ask the AST where the emit sits.
_emit = [n for n in _skip_emits
         if "no_catalogue_component" in ast.unparse(n.args[0])]
check("the authoring remedy is emitted from a card skip, not offered standing",
      bool(_emit),
      "the remedy must attach to the proven failure, not to every card")
# AND IT MUST BE INSIDE THE None BRANCH. An emit that sits outside it would
# route every card to authoring, which is the failure this leg exists for.
_none_branch = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and "_ctype" in ast.unparse(n.test)
                and any("no_catalogue_component" in ast.unparse(c)
                        for c in n.body)]
check("and that emit sits on the branch where derive_card_type returned None",
      bool(_none_branch),
      "the remedy is reachable without the determination having failed")
# THE TWO REASONS STAY DISTINGUISHED. A copy fault routed to authoring spends a
# render round-trip on a hero that is six words long.
# THE BRANCH, NOT THE WORD. `hero_too_long` and `HERO_TOO_LONG` each appear
# twice in the app — in the skip, the tally and the code field — so presence
# says nothing about whether the DISTINCTION is actually made, and
# smoke_legs_are_unambiguous rejected the leg for exactly that. Read the
# conditional that produces the code instead.
_two_codes = [n for n in _skip_emits
              if any(isinstance(k, ast.Constant) and k.value == "code"
                     and isinstance(v, ast.IfExp)
                     and "hero_too_long" in ast.unparse(v)
                     and "no_catalogue_component" in ast.unparse(v)
                     for k, v in zip(n.args[0].keys, n.args[0].values))]
check("a copy fault is NOT routed to authoring — the code is CHOSEN between "
      "the two reasons derive_card_type returns None", bool(_two_codes),
      "offering authoring for a too-long hero spends a render on a copy edit")

# ── REASON 3, now closed: SYSTEM routes to it ───────────────────────────────
_sys = src[src.index("SYSTEM = "):src.index("_KNOWLEDGE_SYSTEM")]
check("SYSTEM names author_component at all", "author_component" in _sys,
      "it appeared ZERO times — the manual existed for a task nobody was told "
      "to begin")
check("SYSTEM names the condition that triggers it",
      "no_catalogue_component" in _sys,
      "routing to a tool without naming when is how cutaway ruled zero")
check("it is framed as a RESPONSE, not a standing invitation",
      "NOT a standing invitation" in _sys,
      "authoring on any beat is a render round-trip each, against E1-E4")
check("and it says when NOT to author",
      "Do not author when a catalogue component would do" in _sys,
      "an offer with no boundary becomes the default")

# REASON 1 STANDS AND IS STATED, not quietly closed. The enum still cannot
# express 'the catalogue has none' — the trigger is a harness determination
# reported back, not a ruling the agent makes. That is deliberate: a treatment
# value meaning 'author' invites it on any beat.
check("the trigger remains DERIVED rather than a ruling the agent can make",
      all(not any(v in ("author", "custom", "new_component") for v in vals)
          for _ln, vals in _enums),
      "if this ever fails, someone added an author treatment and the cost model "
      "changed with it")

print()
if fails:
    print("AUTHORING-REACHABLE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("AUTHORING-REACHABLE: PASS — the catalogue's own failure is now named, "
      "carries the hero and a remedy, and is ledgered for counting")
