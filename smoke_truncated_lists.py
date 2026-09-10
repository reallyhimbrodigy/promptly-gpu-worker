#!/usr/bin/env python3
"""A truncated list printed without its denominator reads as a total.

Rule 2 applied to OUTPUT rather than measurement. "Report zero only with what it
is zero out of" and "print a list only with what it is a subset of" are the same
instruction, and they fail in the same direction: THE INCOMPLETE THING RENDERS
IDENTICALLY TO THE COMPLETE THING.

FOUND FROM BOTH SIDES ON 2026-09-09, which is why it is a rule and not two
fixes. Builder-1's report printed `(_vq.get("sample") or [])` with no "sample",
no "N of M" and no ellipsis, so 8 of 9 beats read as 9 and a ruled-vs-built
count came out impossible. I found that in a printer they had read every round
for weeks — and they found `marked[:20]` / `broken[:20]` in THIS FILE'S
companion check, which I had shipped them two hours earlier. A truncated print
looks correct from the inside: you wrote the [:20] and you remember it is 20.
The reader does not.

WHAT COUNTS, AND WHY THE WIDE SCOPE IS WORTHLESS. Builder-1's first scan found
187 instances by counting every `[:N]` in a print-bearing scope. That number is
useless: it is dominated by `str[:200]` and `str[:140]` truncating error
messages, which is legitimate. TRUNCATING A MESSAGE LOSES CHARACTERS;
TRUNCATING A COLLECTION LOSES COUNTABLE ITEMS, and only the second makes a
subset read as a total. Scoped to iteration over a sliced name, the same class
is six instances, all real and all fixable in one pass. A check that reports 187
findings nobody can action is a check that gets suppressed.

THE HALF THIS CANNOT SEE, stated rather than implied. `for x in NAME[:N]`
catches truncation AT THE PRINT. It cannot catch truncation BEFORE it: a list
sampled upstream and handed over as a plain list has no slice at the printer,
which is exactly the shape of the defect that motivated the rule. The second leg
is therefore a NAMING CONVENTION, not a proof — a subset must be NAMED as one
where it is created, so anything called sample/head/first/subset must be printed
with a count beside it. Saying that plainly is better than dressing a convention
up as a guarantee.

RED-proven by red_proof_truncated_lists.py.
"""
import ast
import pathlib
import sys

# The files whose output someone READS to make a decision. Not repo-wide: a
# `[:3]` in a message that says "first 3" is legitimate, and this check has no
# way to tell. Scope stated, so widening it is a decision rather than a drift.
TARGETS = ["agentic_editor_app.py", "smoke_tree_parses.py"]
SUBSET_NAMES = ("sample", "_sample", "head", "first", "subset", "_subset")

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


def _prints_in(scope):
    return [n for n in ast.walk(scope)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "print"]


def _names_counted(block):
    """Names inside a len() in the SAME BLOCK as the loop — siblings only.

    MY FIRST VERSION SCOPED THIS TO THE ENCLOSING FUNCTION AND SCORED A FALSE
    GREEN. `main` is thousands of lines; a `len(pls)` anywhere in it excused a
    `for ... in pls[:10]` that printed no count at all. The check reported 0
    findings on a file Builder-1 had already measured at 4, and a clean zero is
    guilty until proven innocent — this one was a reader bug, like the four
    before it.

    Third time this exact scoping error has bitten me: the per-tool orphan check
    collected `_v.get('b')` from 800 lines away, and the `or 0` check's second
    scope swept 17 innocents out of a 3,000-line function. THE DENOMINATOR HAS
    TO BE WHERE THE READER IS, which means beside the loop, not somewhere in the
    same function.
    """
    out = set()
    for st in block:
        for n in ast.walk(st):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "len":
                for a in n.args:
                    if isinstance(a, ast.Name):
                        out.add(a.id)
                    elif isinstance(a, ast.Attribute):
                        out.add(a.attr)
    return out


def _states_denominator(block, subset_name):
    """Does this block PRINT a denominator for `subset_name`?

    Static text carrying " of " or "SAMPLE", plus a reference to some name that
    is not the subset itself. Deliberately a convention: nothing static can
    prove that the number printed is the true total, and pretending otherwise
    would be the third time today a check claimed coverage it cannot have.
    """
    for st in block:
        for n in ast.walk(st):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "print"):
                continue
            _txt, _names = "", set()
            for sub in ast.walk(n):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    _txt += sub.value
                elif isinstance(sub, ast.Name):
                    _names.add(sub.id)
            # THE RESCUING PRINT MUST BE ABOUT THIS SUBSET. Keying on " of "
            # anywhere in the block let an UNRELATED line rescue it: the block
            # holding the sample listing also prints "BEAT VERDICTS: N ruled of
            # M beats", and that " of " marked the sample as denominated. A
            # denominator for something else is not a denominator for this.
            if (" of " in _txt or "SAMPLE" in _txt) \
                    and subset_name in _names and (_names - {subset_name}):
                return True
    return False


def _blocks(scope):
    """Every statement list in this scope, so a loop can be scored against its
    OWN siblings rather than the whole function."""
    out = []
    for n in ast.walk(scope):
        for _f in ("body", "orelse", "finalbody"):
            _b = getattr(n, _f, None)
            if isinstance(_b, list) and _b and isinstance(_b[0], ast.stmt):
                out.append(_b)
    return out


_sliced, _unnamed_subsets, _scanned = [], [], 0
for _f in TARGETS:
    _p = pathlib.Path(_f)
    if not _p.is_file():
        continue
    _scanned += 1
    _tree = ast.parse(_p.read_text())
    for _blk in _blocks(_tree):
        if not any(_prints_in(_st) for _st in _blk):
            continue
        _counted = _names_counted(_blk)
        for _n in _blk:
            # LEG 1 — iteration over a SLICED NAME, printed in this scope.
            if isinstance(_n, ast.For) and isinstance(_n.iter, ast.Subscript) \
                    and isinstance(_n.iter.slice, ast.Slice) \
                    and _n.iter.slice.upper is not None \
                    and _prints_in(_n):
                # `spans[1:]` is a SKIP, not a truncation — no upper bound, so
                # nothing is withheld and there is no denominator to state.
                _v = _n.iter.value
                _nm = getattr(_v, "id", None) or getattr(_v, "attr", None)
                if _nm:
                    if _nm not in _counted:
                        _sliced.append(f"{_f}:{_n.lineno}  for ... in {_nm}[:N] "
                                       f"with no len({_nm}) beside it")
                elif not _counted:
                    # AN UNNAMEABLE ITERABLE — `(_ep.get("skips") or [])[:8]`.
                    # There is no name to count, so the only thing that can
                    # rescue it is SOME length in the same block. None here
                    # means the reader gets 8 lines and no idea of 8 out of
                    # what. My first matcher skipped these entirely because it
                    # keyed on a name, which is how a real finding hid behind a
                    # slightly more complex expression.
                    _sliced.append(f"{_f}:{_n.lineno}  for ... in <expr>[:N] "
                                   f"with no len() anywhere in the same block")
            # LEG 2 — a name that DECLARES itself a subset, printed without a
            # count. The convention half; it cannot prove anything.
            #
            # RESOLVED THROUGH ONE BINDING, and I needed that the hard way. The
            # first version keyed on the literal name appearing in the ITERABLE
            # EXPRESSION. My own fix for the defect it found bound
            # `_vq.get("sample")` to `_vs` and iterated THAT — so the check
            # stopped seeing the site entirely, and its own red proof reported
            # the un-labelling mutation as NOT RED. The check passed because the
            # signal had moved one line up, not because the code was right.
            #
            # This repo already has the rule: ONE HOP OF INDIRECTION IS STILL
            # SCOPE. I wrote a check that broke it, then broke it again fixing
            # what the check found.
            if isinstance(_n, ast.For) and _prints_in(_n):
                _srcs = [_n.iter]
                _it = getattr(_n.iter, "id", None)
                if _it:
                    for _st in _blk:
                        if isinstance(_st, ast.Assign) and any(
                                getattr(_t, "id", None) == _it for _t in _st.targets):
                            _srcs.append(_st.value)
                for _root in _srcs:
                    for _sub in ast.walk(_root):
                        _cand = (getattr(_sub, "id", None)
                                 or (getattr(_sub, "value", None)
                                     if isinstance(_sub, ast.Constant) else None)
                                 or getattr(_sub, "attr", None))
                        # THE DENOMINATOR MUST BE OF THE WHOLE, NOT THE PART.
                        # `len(_vs)` where _vs IS the sample counts the subset
                        # against itself and answers nothing — "3 shown" of how
                        # many? So the iterated name is struck from the set of
                        # things that can rescue it, and something ELSE must be
                        # counted. This is the leg my own red proof exposed:
                        # un-labelling the print left `len(_vs)` in place and the
                        # check called it counted.
                        # WHAT RESCUES IT IS A STATED DENOMINATOR, not any
                        # count. `len(_vs)` where _vs IS the sample counts the
                        # subset against itself — "3 shown" of how many? — and
                        # my first two attempts both accepted it. The convention
                        # this leg enforces (and it IS a convention, not a
                        # proof) is that the block prints "N of M" or names the
                        # listing a SAMPLE, referencing something other than the
                        # subset itself.
                        if isinstance(_cand, str) and _cand in SUBSET_NAMES \
                                and not _states_denominator(_blk, _it):
                            _unnamed_subsets.append(
                                f"{_f}:{_n.lineno}  iterates {_cand!r} — a name "
                                f"that says it is a subset — with no count printed")

check(f"the scan read its targets ({_scanned} of {len(TARGETS)})",
      _scanned == len(TARGETS), f"missing: "
      f"{[f for f in TARGETS if not pathlib.Path(f).is_file()]}")
check("the scan can see a sliced-name loop at all (non-vacuity)",
      bool([n for n in ast.walk(ast.parse(
          "def f(x):\n for i in x[:3]:\n  print(i)\n")) 
          if isinstance(n, ast.For) and isinstance(n.iter, ast.Subscript)]),
      "the matcher does not recognise the shape it is built to find")
check("no collection is iterated sliced and printed without its length",
      not _sliced,
      "\n         ".join(_sliced) + "\n         A subset renders identically to "
      "a total. Print `showing N of M`.")
check("no self-declared subset is printed without a count",
      not _unnamed_subsets, "\n         ".join(_unnamed_subsets))

print()
if fails:
    print("TRUNCATED-LISTS: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"TRUNCATED-LISTS: PASS — {_scanned} file(s); every sliced-and-printed "
      f"collection carries its length, and no self-declared subset prints "
      f"without a count")
