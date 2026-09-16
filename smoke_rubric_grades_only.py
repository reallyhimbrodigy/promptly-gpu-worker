#!/usr/bin/env python3
"""SMOKE: the density rubric GRADES. It never reaches the agent as a demand.

THE RULING (2026-09-07): the reference rates are a grading instrument only. They
must never reach the agent as a target, appear in the prompt, or be enforced as a
floor at ruling time. The agent places components where they fit; the rubric asks
AFTERWARDS whether the result is in the plausible range. A run that places two
zooms because two moments deserved them is correct, and a rubric that calls it
short is the rubric's problem.

WHAT WAS ENFORCING A RATE, all removed:
  spec_shortfall_unresolved   a CONTRACT failure for density below the spec
  spec_family_built_zero      a CONTRACT failure for a family that built none
  spec_targets_all_zero       the inverse floor — a demand that the spec ask
  execute_plan's refusal      "rulings fall short of your own spec … rule more
                              beats for those families"
  out["fix_shortfall"]        "your rulings do not reach them"
  accept_shortfall            a schema field whose only purpose was discharging
  shortfall_reasons           the floor, per beat
  five prompt statements      corpus rates quoted at the agent as reference

WHAT STAYS, because it is the grading half and was never the problem:
  REFERENCE_PER_25S / _NOSPEECH   the corpus rates themselves
  rate_regimes, spec_shortfall    computed and ledgered
  the FAMILY MIX report           density against reference, after the fact
"""
import ast
import json
import re
import sys
import types

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = open(A.__file__, encoding="utf-8").read()

# ── 1. NO RATE ON ANY SURFACE THE AGENT READS ───────────────────────────────
# The agent sees exactly two cached surfaces: the system prompt and the tool
# schemas. A rate on either is a target, whatever the surrounding words say.
# EVERY PROMPT CONSTANT, DERIVED — not a hand-cut slice.
#
# THE MISS THIS FIXES, found by Builder-1 on my own output. I defined the
# "system prompt" surface as src[SYSTEM : _KNOWLEDGE_SYSTEM] — a slice ENDING at
# the second prompt block, so _KNOWLEDGE_SYSTEM was never read at all. It still
# carried "Overlay text is the WORKHORSE (~7.5 per 25s) ... RARE (~0.5 per 25s)",
# and I reported "system prompt rate-as-demand: NONE" with that block outside
# the window I was looking through. The claim was true of what I measured and
# false of what I said I measured.
#
# It also would have survived being caught: prose that DESCRIBES a rate reads as
# harmless beside a schema field that DEMANDS one, and the ruling bans both —
# a rate must not "reach the agent as a target, APPEAR IN THE PROMPT, or be
# enforced as a floor". Appearing is the clause.
#
# Derived by suffix so a prompt block added tomorrow is covered by this check
# without anyone remembering to add it.
_PROMPT_CONSTS = {n: v for n, v in vars(A).items()
                  if isinstance(v, str) and (n == "SYSTEM" or n.endswith("SYSTEM"))}
check("every prompt constant is found by the derivation",
      len(_PROMPT_CONSTS) >= 2,
      f"found {sorted(_PROMPT_CONSTS)} — a hand-cut window is what let a rate "
      f"through last time")
SURFACES = dict(_PROMPT_CONSTS)
SURFACES["tool schemas"] = json.dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
# CATCHES THE PROSE FORM TOO. "~7.5 per 25s" is not a demand and was never
# meant as one; it is still a rate appearing in the prompt, which is what the
# ruling forbids. A pattern tuned only to demands is how it survived.
RATE = r"/25\s?s|per[ _]25s|density is a FLOOR|rule to it|~?[0-9.]+\s*per\s*25"
for _name, _text in SURFACES.items():
    _hits = re.findall(RATE, _text)
    check(f"no per-25s rate reaches the agent via the {_name}",
          not _hits,
          f"{len(_hits)} occurrence(s): {sorted(set(_hits))} — a rate the agent "
          f"can read is a rate the agent will try to hit")

# ── 2. NO CONTRACT FAILURE ENFORCES A RATE ──────────────────────────────────
for _kind in ("spec_shortfall_unresolved", "spec_family_built_zero",
              "spec_targets_all_zero"):
    check(f"{_kind} no longer fails the round",
          _kind not in A.CONTRACT_FAILURES,
          "density below a reference rate is an observation about the edit, "
          "not a defect in it")
# Non-vacuity: the frozenset must still carry the failures that are about the
# OUTPUT rather than about density, or this check is passing on an empty set.
for _kind in ("wrong_resolution", "no_output", "placement_inert",
              "alpha_layer_empty"):
    check(f"{_kind} still fails the round — this check is not vacuous",
          _kind in A.CONTRACT_FAILURES)

# ── 2b. AND THE BEHAVIOUR, NOT ONLY THE MEMBERSHIP ──────────────────────────
# THE FALSE GREEN THIS REPLACES. Section 2 asks whether a name is in
# CONTRACT_FAILURES, and for these two that question was IRRELEVANT: both were
# appended to the violation list straight from the ledger, never consulting the
# frozenset at all. I removed both names, section 2 went green, and both were
# still failing rounds. Membership is a proxy; CALL THE FUNCTION.
_OK_FINAL = {"exists": True, "width": 1080, "height": 1920, "audio": True}
for _label, _led in (
        ("a family below its implied count",
         {"failures": [], "final_inspect": _OK_FINAL,
          "spec_shortfall": {"sfx": {"direction": "absent"},
                             "zoom": {"direction": "over"}}}),
        ("a spec whose rates imply zero placements",
         {"failures": [], "final_inspect": _OK_FINAL,
          "spec_implies_nothing": True}),
        ("both at once",
         {"failures": [], "final_inspect": _OK_FINAL,
          "spec_implies_nothing": True,
          "spec_shortfall": {"text": {"direction": "under"}}})):
    _v = A._contract_violations(_led)
    check(f"{_label} produces NO contract violation", _v == [],
          f"{_v} — the rubric is still refusing, whatever CONTRACT_FAILURES says")
# NON-VACUOUS: the same function must still report a real defect in the artifact.
_bad = A._contract_violations(
    {"failures": [], "final_inspect": dict(_OK_FINAL, width=1920, height=1080)})
check("_contract_violations still catches a real defect — not vacuous",
      any("wrong_resolution" in c for c in _bad),
      f"{_bad} — the violation path has been disabled, not narrowed")

# ── 3. NOTHING REFUSES OR NAGS ON DENSITY ───────────────────────────────────
# SEARCHED IN STRING LITERALS, NOT IN THE SOURCE TEXT. The first version greped
# `src` and failed on the COMMENT that documents the removal — a substring test
# cannot tell a comment from a live string, and only strings can reach the
# agent. Ninth instance of that trap in this port; the AST does not have
# comments in it at all, which is exactly why it is the right reader.
_STRINGS = [n.value for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
_alltext = "\n".join(_STRINGS)
check("this smoke actually found the module's strings",
      len(_STRINGS) > 500, f"only {len(_STRINGS)} — the walk is not reaching them")
for _phrase, _why in (
        ("rulings fall short of your own spec", "execute_plan refusing on density"),
        ("rule more beats for those families", "telling the agent to hit a rate"),
        ("SPEC_SHORTFALL", "the shortfall returned in a tool result"),
        ("fix_shortfall", "a fix-the-density instruction to the agent")):
    check(f"no live string carries {_why}",
          _phrase not in _alltext,
          f"{_phrase!r} is still in a string the agent can receive")
# RETIRED FIELDS, AND THE GENERIC CHECK THAT FOUND ONE.
#
# My first pass listed four phrases and greped for them. It missed a LIVE string
# — the second-execute refusal told the agent "call rule_all_beats ONCE more
# with shortfall_reasons naming the declined beats", pointing at a schema field
# I had just deleted and at the density remedy the ruling retires. A hand-listed
# phrase set only ever catches the phrases you thought of.
#
# The generic form: an instruction string may only name fields that EXIST. Build
# the vocabulary from the schemas themselves, then read every string that tells
# the agent to call a tool and require each snake_case token in it to be a real
# field or a real tool.
_VOCAB, _NAMES = set(), {t["name"] for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS)}


def _collect(sch):
    if not isinstance(sch, dict):
        return
    for _k, _v in (sch.get("properties") or {}).items():
        _VOCAB.add(_k)
        _collect(_v)
    for _key in ("items", "additionalProperties"):
        _collect(sch.get(_key))


for _t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS):
    _collect(_t.get("input_schema") or {})
# WHOLE WORDS. The first version matched tool names as substrings and flagged 51
# innocent strings — `build_cut_calls` contains the tool `build_cut`. Same trap
# as the comment one, two checks apart.
_CALL = re.compile(r"\bcall (?:%s)\b" % "|".join(sorted(_NAMES)))
_TOK = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_instr = [n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.Constant) and isinstance(n.value, str)
          and len(n.value) >= 40 and _CALL.search(n.value)]
# NON-VACUITY, stated as a denominator rather than assumed. Two strings tell the
# agent to call a tool; if that ever reads zero the check below is passing on an
# empty set and proves nothing.
check("the instruction-string check has strings to read",
      len(_instr) >= 2, f"only {len(_instr)} — nothing is being checked")
for _n in _instr:
    _unknown = sorted({t for t in _TOK.findall(_n.value)
                       if t not in _VOCAB and t not in _NAMES})
    check(f"the instruction at line {_n.lineno} names only fields that exist",
          not _unknown,
          f"{_unknown} — a field the schema does not have. The agent cannot "
          f"supply it, so the instruction is either dead or a demand for "
          f"something that was removed")

# The two the ruling retired, by name, on every surface.
for _f in ("accept_shortfall", "shortfall_reasons"):
    check(f"{_f} is gone from the schemas", _f not in _VOCAB,
          "it existed only so the agent could discharge a density floor")
    check(f"{_f} is named in no live string", _f not in _alltext,
          "a removed field still quoted at the agent is an instruction it "
          "cannot follow")
# THE ARITHMETIC ITSELF IS GONE, 2026-09-15, and that is a STRONGER form of
# the same property. The leg here used to assert `spec_shortfall` no longer
# took a `reasons` argument — the excuse channel — which was correct while the
# shortfall was still computed. The sweep that removed `targets` removed the
# shortfall too, so there is no signature left to inspect. Written against the
# property rather than the decision: nothing anywhere computes a per-family
# shortfall against a rate, whether or not it offers an excuse for one.
for _gone in ("spec_shortfall", "family_regimes", "spec_implies_nothing"):
    check(f"{_gone} is gone from the module",
          not hasattr(A, _gone),
          "a shortfall is a demand wearing a measurement's clothes; the "
          "grading that survives is the FAMILY MIX report, which states what "
          "was placed and never what was owed")

check("the floor-only schema fields are gone",
      '"accept_shortfall": {' not in src and '"shortfall_reasons": {' not in src,
      "both existed only so the agent could discharge a floor")

# ── 4. THE GRADING HALF SURVIVES ────────────────────────────────────────────
# Removing the demand must not remove the measurement — otherwise the rubric
# stops answering the question it is FOR.
check("the corpus rates are still defined", bool(A.REFERENCE_PER_25S))
check("the no-speech corpus is still defined", bool(A.REFERENCE_PER_25S_NOSPEECH))
# WHAT SURVIVES IS THE REPORT, NOT THE ARITHMETIC. The grading question — is
# this in the plausible range — is still worth asking, and the FAMILY MIX line
# is where it is asked, of a human reading a round. It states what was placed
# beside what the corpus placed; it computes no shortfall and issues no verdict.
check("the corpus rates are still defined for the report",
      bool(A.REFERENCE_PER_25S))
check("the family mix still reports density against reference",
      "FAMILY MIX" in src)
# AND IT IS A REPORT, NOT A VERDICT — asked of CODE, not of text. The names
# survive in comments on purpose (a note that records why something went is the
# thing the next reader needs); what must not survive is a live read or write.
import ast as _ast                                               # noqa: E402
_dead = []
for _n in _ast.walk(_ast.parse(src)):
    if isinstance(_n, _ast.Constant) and isinstance(_n.value, str) \
            and _n.value in ("spec_shortfall", "rate_regimes",
                             "spec_shortfall_unresolved"):
        _dead.append(_n.value)
    if isinstance(_n, _ast.Name) and _n.id in ("spec_shortfall",
                                               "rate_regimes",
                                               "family_regimes"):
        _dead.append(_n.id)
check("and it is a REPORT, not a verdict", not _dead,
      "these names are still LIVE in the app (%s) — a regime label and a "
      "shortfall are both the rubric instructing, and the ruling was that it "
      "grades and never instructs" % sorted(set(_dead)))

# ── 5. AND A ZERO IS A REAL ANSWER ──────────────────────────────────────────
# The clearest expression of the ruling: a family that placed nothing must be
# reportable without anything calling it a defect.
_zero_fails = [k for k in A.CONTRACT_FAILURES
               if "zero" in k or "shortfall" in k]
check("no contract failure is about a family placing zero",
      not _zero_fails,
      f"{_zero_fails} — zero placements of a family is an editorial answer")

if fails:
    print(f"RUBRIC-GRADES-ONLY: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RUBRIC-GRADES-ONLY: PASS")
