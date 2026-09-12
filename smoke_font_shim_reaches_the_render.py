#!/usr/bin/env python3
"""The bundler that RENDERS must apply the font shim, not only the one that doesn't.

MEASURED INSIDE THE RENDER LOOP, on a zoom composition that draws no text:

    Fetching Roboto font          n=96  total 253,971ms  max 3,460ms
    Fetching Oswald font          n=96  total 252,243ms  max 3,458ms
    Fetching JetBrains Mono font  n=48  total 144,816ms  max 3,489ms

240 network font fetches per render — while src/shims/google-fonts/_shared.ts
asserts in its own header: "Zero runtime cost. Zero network dependency. Zero
@font-face rules." The shim is real and correct. prebundle.mjs wires it
through webpackOverride. remotion_batch.mjs — the path every job renders
through — called bundle() with NO webpackOverride, so the alias never applied
and the real @remotion/google-fonts shipped.

A CORRECT, DOCUMENTED FIX THAT IS INERT because the caller that mattered did
not use it. Three legs:
  1. every bundle() in the render path passes webpackOverride;
  2. both bundlers read ONE alias map, so it cannot be right in one and absent
     in the other;
  3. every font the components import has an alias — an unaliased import
     silently re-introduces the fetch, which is how this class returns.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# THE MOUNTED TREE, DERIVED THE WAY THE APP DERIVES IT — not this worktree's
# copy. `_REMOTION_SRC = ../../src/remotion` resolves to the MAIN CHECKOUT, so
# the lane worktree has a src/remotion that never reaches a container. I edited
# that copy for a week and two ladder rungs measured a component that was not
# the one rendering. A check that reads the unmounted copy would pass on code
# nothing runs — the same failure, one level up.
REMOTION = os.path.abspath(os.path.join(HERE, "..", "..", "src", "remotion"))

fail = 0
if not os.path.isdir(REMOTION):
    print(f"  *** {REMOTION} does not exist — this check cannot see the tree "
          f"that is actually mounted")
    sys.exit(1)
_app = open(os.path.join(HERE, "agentic_editor_app.py")).read()
if '"..", "..", "src", "remotion"' not in _app:
    print("  *** the app no longer derives _REMOTION_SRC as ../../src/remotion "
          "— this check may now be reading the wrong tree, which is exactly "
          "the defect it exists to prevent")
    fail += 1

batch = open(os.path.join(HERE, "remotion_batch.mjs")).read()
pre = open(os.path.join(REMOTION, "prebundle.mjs")).read()
al = open(os.path.join(REMOTION, "font-aliases.mjs")).read()

for name, src in (("remotion_batch.mjs", batch), ("prebundle.mjs", pre)):
    for m in re.finditer(r"bundle\(\{(.{0,600}?)\}\)", src, re.S):
        if "webpackOverride" not in m.group(1):
            print(f"  *** {name}: a bundle() call with NO webpackOverride — "
                  f"the font shim does not reach it and every render it "
                  f"produces fetches fonts over the network")
            fail += 1
    if "font-aliases.mjs" not in src:
        print(f"  *** {name} does not read the shared alias map — two copies "
              f"drift, and one being right is what made this invisible")
        fail += 1

aliased = set(re.findall(r'"@remotion/google-fonts/([A-Za-z]+)"', al))
imported = set()
for root, _dirs, files in os.walk(os.path.join(REMOTION, "src")):
    if "shims" in root:
        continue
    for fn in files:
        if not fn.endswith((".ts", ".tsx")):
            continue
        with open(os.path.join(root, fn), errors="ignore") as fh:
            imported |= set(re.findall(
                r'from "@remotion/google-fonts/([A-Za-z]+)"', fh.read()))
missing = sorted(imported - aliased)
for f in missing:
    print(f"  *** a component imports @remotion/google-fonts/{f} and no alias "
          f"covers it — the real module loads and the fetch comes back")
    fail += len(missing[:1])
if not imported:
    print("  *** no google-fonts imports found at all — this check is looking "
          "in the wrong place and would pass forever")
    fail += 1

print(f"smoke_font_shim_reaches_the_render: {len(imported)} font import(s), "
      f"{len(aliased)} aliased, {len(missing)} unaliased, {fail} wrong")
sys.exit(1 if fail else 0)
