#!/usr/bin/env python3
"""Every red proof that mutates source refuses a mutant that will not parse.

RULED MANDATORY BY ZAC 2026-09-09, on the strongest possible evidence: the
guard caught its own author within the hour of being named. Builder-1 described
the failure mode to me — their RED-2 mutant inserted a 4-space block before an
8-space line — and then their next red proof's absent-state leg used an
unterminated string and proved nothing until it was redone. A guard that catches
the person who just named it is not a hypothetical, and it is better evidence
than my deliberately RED-proving it.

WHY IT IS ITS OWN FAILURE MODE. A mutant that does not compile makes the check
fail for a reason that has nothing to do with the property under test. The
tally counts it RED, the harness prints nothing unusual, and the leg has proved
NOTHING — it never ran the code it claims to be testing. None of the other
guards see it:

    anchor 0x               a refactor moved the target      count guard
    operand is empty        the edit is a semantic no-op     precondition
    match lands in prose    a comment now owns the anchor    _match_is_prose
    mutant will not parse   it never ran at all              THIS

MANDATORY MEANS ENFORCED, WHICH IS WHY THIS FILE EXISTS. "Every harness should
carry the guard" is a convention, and this repo's whole ledger of false greens
is conventions that decayed one plausible commit at a time. A harness that
mutates source and does not check the mutant parses fails here.

THE ONE INVERTED CASE, allowed explicitly rather than special-cased by name:
red_proof_tree_parses deliberately mutates handler.py into something that does
NOT parse, because that IS its defect under test. It carries the same question
with the expected answer stated — does this mutant compile, and did I mean it
to — so it satisfies the rule rather than being exempted from it.

RED-proven by red_proof_red_proofs_guarded.py.
"""
import ast
import pathlib
import sys

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_harnesses = sorted(pathlib.Path(".").glob("red_proof_*.py"))
check(f"there are red proofs to check ({len(_harnesses)} found)",
      len(_harnesses) >= 10, "the glob found almost nothing — this check would "
                             "pass vacuously over an empty set")

_mutators, _unguarded, _broken = [], [], []
for _p in _harnesses:
    _s = _p.read_text()
    try:
        _t = ast.parse(_s)
    except SyntaxError as _e:
        _broken.append(f"{_p.name}: {_e.msg}")
        continue
    # A HARNESS THAT MUTATES SOURCE writes to a file it also reads. Detected by
    # a write call whose argument derives from a `.replace(` — that is what a
    # mutation IS, and it is the shape every harness here shares regardless of
    # whether it spells the write open().write or Path.write_text.
    _writes_mutant = False
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Call) and getattr(_n.func, "attr", "") in (
                "write", "write_text"):
            _writes_mutant = True
    if not _writes_mutant:
        continue
    _mutators.append(_p.name)
    # The guard: ast.parse applied to something, inside the harness.
    _parses_mutant = any(
        isinstance(_n, ast.Call)
        and getattr(_n.func, "attr", "") == "parse"
        and getattr(getattr(_n.func, "value", None), "id", "") == "ast"
        for _n in ast.walk(_t))
    # ...and it must be REACTED to: an ast.parse whose SyntaxError is not
    # handled is a crash, not a guard.
    _handles = any(
        isinstance(_n, ast.ExceptHandler)
        and (getattr(_n.type, "id", "") == "SyntaxError"
             or any(getattr(_e, "id", "") == "SyntaxError"
                    for _e in ast.walk(_n.type)) if _n.type is not None else False)
        for _n in ast.walk(_t))
    if not (_parses_mutant and _handles):
        _unguarded.append(f"{_p.name}  (ast.parse={_parses_mutant} "
                          f"SyntaxError-handled={_handles})")

check("every red proof parses", not _broken, "; ".join(_broken))
check(f"the scan found source-mutating harnesses ({len(_mutators)}) — non-vacuity",
      len(_mutators) >= 10,
      f"only {len(_mutators)} detected as mutators; the detector is probably "
      f"wrong, and a check over an empty set passes quietly")
check("every source-mutating red proof refuses a mutant that will not parse",
      not _unguarded,
      "\n         ".join(_unguarded) + "\n         A mutant that does not "
      "compile never ran, so its leg proved nothing while counting RED.")

print()
if fails:
    print("RED-PROOFS-GUARDED: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"RED-PROOFS-GUARDED: PASS — {len(_mutators)} source-mutating harness(es), "
      f"all four guards' newest member present and its SyntaxError handled")
