#!/usr/bin/env python3
"""CERT: a tuple-unpack call site must match EVERY literal return arity of its callee.

WHY THIS EXISTS — five users, six jobs, forty-five days, one message:

    ValueError: not enough values to unpack (expected 3, got 0)

`build_clips_from_words` returned `final_clips, set(removed_indices),
_removal_reason_by_index` on its success path and a bare `return []` on its two
guard paths (empty transcript; Gemini removed every word). The call site unpacked
three. Both guards were therefore a crash, not a guard.

WHAT MADE IT EXPENSIVE was not the crash — it was the LAUNDERING. The recipe
repair loop catches `(ValueError, RuntimeError)` because that is how the plan
validator signals a bad plan (57 raise sites). A ValueError from a Python arity
bug is indistinguishable from one, so the pipeline appended

    "The validator rejected one element of the previous plan. Re-emit the
     complete recipe JSON with this corrected: not enough values to unpack..."

and asked Gemini — twice, at full planning cost — to repair a Python bug it
could not see. Then it told the user their edit plan failed validation. Every
one of those six jobs failed identically on both attempts, deterministically,
because nothing about the re-ask could ever address the actual fault.

SCOPE — deliberately narrow, so it never cries wolf. Only LITERAL tuple/list
returns are judged; a `return some_var` has unknowable arity and is skipped.
Nested defs are skipped (an inner helper's returns are not the outer's).
"""
import ast, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "handler.py"
src = open(PATH).read()
tree = ast.parse(src)
lines = src.splitlines()

def own_returns(fn):
    """Returns belonging to fn itself — NOT to defs nested inside it."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node is not fn:
            owner = None
            for cand in ast.walk(fn):
                if isinstance(cand, (ast.FunctionDef, ast.AsyncFunctionDef)) and cand is not fn:
                    if cand.lineno <= node.lineno <= (cand.end_lineno or cand.lineno):
                        owner = cand
            if owner is None:
                out.append(node)
    return out

funcs = {n.name: n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

violations = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        continue
    tgt = node.targets[0]
    if not isinstance(tgt, (ast.Tuple, ast.List)):
        continue
    if any(isinstance(e, ast.Starred) for e in tgt.elts):
        continue                      # `a, *rest = f()` absorbs any arity
    if not isinstance(node.value, ast.Call):
        continue
    fn_name = getattr(node.value.func, "id", None)
    if fn_name not in funcs:
        continue
    want = len(tgt.elts)
    for r in own_returns(funcs[fn_name]):
        if isinstance(r.value, (ast.Tuple, ast.List)):
            got = len(r.value.elts)
            if got != want:
                violations.append(
                    f"  {PATH}:{node.lineno} unpacks {want} from {fn_name}(), "
                    f"but {PATH}:{r.lineno} returns {got}\n"
                    f"      call:   {lines[node.lineno-1].strip()[:88]}\n"
                    f"      return: {lines[r.lineno-1].strip()[:88]}")

if violations:
    print(f"UNPACK-ARITY: {len(violations)} mismatch(es) — each is a "
          f"ValueError the repair loop will launder into a Gemini re-ask\n")
    print("\n".join(violations))
    sys.exit(1)
print("UNPACK-ARITY: PASS — every literal return matches its unpack call site")
