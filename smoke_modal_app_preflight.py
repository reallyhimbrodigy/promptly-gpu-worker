#!/usr/bin/env python3
"""SMOKE: a Modal app module must be importable and path-resolvable OFF the local tree.

EARNED 2026-09-07, four launches for one number. Modal executes the app module
INSIDE the container as well as locally, and three separate local-only
assumptions each killed a run before it painted a single frame:

  1. `from agentic_editor_app import IMG` — resolves locally, ModuleNotFound in
     the container, which does not have that file.
  2. module-level `open(".../src/remotion/src/CaptionCostProbe.tsx")` with a path
     relative to the source tree — FileNotFoundError in the container.
  3. an edit script that raised NameError so the fix never applied, and I
     launched anyway. That one is on the verify-the-mutation rule, not on Modal.

Every one was checkable locally in a second. This is that second.

WHAT IT CHECKS, by simulating the container's view:
  * every module-level import resolves from a directory that is NOT this one;
  * no module-level open()/read() of a path relative to __file__ or the repo —
    those are the ones that vanish in the container. Reads belong inside the
    function, from a mounted path.

DELIBERATELY STATIC for the path rule: actually importing would run the reads
and mask them behind whatever happens to exist locally, which is the whole bug.
"""
import ast, os, subprocess, sys, tempfile

TARGETS = [f for f in sorted(os.listdir(os.path.dirname(os.path.abspath(__file__))))
           if f.endswith("_app.py")]
HERE = os.path.dirname(os.path.abspath(__file__))
fails = []

for t in TARGETS:
    p = os.path.join(HERE, t)
    src = open(p, encoding="utf-8", errors="ignore").read()
    if "import modal" not in src:
        continue
    tree = ast.parse(src)

    # ── module-level file reads on tree-relative paths ─────────────────────
    for node in tree.body:
        for n in ast.walk(node):
            if not (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open"):
                continue
            seg = ast.dump(n)
            if "__file__" in seg or "dirname" in seg or "src" in seg:
                fails.append(
                    f"{t}:{n.lineno} module-level open() on a tree-relative path — "
                    f"the container executes this module and that path is not there. "
                    f"Mount the file and read it inside the function.")

    # ── module-level imports of sibling repo modules ──────────────────────
    for node in tree.body:
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if os.path.exists(os.path.join(HERE, m + ".py")):
                # A sibling .py imported at module level must be MOUNTED, or the
                # container's import of this module fails outright.
                if f'"{m}.py"' not in src and f"/{m}.py" not in src:
                    fails.append(
                        f"{t}:{node.lineno} imports sibling `{m}` at module level "
                        f"but never mounts {m}.py — ModuleNotFoundError in the "
                        f"container, before any work runs.")

if fails:
    print(f"MODAL-PREFLIGHT: {len(fails)} FAILED")
    for f in sorted(set(fails)):
        print("  - " + f)
    sys.exit(1)
print(f"MODAL-PREFLIGHT: PASS — {len(TARGETS)} app module(s) safe to launch")
