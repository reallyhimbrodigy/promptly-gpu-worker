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


src = open(A.__file__, encoding="utf-8").read()

# ── 1. NO RATE ON ANY SURFACE THE AGENT READS ───────────────────────────────
# The agent sees exactly two cached surfaces: the system prompt and the tool
# schemas. A rate on either is a target, whatever the surrounding words say.
_i, _j = src.index("SYSTEM = "), src.index("_KNOWLEDGE_SYSTEM")
SURFACES = {
    "system prompt": src[_i:_j],
    "tool schemas": json.dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS)),
}
RATE = r"/25\s?s|per[ _]25s|density is a FLOOR|rule to it"
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
check("the excuse channel is gone from the arithmetic too",
      "reasons" not in
      list(__import__("inspect").signature(A.spec_shortfall).parameters),
      "spec_shortfall still takes reasons — an excuse channel needs a demand "
      "to be excused from, and there is none")

check("the floor-only schema fields are gone",
      '"accept_shortfall": {' not in src and '"shortfall_reasons": {' not in src,
      "both existed only so the agent could discharge a floor")

# ── 4. THE GRADING HALF SURVIVES ────────────────────────────────────────────
# Removing the demand must not remove the measurement — otherwise the rubric
# stops answering the question it is FOR.
check("the corpus rates are still defined", bool(A.REFERENCE_PER_25S))
check("the no-speech corpus is still defined", bool(A.REFERENCE_PER_25S_NOSPEECH))
check("spec_shortfall is still computed", callable(getattr(A, "spec_shortfall", None)),
      "the grading question — is this in the plausible range — is still worth "
      "asking; it is just not asked OF the agent")
check("the shortfall is still ledgered",
      'led["spec_shortfall"] = _short' in src)
check("rate regimes are still classified",
      "rate_regimes" in src and callable(getattr(A, "rate_regime", None)))
check("the family mix still reports density against reference",
      "FAMILY MIX" in src)

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
