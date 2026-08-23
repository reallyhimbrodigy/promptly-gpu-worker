#!/usr/bin/env python3
"""cert_overlay_skip.py — SKIP ONLY WHEN NOTHING CAN PAINT, AND NEVER HALF-SKIP.

PromptlyOverlay renders a TRANSPARENT canvas for the full output duration. On
14% of editorial jobs every layer it can draw is empty — no captions, no MG, no
text overlays, no tight-cut overlays, no generated scenes, no b-roll — and it
renders anyway, then ffmpeg composites a provably invisible ProRes 4444 layer.

SIZED HONESTLY: the overlay runs OFF THE CRITICAL PATH (72.0s inside a 103.4s
micro window), so this is COST and CORRECTNESS, not speed. It pays in full only
on jobs with no micro segments, which are already the fast ones.

THE FAILURE THIS GUARDS IS NOT "SLOW" — IT IS A USER'S CAPTIONS VANISHING.

  1  SAFE BY CONSTRUCTION. The predicate allowlists STRUCTURAL keys and treats
     everything else as potentially-painting, so a content family added later
     defaults to RENDER. Enumerating painting layers instead would silently skip
     the next one somebody adds.
  2  EVERY FAMILY BLOCKS THE SKIP — captions, motionGraphics, textOverlays,
     tightCutOverlays, generatedScenes, broll. Six separate clauses because
     during this work I twice measured occupancy on a subset and drew a
     conclusion from it (99% "near-empty" was three families, not six).
  3  DOUBT RENDERS: a non-dict, an empty dict, or an unknown key with content
     all return False.
  4  ONE DECISION, READ EVERYWHERE. The skip is computed ONCE and consumed at
     every site (chunk build, composite input, chain wait, concat, output
     validator). A site that re-derives it can disagree — and the specific
     disagreement is a filtergraph referencing an input nobody rendered, or a
     validator raising RENDER_FATAL because the file it demands was
     deliberately not produced.

    python3 cert_overlay_skip.py
"""
import os, re, sys
os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    import handler as H
    fails = []
    raw = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())

    BASE = {"sourceUrl": "x", "fps": 30, "width": 1080, "height": 1920,
            "totalDurationInFrames": 600, "clips": [{"a": 1}],
            "transitions": [{"t": 1}], "outro": "none", "broll": [],
            "generatedScenes": [], "caption": None, "textOverlays": [],
            "motionGraphics": [], "tightCutOverlays": []}

    print(f"  [1] empty canvas -> skip = {H._overlay_paints_nothing(BASE)}")
    if not H._overlay_paints_nothing(BASE):
        fails.append("an entirely empty canvas does NOT skip — the lever does nothing")

    # ── 2: every family blocks it ──────────────────────────────────────────
    for k, v in (("caption", {"style": "CleanCut"}),
                 ("motionGraphics", [{"type": "StatCard"}]),
                 ("textOverlays", [{"x": 1}]),
                 ("tightCutOverlays", [{"a": 1}]),
                 ("generatedScenes", [{"s": 1}]),
                 ("broll", [{"b": 1}])):
        d = dict(BASE); d[k] = v
        got = H._overlay_paints_nothing(d)
        print(f"  [2] +{k:<18} -> skip = {got}")
        if got:
            fails.append(f"a canvas carrying {k} was SKIPPED — that content would "
                         f"vanish from the user's video")

    # ── 1 + 3: safe by construction ────────────────────────────────────────
    d = dict(BASE); d["someLayerAddedNextMonth"] = [{"new": 1}]
    unknown_skips = H._overlay_paints_nothing(d)
    print(f"  [1] unknown content key -> skip = {unknown_skips} (must be False)")
    if unknown_skips:
        fails.append("an UNKNOWN key with content was skipped — the predicate "
                     "enumerates painters instead of allowlisting structure, so "
                     "the next family added silently disappears")
    for bad, lbl in ((None, "None"), ({}, "empty dict"), ("nope", "a string")):
        if H._overlay_paints_nothing(bad):
            fails.append(f"{lbl} was treated as skippable — doubt must render")
    print(f"  [3] None/empty/non-dict -> skip = False: "
          f"{not any(H._overlay_paints_nothing(b) for b in (None, {}, 'nope'))}")

    # structural keys must NOT block the skip, or it never fires
    for k in ("clips", "transitions", "outro", "motionTokens"):
        d = dict(BASE)
        d[k] = [{"z": 1}] if k in ("clips", "transitions") else "x"
        if not H._overlay_paints_nothing(d):
            fails.append(f"structural key {k!r} blocked the skip — it describes "
                         f"the canvas or the BASE video and never paints on the "
                         f"overlay, so the lever would never fire")

    # ── 4: one decision, consumed at every site ────────────────────────────
    sites = len(re.findall(r"\b_overlay_skip\b", src))
    decided = len(re.findall(r"_overlay_skip\s*=\s*_overlay_paints_nothing", src))
    print(f"  [4] _overlay_skip decided {decided}x, referenced at {sites} site(s)")
    if decided != 1:
        fails.append(f"the skip is decided {decided} times — two derivations can "
                     f"disagree, and the disagreement is a filtergraph pointing "
                     f"at an input nobody rendered")
    # SITE COUNT, not proximity. Two rewrites of this clause failed correct
    # code — first a regex that needed re.S and matched nothing, then a
    # proximity check anchored on `elif _pipeline_chunks:`, which appears TWICE
    # so str.find inspected the wrong block. The robust invariant is simply
    # that the decision is consumed at EVERY site: remove any one guard and the
    # count drops. It cannot say WHICH guard went, so the expected sites are
    # named here for whoever reads the failure.
    EXPECTED_SITES = 7   # 1 decision + chunk-build, composite-input,
                         # chain-wait, concat, output-validator, and the log
    if sites < EXPECTED_SITES:
        fails.append(
            f"_overlay_skip is consumed at only {sites} site(s), expected "
            f"{EXPECTED_SITES}. One of these guards is gone: chunk-build (would "
            f"render an overlay nobody composites), composite-input (filtergraph "
            f"references an input never rendered), chain-wait (blocks on a future "
            f"that never existed), concat (concats an empty list), or the OUTPUT "
            f"VALIDATOR (raises 'PromptlyOverlay output missing/invalid' on "
            f"exactly the jobs the skip exists to help — a saving turned into a "
            f"RENDER_FATAL).")
    for lit, why in (("c_overlay_idx = None", "composite-input guard"),
                     ("_ov_path = None", "chain-wait guard")):
        if lit not in src:
            fails.append(f"missing {why} ({lit!r})")

    print(f"  [4] guards intact: {not any('guard' in f or 'site' in f for f in fails)}")

    # ── ledgered, so the saving is countable and a wrong skip is visible ───
    print(f"  [5] ledgered: {bool(re.search(chr(34)+'empty_canvas'+chr(34), src))}")
    if not re.search(r'_ledger_dropped\("overlay", None, "empty_canvas"\)', src):
        fails.append("the skip is not ledgered — a saving nobody can count, and "
                     "a wrong predicate would be silent")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT OVERLAY-SKIP: FAIL")
        return 1
    print("  CERT OVERLAY-SKIP: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
