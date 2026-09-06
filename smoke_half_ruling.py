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


# ══════════════════════════════════════════════════════════════════════════
# DERIVED FLOORS. The agent's value wins; derivation only fills what it left
# empty, and only where the answer is in the data.
#
# Round 13 built ZERO cards and ZERO sfx from 5 and 4 rulings — every one named
# the family and omitted its content. Stripping is right for a card nobody can
# name; it is wrong for a card on a beat whose own words carry the number.
# ══════════════════════════════════════════════════════════════════════════
_ns = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "") == "_SFX_BY_ROLE":
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name in ("_derive_card_hero", "_derive_sfx_name"):
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
ok("_derive_card_hero" in _ns and "_derive_sfx_name" in _ns,
   "the derivation helpers are not defined at module level")

if "_derive_card_hero" in _ns:
    hero, sfxn = _ns["_derive_card_hero"], _ns["_derive_sfx_name"]

    NUMS = [{"t": 9.4, "word": "$400"}, {"t": 17.2, "word": "30,000"}]
    NUMBER_BEAT = {"i": 1, "t_start": 8.0, "t_end": 12.0, "has_number": True}
    PLAIN_BEAT = {"i": 4, "t_start": 20.0, "t_end": 24.0, "has_number": False}
    HOOK = {"i": 0, "t_start": 0.0, "t_end": 3.0, "role": "hook"}
    CLOSE = {"i": 9, "t_start": 30.0, "t_end": 34.0, "role": "close"}

    # 1. a card without a hero ON A NUMBER BEAT builds with the number
    ok(hero(NUMBER_BEAT, NUMS) == "$400",
       f"a card on a beat carrying '$400' derived {hero(NUMBER_BEAT, NUMS)!r} — "
       f"the hero is in the beat's own words")

    # 2. on a NON-number beat there is nothing to derive: stripped and named
    ok(hero(PLAIN_BEAT, NUMS) is None,
       f"a card on a beat with NO number derived {hero(PLAIN_BEAT, NUMS)!r} — "
       f"inventing a hero is exactly the fallback this must not be")

    # only numbers INSIDE the beat count
    ok(hero({"i": 2, "t_start": 0.0, "t_end": 5.0}, NUMS) is None,
       "a number outside the beat's own span was used as its hero")

    # 3. sfx yes on a HOOK with no name builds with the hook file
    ok(sfxn(HOOK) == "swoosh-sound-effects",
       f"a hook derived {sfxn(HOOK)!r} — the catalogue calls swoosh 'the safe "
       f"motion cue, any vibe', and Sonnet chose it unprompted at the hook")
    ok(sfxn(CLOSE) == "boom",
       f"a close derived {sfxn(CLOSE)!r} — boom is 'the payoff line the whole "
       f"video was built to deliver'")
    ok(sfxn({"i": 5, "role": "evidence"}) is None,
       "a mid-video role derived a sound — only hook and close are answered by "
       "the corpus (64% of SFX), the rest is not derivable")
    ok(sfxn({"i": 5}) is None and sfxn(None) is None,
       "a beat with no role derived a sound")

    # THE AGENT'S VALUE WINS. Derivation must never overwrite.
    _src_seg = SRC[SRC.index("# DERIVE BEFORE STRIPPING"):]
    _seg = _src_seg[:_src_seg.index("_incomplete = {")]
    ok('not str(_v5.get("card_hero") or "").strip()' in _seg,
       "derivation does not check that card_hero is EMPTY first — it would "
       "overwrite the agent's own hero")
    ok('not str(_v5.get("sfx_name") or "").strip()' in _seg,
       "derivation does not check that sfx_name is EMPTY first")

    # AND THE STRIP MUST BE RECOMPUTED AFTER. A field just filled is no longer
    # missing; stripping on the stale list would discard the floor.
    _after = SRC.index("Recompute AFTER derivation")
    ok(_after > SRC.index("# DERIVE BEFORE STRIPPING"),
       "the incomplete lists are not recomputed after derivation — a derived "
       "field would be stripped immediately after being filled")

if FAIL:
    print("FAIL smoke_half_ruling (derivation):")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok derivation — hero from the beat's own number, stripped when there is "
      "none, sfx from hook/close role, agent values never overwritten, strip "
      "recomputed after")
