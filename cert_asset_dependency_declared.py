#!/usr/bin/env python3
"""cert_asset_dependency_declared.py — A COMPONENT THAT LOADS AN ASSET MUST BE ABLE TO RESOLVE IT.

MEASURED 2026-08-20. `[overlay-01]` failed with:

    SymbolicateableError: Received a status code of 404 while downloading file
      http://localhost:3004/promptly-<job>__source_canonical.mp4

`[overlay-00]`, the chunk WITHOUT source-reading components, rendered fine. The
chunk that failed is exactly the chunk whose components read the user's video.

THE ASSUMPTION THAT BROKE. The staging comment in handler.py states it outright:

    "if that symlink's target becomes unresolvable at frame-serve time
     (THE TRANSITION/MICRO SUBPROCESS IS THE ONLY SOURCE READER) ..."

That was true when it was written. EvidenceCard and DeviceMockup render
`SourceStill` -> `<Video src={sourceUrl}>`, which makes the OVERLAY subprocess a
source reader too. The invariant the staging path was designed around is no
longer the invariant the renderer obeys.

WHAT THIS CERT ASSERTS — the DECLARATION, not the runtime file:

  1  EVERY frame-composition that renders user footage is in
     FRAME_COMPOSITION_TYPES, so MotionGraphicRenderer hands it `sourceUrl`.
     A component that reads the source but is NOT in that set receives
     `undefined` and refuses silently.
  2  EVERY such component is ALSO in _MG_FRAME_REPLACING_TYPES, since a
     component that replaces the frame with user footage is by definition
     frame-replacing.
  3  The staging comment's "only source reader" claim is either TRUE or
     CARRIES AN EXPLICIT EXCEPTION naming the overlay. A stale invariant in a
     comment is how the next person re-derives the same 404.

WHAT IT CANNOT ASSERT, said plainly rather than implied: whether the file is
actually SERVABLE from the overlay's root at frame-serve time. That is runtime
state in a headless browser, and no static check reaches it. This cert makes the
DEPENDENCY visible; only a render proves the resolution.

    python3 cert_asset_dependency_declared.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TSX = os.path.join(HERE, "src", "remotion", "src")


def main():
    fails = []
    comps = open(os.path.join(TSX, "FrameCompositions.tsx"), encoding="utf-8").read()
    render = open(os.path.join(TSX, "PromptlyRender.tsx"), encoding="utf-8").read()
    handler = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()

    # Which components actually read the user's video? The RENDER decides that,
    # not a list: withSpec(Comp, needsSource=true) is the declaration.
    source_readers = set(re.findall(
        r"export const (\w+)MG = withSpec\(\w+,\s*true\s*\)", comps))
    print(f"  source-reading frame comps (from withSpec): {sorted(source_readers)}")
    if not source_readers:
        fails.append("found ZERO source-reading components — the matcher is "
                     "broken, and a cert that inspects nothing passes everything")

    # ── 1: each one receives sourceUrl ──────────────────────────────────────
    m = re.search(r"FRAME_COMPOSITION_TYPES = new Set\(\[(.*?)\]\)", render, re.S)
    declared = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()
    print(f"  FRAME_COMPOSITION_TYPES (get sourceUrl) : {sorted(declared)}")
    for c in sorted(source_readers - declared):
        fails.append(f"{c} reads the source but is NOT in FRAME_COMPOSITION_TYPES "
                     f"— it receives sourceUrl=undefined and refuses silently")

    # ── 2: reading the source implies replacing the frame ───────────────────
    fr = re.search(r"_MG_FRAME_REPLACING_TYPES = frozenset\(\{(.*?)\}\)", handler, re.S)
    replacing = set(re.findall(r'"(\w+)"', fr.group(1))) if fr else set()
    for c in sorted(source_readers - replacing):
        fails.append(f"{c} renders user footage full-frame but is not in "
                     f"_MG_FRAME_REPLACING_TYPES")
    print(f"  _MG_FRAME_REPLACING_TYPES               : {sorted(replacing)}")

    # ── 3: the staging invariant is not stale ───────────────────────────────
    stale = ("the transition/micro subprocess is the only source reader"
             in handler.lower().replace("\n", " ").replace("  ", " "))
    has_exception = "OVERLAY IS ALSO A SOURCE READER" in handler
    print(f"  staging comment claims 'only source reader': {stale}   "
          f"exception noted: {has_exception}")
    if stale and not has_exception:
        fails.append("handler.py still claims the transition/micro subprocess is "
                     "THE ONLY source reader, but frame comps make the OVERLAY one "
                     "too — that stale invariant is how the 404 gets re-derived")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT ASSET-DEPENDENCY: FAIL")
        return 1
    print("  NOTE: this asserts the DECLARATION. Whether the file is servable "
          "from the overlay root at frame-serve time is runtime state no static "
          "check reaches — only a render proves that.")
    print("  CERT ASSET-DEPENDENCY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
