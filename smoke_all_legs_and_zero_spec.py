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

_m = types.ModuleType("modal")
class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f
for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True; _m.enable_output = _S()
sys.modules.setdefault("modal", _m)

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

# ── 6. and it is a CONTRACT failure that reaches the gate ──────────────────
check("spec_targets_all_zero is a contract failure",
      "spec_targets_all_zero" in A.CONTRACT_FAILURES)
cv = A._contract_violations({"spec_implies_nothing": True, "failures": []})
check("_contract_violations emits it from the ledger flag",
      any("spec_targets_all_zero" in c for c in cv), str(cv))
cv0 = A._contract_violations({"spec_implies_nothing": False, "failures": []})
check("and stays quiet when the spec asks for something",
      not any("spec_targets_all_zero" in c for c in cv0), str(cv0))

if fails:
    print(f"ALL-LEGS/ZERO-SPEC: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL-LEGS/ZERO-SPEC: PASS")
