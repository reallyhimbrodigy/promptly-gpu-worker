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

import modal_stub                                         # noqa: E402
modal_stub.install()
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
# card_hero IS THE WHOLE CARD CONTRACT NOW, and must say REQUIRED like the
# field it is modelled on. Removing card_type and card_props left it carrying
# everything while still described as one optional field among several — a gap
# my own change created.
_ch = __import__("json").loads(_schema)
_hero_desc = ""
def _find(o):
    global _hero_desc
    if isinstance(o, dict):
        for _k, _v in o.items():
            if _k == "card_hero" and isinstance(_v, dict):
                _hero_desc = _v.get("description", "")
            _find(_v)
    elif isinstance(o, list):
        for _v in o:
            _find(_v)
_find(_ch)
check("card_hero says REQUIRED, like zoom_arc", "REQUIRED" in _hero_desc,
      f"{_hero_desc[:80]!r} — it is now the ONLY thing the agent says about a "
      f"card, and the field it is modelled on has said REQUIRED since it shipped")
check("and says the component is derived from it",
      "derived" in _hero_desc and "zoom_arc" in _hero_desc,
      "the agent has to know the phrase decides the component, or it will treat "
      "card_hero as decoration")

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

# ── 6. CARD AND TEXT ARE NOT ALTERNATIVES ───────────────────────────────────
# Zac, 2026-09-09. The derivation removed the 29-way pick; it did NOT address
# the miss, because the card path is gated on the AGENT's treatment and round 45
# ruled those beats ['text','zoom'] with no card at all. The agent was treating
# card and text as competing answers to one beat. The reference does both — a
# counter AND a caption — and round 42 did too, ruling
# ['text','card','zoom','sfx'] on the very beats round 45 captioned.
#
# ONE SENTENCE, on both surfaces the agent reads, and it removes no judgement:
# the beat still has to be worth stamping, and that call stays the agent's.
_SURF = {"system prompt": src[src.index("SYSTEM = "):src.index("_KNOWLEDGE_SYSTEM")],
         "tool schemas": __import__("json").dumps(
             list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))}
for _name, _text in _SURF.items():
    check(f"the {_name} says card and text are not alternatives",
          "not alternatives" in _text.lower() or "NOT alternatives" in _text,
          "the agent chose between them run to run — 'the headline stat' carded "
          "in r42, 'the headline win' captioned in r45, same beat, same figure")
    check(f"the {_name} says which carries what",
          "carries the words" in _text and "carries the number" in _text,
          "without the division it reads as a licence to double up rather than "
          "a split of duties")
# IT MUST NOT BECOME A FLOOR. "takes BOTH" is CONDITIONAL on the beat being
# worth stamping; an unconditional form would be the density ruling undone.
for _text in _SURF.values():
    check("the sentence carries no rate", "/25" not in _text and "per 25" not in _text)
# The condition must be IN the sentence. My first version asked whether the
# surface contained "every beat" anywhere and "card" anywhere — and the prompt
# says "Rule on EVERY beat" for unrelated reasons, so it flagged prose that has
# nothing to do with cards. Read the sentence, not the surface.
for _name, _text in _SURF.items():
    _i = _text.lower().find("not alternatives")
    _sentence = _text[max(0, _i - 200):_i + 400] if _i >= 0 else ""
    check(f"the {_name}'s sentence is CONDITIONAL, not a floor",
          "worth stamping" in _sentence or "quotes a" in _sentence,
          "an unconditional 'card every beat' is a density demand, which is the "
          "thing Zac's rubric ruling removed")

# ── 7. NO GATE DEMANDS A FIELD THE SCHEMA NO LONGER OFFERS ──────────────────
# THE DEFECT THIS EXISTS FOR. b13730c removed card_type from the schema and the
# beat_verdict ACCEPTANCE GATE kept demanding it. The agent could not supply it,
# was rejected, and re-ruled the same beat identically about five times — round
# 47's control shows that loop on three beats.
#
# I removed the field and left the gate asking for it. Mirror of the
# card_props_mismatch orphan: there a NAME with no producer, here a DEMAND with
# no supply. Both are invisible until something tries to satisfy them.
# PER TOOL, NOT ACROSS THE UNION. My first version collected `properties` from
# every tool into ONE flat set and compared the gate's demands against that. A
# field offered by rule_all_beats and MISSING from beat_verdict passes such a
# check — the union contains it — while every ruling made through the repair
# path is rejected forever for a field it cannot send.
#
# Builder-1 found exactly that in their tree: beat_verdict offers the full
# treatment enum and NONE of text_content, zoom_arc or cutaway_from_s. Three
# fields wide, on the path whose whole job is to fix a rejected ruling, and 22
# rejections logged on one fixture in round 47.
#
# Checking the union is the "wrong collection is indistinguishable from checking
# nothing" failure this repo already has on record — smoke_five_families read
# TOOLS and never saw that place_cutaway lived in KNOWLEDGE_TOOLS.
def _props_of(tool):
    _out = set()

    def _w(o):
        if isinstance(o, dict):
            for _k, _v2 in o.items():
                if _k == "properties" and isinstance(_v2, dict):
                    _out.update(_v2.keys())
                _w(_v2)
        elif isinstance(o, list):
            for _v2 in o:
                _w(_v2)

    _w(tool.get("input_schema") or {})
    return _out


def _rules_verdicts(tool):
    """Does this tool let the agent rule a TREATMENT? Then the gate applies."""
    _hit = [False]

    def _w(o):
        if isinstance(o, dict):
            if o.get("type") == "array" and isinstance(o.get("items"), dict):
                if "card" in (o["items"].get("enum") or []):
                    _hit[0] = True
            for _v2 in o.values():
                _w(_v2)
        elif isinstance(o, list):
            for _v2 in o:
                _w(_v2)

    _w(tool.get("input_schema") or {})
    return _hit[0]


_verdict_tools = [t for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS)
                  if _rules_verdicts(t)]
check("at least one tool rules verdicts", _verdict_tools,
      "the per-tool check below would be vacuous")

# SCOPED TO THE ACCEPTANCE PATH, not the whole module. Walking every
# `_v.get(...)` in the file collected `_v.get('b')`, `_v.get('t')` and
# `_v.get('c')` from an unrelated reporting line 800 lines away that happens to
# bind the same name — and reported them as fields the schema fails to offer.
# Scope is not text, in my own check this time.
# Bounded by the gate's own lines: from the verdict-acceptance branch to the
# rejection it appends. Scoping by ENCLOSING FUNCTION was not enough — the gate
# lives inside `edit`, which is 3,000 lines and contains the stranger.
# THE BOUND IS NOW THE FUNCTION ITSELF. The note above says scoping by
# enclosing function was not enough because the gate lived inside `edit` — that
# is fixed at the source: the gate is `half_ruling_refusal`, a named pure
# function, so there is no stranger to exclude and no line window to drift.
_gate_fn = next((_n for _n in ast.walk(tree) if isinstance(_n, ast.FunctionDef)
                 and _n.name == "half_ruling_refusal"), None)
check("the acceptance gate was located", _gate_fn is not None,
      "half_ruling_refusal is gone — without it the gate is inline again and "
      "this walks the whole module reporting strangers as schema fields")
_demanded = set()
for _n in (ast.walk(_gate_fn) if _gate_fn else []):
    if (isinstance(_n, ast.Call) and getattr(_n.func, "attr", "") == "get"
            and getattr(getattr(_n.func, "value", None), "id", "") == "v"
            and _n.args and isinstance(_n.args[0], ast.Constant)
            and isinstance(_n.args[0].value, str)):
        _demanded.add(_n.args[0].value)
check("the gate's demands were found", len(_demanded) >= 2, sorted(_demanded))
check("and they are real field names, not strangers from another scope",
      all(len(_f) > 2 for _f in _demanded), sorted(_demanded))

for _t in _verdict_tools:
    _offered = _props_of(_t)
    _orphaned = sorted(_demanded - _offered - {"beat"})
    check(f"{_t['name']} offers every field the gate demands",
          not _orphaned,
          f"{_orphaned} — this tool can rule a treatment and cannot supply "
          f"what the gate then requires, so every such ruling is rejected and "
          f"re-ruled identically until the turn budget absorbs it")

_retired = {"card_type", "card_props"}
check("no acceptance gate reads a retired field",
      not sorted(_demanded & _retired),
      f"{sorted(_demanded & _retired)} — the schema does not offer these")
check("the gate asks for card_hero, which every verdict tool offers",
      "card_hero" in _demanded
      and all("card_hero" in _props_of(_t) for _t in _verdict_tools))
# ASKED OF THE AST, not of the gate's old local variable names. This matched
# `_ct6, _dw6 = derive_card_type(` — names that existed only while the gate was
# inline — so extracting the gate would have silently un-checked it while the
# property still held. A check pinned to a variable name is pinned to nothing.
_gate_calls = {getattr(_n.func, "id", "") for _n in
               (ast.walk(_gate_fn) if _gate_fn else [])
               if isinstance(_n, ast.Call)}
check("and it uses the SAME derivation as the builder",
      "derive_card_type" in _gate_calls,
      "a gate that accepts what the builder refuses is a second opinion nobody "
      "asked for")

if fails:
    print(f"CARD-DERIVED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CARD-DERIVED: PASS — the three missed moments derive StatCard/PullQuote, "
      "props follow the type, and the 29-name enum is gone")
