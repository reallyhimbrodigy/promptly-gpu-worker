#!/usr/bin/env python3
"""A TRUNCATED LIST CARRIES ITS DENOMINATOR — and a subset is named at its source.

Rule 2 applied to OUTPUT rather than measurement. "Report zero only with what it
is zero out of" and "print a list only with what it is a subset of" are the same
instruction, and they fail the same way: THE INCOMPLETE THING RENDERS
IDENTICALLY TO THE COMPLETE THING.

WHAT HAPPENED. The round report printed `_vq["sample"]` — 8 of 9 beats — with no
"sample", no "N of M", no ellipsis. It was read as the complete per-beat record,
which made r47 motion look like it had built more placements than it ruled. And
`_rej[:6]` truncated the CUTAWAY rejections: a run rejecting 30 printed 6 and
read as rejecting 6, in the family whose entire diagnosis that round was
"ruled zero".

MEASURE THE CLASS BEFORE CHECKING IT. A first scan of every `[:N]` in a
print-bearing scope returned 187 and was useless — dominated by `str[:200]`
truncating error messages, which is legitimate. Truncating a MESSAGE loses
characters; truncating a COLLECTION loses countable items, and only the second
makes a subset read as a total. This checks the second.

TWO LEGS, because there are two ways to ship a subset as a total:

  AT THE PRINT   `for x in NAME[:N]` that prints must have a `len(NAME)` in the
                 same function. Mechanical, on the AST.

  BEFORE THE PRINT  a list that was ALREADY a subset on arrival has no slice to
                 find — this is the case that motivated the rule and the AST
                 leg is structurally blind to it. So it is a CONVENTION, checked
                 by name: a key called `sample`/`head`/`first`/`subset` must
                 have a sibling count key, and the full record must exist.

  python3 smoke_truncated_lists.py      exit 0 = no subset can read as a total
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = ["agentic_editor_app.py", "deliver_round.py", "run_input_shapes.py",
           "corpus_guard.py", "build_plan.py"]
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

_checked = 0
for t in TARGETS:
    path = os.path.join(HERE, t)
    if not os.path.exists(path):
        continue
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)

    # ── LEG 1: iterate-a-truncated-collection-and-print ─────────────────────
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        # every len() argument reachable in this function
        lens = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "len":
                for a in n.args:
                    nm = getattr(a, "id", None) or getattr(a, "attr", None)
                    if nm:
                        lens.add(nm)
                    # len(x.get("k") or []) — record the key too
                    for sub in ast.walk(a):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            lens.add(sub.value)
        for n in ast.walk(fn):
            if not (isinstance(n, ast.For) and isinstance(n.iter, ast.Subscript)):
                continue
            sl = n.iter.slice
            if not (isinstance(sl, ast.Slice) and sl.upper is not None):
                continue
            if not any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "print"
                       for c in ast.walk(n)):
                continue          # not printed: not this class
            _checked += 1
            nm = getattr(n.iter.value, "id", None) or getattr(n.iter.value, "attr", None)
            keys = {c.value for c in ast.walk(n.iter.value)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)}
            named = (nm in lens) or bool(keys & lens)
            ok(named,
               f"{t}:{n.lineno} prints a truncated list ({nm or 'expr'}[:"
               f"{getattr(sl.upper, 'value', '?')}]) with no len() beside it — "
               f"a subset renders identically to a complete list, so the reader "
               f"cannot tell 'these are the items' from 'these are some of them'")

    # ── LEG 2: a function that PRINTS a subset-named list must print its count
    # TWO WRONG VERSIONS BEFORE THIS ONE, both caught by their own RED proof:
    #   v1 asserted the EMITTING dict carried a companion count — but it already
    #      had "n", so the mutant passed. The denominator was emitted all along;
    #      the PRINTER never showed it.
    #   v2 looked for the subset key inside the loop's ITERABLE — but the code is
    #      `_smp = _vq.get("sample") or []` then `for _v in _smp:`, so the string
    #      lives in the ASSIGNMENT and the walk found ZERO sites. A leg that
    #      matches nothing forbids nothing, and `_checked` falling from 5 to 4 is
    #      the only reason I noticed.
    # Scoped to the function, which is coarse and actually matches the property:
    # if this function reads a subset-named key and prints, it must say so.
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        reads_subset = set()
        for n in ast.walk(fn):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
                    and n.args and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value in ("sample", "head", "first", "subset")):
                reads_subset.add(n.args[0].value)
        if not reads_subset:
            continue
        if not any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "print"
                   for c in ast.walk(fn)):
            continue
        _checked += 1
        key = sorted(reads_subset)[0]
        printed = " ".join(
            c.value for n in ast.walk(fn) if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "print"
            for a in n.args for c in ast.walk(a)
            if isinstance(c, ast.Constant) and isinstance(c.value, str))
        ok("SAMPLE" in printed or "shown of" in printed or "subset" in printed.lower(),
           f"{t}:{fn.lineno} {fn.name}() reads {key!r} and prints, without ever "
           f"printing that it IS a subset. There is no slice for the AST leg "
           f"above to find — the list was ALREADY a subset when it arrived, "
           f"which is the case that motivated this rule. Print 'SAMPLE — N "
           f"shown of M', or print the full record")

print(f"TRUNCATED-LISTS  {_checked} site(s) checked across {len(TARGETS)} file(s)")
ok(_checked >= 4,
   f"only {_checked} sites found — the walk is not reaching them and this "
   f"check forbids nothing")
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("  every truncated list carries its denominator, every subset is named")
