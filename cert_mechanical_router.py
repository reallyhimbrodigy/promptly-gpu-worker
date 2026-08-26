#!/usr/bin/env python3
"""THE ROUTER'S NEAR-MISS MATRIX. `[Rule 1]`

A mechanical route that mis-fires produces a WRONG EDIT with no model in the loop
to catch it — silently, deterministically, every time. A creative route that
handles a mechanical request wastes $0.02 and one round trip. Those costs are not
comparable, so every test below that asserts "creative" is a SAFETY test, and
they matter more than the ones asserting "mechanical".

THE INTERSECTION IS THE HARDEST CASE AND IT HAS ITS OWN BLOCK: a request can be
both mechanical AND word-mutating. Routing it mechanically applies the scalar and
SILENTLY DROPS the cut — the user gets a video that ignored half their request,
and nothing records the dropped half. It looks like success, which is why it is
the worst thing this router can do.

    python3 cert_mechanical_router.py
"""
import sys

import mechanical_router as R

STYLES = {"Cove", "Prime", "TwoTone", "CleanCut", "Gadzhi", "Lumen", "Pulse"}

# (message, expected_verdict, note)
CASES = [
    # ── MECHANICAL: must route with no model call ────────────────────────────
    ("use Cove captions", "mechanical", "registered style"),
    ("change the captions to TwoTone", "mechanical", "registered style"),
    ("no captions please", "mechanical", "caption off"),
    ("turn off the subtitles", "mechanical", "caption off"),
    ("make it 9:16", "mechanical", "aspect"),
    ("make it square", "mechanical", "aspect word"),
    ('you spelled "Sujay" wrong, it should be "Sujai"', "mechanical", "text swap"),
    ('change "Clippers" to "Clipperz"', "mechanical", "text swap"),
    ("clean up the background noise", "mechanical", "denoise"),
    ("use Prime captions and make it 9:16", "mechanical", "two clean scalars"),

    # ── THE INTERSECTION: mechanical scalar BESIDE a word mutation ───────────
    # Every one of these MUST be creative. Routing mechanically would apply the
    # scalar and drop the cut.
    ("use Cove captions and cut the dead air at the start", "creative",
     "INTERSECTION — scalar + cut"),
    ("no captions, and trim the first 5 seconds", "creative",
     "INTERSECTION — scalar + trim"),
    ("make it 9:16 and make it 30 seconds", "creative",
     "INTERSECTION — scalar + duration target"),
    ('fix "Sujay" to "Sujai" and remove the ums', "creative",
     "INTERSECTION — text swap + filler removal"),
    ("switch to TwoTone captions and tighten the middle", "creative",
     "INTERSECTION — scalar + tighten"),

    # ── THE SECOND INTERSECTION: creative intent BESIDE a valid scalar ───────
    # Added after a RED proof showed the creative-intent disqualifier was never
    # load-bearing in this matrix: every creative case produced no mechanical op
    # anyway, so they fell through at "no op recognised" and removing the
    # disqualifier changed nothing. These are the cases where it actually earns
    # its keep — a recognisable scalar sitting next to a judgement word. Routing
    # them mechanically applies the scalar and SILENTLY DROPS the judgement half.
    ("use Cove captions but make it punchier", "creative",
     "INTERSECTION 2 — scalar + judgement"),
    ("make it 9:16 and more engaging", "creative",
     "INTERSECTION 2 — scalar + judgement"),
    ('change "Sujay" to "Sujai" and add some b-roll', "creative",
     "INTERSECTION 2 — text swap + new content"),
    ("no captions, and make it better", "creative",
     "INTERSECTION 2 — caption off + judgement"),

    # ── WORD MUTATION ALONE: never mechanical ────────────────────────────────
    ("make it 30 seconds", "creative", "duration target"),
    ("cut the silence", "creative", "word mutation"),
    ("remove the filler words", "creative", "word mutation"),
    ("make it shorter", "creative", "word mutation"),
    ("speed it up", "creative", "word mutation"),

    # ── CREATIVE / JUDGEMENT: never mechanical ───────────────────────────────
    ("make it punchier", "creative", "judgement"),
    ("make it more viral", "creative", "judgement"),
    ("add some b-roll", "creative", "new content"),
    ("this feels off, redo it", "creative", "rework"),
    ("fix the pacing", "creative", "judgement"),

    # ── NEAR MISSES: shaped like mechanical, must NOT route ──────────────────
    ("use Cinematic captions", "creative",
     "NEAR MISS — unregistered style name, refuse rather than coerce"),
    ("use nicer captions", "creative", "NEAR MISS — judgement word"),
    ("change the captions", "creative", "NEAR MISS — no target named"),
    ("make the captions better", "creative", "NEAR MISS — judgement"),
    ("", "creative", "empty"),
    (None, "creative", "None"),
]


def main():
    fails = []
    n_mech = n_creative = 0
    for msg, want, note in CASES:
        verdict, ops, reason = R.classify(msg, valid_caption_styles=STYLES)
        if want == "mechanical":
            n_mech += 1
        else:
            n_creative += 1
        if verdict != want:
            sev = "SAFETY" if want == "creative" else "coverage"
            fails.append(f"[{sev}] {note}: {msg!r} -> {verdict} "
                         f"(want {want}; reason={reason})")
            continue
        if want == "mechanical" and not ops:
            fails.append(f"[coverage] {note}: routed mechanical with NO ops")
        if want == "creative" and ops:
            fails.append(f"[SAFETY] {note}: creative verdict must carry NO ops")

    # Every emitted op must be in the merge's own shape, or the router promises
    # something the merge cannot apply.
    v, ops, _ = R.classify('use Cove captions and change "a" to "b"',
                           valid_caption_styles=STYLES)
    for o in ops:
        if "op" not in o or "list_key" not in o:
            fails.append(f"op missing required keys: {o}")
        if o["list_key"] not in (list(R.MECHANICAL_SCALARS)
                                 + ["caption_text_overrides"]):
            fails.append(f"op targets {o['list_key']!r}, not a mechanical key")

    # DARK BY DEFAULT — unset means every request takes today's model path.
    import os
    os.environ.pop("PROMPTLY_MECHANICAL_ROUTER", None)
    if R.enabled():
        fails.append("the router must be DARK by default")

    if fails:
        print("CERT MECHANICAL-ROUTER: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT MECHANICAL-ROUTER: PASS")
    print(f"  {n_mech} mechanical routed, {n_creative} correctly fell through")
    print("  5 word-mutation + 4 judgement INTERSECTION cases all -> creative")
    print("  unregistered style refused rather than coerced; dark by default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
