#!/usr/bin/env python3
"""EVERY RED PROOF FAILS ON AN EMPTY MUTATION LIST.

`all([])` is True. `0 == len([])` is True. So a red proof whose mutations are
all deleted — by a bad merge, a botched refactor, a commented-out block —
reports SUCCESS. An instrument whose entire job is to prove a check CAN FAIL,
rendering its own absence as success.

FOUND IN 10 OF 11 HERE and 16 of 16 on Builder-2's tree: 26 of 27 across both.
Neither of us had a floor anywhere, in the class of instrument least able to
afford one.

This is the empty-set rule arriving inside the red proofs rather than inside a
check leg, and it is the sharper instance for that reason. It is also invisible
until the day it matters, which is why it needs a check rather than a habit.

  python3 smoke_red_proofs_have_floors.py     exit 0 = no harness passes empty
"""
import ast
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL = []
_checked = 0

for path in sorted(glob.glob(os.path.join(HERE, "red_proof_*.py"))):
    name = os.path.basename(path)
    tree = ast.parse(open(path, encoding="utf-8").read())
    exits = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and (getattr(n.func, "attr", "") == "exit"
                  or getattr(n.func, "id", "") == "exit")]
    if not exits:
        FAIL.append(f"{name} never calls sys.exit — its result reaches nobody")
        continue
    _checked += 1
    # THE FLOOR MUST BE THE CONTAINER ITSELF, AS A BARE TRUTHY OPERAND.
    #
    # MY FIRST VERSION MATCHED "BoolOp and And and (all|Compare)" and therefore
    # PASSED `all(r) and rc == 0` — which has no floor whatsoever. Its own RED
    # proof caught it: I stripped a real floor and the check stayed green. A
    # pattern loose enough to match the defect is not a check, and this is the
    # second time today a leg of mine matched a shape instead of a property.
    #
    # The property: whatever container the exit reasons about (`r` inside
    # all(r), or MUTATIONS inside len(MUTATIONS)) must ALSO appear as a bare
    # Name operand of the same `and` — that is what makes [] falsy and fails.
    guarded = False
    for e in exits:
        for node in ast.walk(e):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And)):
                continue
            bare = {v.id for v in node.values if isinstance(v, ast.Name)}
            if not bare:
                continue
            reasoned = set()
            for v in node.values:
                for sub in ast.walk(v):
                    if isinstance(sub, ast.Call) and getattr(sub.func, "id", "") in ("all", "len", "sum", "any"):
                        for a in sub.args:
                            nm = getattr(a, "id", None)
                            if nm:
                                reasoned.add(nm)
            if bare & reasoned:
                guarded = True
    if not guarded:
        FAIL.append(
            f"{name} exits on a predicate with NO FLOOR — all([]) is True and "
            f"0 == len([]) is True, so emptying its mutation list reports "
            f"SUCCESS. The container it reasons about must also appear as a "
            f"bare operand: `r and all(r)`, not `all(r) and rc == 0`")

print(f"RED-PROOF FLOORS  {_checked} harness(es) checked")
# A check over an empty population asserts nothing — the rule that produced this
# check, applied to this check.
if _checked < 5:
    FAIL.append(f"only {_checked} red proofs found — this walk is not reaching "
                f"them and the check forbids nothing")
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("  every red proof fails on an empty mutation list")
