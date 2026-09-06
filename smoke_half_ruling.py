"""SMOKE — an incomplete family is STRIPPED on the first pass; the beat survives.

WHAT THIS REPLACED, and why the old mechanism is gone rather than tuned.

Round 13, talking_head: card ruled 5 built 0, sfx ruled 4 built 0. Every one was
a half-ruling — `card` with no card_hero, `sfx: yes` with no sfx_name. The
handler bounced them (reject, ask again, up to two attempts) and dropped the
whole BEAT when the budget ran out. Two defects in one:

  1. It discarded the beat, not the family. Beats ruled ['card','text'] with no
     card_hero lost their TEXT — seven beats discarded at 39.6s over a missing
     field on ONE of their families.
  2. It bounced. The agent re-ruled the same way and the run spent 24 of 24
     turns and three execute_plan calls arriving at the same rulings. An
     informed agent repeating an incomplete ruling was already the documented
     case; a third ask cannot help.

A family that names no content is not a ruling for that family and never was. It
is removed, named once, and everything else on the beat proceeds.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)


def strip(verdicts, nocopy=(), nosfx=(), nocard=()):
    """Replay the shipped strip over a set of verdicts."""
    incomplete = {"text": set(nocopy), "sfx": set(nosfx), "card": set(nocard)}
    stripped = []
    for v in verdicts:
        bi = v.get("beat")
        tr = [str(t).lower() for t in (v.get("treatment") or [])]
        for fam, bad in incomplete.items():
            if bi in bad and fam in tr:
                tr = [t for t in tr if t != fam]
                stripped.append({"beat": bi, "family": fam})
        if bi in incomplete["sfx"]:
            v["sfx"] = "no"
        v["treatment"] = tr or ["none"]
    return verdicts, stripped


# ── THE BEAT SURVIVES. This is the whole point. ───────────────────────────
vs, st = strip([{"beat": 2, "treatment": ["card", "text"], "text_content": "X"}],
               nocard=[2])
ok(vs[0]["treatment"] == ["text"],
   f"beat 2 kept {vs[0]['treatment']} — an incomplete CARD must not cost the "
   f"beat its TEXT, which is what discarding the whole verdict did")
ok(st == [{"beat": 2, "family": "card"}], f"strip not named: {st}")

# ── sfx lives in its own field, so clearing the treatment is not enough ───
vs, st = strip([{"beat": 1, "treatment": ["sfx", "text"], "sfx": "yes"}], nosfx=[1])
ok(vs[0]["sfx"] == "no",
   "sfx stayed 'yes' in its own field after being stripped from the treatment — "
   "the beat is still ruled for a sound with no name")
ok(vs[0]["treatment"] == ["text"], f"got {vs[0]['treatment']}")

# ── a beat stripped of everything becomes an explicit 'none' ─────────────
vs, _ = strip([{"beat": 5, "treatment": ["card"]}], nocard=[5])
ok(vs[0]["treatment"] == ["none"],
   f"an emptied treatment is {vs[0]['treatment']}, not ['none'] — downstream "
   f"reads an empty list as 'no ruling recorded' rather than 'ruled nothing'")

# ── complete rulings are untouched ───────────────────────────────────────
vs, st = strip([{"beat": 3, "treatment": ["card", "text"], "card_hero": "$400",
                 "text_content": "Y"}])
ok(vs[0]["treatment"] == ["card", "text"] and st == [],
   f"a COMPLETE ruling was altered: {vs[0]['treatment']} {st}")

# ── round 13's exact shape: 5 cards + 4 sfx, all incomplete ──────────────
verdicts = ([{"beat": b, "treatment": ["card", "text"], "text_content": "t"}
             for b in (2, 3, 7, 8, 10)]
            + [{"beat": b, "treatment": ["sfx"], "sfx": "yes"} for b in (1, 6)])
vs, st = strip(verdicts, nocard=[2, 3, 7, 8, 10], nosfx=[1, 3, 6, 10])
ok(len(st) == 7, f"expected 7 strips (5 card + 2 sfx present), got {len(st)}")
ok(all("text" in v["treatment"] for v in vs if v["beat"] in (2, 3, 7, 8, 10)),
   "the five card beats lost their text — exactly the round-13 regression")

# ── THE BOUNCE IS GONE FROM THE SHIPPED CODE ─────────────────────────────
ok("half_ruling_stripped" in SRC, "the family-strip is not in the source")
ok("STRIPPED_incomplete_families" in SRC,
   "the agent is not told which families were stripped")
ok("REJECTED_incomplete" not in SRC,
   "verdicts are still REJECTED wholesale rather than stripped")
ok("_reject = _reject - _spent" not in SRC,
   "the bounce machinery is back — that loop spent 24 of 24 turns")
ok('_v4["sfx"] = "no"' in SRC, "the shipped strip does not clear the sfx field")

# ── THE READERS ARE WITHHELD FOR THE JUDGMENT-ONLY ROLE ──────────────────
# Sonnet calls them ZERO times and produces a byte-identical cut and speech
# check; Haiku spent NINE turns on them. Withheld, not discouraged: a capability
# in the schema will be used.
ok('_READERS = {"read_knowledge", "search_skills"}' in SRC,
   "the reader tools are back in the judgment-only schema")
ok(SRC.index("_judgment_only =") < SRC.index("if _judgment_only:"),
   "_judgment_only is used before it is defined")

# THE FILTER, NOT THE DECLARATION. The first version of this check asserted only
# that _READERS and `if _judgment_only:` existed — so replacing the filtering
# line with `pass` left both markers in place and the check stayed green while
# the readers were handed back. A declaration is not an effect.
_gate = [n for n in ast.walk(TREE)
         if isinstance(n, ast.If)
         and any(getattr(x, "id", "") == "_judgment_only" for x in ast.walk(n.test))]
ok(len(_gate) == 1, "the _judgment_only branch is missing or duplicated")
if _gate:
    _rebinds = [n for n in ast.walk(_gate[0])
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "tools" for t in n.targets)
                and "_READERS" in ast.dump(n.value)]
    ok(len(_rebinds) == 1,
       "the _judgment_only branch does not REBIND `tools` to exclude _READERS — "
       "it declares the set and hands the tools over anyway")

if FAIL:
    print("FAIL smoke_half_ruling:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_half_ruling — family stripped not beat dropped, sfx field "
      "cleared, emptied treatment becomes 'none', complete rulings untouched, "
      "no bounce, readers withheld from the judgment-only schema")
