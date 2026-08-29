"""CERT — the lean-schema backfill reaches video_plan.key_moments (RULE-1).

THE DEFECT. `_backfill_lean_fields` restores the telemetry prose the lean
response schema strips (what_lands / why_emphasis / what_i_saw /
viewer_feeling), so a lean-arm plan still satisfies the strict PostCutPlan
contract. It read `_parsed.get("key_moments")` — but PostCutPlan declares
`video_plan: _VideoPlan` and _VideoPlan owns key_moments. The lookup returned
None on every job, the loop never ran, and the backfill was INERT for the exact
field class it exists to restore.

MEASURED before the fix: 66/244 organic completions (27.0%) failed strict
PostCutPlan.model_validate; all 69 field-level failures were
`video_plan.key_moments.N.what_lands  Field required`, 12-24 per plan.

WHY A CERT AND NOT A COMMENT. This is the campaign's most repeated class — a fix
that reads as shipped and is inert. A regression here is silent: the outcome gate
runs in SHADOW, so nothing fails, nothing alerts, and the rate simply climbs back
to 27% unnoticed. The only thing that can catch it is an assertion that the
backfill CHANGES the object.

BOTH DIRECTIONS:
  GREEN — a lean-shaped plan (prose stripped, nested under video_plan) validates
          against strict PostCutPlan AFTER the backfill.
  RED   — the same plan does NOT validate BEFORE it, so the cert is proving the
          backfill did the work rather than the fixture being valid anyway.
  GUARD — the backfill must not paper over a genuinely broken plan: a missing
          REQUIRED non-prose field (word_index) must still fail.

Offline. Zero network, zero Modal, zero Gemini.
"""
import copy
import sys

import handler as H

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


# A LEAN-ARM PLAN, shaped exactly as the model emits it: key_moments nested
# under video_plan, prose fields absent (the schema dropped them), everything
# else present. This is the real failing shape from the ledger:
#   video_plan.key_moments.0.what_lands  Field required
#   input_value={'word_index': 2}
LEAN_MOMENT = {"word_index": 2}

print("=== C1: the failing shape is reproduced, and it really is invalid ===")
check("_VideoPlanMoment declares the prose fields as REQUIRED",
      all(f in H._LEAN_DROP_FIELDS["_VideoPlanMoment"]
          for f in ("what_lands", "why_emphasis", "what_i_saw", "viewer_feeling")),
      f"drop set is {H._LEAN_DROP_FIELDS['_VideoPlanMoment']}")

_moment_model = H._VideoPlanMoment
_pre_err = None
try:
    _moment_model.model_validate(dict(LEAN_MOMENT))
except Exception as e:
    _pre_err = str(e)
check("a bare {word_index} moment FAILS _VideoPlanMoment validation",
      _pre_err is not None and "what_lands" in _pre_err,
      f"error was {_pre_err!r}")

print("\n=== C2: the backfill REACHES the nested list (the actual fix) ===")
nested = {"video_plan": {"key_moments": [copy.deepcopy(LEAN_MOMENT)]}}
before = copy.deepcopy(nested)
H._backfill_lean_fields(nested)
_km = nested["video_plan"]["key_moments"][0]
check("nested video_plan.key_moments was MUTATED (was a silent no-op)",
      nested != before,
      "backfill returned without touching the nested list — the original defect")
for f in ("what_lands", "why_emphasis", "what_i_saw", "viewer_feeling"):
    check(f"  {f} restored as \"\"", _km.get(f) == "",
          f"got {_km.get(f)!r}")
_post_err = None
try:
    _moment_model.model_validate(_km)
except Exception as e:
    _post_err = str(e)
check("the backfilled moment now VALIDATES", _post_err is None,
      f"still failing: {_post_err!r}")

print("\n=== C3: the sibling loops still work (no regression) ===")
sib = {"emphasis_moments": [{"word_indices": [1]}],
       "cut_refinements": [{"x": 1}]}
H._backfill_lean_fields(sib)
check("emphasis_moments.viewer_feeling restored",
      sib["emphasis_moments"][0].get("viewer_feeling") == "")
check("cut_refinements.reason restored",
      sib["cut_refinements"][0].get("reason") == "")

print("\n=== C4: a top-level key_moments shape is ALSO covered ===")
# The v2/flatten arm restructures the plan. Asserting one shape from one sample
# is exactly how the original bug was born, so both are walked.
flat = {"key_moments": [copy.deepcopy(LEAN_MOMENT)]}
H._backfill_lean_fields(flat)
check("top-level key_moments still backfilled",
      flat["key_moments"][0].get("what_lands") == "")

print("\n=== C5: GUARD — it must not paper over a genuinely broken plan ===")
# word_index is REQUIRED and is NOT prose. The backfill must leave it missing so
# a real structural break still fails. A backfill that made everything validate
# would be worse than the bug.
broken = {"video_plan": {"key_moments": [{"what_lands": "x"}]}}
H._backfill_lean_fields(broken)
_b_err = None
try:
    _moment_model.model_validate(broken["video_plan"]["key_moments"][0])
except Exception as e:
    _b_err = str(e)
check("a moment missing word_index STILL fails after backfill",
      _b_err is not None and "word_index" in _b_err,
      f"error was {_b_err!r} — the backfill is masking real breakage")
check("backfill did not invent word_index",
      "word_index" not in broken["video_plan"]["key_moments"][0])

print("\n=== C6: the gate stays SHADOW (this fix changes no behaviour) ===")
_src = open(H.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
check("PROMPTLY_OUTCOME_GATE still defaults to shadow",
      'os.environ.get("PROMPTLY_OUTCOME_GATE", "shadow")' in _src,
      "the default changed — this fix was meant to be behaviour-neutral")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
