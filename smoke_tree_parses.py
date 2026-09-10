#!/usr/bin/env python3
"""Every tracked .py parses, and no tracked file carries a conflict marker.

THE DEFECT THIS CLOSES (found 2026-09-09, by accident, while running the suite).
`ff9311f` committed THREE `git stash pop` conflict blocks into handler.py — the
main pipeline worker — and nobody noticed for a day. handler.py has not parsed
on FOUR lane branches since, including the tree round 48 is running from.

WHY IT SURVIVED A DAY. Every consequence was somewhere nobody was looking:
  * handler.py is not one of the ten paths the agentic image mounts, so no
    round could fail on it and no round did.
  * ~20 certs that parse handler.py went red at once, which reads as "the
    handler certs are red again" rather than as one file being broken.
  * the deploy branch never had it (`git merge-base --is-ancestor ff9311f
    zero-reject-routing` exits 1), so nothing live ever broke — the damage was
    a landmine for whoever merged a lane, not an outage.

Taking the "Updated upstream" side of all three blocks reproduces
`ff9311f~1:handler.py` BYTE-IDENTICALLY, which is the proof that the commit
never meant to touch the file: it was a stash-pop accident, not an edit. That
is also why fixing it needed no judgement about someone else's region.

WHAT THIS CHECKS, on every tracked file, not a list:
  1. no conflict markers anywhere (any file type — a marker in .json, .mjs or
     .md breaks a mount just as thoroughly as one in .py)
  2. every tracked .py compiles

DELIBERATELY REPO-WIDE. A check scoped to "the files this lane touches" is a
population fitted to today's lane, and this defect landed in a file its own
commit was not editing.
"""
import ast
import pathlib
import subprocess
import sys

MARKERS = ("<<<<<<< ", ">>>>>>> ")
_r = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
if _r.returncode != 0:
    print("TREE-PARSES: FAILED — git ls-files refused"); sys.exit(2)
files = [f for f in _r.stdout.split("\n") if f.strip()]

marked, broken, unreadable = [], [], []
for f in files:
    p = pathlib.Path(f)
    if not p.is_file():
        continue  # a submodule or a deleted-but-tracked path
    try:
        txt = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue  # binary: no markers to find, nothing to parse
    for ln, line in enumerate(txt.split("\n"), 1):
        # A marker only counts at the START of a line. `>>> ` inside a docstring
        # or a diff quoted in a comment is not a conflict, and a check that
        # cannot tell them apart gets suppressed the first time someone
        # documents a merge.
        if line.startswith(MARKERS) or line == "=======" and any(
                l.startswith("<<<<<<< ") for l in txt.split("\n")):
            marked.append(f"{f}:{ln}  {line[:60]}")
    if f.endswith(".py"):
        try:
            ast.parse(txt)
        except SyntaxError as e:
            broken.append(f"{f}:{e.lineno}  {e.msg}")

print(f"TREE-PARSES  {len(files)} tracked file(s), "
      f"{sum(1 for f in files if f.endswith('.py'))} python")
ok = True
if marked:
    ok = False
    print(f"\n  CONFLICT MARKERS in {len(marked)} place(s):")
    for m in marked[:20]:
        print("    " + m)
if broken:
    ok = False
    print(f"\n  DOES NOT PARSE — {len(broken)} file(s):")
    for b in broken[:20]:
        print("    " + b)
if not ok:
    print("\n  A tracked file in this state is a landmine for whoever merges "
          "the lane.\n  It breaks nothing until it breaks everything.")
    sys.exit(1)
print("  no conflict markers; every tracked .py parses")
