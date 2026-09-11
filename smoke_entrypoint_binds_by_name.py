#!/usr/bin/env python3
"""The entrypoint must bind edit() BY NAME, and every argument must exist.

ROUND 56, ALL FIVE ARMS, DEAD ON ARRIVAL: "ValueError: unknown url type: '24'".
A merge inserted prior_plan/instruction/result_url as parameters 3-5 of edit()
and main() still passed ten positionals, so the presigned source URL landed on
`prior_plan` and the iteration count landed on `src_url`. Nothing caught it:
pyflakes is clean on a positional call, the in-container import probe imports
without calling, and all 80 smokes passed. The only thing that could have
caught it is binding the call.

TWO CHECKS, because the second is the one that survives a rename:
  1. no POSITIONAL argument past the first two — a keyword call cannot drift
     when a signature grows;
  2. the call BINDS against the real signature (inspect.Signature.bind), so a
     keyword that no longer exists fails here rather than in a container.
"""
import ast
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

src = open(os.path.join(HERE, "agentic_editor_app.py")).read()
tree = ast.parse(src)
fail = 0

main_fn = next((n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
if main_fn is None:
    print("  *** no main() — the entrypoint moved")
    sys.exit(1)

calls = [n for n in ast.walk(main_fn) if isinstance(n, ast.Call)
         and getattr(n.func, "attr", "") in ("remote", "local")
         and getattr(getattr(n.func, "value", None), "id", "") == "edit"]
if not calls:
    print("  *** main() does not call edit.remote/.local — nothing to check")
    sys.exit(1)

# the REAL signature, unwrapped from the modal decorator
fn = A.edit
for _ in range(6):
    inner = getattr(fn, "__wrapped__", None) or getattr(fn, "_info", None)
    fn = getattr(getattr(fn, "_info", None), "raw_f", None) or inner or fn
    if inspect.isfunction(fn):
        break
if not inspect.isfunction(fn):
    print("  *** could not reach edit()'s raw function through the decorator "
          "— the bind cannot be checked")
    sys.exit(1)
sig = inspect.signature(fn)

for c in calls:
    if len(c.args) > 2:
        print(f"  *** edit.{c.func.attr}() passes {len(c.args)} POSITIONAL "
              f"arguments at line {c.lineno} — a signature that grows in the "
              f"middle silently rebinds them, as it did in round 56")
        fail += 1
    kw = {k.arg: None for k in c.keywords if k.arg}
    try:
        sig.bind(*(["x"] * len(c.args)), **{k: "x" for k in kw})
    except TypeError as e:
        print(f"  *** the call at line {c.lineno} does not BIND against "
              f"edit()'s signature: {e}")
        fail += 1
    unknown = [k for k in kw if k not in sig.parameters]
    for u in unknown:
        print(f"  *** edit() has no parameter {u!r}")
        fail += 1

print(f"smoke_entrypoint_binds_by_name: {len(calls)} call(s), {fail} wrong")
sys.exit(1 if fail else 0)
