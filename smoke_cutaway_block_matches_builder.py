#!/usr/bin/env python3
"""The cutaway prompt block advertises exactly what cutaway_plan accepts.

WHEN WE ADVERTISE A SHAPE, THE ACCEPTOR MUST TAKE THE SHAPE WE ADVERTISED —
and this is the family that proved the rule three times in one week. card_props
described a shape reachable only by spending a read_knowledge turn and THREE
ROUNDS BUILT ZERO CARDS. `_asset_inventory.json` advertised sfx names WITH
extensions while place_sfx stripped the dot, and 2 of 4 ruled sfx were lost to
a name the agent had been SHOWN. A refusal that is technically correct still
loses the placement, and it fails silently: the family arrives short, every gate
passes, and the log reads like a judgement the model made.

Cutaway is the family with ZERO prompt mention and ruled=0 for the whole round,
so this block is the first thing the agent will ever be told about it. If the
block states a constraint the builder does not enforce, the agent is being
taught a superstition; if the builder enforces one the block does not state,
every ruling that trips it is a placement lost to a rule nobody published.

THIS CHECK DRIVES THE SHIPPED FUNCTION rather than reading it. Each leg builds a
ruling that exercises one documented behaviour and asserts cutaway_plan does
what the block promises — so the block cannot drift from the acceptor without
this going red.

RED-proven by red_proof_cutaway_block.py.
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


# ------------------------------------------------- the block reaches the agent
_sys = next((n for n in tree.body if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "SYSTEM" for t in n.targets)), None)
check("SYSTEM is a module-level constant", _sys is not None)
_systext = _sys.value.value if _sys and isinstance(_sys.value, ast.Constant) else ""
check("the cutaway block is IN SYSTEM, not behind the knowledge flag",
      "CUTAWAY — SHOW THE THING" in _systext,
      "cutaway is in the treatment enum unconditionally, so a run with the "
      "knowledge block off would rule a family it has never been told about")
_blk = ""
if "CUTAWAY — SHOW THE THING" in _systext:
    _i = _systext.index("CUTAWAY — SHOW THE THING")
    _blk = _systext[_i:_systext.index("HARD RULES", _i)]

# THE RATES GRADE, THEY NEVER INSTRUCT (Zac, 2026-09-08). The reference corpus
# places a cutaway on 72 of 153 beats and that number must not appear here in
# any form — a frequency in a prompt is a target.
import re
check("the block states no rate, frequency or count target",
      not re.search(r"per 25s|/25s|\b\d+ of \d+\b|\b\d+\.\d+ per\b|72\b", _blk),
      "a rate in the prompt is a demand, not a grade")

# ------------------------------------------------- drive the shipped function
_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.FunctionDef) and _n.name in ("cutaway_plan", "source_to_output"):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.Assign) and any(
            getattr(t, "id", "").startswith("_CUTAWAY_") for t in _n.targets):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("cutaway_plan and source_to_output are module-level and drivable",
      "cutaway_plan" in _ns and "source_to_output" in _ns)
if "cutaway_plan" not in _ns:
    print("\nCUTAWAY-BLOCK: FAIL"); sys.exit(1)
_plan = _ns["cutaway_plan"]

# One 20s source kept whole, so output time == source time and the arithmetic
# below is readable.
KEEP = [[0.0, 20.0]]
DUR = 20.0
BEATS = [{"i": 0, "t_start": 0.0, "t_end": 3.0},     # 3.0s, comfortably over
         {"i": 1, "t_start": 10.0, "t_end": 10.3},   # 0.3s, under the floor
         {"i": 2, "t_start": 4.0, "t_end": 12.0}]    # 8.0s, over the cap


def _one(ruling, beats=BEATS, dur=DUR):
    return _plan([ruling], KEEP, dur, beats=beats)


# THE BLOCK SAYS: name a timestamp and it builds.
_p, _r = _one({"beat": 0, "cutaway_from_s": 15.0})
check("a ruling that names a moment outside its own beat BUILDS",
      len(_p) == 1 and not _r, f"plans={_p} rejects={_r}")

# THE BLOCK SAYS: a cutaway without a timestamp is not a ruling.
_p, _r = _one({"beat": 0})
check("no cutaway_from_s is REFUSED and says so",
      not _p and len(_r) == 1 and "named no source moment" in _r[0]["why"], f"{_r}")

# THE BLOCK SAYS: source seconds, and it must fall inside the source.
_p, _r = _one({"beat": 0, "cutaway_from_s": 25.0})
check("a timestamp past the end of the source is REFUSED",
      not _p and "outside the source" in (_r[0]["why"] if _r else ""), f"{_r}")

# THE BLOCK SAYS: it cannot fall inside this beat's own footage.
_p, _r = _one({"beat": 0, "cutaway_from_s": 1.0})
check("a timestamp inside the beat's own footage is REFUSED",
      not _p and "same picture" in (_r[0]["why"] if _r else ""), f"{_r}")

# THE BLOCK SAYS: the beat needs at least 0.6s in the OUTPUT.
_p, _r = _one({"beat": 1, "cutaway_from_s": 16.0})
check("a beat under the 0.6s output floor is REFUSED",
      not _p and "glitch" in (_r[0]["why"] if _r else ""), f"{_r}")
check("the floor the block states IS the floor the builder uses",
      _ns.get("_CUTAWAY_MIN_S") == 0.6, f"{_ns.get('_CUTAWAY_MIN_S')}")

# THE BLOCK SAYS: held for the beat's length, capped at 4.0s.
# 0.0s: the only window that is BEFORE this 8s beat once the 4s cap is
# applied, so the cap is what is under test and not the
# next-footage rule (added 2026-09-10 — a cutaway to 15.0 for a beat ending at
# 12.0 is the footage about to play, which is now refused by name).
_p, _r = _one({"beat": 2, "cutaway_from_s": 0.0})
check("a beat longer than the cap is HELD AT THE CAP, not refused",
      len(_p) == 1 and abs(_p[0]["duration_s"] - 4.0) < 1e-6, f"{_p} {_r}")
check("the cap the block states IS the cap the builder uses",
      _ns.get("_CUTAWAY_MAX_S") == 4.0, f"{_ns.get('_CUTAWAY_MAX_S')}")

# THE BLOCK SAYS: near the end it slides back rather than refusing.
_p, _r = _one({"beat": 0, "cutaway_from_s": 19.0})
check("a moment too near the end SLIDES BACK rather than being refused",
      len(_p) == 1 and _p[0]["src_t1"] <= DUR + 1e-9 and not _r, f"{_p} {_r}")

# THE BLOCK SAYS: a beat you also cut cannot carry one.
_p, _r = _plan([{"beat": 0, "cutaway_from_s": 15.0}], [[5.0, 20.0]], DUR, beats=BEATS)
check("a beat removed by the cut is REFUSED with the reason",
      not _p and "no output span" in (_r[0]["why"] if _r else ""), f"{_r}")

# ------------------- every rejection the builder can emit is a concept we state
_CONCEPTS = {"named no source moment": "cutaway_from_s",
             "not a number of seconds": "timestamp",
             "no such beat": "beat",
             "no output span to cover": "survive the cut",
             "glitch": "0.6s",
             "outside the source": "inside the source",
             # KEYED ON THE PHRASE THAT CARRIES THE RULE, not one nearby.
             # This mapped to "own footage" and a mutation deleting the whole
             # sentence still passed, because the words "beat\'s own footage"
             # survived in the line above it. A concept map that points at
             # incidental wording tests the wording, not the concept.
             "same picture": "shows the same picture"}
# WHITESPACE-NORMALISED, because prose wraps. "this beat\'s own\n  footage"
# does not contain "own footage" as a substring, and a check that goes red when
# someone re-wraps a paragraph is a check that gets weakened rather than
# satisfied. Wrapping is not semantic; the words are.
_flat = " ".join(_blk.lower().split())
_missing = [k for k, v in _CONCEPTS.items() if " ".join(v.lower().split()) not in _flat]
check("every rejection reason the builder emits is published in the block",
      not _missing, f"unpublished: {_missing} — a placement lost to a rule "
                    f"nobody told the agent about")

print()
if fails:
    print("CUTAWAY-BLOCK: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"CUTAWAY-BLOCK: PASS — block is in SYSTEM, states no rate, and all "
      f"{len(_CONCEPTS)} builder rejection reasons are published; 9 behaviours "
      f"driven against the shipped cutaway_plan")
