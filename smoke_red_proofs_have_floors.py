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
    # THE FLOOR MUST MAKE AN EMPTY LIST FALSY. Two spellings do that, and a
    # check that admits only one is a STYLE rule wearing a correctness rule's
    # clothes.
    #
    #   r and all(r)                        floors on the CONTAINER
    #   red and red == len(MUTATIONS)       floors on the COUNT of red legs —
    #                                       if the list is empty nothing can be
    #                                       counted, so red is 0 and falsy
    #
    # v1 matched a shape LOOSE enough to admit the defect (`all(r) and rc == 0`
    # passed). v2 matched a shape TIGHT enough to exclude a correct
    # implementation — it failed 5 of Builder-2's 16 working harnesses. Same
    # axis, opposite error, and the twin of the rule this file exists under:
    # A PATTERN TIGHT ENOUGH TO EXCLUDE A CORRECT IMPLEMENTATION IS NOT A CHECK
    # EITHER. Whoever hit it next would have "fixed" their working floor by
    # rewriting it to my spelling.
    #
    # THE FIX IS TO TIE NAMES THE WAY THE CODE TIES THEM: a bare Name COMPARED
    # to len(X) is bound to X, so it reasons about X. Not `bare and reasoned`,
    # which would admit `unrelated_flag and all(r)` — a real hole.
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
                    # all(X) / len(X) / sum(X) / any(X) -> reasons about X
                    if (isinstance(sub, ast.Call)
                            and getattr(sub.func, "id", "") in ("all", "len", "sum", "any")):
                        for a in sub.args:
                            nm = getattr(a, "id", None)
                            if nm:
                                reasoned.add(nm)
                    # n == len(X)  ->  n is a count OF X, so n reasons about X
                    if isinstance(sub, ast.Compare):
                        sides = [sub.left] + list(sub.comparators)
                        names = {x.id for x in sides if isinstance(x, ast.Name)}
                        lens = any(isinstance(x, ast.Call)
                                   and getattr(x.func, "id", "") in ("len", "sum")
                                   for x in sides)
                        if names and lens:
                            reasoned |= names
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
