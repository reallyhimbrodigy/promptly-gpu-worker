#!/usr/bin/env python3
"""A SAFE-EDIT FALLBACK NAMES ITS OWN CAUSE. `[Rule 1]`

WHY (2026-08-17). The Step-A differ found 5 of 12 control cells falling to the
deterministic safe edit. The plan said `notes: "safe-edit fallback"` and nothing
else, so the run could not distinguish:

    capacity   (retry-then-timeout under concurrent load)
    transport  (recipe_transport:<Error>)
    schema     (RECIPE_INVALID:<detail>)
    config     (editorial_live_off)

Four causes, four different fixes, and the wall clocks were split 3 long /
2 short — which means it was demonstrably NOT one cause. The measurement could
not settle it because `_safe_reason` was a local that died with its frame.

This is the same class as the ASR diagnostics hole closed earlier the same day:
the VERDICT survived into the row, the EVIDENCE did not.

THE RULE: every assignment to `_safe_reason` routes through `_mark_safe_edit()`,
so a new fallback door cannot be opened without naming itself. The only exempt
assignment is the initial empty-string sentinel.

    python3 cert_safe_edit_reason.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")


def main():
    src = open(HANDLER).read()
    tree = ast.parse(src)
    fails = []

    assigns = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "_safe_reason":
                    assigns.append(n)

    if not assigns:
        print("CERT SAFE-EDIT-REASON: FAIL\n  - no _safe_reason assignment found")
        return 1

    named, sentinel, unnamed = 0, 0, []
    for n in assigns:
        v = n.value
        if isinstance(v, ast.Constant) and v.value == "":
            sentinel += 1
            continue
        if isinstance(v, ast.Call) and getattr(v.func, "id", None) == "_mark_safe_edit":
            named += 1
            continue
        unnamed.append(n.lineno)

    if unnamed:
        fails.append(f"_safe_reason assigned WITHOUT _mark_safe_edit at line(s) "
                     f"{unnamed} — that fallback door is unnamed, and a differ "
                     f"cannot tell capacity from transport from schema")

    if named < 4:
        fails.append(f"only {named} named fallback reasons; the four known doors "
                     f"are editorial_live_off, recipe wall-clock, "
                     f"recipe_transport, RECIPE_INVALID")

    # The recorder is module-scoped ON PURPOSE — set deep in the recipe closure,
    # read by callers outside it — and must reset per call, because a stale
    # reason attributed to the wrong plan is worse than no reason at all.
    if "_LAST_SAFE_EDIT" not in src:
        fails.append("the module-scoped recorder _LAST_SAFE_EDIT is gone")
    else:
        fn = None
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == "generate_edit_gemini":
                fn = n
        reset = False
        if fn is not None:
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                        and n.value.value is None:
                    for t in n.targets:
                        if isinstance(t, ast.Subscript) and \
                                getattr(t.value, "id", None) == "_LAST_SAFE_EDIT":
                            reset = True
        if not reset:
            fails.append("_LAST_SAFE_EDIT is never reset inside "
                         "generate_edit_gemini — a stale reason would be "
                         "attributed to the next plan")

    if fails:
        print("CERT SAFE-EDIT-REASON: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT SAFE-EDIT-REASON: PASS")
    print(f"  {named} fallback doors, every one routed through _mark_safe_edit")
    print(f"  {sentinel} sentinel init exempt")
    print("  reason resets per call — no cross-plan attribution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
