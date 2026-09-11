#!/usr/bin/env python3
"""SMOKE: every failing leg is reported, and a spec that asks for nothing fails.

TWO FIXES, ONE FAILURE MODE — a scorer that shows less than it knows.

1. ALL LEGS. round_is_green returned on the FIRST failure. Round 24 was red on
   talking_head's unresolved shortfall AND screen_recording's passthrough, and
   reported one; the second surfaced only by re-running the gate by hand with
   the other fixtures stubbed clean. A multi-cause round that reports one cause
   reads as single-cause, and fixing the reported one then reads as fixing the
   round.

2. ZERO-TARGET SPECS. Round 24 screen_recording set text=0.4, card=0.1,
   zoom=0.2 per 25s. Over a 20s source those imply 0, 0 and 0, so spec_shortfall
   honestly found nothing to fall short of, the run built NOTHING, and it
   reported `CONTRACT VIOLATIONS: 0 — none`. A bar the run cannot fail is not a
   bar. Only the passthrough backstop refused it.

   NOT the max(1, ...) floor returning: per-family zero stays legitimate (text
   and sfx are 0.00/25s on the measured no-speech corpus). The check is on the
   TOTAL across families.
"""
import sys, types, json

import modal_stub                                         # noqa: E402
modal_stub.install()

import reliability_gate as rg
import agentic_editor_app as A

fails = []
def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))

OK = {"ok": True, "kept_ratio": 0.7, "placements": 6, "contract_violations": []}
def round_of(**over):
    r = {s: dict(OK) for s in rg.REQUIRED_SOURCES}
    r.update(over)
    return r

# ── 1. ALL LEGS ────────────────────────────────────────────────────────────
srcs = list(rg.REQUIRED_SOURCES)
multi = round_of(**{
    srcs[0]: {**OK, "contract_violations": ["spec_shortfall_unresolved: text"]},
    srcs[1]: {**OK, "kept_ratio": 1.0, "placements": 0},
    srcs[2]: {**OK, "degraded": True},
})
g, why = rg.round_is_green(multi)
check("a multi-cause round is not green", g is False)
check("the FIRST source's leg is reported", srcs[0] in why, why[:200])
check("the SECOND source's leg is reported TOO (not just the first)",
      srcs[1] in why and "PASSTHROUGH" in why,
      "a scorer that stops at the first failure hides the rest")
check("the THIRD source's leg is reported", srcs[2] in why and "degraded" in why)
check("the leg count is stated", "3 failing leg(s)" in why, why[:120])

# ── 2. duplicate violations: counted in full, deduped for display ──────────
dup = round_of(**{srcs[0]: {**OK, "contract_violations": ["same", "same", "same", "other"]}})
_, why_d = rg.round_is_green(dup)
check("duplicates counted honestly", "x4" in why_d, why_d[:160])
check("duplicates deduped for display", "2 distinct" in why_d, why_d[:160])

# ── 3. a genuinely clean round still passes ────────────────────────────────
g2, why2 = rg.round_is_green(round_of())
check("a clean round is still green", g2 is True and why2 == "all five green", why2)

# ── 4. absent source is still not a pass ───────────────────────────────────
miss = round_of(); miss.pop(srcs[0])
g3, why3 = rg.round_is_green(miss)
check("an absent source is not a pass", g3 is False and "NO RESULT" in why3)

# ── 5. ZERO-TARGET SPEC, on the MEASURED round-24 numbers ──────────────────
check("the round-24 screen_recording spec implies nothing",
      A.spec_implies_nothing({"text": 0.4, "card": 0.1, "zoom": 0.2}, 4, 20.0) is True,
      "text=0.4/card=0.1/zoom=0.2 over 20s implies 0+0+0")
check("the measured no-speech reference does NOT trip it",
      A.spec_implies_nothing(
          {"text": 0.0, "cut": 4.26, "card": 0.23, "sfx": 0.0, "zoom": 0.0}, 8, 20.0) is False,
      "per-family zero is legitimate; this must not re-impose max(1, ...)")
check("a normal talking-head spec does NOT trip it",
      A.spec_implies_nothing({"text": 6.5, "card": 1.0, "sfx": 0.8}, 11, 38.5) is False)
check("the same tiny rate over a LONG source does NOT trip it",
      A.spec_implies_nothing({"text": 0.4}, 12, 200.0) is False,
      "it is the source length that makes the target zero, not the rate alone")
check("no spec at all is a different failure, not this one",
      A.spec_implies_nothing({}, 4, 20.0) is False)

# ── 6. and it OBSERVES, it does not fail the round ────────────────────────
# INVERTED BY THE RULING (2026-09-07). This asserted that spec_targets_all_zero
# was a CONTRACT failure — a demand that the spec ASK for something, which is
# the same rate-as-demand from the other direction. A brief that resolves to
# small rates over a short source implies zero placements and that is a real
# answer, not a bar the agent dodged.
#
# The observation survives: "did the agent set a bar it can fail?" is worth
# recording and reporting. It just does not refuse anything.
check("spec_targets_all_zero no longer fails the round",
      "spec_targets_all_zero" not in A.CONTRACT_FAILURES,
      "a spec that implies nothing is an observation about the brief, not a "
      "defect in the edit")
cv = A._contract_violations({"spec_implies_nothing": True, "failures": []})
check("a spec implying nothing produces NO violation",
      not any("spec_targets_all_zero" in c for c in cv), str(cv))
check("and the observation is still RECORDED",
      'led["spec_implies_nothing"]' in open(A.__file__, encoding="utf-8").read(),
      "removing the failure must not remove the measurement — a grade nobody "
      "keeps is not a grade")

# ── 7. THE CALL SITE READS THE FULL SPEC, NOT THE SHORTFALL-FILTERED ONE ───
# Round 25 caught this on the check's first live run. `_spec_t` has ACCEPTED
# families removed — right for the shortfall, wrong here. music and
# screen_recording had both accepted a shortfall on `cut`, so cut left the set,
# the remaining rates implied zero over a 20s source, and the check fired on two
# specs that HAD asked for cuts: two false positives of three firings. A check
# that fires on correct behaviour gets switched off, so this is pinned by AST,
# not by hoping the comment is read.
import ast as _ast, pathlib as _pl
_tree = _ast.parse(_pl.Path(A.__file__).read_text())
_calls = [n for n in _ast.walk(_tree)
          if isinstance(n, _ast.Call)
          and getattr(n.func, "id", None) == "spec_implies_nothing"]
check("spec_implies_nothing is called", len(_calls) >= 1)
for _c in _calls:
    _first = _c.args[0] if _c.args else None
    check("its target argument is NOT the shortfall-filtered `_spec_t`",
          not (isinstance(_first, _ast.Name) and _first.id == "_spec_t"),
          "accepted families are removed from _spec_t; a spec that excused one "
          "still SET it, and judging the bar on what remains after the excuses "
          "fires on correct behaviour")
    check("it reads the SCOPED target set (full targets minus out_of_scope)",
          isinstance(_first, _ast.Name) and _first.id == "_scoped_t",
          _ast.dump(_first)[:120] if _first else "no argument")

if fails:
    print(f"ALL-LEGS/ZERO-SPEC: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL-LEGS/ZERO-SPEC: PASS")
