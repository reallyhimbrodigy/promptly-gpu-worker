#!/usr/bin/env python3
"""A SAFE EDIT IS AN INCIDENT, NOT A DELIVERABLE. `[Rule 1, owner ruling 2026-08-18]`

WHEN EDITORIAL FAILS, THE JOB FAILS. It does not quietly ship a deterministic
clean-cut as if that were the product. A degraded edit delivered silently is
invisible in every metric we have — the job completes, the user gets a video,
and nothing anywhere counts the quality we did not deliver.

MEASURED BEFORE THE CHANGE, because it converts deliveries into failures:

    since Aug 11    216 safe_edit  /  174 FAILURE-driven  (148 users)
    post-v557        41 safe_edit  /    0 failure-driven

All 174 were the success-path TypeError class, already fixed. So at today's rate
this costs ZERO deliveries — it is the guard for when PROMPTLY_EDITORIAL_LIVE
flips, not a withdrawal of something users are currently getting. It must land
BEFORE that flip: once editorial is live, this path would ship degraded edits at
scale, silently.

TWO DOORS STAY OPEN, and confusing them with failure is the way this gets
wrongly "fixed" later:

    editorial_live_off   CONFIG. Editorial is suppressed; the deterministic path
                         IS the product today (41 of 41 post-v557 safe edits).
    recipe wall-clock    A BUDGET guard that stops compounding before the render
                         SIGKILL. A safe edit beats a killed job.

    python3 cert_safe_edit_not_a_deliverable.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")
PRED = "_safe_edit_deliverable_on_failure"

# reason-literal -> must the FAILURE door be gated by the predicate?
FAILURE_DOORS = ("recipe_transport:", "RECIPE_INVALID:")
CONFIG_DOORS = ("force_safe_reason", "recipe wall-clock budget exhausted")


def main():
    src = open(HANDLER).read()
    tree = ast.parse(src)
    fails = []

    if f"def {PRED}(" not in src:
        print(f"CERT SAFE-EDIT-DELIVERABLE: FAIL\n  - {PRED}() is gone; an "
              f"editorial failure would silently ship a deterministic edit again")
        return 1

    # Default MUST be off. A default-on predicate restores the old behaviour
    # while looking like the fix is in place.
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == PRED:
            fn = n
    seg = ast.get_source_segment(src, fn) or ""
    if "PROMPTLY_SAFE_EDIT_ON_FAILURE" not in seg:
        fails.append(f"{PRED}() no longer reads its rollback env key")
    if 'os.environ.get("PROMPTLY_SAFE_EDIT_ON_FAILURE", "")' not in seg:
        fails.append(f"{PRED}() must DEFAULT to empty (off) — a default-on flag "
                     f"restores the old behaviour while looking fixed")

    # Every FAILURE door must be gated by the predicate; the CONFIG doors must
    # NOT be (gating them would strand the suppressed path with no output).
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        blk = ast.get_source_segment(src, n) or ""
        if "_mark_safe_edit" not in blk:
            continue
        is_failure = any(d in blk for d in FAILURE_DOORS)
        gated = PRED in blk
        if is_failure and not gated:
            fails.append(f"the safe-edit door at line {n.lineno} handles an "
                         f"editorial FAILURE and is NOT gated by {PRED}() — it "
                         f"would ship a degraded edit as the product")
        if (not is_failure) and gated and "force_safe_reason" in blk:
            fails.append(f"the CONFIG door at line {n.lineno} is gated by "
                         f"{PRED}() — suppressed editorial would have no output "
                         f"path at all")

    # And EVERY refusal must be LEDGERED — COUNTED, not merely present.
    #
    # The first version of this check was `"safe_edit_refused" not in src`, and a
    # RED mutation that renamed ONE of the two ledger calls sailed through it:
    # presence survived on the other door. There are two failure doors, so there
    # must be two refusal records, and an incident nobody counts is the same
    # defect wearing the other face.
    n_refusals = sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == "_record_divergence")
        and any(isinstance(a, ast.Constant) and a.value == "safe_edit_refused"
                for a in n.args))
    if n_refusals < 2:
        fails.append(f"only {n_refusals} refusal(s) ledgered as safe_edit_refused; "
                     f"both failure doors (transport AND RECIPE_INVALID) must "
                     f"record one — presence alone let a renamed call pass")

    if fails:
        print("CERT SAFE-EDIT-DELIVERABLE: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT SAFE-EDIT-DELIVERABLE: PASS")
    print("  editorial FAILURE doors gated; the job fails instead of degrading")
    print("  config + wall-clock doors deliberately NOT gated")
    print("  the refusal is ledgered as safe_edit_refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())
