#!/usr/bin/env python3
"""A decorator that needs a package needs that package IN THE IMAGE.

ROUND 55, ALL FIVE ARMS, AT LAUNCH: "Functions using @modal.fastapi_endpoint
require FastAPI to be installed in their Image." The merge brought the
server's way in (@modal.fastapi_endpoint) from a branch that never ran on
Modal; 80 smokes were green on the laptop, where the decorator is a stub, and
the container refused to start. Nothing ships on a path you have not verified
in the running image — this is the static half of that law: the decorators
the app uses must be paid for in IMG's pip_install.
"""
import ast
import os
import re
import sys

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentic_editor_app.py")).read()
tree = ast.parse(src)

# what the image installs: every string constant inside a pip_install(...) call
installed = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "pip_install":
        for a in n.args:
            for c in ast.walk(a):          # pip_install(["a", "b"]) is a List arg
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    installed.add(re.split(r"[\[<>=!~ ]", c.value)[0].lower())
# what the decorators need
NEEDS = {"fastapi_endpoint": "fastapi", "asgi_app": "fastapi", "wsgi_app": "fastapi"}
used = set()
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for d in n.decorator_list:
            f = d.func if isinstance(d, ast.Call) else d
            name = getattr(f, "attr", None)
            if name in NEEDS:
                used.add(name)

fail = 0
if not installed:
    print("  *** no pip_install() with string arguments found — the image cannot be checked")
    fail += 1
for deco in sorted(used):
    pkg = NEEDS[deco]
    if pkg not in installed:
        print(f"  *** @modal.{deco} is used but {pkg!r} is not in IMG's pip_install — "
              f"every container refuses to start, as round 55 did")
        fail += 1
print(f"smoke_endpoint_deps_in_image: decorators {sorted(used) or 'none'}, "
      f"installed {len(installed)} pkgs, {fail} wrong")
sys.exit(1 if fail else 0)
