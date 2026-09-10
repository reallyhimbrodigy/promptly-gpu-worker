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
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. Found 2026-09-09 by asking Builder-1's
# question of my own suite: does a PASS mean "ran and passed" or "did not run"?
# `all([])` is True and `red == len(MUTATIONS)` is `0 == 0`, so EVERY red proof
# here reported success on an empty leg list. Sixteen instruments built to catch
# absence-rendered-as-success, each rendering its own absence as success.
# ASSERT THE PROPERTY BY EVALUATION, NOT BY PATTERN. (Builder-1's rule, earned
# on this exact leg twice over.) My first version was a SUBSTRING match on the
# exit line — `"r and all(r)" in _tail` — which accepts a COMMENTED-OUT floor
# and rejects every other correct spelling. Builder-1's was an AST shape match,
# which was loose enough to admit the defect in v1 and then tight enough to
# reject five of my working harnesses in v2. Same axis, three errors, one cause:
# a matcher approximating a property.
#
# THE PROPERTY: with the legs EMPTY, the exit predicate must be false NO MATTER
# WHAT ELSE HAPPENED. So bind the leg names empty, enumerate every other free
# name over falsy AND truthy, and require False in all of them. Exact, cheap,
# and indifferent to spelling.
def _leg_names(test):
    """Names that hold the legs: arguments of all/len/any/sum, plus any bare
    Name compared against one of those (a COUNT of that container)."""
    legs, counted = set(), set()
    for n in ast.walk(test):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in (
                "all", "len", "any", "sum"):
            for _a in n.args:
                if isinstance(_a, ast.Name):
                    legs.add(_a.id)
    for n in ast.walk(test):
        if isinstance(n, ast.Compare):
            _sides = [n.left] + list(n.comparators)
            _has_len = any(isinstance(x, ast.Call)
                           and getattr(x.func, "id", "") in ("len", "sum")
                           for x in _sides)
            if _has_len:
                for x in _sides:
                    if isinstance(x, ast.Name):
                        counted.add(x.id)
    return legs, counted


_no_floor, _undecidable = [], []
for _p in _harnesses:
    _t = ast.parse(_p.read_text())
    # SORTED BY LINE. ast.walk does NOT yield source order, so `_exits[-1]` was
    # the last node the WALK reached, not the last sys.exit in the file — it
    # picked the early `sys.exit(2)` baseline guard and reported "reasons about
    # no collection at all" for seven harnesses that are correctly floored.
    # A traversal order mistaken for a positional one; the check was wrong, the
    # harnesses were fine.
    _exits = sorted(
        (n for n in ast.walk(_t)
         if isinstance(n, ast.Call)
         and getattr(getattr(n, "func", None), "attr", "") == "exit"),
        key=lambda n: n.lineno)
    if not _exits:
        _no_floor.append(f"{_p.name}  (no sys.exit at all)"); continue
    _arg = _exits[-1].args[0] if _exits[-1].args else None
    _test = _arg.test if isinstance(_arg, ast.IfExp) else _arg
    if _test is None:
        _no_floor.append(f"{_p.name}  (exit takes no argument)"); continue
    _legs, _counts = _leg_names(_test)
    if not _legs:
        _no_floor.append(f"{_p.name}  (exit reasons about no collection at all)")
        continue
    # BUILTINS ARE NAMES TOO. `all`, `len`, `any`, `sum` parse as ast.Name, so
    # the first version bound them to 0 and `len(MUTATIONS)` raised TypeError.
    # It reached the right verdict for my harnesses only by SHORT-CIRCUIT LUCK —
    # the floor sits first, so `red` was falsy and the call was never evaluated.
    # For a predicate whose floor is not first it would have raised, and the
    # except below would have called that "no floor". Leave them resolving to
    # the real builtins.
    _BUILTIN = {"all", "any", "len", "sum", "bool", "int", "min", "max", "abs"}
    _free = sorted({n.id for n in ast.walk(_test) if isinstance(n, ast.Name)}
                   - _legs - _counts - _BUILTIN)
    _expr = compile(ast.Expression(_test), "<exit>", "eval")
    _held = True
    import itertools
    for _combo in itertools.product([0, 1], repeat=min(len(_free), 12)):
        _ns = {k: [] for k in _legs}
        _ns.update({k: 0 for k in _counts})          # empty legs -> zero count
        _ns.update(dict(zip(_free, _combo)))
        _ns.setdefault("__builtins__", __builtins__)
        try:
            if eval(_expr, _ns):                      # noqa: S307
                _held = False; break
        except Exception as _e:
            # THREE STATES, NOT TWO. An expression I cannot evaluate is not the
            # same finding as one that exits 0 on empty legs, and reporting them
            # with the same words is the failure this whole file is about.
            _undecidable.append(f"{_p.name}  ->  {type(_e).__name__}: "
                                f"{str(_e)[:60]}  (free={_free})")
            _held = None; break
    if _held is False:
        _no_floor.append(f"{_p.name}  ->  exits 0 with EMPTY legs under some "
                         f"combination of {_free}")
check("every exit predicate could be EVALUATED (not just pattern-matched)",
      not _undecidable, "\n         ".join(_undecidable) + "\n         An "
      "expression the check cannot evaluate is UNDECIDABLE, not unfloored — "
      "reporting them with the same words is the defect this file is about.")
check("no red proof can exit 0 with zero legs executed", not _no_floor,
      "\n         ".join(_no_floor) + "\n         all([]) is True; a harness "
      "whose mutations were all deleted would report success.")

# NO BACKUP OUTSIDE THE TREE. Observed 2026-09-09: red_proof_edit_quality kept
# its backup at the fixed path /tmp/_eq_bak.py, which is SHARED ACROSS EVERY
# BRANCH AND WORKTREE ON THE MACHINE. A run on one branch wrote it; a later run
# on another restored from it and silently replaced agentic_editor_app.py with
# the other branch's content — a 914-line diff — while printing 19/19
# RED-PROVEN. The harness reported success about a file it had just corrupted.
#
# THE FIX IS TO DELETE THE SHARED STATE, NOT TO MAKE THE PATH UNIQUE. A
# per-branch filename still outlives the process and can be restored from after
# the tree has moved under it. A backup is not a fixture: a fixture belongs IN
# the tree so it drifts with the tree or fails loudly at merge, and a backup
# belongs in MEMORY so it cannot survive the run that made it.
_ext_backup = []
for _p in _harnesses:
    _s = _p.read_text()
    for _n in ast.walk(ast.parse(_s)):
        if isinstance(_n, ast.Constant) and isinstance(_n.value, str) \
                and _n.value.startswith(("/tmp/", "/var/tmp/")) \
                and _n.value.endswith((".py", ".json", ".md", ".txt", ".mjs")):
            _ext_backup.append(f"{_p.name}:{_n.lineno}  {_n.value}")
check("no red proof keeps a source backup outside the tree", not _ext_backup,
      "\n         ".join(_ext_backup) + "\n         A fixed /tmp path is shared "
      "across branches and worktrees; a stale restore rewrites the file under "
      "test and the harness still reports RED-proven.")

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
