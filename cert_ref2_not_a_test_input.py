#!/usr/bin/env python3
"""REF-2 IS A BAR, NOT AN INPUT. `[Rule 1, Rule 3]`

OWNER RULING 2026-08-17, after watching the first Lumen edit end to end:
REF-2 is **already fully edited**. The planner's refusal to decorate it —
"already contains bespoke 3D motion graphics... declined extra scenes to prevent
clutter" — was CORRECT judgement, not a defect.

That settles a question this project spent real money re-asking. A finished
video cannot measure whether the planner decorates a RAW one, so every run that
used REF-2 as an input was measuring the wrong thing and reading a correct
decline as a failure. It is the third corpus-selection error in the same class,
and the only one the owner had to resolve by watching the output himself.

  RETIRED as a test input — nothing may plan, transcribe, probe or mount it.
  KEPT as the bar — `golden/lumen-refs/` stays exactly where it is, and an edit
  is still judged against it by eye. Deleting it would lose the reference; the
  files are deliberately untouched.

WHAT THIS ALLOWS. Prose. Comments do not appear in the AST at all, and
docstrings are exempted by name below, so the reasoning above can be written
down wherever it is useful. What fails is a ref2 path reaching CODE — a mount, a
path constant, an argument.

    python3 cert_ref2_not_a_test_input.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The harnesses that can spend money on a source. A ref2 literal in any of them
# is a run about to measure the wrong thing.
WATCHED = ["lumen_first_edit_app.py", "ab_matrix_app.py", "lumen_first_light_app.py",
           "lumen_reel_app.py", "cert_golden_output.py", "handler.py",
           "modal_app.py"]   # the DEPLOY path — a ref2 literal here is the worst case


def _docstring_nodes(tree):
    """Constant nodes that ARE docstrings — exempt, because prose is allowed."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(n, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def main():
    fails = []
    checked = 0
    for fn in WATCHED:
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            continue
        checked += 1
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError as e:
            fails.append(f"{fn} does not parse ({e})")
            continue
        exempt = _docstring_nodes(tree)
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in exempt:
                v = n.value.lower()
                if "ref2" in v or "lumen-refs" in v:
                    fails.append(f"{fn}:{n.lineno} uses {n.value[:60]!r} as CODE — "
                                 f"REF-2 is retired as a test input (owner ruling "
                                 f"2026-08-17: it is already fully edited, so the "
                                 f"decline it produces is correct and measures nothing)")

    if not checked:
        print("CERT REF2-NOT-AN-INPUT: FAIL\n  - no watched harness found; the "
              "check would pass vacuously")
        return 1
    if fails:
        print("CERT REF2-NOT-AN-INPUT: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT REF2-NOT-AN-INPUT: PASS")
    print(f"  {checked} harness(es) checked; no ref2 path reaches code")
    print("  prose and docstrings are deliberately still allowed")
    print("  golden/lumen-refs/ is UNTOUCHED — it remains the bar to judge against")
    return 0


if __name__ == "__main__":
    sys.exit(main())
