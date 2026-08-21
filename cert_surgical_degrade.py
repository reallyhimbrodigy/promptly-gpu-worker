#!/usr/bin/env python3
"""cert_surgical_degrade.py — ONE BAD COMPONENT MUST NOT COST THE DECORATION LAYER.

MEASURED 2026-08-20, and verified by a falsifiable prediction. One EvidenceCard
whose <Video> 404'd on the staged source took down EVERY decoration in the
video:

    [overlay-01] SymbolicateableError: 404 ... __source_canonical.mp4
    rung=1 SKIPPED — inputs byte-identical
    stripped=['motion_graphics','text_overlays','transitions',
              'tight_cut_overlays','broll','generated_scenes']

The prediction that confirmed it: StatCard is VISIBLE at t=3.0s in the render
WITHOUT the card, and ABSENT at t=3.6s in the render with it. StatCard does not
reference that asset. It was collateral.

THE PATTERN THIS FOLLOWS is the graceful-placement ladder already shipped for
components: try the NARROWEST repair first, widen only when the narrow one
cannot apply. A render error that NAMES its asset names its culprit; everything
else is innocent.

CLAUSES:

  1  THE ASSET IS EXTRACTED CORRECTLY from a real error string. The first cut
     used a non-greedy \\S*? and returned "localhost:3004" — the first path
     segment, not the filename. A surgical rung that mis-reads the culprit
     drops the wrong components, which is worse than dropping all of them.
  2  ONLY THE IMPLICATED COMPONENTS DROP — the source-reading frame comps for
     a source asset.
  3  THE INNOCENT SURVIVE — StatCard, text overlays, transitions and b-roll are
     untouched. This is the whole point; without it the rung is the old strip
     with extra steps.
  4  NO MATCH RETURNS EMPTY, so the caller WIDENS to the wholesale strip rather
     than silently doing nothing and re-rendering an identical failing spec.

    python3 cert_surgical_degrade.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")

REAL_ERR = ("RuntimeError: [overlay-01] Remotion render failed (rc=1) in 29.6s: "
            "SymbolicateableError: Received a status code of 404 while downloading "
            "file http://localhost:3004/promptly-0fac87fa-wvo0fcb9__source_canonical.mp4 .")
RX = r"status code of 404 while downloading file\s+\S*/([^/\s]+)"


def main():
    import handler as H
    fails = []

    # ── 1: the culprit is read correctly ────────────────────────────────────
    m = re.search(RX, REAL_ERR)
    asset = m.group(1) if m else None
    print(f"  [1] extracted asset: {asset!r}")
    if asset != "promptly-0fac87fa-wvo0fcb9__source_canonical.mp4":
        fails.append(f"asset extraction wrong: {asset!r} — a surgical rung that "
                     f"mis-reads the culprit drops the wrong components")
    # the exact regression that bit: non-greedy grabs the host, not the file
    bad = re.search(r"status code of 404 while downloading file\s+\S*?/([^/\s]+)", REAL_ERR)
    if bad and bad.group(1) == asset:
        fails.append("greedy and non-greedy agree — the fixture no longer "
                     "discriminates, so clause 1 proves nothing")
    print(f"      non-greedy would have given: {bad.group(1)!r}  (the bug)")

    # ── 2 + 3: implicated drop, innocent survive ────────────────────────────
    plan = {
        "motion_graphics": [{"type": "StatCard"}, {"type": "EvidenceCard"},
                            {"type": "DeviceMockup"}, {"type": "EmojiCard"}],
        "broll_clips": [{"_local_path": "/tmp/unrelated.mp4"}],
        "text_overlays": [{"x": 1}], "transitions": [{"t": 1}],
    }
    dropped = H._surgical_drop_for_asset(plan, asset)
    survivors = [g["type"] for g in plan["motion_graphics"]]
    print(f"  [2] dropped   : {dropped}")
    print(f"  [3] survivors : mgs={survivors} overlays={len(plan['text_overlays'])} "
          f"transitions={len(plan['transitions'])} broll={len(plan['broll_clips'])}")
    for t in ("EvidenceCard", "DeviceMockup"):
        if f"mg:{t}" not in dropped:
            fails.append(f"{t} reads the source but was NOT dropped for an "
                         f"unresolvable source asset")
    for t in ("StatCard", "EmojiCard"):
        if t not in survivors:
            fails.append(f"INNOCENT {t} was destroyed — it does not reference "
                         f"the failing asset (this is the original defect)")
    if not plan["text_overlays"] or not plan["transitions"] or not plan["broll_clips"]:
        fails.append("innocent non-MG decorations were destroyed — the surgical "
                     "rung is behaving like the wholesale strip")

    # ── 4: no match widens ──────────────────────────────────────────────────
    plan2 = {"motion_graphics": [{"type": "StatCard"}], "broll_clips": [],
             "text_overlays": [{"x": 1}]}
    none_dropped = H._surgical_drop_for_asset(plan2, "something-unrelated.png")
    print(f"  [4] unmatched asset -> dropped={none_dropped} (must be empty so the "
          f"caller widens)")
    if none_dropped:
        fails.append(f"an unmatched asset dropped {none_dropped} — the rung must "
                     f"return empty so the ladder widens instead")
    if len(plan2["motion_graphics"]) != 1:
        fails.append("an unmatched asset still mutated the plan")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT SURGICAL-DEGRADE: FAIL")
        return 1
    print("  CERT SURGICAL-DEGRADE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
