#!/usr/bin/env python3
"""THE EDITORIAL PLANNER IS OVERRIDABLE AND PINNED. `[Rule 1, §4.7]`

WHY BOTH HALVES ARE LOAD-BEARING (2026-08-17)

  OVERRIDABLE, because §4.7 is `change dark -> differ verdict -> keep or kill`
  and an editorial-model swap that requires a code edit per arm cannot be
  staged behind the differ. The measured case for gemini-3.7-flash on the
  editorial path (3/3 replicated, component parity, better latency) is worth
  nothing until it can be run against the frozen goldens without shipping it
  to a user first.

  PINNED, because a planner whose identity can change without a deploy cannot
  be held to a differ verdict — a GREEN would be scored against a model that
  no longer exists by the time it matters. The chat path already paid for this
  lesson: an alias was blamed, a pin shipped on the hypothesis, and the real
  cause was prepay depletion. The pin was still right; the reasoning was not.

  A `-latest` alias is therefore refused OUTRIGHT as the default. `-preview` is
  allowed: `gemini-3.1-pro-preview` is a concrete, resolvable version name, not
  a moving pointer.

  The default must ALSO stay unchanged from what production runs today, so that
  merely shipping the override cannot silently re-point the live planner. This
  check pins the default by name for exactly that reason: changing which model
  production plans on becomes a deliberate, visible edit to THIS file, not a
  side effect.

    python3 cert_editorial_model_pinned.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")

# The model production plans on TODAY. Changing the live planner must be a
# deliberate edit here, reviewed as its own change.
EXPECTED_DEFAULT = "gemini-3.1-pro-preview"
ENV_KEY = "PROMPTLY_EDITORIAL_MODEL"


def main():
    tree = ast.parse(open(HANDLER).read())
    assign = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "GEMINI_EDITORIAL_MODEL":
                    assign = n
    fails = []
    if assign is None:
        print("CERT EDITORIAL-MODEL: FAIL\n  - GEMINI_EDITORIAL_MODEL not found")
        return 1

    # Every string constant and every env key mentioned in the assignment.
    strings, envkeys = [], []
    for n in ast.walk(assign.value):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            strings.append(n.value)
        if isinstance(n, ast.Call):
            f = n.func
            if getattr(f, "attr", None) == "get" and isinstance(getattr(f, "value", None), ast.Attribute):
                if getattr(f.value, "attr", None) == "environ" and n.args:
                    a0 = n.args[0]
                    if isinstance(a0, ast.Constant):
                        envkeys.append(a0.value)

    # 1. OVERRIDABLE — the differ cannot stage an arm it cannot select.
    if ENV_KEY not in envkeys:
        fails.append(f"GEMINI_EDITORIAL_MODEL does not read {ENV_KEY} — an "
                     f"editorial-model arm could not be staged behind the "
                     f"differ without editing code per arm (§4.7)")

    # 2. PINNED — never a moving alias.
    aliases = [s for s in strings if "latest" in s.lower()]
    if aliases:
        fails.append(f"the editorial model may not be an alias: {aliases} — a "
                     f"planner that can change without a deploy cannot be held "
                     f"to a differ verdict")

    # 3. THE DEFAULT IS THE MODEL PRODUCTION RUNS TODAY. Shipping the override
    #    must not silently re-point live traffic.
    if EXPECTED_DEFAULT not in strings:
        fails.append(f"the default is no longer {EXPECTED_DEFAULT!r} (found "
                     f"{strings!r}) — changing the LIVE planner must be a "
                     f"deliberate, reviewed edit, not a side effect of adding "
                     f"an override")

    # 4. THE STARTUP LOG REPORTS THE VALUE, NOT A CONSTANT. This file has
    #    already shipped a log that printed a hardcoded number while the real
    #    value differed (the thinking-budget log), which made a matrix
    #    unreadable until it was caught.
    src = open(HANDLER).read()
    if "editorial={GEMINI_EDITORIAL_MODEL}" not in src:
        fails.append("the startup line no longer interpolates "
                     "GEMINI_EDITORIAL_MODEL — a log that names a constant "
                     "instead of the value in force cannot confirm which arm ran")

    if fails:
        print("CERT EDITORIAL-MODEL: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT EDITORIAL-MODEL: PASS")
    print(f"  overridable via {ENV_KEY} (an arm can be staged behind the differ)")
    print(f"  default pinned to {EXPECTED_DEFAULT} — live traffic unchanged by this edit")
    print("  no -latest alias: the planner cannot move without a deploy")
    print("  startup log prints the value in force, not a constant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
