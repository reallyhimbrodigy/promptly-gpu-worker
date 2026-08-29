#!/usr/bin/env python3
"""cert_frame_replacing_types.py — A COMPONENT THAT COVERS THE FACE IS NOT JUDGED ON CLEARING IT.

THE MISCLASSIFICATION. EvidenceCard, DeviceMockup and EmojiCard each render as a
full-frame `AbsoluteFill` with an OPAQUE BACKGROUND: during their window the
source video, and the speaker's face, are not on screen at all. They were
classed as ordinary overlays, so F7 judged them against a single anchor band and
the graceful ladder checked them against caption occupancy and the source's
burned-text bands.

Both gates describe a frame the component does not leave visible. Asking "does a
band clear the face?" of something that has already covered the face is a
question with no meaning, and it can only ever produce a FALSE DROP.

WHAT IT HAS COST SO FAR: nothing observable. These three were requested ZERO
times in every measurement to date, so the ladder never ran on them. This is a
PRECONDITION for the cutaway work, not a fix for an observed loss.

FOUR CLAUSES:

  1  THE SET MATCHES THE MODULE. _MG_FRAME_REPLACING_TYPES is exactly
     frame_compositions.BUILDERS. A hand-maintained list drifts from the thing
     it describes; this makes drift a gate failure.
  2  MEMBERSHIP IS THE RENDER, NOT AN OPINION. Every member is a full-frame
     AbsoluteFill in FrameCompositions.tsx. A type only belongs here if it
     really does replace the frame.
  3  THE EXEMPTION DISCRIMINATES. On input that DROPS an overlay (every band
     burned, dense centred face), a frame-replacing type is PLACED. Without
     this clause the exemption could be a no-op and every other clause would
     still pass.
  4  IT DOES NOT LEAK. Overlay types are still judged, and still dropped, on
     that same input. An exemption that quietly widened would disable F7 for
     the whole catalogue.

    python3 cert_frame_replacing_types.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))
TSX = os.path.join(HERE, "src", "remotion", "src", "FrameCompositions.tsx")
# Overlay controls: each sits ON the footage and must stay judged.
OVERLAYS = ["StatCard", "PillCluster", "DropCard"]


def main():
    import handler as H
    import frame_compositions as fc
    fails = []
    frame_types = set(H._MG_FRAME_REPLACING_TYPES)

    # ── 1: the set matches the module ───────────────────────────────────────
    if frame_types != set(fc.BUILDERS):
        fails.append(f"_MG_FRAME_REPLACING_TYPES {sorted(frame_types)} != "
                     f"frame_compositions.BUILDERS {sorted(fc.BUILDERS)}")
    print(f"  [1] set == BUILDERS: {frame_types == set(fc.BUILDERS)}  "
          f"{sorted(frame_types)}")

    # ── 2: membership is the render ─────────────────────────────────────────
    src = open(TSX, encoding="utf-8").read()
    for t in sorted(frame_types):
        # SCOPE THE SEARCH TO THE COMPONENT, NOT TO A CHARACTER COUNT.
        #
        # This was `[\s\S]{0,400}?<AbsoluteFill` — a fixed 400-char window. On
        # 2026-08-29 the frame-comp lane added six lines of legitimate setup to
        # EvidenceCard (useCardEntrance + mgTextMetrics for the font census) and
        # pushed its `<AbsoluteFill` to +528. The cert failed, and the component
        # had not changed structurally at all: it is still a full-frame
        # AbsoluteFill, so the exemption was still correct and the gate was
        # blocking a deploy over a magic number.
        #
        # A width is not the property. The property is "the first element this
        # component renders is an AbsoluteFill", so search from the export to
        # the NEXT export — the component's own body — which cannot leak into a
        # neighbour and cannot rot when a line is added.
        m0 = re.search(r"export const " + re.escape(t) + r"\s*:\s*React\.FC", src)
        ok = False
        if m0:
            nxt = re.search(r"\nexport const ", src[m0.end():])
            body = src[m0.end(): m0.end() + (nxt.start() if nxt else len(src))]
            # FIRST JSX element in the body, so a component that renders a
            # non-fullscreen wrapper and only later nests an AbsoluteFill still
            # FAILS — which is the misclassification this clause exists to catch.
            first_tag = re.search(r"<([A-Za-z][\w.]*)", body)
            ok = bool(first_tag) and first_tag.group(1) == "AbsoluteFill"
        print(f"  [2] {t:14} renders as a full-frame AbsoluteFill: {ok}")
        if not ok:
            fails.append(f"{t} is in _MG_FRAME_REPLACING_TYPES but does not "
                         f"render as a full-frame AbsoluteFill — it does not "
                         f"replace the frame and must not be exempt")

    # ── 3 + 4: discrimination, on input that drops an overlay ───────────────
    face = [{"found": True, "t": i / 10.0, "cy": 960} for i in range(25)]
    plan = {"source_text_regions": ["top", "center", "bottom"]}
    placed, dropped = [], []
    for t in sorted(frame_types) + OVERLAYS:
        out = H._place_component_gracefully(t, 0.0, 2.0, face, plan)[0]
        (placed if out == "placed" else dropped).append((t, out))
    print(f"  [3] frame-replacing placed on drop-input: "
          f"{[t for t, _ in placed if t in frame_types]}")
    print(f"  [4] overlays still judged/dropped       : "
          f"{[f'{t}={o}' for t, o in dropped]}")
    for t in frame_types:
        if t not in [x for x, _ in placed]:
            fails.append(f"{t} was NOT placed on input where it covers the "
                         f"frame — the exemption is not doing its work")
    for t in OVERLAYS:
        if t in [x for x, _ in placed]:
            fails.append(f"OVERLAY {t} was placed on input that must drop it — "
                         f"the exemption has leaked past frame-replacing types")
    if not dropped:
        fails.append("NOTHING dropped on the drop-input — the scenario no "
                     "longer discriminates and clause 3 proves nothing")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT FRAME-REPLACING: FAIL")
        return 1
    print("  CERT FRAME-REPLACING: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
