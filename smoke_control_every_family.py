#!/usr/bin/env python3
"""The same-window control is built for EVERY fixture, not only captioned ones.

BUILDER-2 BUILT IT INSIDE THE CAPTION-COMPOSITE BRANCH and flagged the
consequence rather than reaching into my file: `motion` came back
ctrl_composite=None, because a fixture with no caption pass never enters that
branch. On round 60 `card` was still scored under `window_elsewhere` — the
control that measured -10.75 to 8.13 dB on NO INK AT ALL, while the same-window
null reads exactly 0.00.

A CONTROL THAT EXISTS FOR SOME FAMILIES IS NOT A CONTROL. 46.5% of traffic is
the silent route; without this, a silent-route source that places text falls
back to the window control and every verdict it produces reads UNVALIDATED.

THREE PROPERTIES:
  1. the build is reachable OUTSIDE the caption branch;
  2. _record_effect picks the control up without any caller passing it — a
     fix that required eight call sites to change is a fix that misses one;
  3. the helper returns None and FAILS LOUDLY rather than silently handing
     back a control that is not one.
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

fail = 0
src = open(os.path.join(HERE, "agentic_editor_app.py")).read()
tree = ast.parse(src)

if not hasattr(A, "build_same_window_control"):
    print("  *** the control build is not a module-level helper — it cannot "
          "be reached from outside the caption branch")
    sys.exit(1)

edit_fn = next((n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
calls = [n for n in ast.walk(edit_fn)
         if isinstance(n, ast.Call)
         and getattr(n.func, "id", "") == "build_same_window_control"]
if len(calls) < 2:
    print(f"  *** build_same_window_control is called {len(calls)}x in edit() "
          f"— a captioned fixture and a silent one need different bases, so "
          f"one call means one of them has no control")
    fail += 1

# 2. the pickup is automatic
rec = next((n for n in ast.walk(edit_fn)
            if isinstance(n, ast.FunctionDef) and n.name == "_record_effect"), None)
if rec is None:
    print("  *** _record_effect moved")
    fail += 1
else:
    picks = any(isinstance(n, ast.Attribute) and n.attr == "get"
                and getattr(getattr(n, "value", None), "id", "") == "_ctrl_same_holder"
                for n in ast.walk(rec))
    if not picks:
        print("  *** _record_effect does not pick the control up itself — a "
              "fix that needs every call site changed is a fix that misses one")
        fail += 1

# 3. the helper says so when it cannot build one
hsrc = inspect.getsource(A.build_same_window_control)
for need, why in (("control_layer_unbuildable", "a bad empty layer"),
                  ("control_composite_failed", "a failed composite")):
    if need not in hsrc:
        print(f"  *** the helper does not fail() on {why}")
        fail += 1
if 'led["ctrl_composite"]' not in hsrc:
    print("  *** the helper does not record whether a control exists — a "
          "fallback would be assumed rather than visible")
    fail += 1

print(f"smoke_control_every_family: {len(calls)} build site(s), {fail} wrong")
sys.exit(1 if fail else 0)
