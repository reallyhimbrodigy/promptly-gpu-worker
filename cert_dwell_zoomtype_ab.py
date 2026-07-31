"""DWELL objective proof (Zac 2026-07-31): render-FREE planning A/B.

The DWELL reframe redefines payoff commitment as land-on-word + DWELL on the landed
state (arrival speed free), replacing the old "slowest move / begins gently / a snap
reads as mid_peak / slow push into the cut" prose. The objective proof that the prose
was STEERING type-selection (not just wording) is the payoff zoom-TYPE distribution:

  PREDICTION ON RECORD: OLD prose over-selects DepthPull / LetterboxPush (the slowest
  types) for the payoff; DWELL prose shifts toward punchier types (SnapReframe /
  StepZoom / StagedPush) because arrival speed is no longer the commitment signal.

Run POST-ROLL (needs Vertex creds in the Modal env). It is a PLANNING-call A/B only —
Gemini cost, no render, no container-hours — inside Zac's spend law. The rendered pair
for Zac's eye rides a real render later.

METHOD (single binary, no branch-switching): build the current (DWELL) system_instruction
via _build_post_cuts_prompt, then produce the OLD variant by string-replacing the DWELL
payoff blocks back to the old text (both texts below). Run the editorial pass with each
variant on the same frozen-corpus clip, extract emphasis_moments[payoff].zoom_effect.type,
tally the distribution across the corpus, and report the shift vs the prediction.
"""

# The two payoff blocks (verbatim) — the A/B patches DWELL -> OLD to build the control arm.
DWELL_BLOCKS = [
    "the deepest move of the video — its peak LANDS ON the payoff word and then DWELLS",
    "the move LANDS its peak on the payoff word and DWELLS there",
    "the peak landing on the payoff word and HELD until that tight cut is the canonical move for the payoff",
]
OLD_BLOCKS = [
    "the slowest and deepest move of the video, holds to the end",
    "the move is the slow committed push that begins gently and RESOLVES on the next cut",
    "a slow push landing INTO a tight cut is the canonical move for the payoff",
]

# Zoom types by arrival character (for the distribution readout).
SLOW_TYPES = {"DepthPull", "LetterboxPush", "SmoothPush"}
PUNCHY_TYPES = {"SnapReframe", "StepZoom", "StagedPush"}


def patch_to_old(system_instruction: str) -> str:
    """Produce the control (old-prose) system_instruction from the DWELL one."""
    out = system_instruction
    # NOTE: the full old paragraphs are longer than these anchors; the runner should
    # revert the COMPLETE old blocks (kept in git history / the DWELL commit diff).
    # These anchors verify which arm a given system_instruction is.
    for d in DWELL_BLOCKS:
        assert d in out, f"expected DWELL block missing — is this the DWELL prompt? {d[:40]!r}"
    return out  # runner substitutes the full old blocks here


def payoff_zoom_type(plan: dict):
    """Extract the payoff emphasis's zoom_effect.type from an editorial plan."""
    pw = (plan.get("video_plan") or {}).get("payoff_word_index")
    for em in plan.get("emphasis_moments") or []:
        ze = em.get("zoom_effect") or {}
        if pw is not None and pw in (em.get("word_indices") or []) and ze.get("arc_position") == "payoff":
            return ze.get("type")
    # fallback: any emphasis claiming arc_position payoff
    for em in plan.get("emphasis_moments") or []:
        ze = em.get("zoom_effect") or {}
        if ze.get("arc_position") == "payoff":
            return ze.get("type")
    return None


def report(dist_old: dict, dist_dwell: dict):
    def slice_(d):
        s = sum(1 for t in d.values() for _ in range(1) if t in SLOW_TYPES)
        return s
    print("payoff zoom-type distribution:")
    print("  OLD  :", dict(sorted(dist_old.items(), key=lambda x: -x[1])))
    print("  DWELL:", dict(sorted(dist_dwell.items(), key=lambda x: -x[1])))
    slow_old = sum(v for k, v in dist_old.items() if k in SLOW_TYPES)
    slow_dw = sum(v for k, v in dist_dwell.items() if k in SLOW_TYPES)
    punch_old = sum(v for k, v in dist_old.items() if k in PUNCHY_TYPES)
    punch_dw = sum(v for k, v in dist_dwell.items() if k in PUNCHY_TYPES)
    print(f"  slow(DepthPull/LetterboxPush/SmoothPush): OLD={slow_old} -> DWELL={slow_dw}")
    print(f"  punchy(SnapReframe/StepZoom/StagedPush) : OLD={punch_old} -> DWELL={punch_dw}")
    print(f"  VERDICT vs prediction (slow DOWN, punchy UP): "
          f"{'CONFIRMED' if slow_dw < slow_old and punch_dw >= punch_old else 'NOT confirmed — prose was not steering type'}")


if __name__ == "__main__":
    print("POST-ROLL runner. Wire to handler._build_post_cuts_prompt + the editorial call:")
    print("  for clip in frozen_corpus:")
    print("    si,uc = _build_post_cuts_prompt(vibe, dur, ...)         # DWELL arm")
    print("    si_old = <revert the 3 full old blocks in si>           # control arm")
    print("    plan_dwell = editorial_call(si, uc);  plan_old = editorial_call(si_old, uc)")
    print("    tally payoff_zoom_type(plan_*) into dist_dwell / dist_old")
    print("  report(dist_old, dist_dwell)")
