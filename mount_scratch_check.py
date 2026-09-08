#!/usr/bin/env python3
"""Is this checkout clean enough to launch a round from?

I ABORTED ROUND 37. I ran Remotion diagnostics in the MAIN checkout's
src/remotion — four .mjs files and 8.1 MB of fixture video in public/ — while a
round was launching from that same checkout. Three arms had gone out. Arms 1-3
would have mounted one tree and 4-5 another, and the round would have scored as
one cohort. Builder-1's fingerprint caught it, which is the first time that
guard has fired on real drift rather than in a RED proof.

THE MECHANISM IS NARROWER THAN IT LOOKED, and the narrow version is the useful
one. src/remotion is NOT shared between worktrees — every worktree has its own
real directory (the lane worktrees have 37 entries; the main checkout had 46,
mine included). `nest_diag.mjs` existed in exactly one place. The hazard is not
"these paths are communal", it is:

    NEVER WRITE INTO THE CHECKOUT A ROUND RUNS FROM.

That distinction matters because the general rule — keep scratch out of the nine
mounted paths — would cost the ability to render Remotion locally at all, and
local rendering is how the props-nesting bug, the four invisible StatCards and
the inverted zoom threshold were all found in one week. Diagnostics belong in a
worktree that no round launches from; there they are free.

WHAT THIS REPORTS: untracked or modified files under the nine paths the image
mounts, for a given checkout. Those files are genuinely part of the arm — the
image really does change — so a round launched over them is measuring a tree
nobody described.

    python3 mount_scratch_check.py [checkout-dir]

Exit 1 if anything is there. It does not distinguish "scratch someone forgot"
from "work in progress"; it cannot, and that is the point — neither can the
image.
"""
import os
import subprocess
import sys

# The nine paths agentic_editor_app.py mounts (IMG, add_local_dir/add_local_file).
# Kept in this order so the output reads like the image definition.
MOUNTED = [
    "src/remotion",
    "knowledge",
    "src/assets/sounds",
    "_asset_inventory.json",
    "moodreel_editor.py",
    "type_registries.py",
    "remotion_batch.mjs",
    "agentic_editor_app.py",
]
# ~/.claude/skills is mounted too and lives outside the repo, so git cannot see
# it. Named here so its absence from the check is a stated gap, not an oversight.
UNCHECKED = ["~/.claude/skills (outside the repo — git cannot see it)"]

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
r = subprocess.run(["git", "status", "--porcelain", "--"] + MOUNTED,
                   cwd=root, capture_output=True, text=True)
if r.returncode != 0:
    print(f"MOUNT-SCRATCH: FAILED — git status refused in {root}\n{r.stderr[:300]}")
    sys.exit(2)

rows = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
print(f"MOUNT-SCRATCH  ({root})")
print(f"  checked {len(MOUNTED)} mounted paths; not checked: {UNCHECKED[0]}")
if not rows:
    print("  CLEAN — nothing untracked or modified under the mounted paths")
    sys.exit(0)

# Size matters here and nowhere else: a 4 KB script and a 4.7 MB fixture are the
# same kind of defect but not the same size of one, and the fingerprint reports
# bytes.
total = 0
print(f"\n  {len(rows)} file(s) would go into the image:")
for ln in rows:
    st, path = ln[:2].strip(), ln[3:].strip()
    full = os.path.join(root, path)
    sz = 0
    if os.path.isfile(full):
        sz = os.path.getsize(full)
    elif os.path.isdir(full):
        for dp, _, fs in os.walk(full):
            for f in fs:
                try:
                    sz += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
    total += sz
    print(f"    {st:<3} {sz/1e6:8.2f} MB  {path}")
print(f"    {'':<3} {total/1e6:8.2f} MB  TOTAL")
print("\n  A round launched over these mounts a tree nobody described. Move them "
      "out, or\n  launch from a checkout that does not carry them — diagnostics "
      "belong in a worktree\n  no round runs from.")
sys.exit(1)
