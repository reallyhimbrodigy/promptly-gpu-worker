#!/usr/bin/env python3
"""RED PROOF, AGAINST THE DEPLOYED FUNCTION: the blend cannot happen.

Zac's ten are the standard; the hundred are other people's work. They are
synthesised SEPARATELY and read side by side so the agent can tell which
document a line came from, and so a contradiction can be resolved by the
standard winning — which is impossible to do to half of a merged document.

The blend would arrive as a reference analysis handed to the FIELD report.
That must FAIL, and it must fail BEFORE any model call — this proof costs
nothing because the refusal is the first thing the function does.
"""
import sys

import modal

fn = modal.Function.from_name("promptly-craft-pass", "synthesise")
A = {"label": "x", "prose": "p " * 300}
ref = dict(A, weight="zac_reference")
field = dict(A, weight="apify_field")

fail = 0

# RED 1: a reference in the field report is the blend.
r = fn.remote([ref, field], mode="field")
if r["state"] != "FAILED" or "blend" not in r["detail"]:
    print(f"  *** the blend was ACCEPTED: {r['state']} {r['detail'][:80]}")
    fail += 1
else:
    print(f"  blend refused: {r['detail'][:70]}")

# RED 2: the field alone must never be synthesised AS the standard — that is
# the taste he did not choose.
r = fn.remote([field], mode="standard")
if r["state"] != "ABSENT":
    print(f"  *** the field passed as the standard: {r['state']}")
    fail += 1
else:
    print(f"  field-as-standard refused: {r['detail'][:70]}")

# RED 3: an unknown mode must not silently fall back to either report.
r = fn.remote([ref], mode="both")
if r["state"] != "FAILED":
    print(f"  *** unknown mode silently ran something: {r['state']}")
    fail += 1
else:
    print(f"  unknown mode refused: {r['detail'][:70]}")

print(f"smoke_two_reports_never_blend: 3 red, {fail} wrong")
sys.exit(1 if fail else 0)
