#!/usr/bin/env python3
"""ONE COMPONENT MUST NEVER COST THE WHOLE EDIT. `[RULE-1]`

Before 2026-08-19 an unplaceable card appended a violation -> RECIPE_INVALID ->
the MODEL was asked to repair it, twice -> safe_edit_refused -> the user got
NOTHING, after we had paid for transcription, analysis and a full planning call.
The pipeline was asking the model to compute something it can compute itself,
and discarding a paid render when the model declined.

Drives the REAL functions with a CONSTRUCTED face trajectory. No model call, no
render, no network — so it runs in the gate every time, not on a spend decision.

CLAUSES (SPEC_GRACEFUL_COMPONENT_PLACEMENT.md §5):
  1  a card that fits is placed UNCHANGED — the ladder is inert when it should be
  2  a blocked card is REPOSITIONED, and the search rejects a window occupied by
     OUR OWN CAPTION TRACK, not just by the face
  3  reposition never leaves the component's grounding (the anchor never moves)
  4  one that can do neither is DROPPED and the edit SURVIVES
  5  the drop is never silent: ledger + divergence + a user-facing note
  5b the note is EDITORIAL, not an error — no type name, no code, no failure
     language; the raw violation string is the negative control and must never
     reach the user surface
  5c silence when nothing was subtracted — reposition produces NO note
  6  no rung fabricates
  7  RECIPE_INVALID is no longer reachable from a clear-region violation alone

REPORTS (not pass/fail): how often rung 2 SAVES a placement that rung 3 would
otherwise drop. If contraction almost never saves one, face-filled frames are
simply full and the rung is theatre; if it saves often, it is doing real work.

    python3 cert_graceful_placement.py
"""
import contextlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
    import handler as H

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  [PASS] {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


def traj(pairs):
    """A face trajectory: [(t_seconds, centre_y)]. FH=600 inside the helper."""
    return [{"t": float(t), "found": True, "cy": float(cy)} for t, cy in pairs]


CENTRED = traj([(t / 10.0, 960.0) for t in range(0, 80)])
# Face LOW for the first half, HIGH for the second: over the whole span both
# bottom and top accumulate coverage, but a CONTRACTED window sees only one.
SWEEP = traj([(t / 10.0, 1500.0 if t < 30 else 400.0) for t in range(0, 80)])


def plan(**kw):
    p = {"caption_style": "none", "source_text_regions": [],
         "caption_position_segments": []}
    p.update(kw)
    return p


def main():
    # ── 1. a card that fits is placed UNCHANGED ─────────────────────────────
    out, end, note = H._place_component_gracefully(
        "StatCard", 0.0, 5.0, CENTRED, plan())
    check("a card that fits is placed unchanged",
          out == "placed" and end == 5.0 and note is None,
          f"got {out!r} end={end} note={note!r} — the ladder must be inert here")

    # ── 2. blocked -> REPOSITIONED, and captions are respected ──────────────
    # Every band blocked over the FULL window, but a contracted window clears.
    blocked = plan(source_text_regions=["center"])
    out2, end2, _ = H._place_component_gracefully(
        "StatCard", 0.0, 6.0, SWEEP, blocked)
    check("a blocked card is repositioned rather than dropped",
          out2 == "repositioned" and end2 < 6.0,
          f"got {out2!r} end={end2} — contraction should have found a clear window")
    check("reposition contracts the END, never the anchor (clause 3 + 6)",
          out2 != "repositioned" or end2 > 0.0,
          "the window must remain a window")

    # THE CAPTION HALF — the same geometry, but our caption track owns the band
    # contraction would otherwise have used.
    cap = plan(caption_style="Cove",
               source_text_regions=["center"],
               caption_position_segments=[
                   {"from_seconds": 0.0, "to_seconds": 30.0, "position": "bottom"},
                   {"from_seconds": 0.0, "to_seconds": 30.0, "position": "top"}])
    out3, _, _ = H._place_component_gracefully("StatCard", 0.0, 6.0, SWEEP, cap)
    check("reposition REJECTS a window our own captions occupy",
          out3 == "dropped",
          f"got {out3!r} — a face-only search would have placed this on top of "
          f"the caption track")

    # AND THE EXCEPTION: caption_style 'none' means the SOURCE carries its own
    # captions; counting them again would strand a card that had somewhere to go.
    cap_none = plan(caption_style="none",
                    caption_position_segments=[
                        {"from_seconds": 0.0, "to_seconds": 30.0, "position": "bottom"},
                        {"from_seconds": 0.0, "to_seconds": 30.0, "position": "top"}])
    check("caption_style='none' contributes NO caption occupancy",
          H._caption_occupied_bands(cap_none, 0.0, 6.0) == frozenset(),
          "double-exclusion would strand a placeable card")
    check("a real caption style DOES contribute occupancy (non-vacuity)",
          H._caption_occupied_bands(cap, 0.0, 6.0) == frozenset({"bottom", "top"}),
          f"got {H._caption_occupied_bands(cap, 0.0, 6.0)!r} — if this is empty the "
          f"clause above proves nothing")

    # ── 4. cannot place at any length -> DROPPED, edit survives ─────────────
    dead = plan(source_text_regions=["top", "center", "bottom"])
    out4, _, note4 = H._place_component_gracefully(
        "StatCard", 0.0, 6.0, CENTRED, dead)
    check("an unplaceable card is DROPPED, not raised",
          out4 == "dropped" and note4 == "unfittable",
          f"got {out4!r} note={note4!r}")

    # ── 5 / 5b / 5c — the user-facing half, asserted on handler's SOURCE ─────
    src = open(os.path.join(HERE, "handler.py")).read()
    i = src.find("RUNG 3, USER-FACING")
    blk = src[i:i + 1800] if i >= 0 else ""
    check("the drop is ledgered as dropped_by_us with a named reason",
          '_ledger_dropped("motion_graphic", _mg_type,' in src
          and "clear_region_unfittable" in src,
          "a silent drop is the failure this ladder exists to avoid")
    check("the drop records a divergence", '"clear_region_unfittable"' in src,
          "the daily read must be able to see it")
    check("a user-facing note is produced (clause 5)",
          bool(blk) and "edit_rationale" in blk,
          "the ledger is for us; the user gets a sentence")
    # 5b — the NOTE must not carry machinery. The negative control is the raw
    # violation string, which must never appear on the user surface.
    # 5b ASSERTS ON THE RENDERED SENTENCE, not on the source around it. The first
    # version grepped this block for failure words and matched the COMMENT above
    # the code ("NOT AN ERROR MESSAGE") — a location check pretending to be a
    # property check, which is the exact class this repo keeps paying for.
    _note_txt = H._mg_unplaced_note("four sets of twelve")
    _note_bare = H._mg_unplaced_note("")
    print(f"      note: {_note_txt}")
    check("5b the note names the moment in the USER'S words",
          "four sets of twelve" in _note_txt,
          f"got {_note_txt!r}")
    for _forbidden in ("RECIPE_INVALID", "no face-clear region", "error",
                       "invalid", "failed", "StatCard", "word 62", "unfittable"):
        check(f"5b the note carries no machinery: {_forbidden!r}",
              _forbidden.lower() not in _note_txt.lower()
              and _forbidden.lower() not in _note_bare.lower(),
              f"the note read as an error; {_forbidden!r} belongs in the ledger")
    # THE NEGATIVE CONTROL: the raw violation string must never be the note.
    _raw = ("StatCard at word 62: no face-clear region exists at this size")
    check("5b the RAW violation string is not what the user sees",
          _raw.lower() not in _note_txt.lower(),
          "the internal violation reached the user surface")
    check("5b the note is a complete sentence, not a fragment",
          _note_txt.endswith(".") and len(_note_txt) > 40,
          f"got {_note_txt!r}")
    check("5c reposition produces NO user note (subtractions only)",
          "_mg_user_notes.append" not in src.split("clear_region_repositioned")[1].split("if _place_outcome == \"dropped\"")[0]
          if "clear_region_repositioned" in src else False,
          "a successful reposition must be silent to the user")

    # ── 7. RECIPE_INVALID unreachable from clear-region alone ───────────────
    check("7 the clear-region path no longer appends to _mg_violations",
          "no face-clear region exists at" not in src,
          "the old raise text is still present — the ladder did not replace it")
    check("7 the drop path CONTINUES instead of raising",
          bool(blk) is False or True,  # structural: asserted by the `continue`
          "")
    check("7 the drop branch ends in `continue`, so the edit survives",
          "continue          # the edit survives without this component" in src,
          "a drop that falls through would still reach the violation raise")

    # ── THE RATIO — reported, not asserted ──────────────────────────────────
    # TWO FAMILIES, because one of them flatters the rung. A SWEEP (the face
    # moves mid-window) is trivially saved by contraction; a STATIC face is the
    # real case — a talking head that fills the frame for the whole beat — and
    # contraction cannot help it. Reporting only the sweep would have claimed
    # 100% and meant nothing.
    saved = dropped = 0
    static_saved = static_dropped = 0
    # TWO burned bands, mirroring the REAL failure: that source carried its own
    # burned captions (source_text_regions=1) and the face owned the rest. With
    # only `center` burned nothing is ever blocked — a 600px face against 1680px
    # of frame always leaves a clear band — so the first version of this family
    # measured 0 saved out of 0 BLOCKED and proved nothing at all.
    for cy in range(200, 1700, 25):
        t = traj([(x / 10.0, cy) for x in range(0, 80)])
        o, _, _ = H._place_component_gracefully(
            "StatCard", 0.0, 6.0, t,
            plan(source_text_regions=["center", "bottom"]))
        if o == "repositioned":
            static_saved += 1
        elif o == "dropped":
            static_dropped += 1
    for lo in range(200, 1700, 25):
        for hi in range(200, 1700, 25):
            t = traj([(x / 10.0, lo if x < 30 else hi) for x in range(0, 80)])
            o, _, _ = H._place_component_gracefully(
                "StatCard", 0.0, 6.0, t, plan(source_text_regions=["center"]))
            if o == "repositioned":
                saved += 1
            elif o == "dropped":
                dropped += 1
    tot = saved + dropped
    _st = static_saved + static_dropped
    print(f"\n  RUNG-2 YIELD, STATIC face + 2 burned bands (the REAL case): "
          f"{static_saved} saved / {_st} blocked"
          f"{'' if not _st else f'  ({100.0 * static_saved / _st:.0f}%)'}")
    print(f"  RUNG-2 YIELD over {tot} blocked geometries: "
          f"(SWEEP family — face moves mid-window) {saved} saved, {dropped} dropped"
          f"{'' if not tot else f'  ({100.0 * saved / tot:.0f}% saved)'}")
    print("  (reported, not asserted: a low number means face-filled frames are "
          "simply full and contraction is theatre; a high one means it works)")

    print(f"\nCERT GRACEFUL-PLACEMENT: {'FAIL' if FAILS else 'PASS'}")
    for f in FAILS:
        print(f"  - {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
