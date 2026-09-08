#!/usr/bin/env python3
"""SMOKE: every name that can fail a round is a name something actually emits.

ROUND 40 WENT GREEN — "all five green", the first green round — while losing
three of three cards, one of one zoom and one of three sfx:

    ruled_not_built: card: ruled 3, built 0
    ruled_not_built: zoom: ruled 1, built 0
    ruled_not_built: sfx:  ruled 3, built 2
    execute_plan_skip: card beat 2: StatCard requires ['label','value'] and the
                       props supply ['heroNumber','label']

The boundary refusal was CORRECT — refusing beats rendering a blank card. But
the refusal emits execute_plan_skip and ruled_not_built, and neither fails a
round; while `card_props_mismatch`, which IS in CONTRACT_FAILURES and would have
failed it, is emitted by NOTHING. A failing name with no producer is a check that
cannot fire, and the round it should have caught scored green.

That is the shape this repo keeps paying for: a consumer with no producer. It is
cheaper to assert the two sets meet than to notice a green that should have been
red — round 40 needed a human reading a log line to spot it.

THIS DOES NOT ASSERT THE CONVERSE. Plenty of emitted names are deliberately
NOT contract failures (a divergence, a note, a soft skip), so an emitted name
absent from the failing set is fine. Only the other direction is a defect: a name
that can fail a round and never will.
"""
import ast
import re
import sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

failing = None
for node in TREE.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CONTRACT_FAILURES":
        v = node.value
        # frozenset(...) is a Call, not a literal — read its argument.
        failing = ast.literal_eval(v.args[0] if isinstance(v, ast.Call) and v.args else v)

if failing is None:
    print("FAILING-NAMES: CONTRACT_FAILURES not found at module level")
    sys.exit(1)
if not failing:
    print("FAILING-NAMES: CONTRACT_FAILURES is EMPTY — nothing can fail a round")
    sys.exit(1)

# Every literal handed to fail(), plus names appended to the ledger directly —
# two contract failures were once appended straight from the ledger and never
# consulted this frozenset, so a fail()-only scan would miss that producer.
emitted = set(re.findall(r'fail\(\s*"([a-z_]+)"', SRC))
emitted |= set(re.findall(r'"kind"\s*:\s*"([a-z_]+)"', SRC))
emitted |= set(re.findall(r'setdefault\(\s*"([a-z_]+)"', SRC))

orphans = sorted(n for n in failing if n not in emitted)

print(f"FAILING-NAMES: {len(failing)} names can fail a round; "
      f"{len(emitted)} names are emitted somewhere")
if orphans:
    print(f"\n  {len(orphans)} CONSUMER(S) WITH NO PRODUCER — these can never fire:")
    for o in orphans:
        print(f"    {o}")
    print("\n  A name in CONTRACT_FAILURES that nothing emits is a check that")
    print("  cannot fail. Round 40 scored 'all five green' while dropping 3 of 3")
    print("  cards, because the refusal emitted execute_plan_skip (not failing)")
    print("  and card_props_mismatch (failing) had no producer.")
    sys.exit(1)
print("  every failing name has a producer")
