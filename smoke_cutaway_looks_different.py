#!/usr/bin/env python3
"""SMOKE — a cutaway goes to a DIFFERENT shot, and the measure already existed.

WHAT ZAC SAW: "rearranged clips playing the wrong audio — it reads as a glitch."

WHAT IS ACTUALLY HAPPENING, from round 70's talking_head: beat 4 (output
9.71-11.60) cuts away to source 5.84-7.73 — the same speaker, same room, same
framing, mid-sentence. NOTHING IS OUT OF SYNC. The cutaway is an ffmpeg overlay
with `enable=between(...)`, frames went 609 -> 609, and the audio track is never
touched. It READS as a desync because the picture is a talking face forming
different words than the narration over it, which is the most legible lip-sync
error there is. The diagnosis matters: an arithmetic fix would have found
nothing wrong and the glitch would have shipped again.

THE MEASURE WAS ALREADY THERE AND THE PLAN NEVER ASKED IT. `cutaway_candidates`
ranks candidates by Jaccard distance over beat descriptions and printed "7 of 7
beats have a candidate at diff>=0.55" ON THE SAME RUN. The plan bounds-checked
and adjacency-checked the agent's free-text `cutaway_from_s` and never
difference-checked it, so the agent could name a moment the candidate finder
would never have offered. A producer and a consumer that never met.

THE CORPUS SETTLES WHAT A CUTAWAY IS, with a denominator. Of 60 cutaway-like
reference treatments, 40 answer `over_subject`:

    no_subject_visible   34      clear_of_subject   4
    over_body             2      over_face          0

Zero over a face, in ten videos. What they show instead: a screen recording, a
hand counting cash, a photo, a Premiere export panel, a rainy street.
"""
import sys

import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(what, passed, detail=""):
    if not passed:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if passed else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not passed and detail else ""))


TALK = "young man in a bedroom holding a microphone talking to camera"
OTHER = "screen recording of an export panel with bitrate sliders"
SPANS = [(0.0, 20.25)]
DUR = 20.36


def beats(src_vision):
    return [{"i": 0, "t_start": 0.0, "t_end": 2.0, "vision": src_vision},
            {"i": 2, "t_start": 5.84, "t_end": 7.47, "vision": TALK},
            {"i": 4, "t_start": 9.71, "t_end": 11.6, "vision": TALK}]


def plan(from_s, src_vision=TALK):
    return A.cutaway_plan(
        [{"beat": 4, "treatment": ["cutaway"], "cutaway_from_s": from_s}],
        SPANS, DUR, beats=beats(src_vision))


# ── 1. THE MEASURE ITSELF DISCRIMINATES ─────────────────────────────────────
_s, _d = A.beat_visual_diff({"vision": TALK}, {"vision": TALK})
check("two identical shots measure as no difference", _s == "MEASURED" and _d == 0.0,
      f"{_s} {_d}")
_s2, _d2 = A.beat_visual_diff({"vision": TALK}, {"vision": OTHER})
check("two different shots measure as fully different",
      _s2 == "MEASURED" and _d2 > 0.9, f"{_s2} {_d2}")
_s3, _d3 = A.beat_visual_diff({"vision": ""}, {"vision": TALK})
check("no description is ABSENT, never a difference of zero — a missing "
      "description and two identical shots must not look the same",
      _s3 == "ABSENT" and _d3 is None, f"{_s3} {_d3}")

# ── 2. ROUND 70'S ACTUAL RULING IS REFUSED ──────────────────────────────────
_p, _r = plan(5.84)
check("the cutaway that shipped on round 70 is now refused", not _p and _r,
      f"{len(_p)} plan(s)")
check("and the refusal names the difference and the floor",
      bool(_r) and "difference 0.00" in _r[0]["why"] and "0.55" in _r[0]["why"],
      (_r[0]["why"][:110] if _r else ""))
check("and it says WHY it reads as broken sync, so the next reader does not "
      "go looking for an arithmetic bug",
      bool(_r) and "lips" in _r[0]["why"].lower())

# ── 3. A GENUINELY DIFFERENT SHOT STILL PLANS ───────────────────────────────
# A refusal arm that refuses everything deletes the family. Cutaway is 72 of the
# 153 reference beats; over-refusing here is more expensive than the defect.
_p2, _r2 = plan(0.2, src_vision=OTHER)
check("a different, non-adjacent shot is still planned", len(_p2) == 1,
      f"{len(_p2)} plan(s), rejects {[x['why'][:50] for x in _r2]}")
check("and the plan carries the measured difference, so a wrong call is "
      "readable afterwards",
      bool(_p2) and _p2[0].get("look_diff_state") == "MEASURED"
      and _p2[0].get("look_diff") is not None,
      str(_p2[:1]))

# ── 4. ABSENT DOES NOT REFUSE ───────────────────────────────────────────────
# Refusing with no descriptions would delete cutaway on every run where vision
# did not arrive — retiring a path for one reason and losing its side-benefits.
_p3, _r3 = plan(5.84, src_vision=TALK)
_p4, _r4 = A.cutaway_plan(
    [{"beat": 4, "treatment": ["cutaway"], "cutaway_from_s": 5.84}],
    SPANS, DUR, beats=[dict(b, vision="") for b in beats(TALK)])
check("with no descriptions at all the cutaway is PLANNED, not refused",
      len(_p4) == 1 and not _r4, f"{len(_p4)} plan(s), {len(_r4)} reject(s)")
check("and the plan says the difference was ABSENT rather than reporting 0",
      bool(_p4) and _p4[0].get("look_diff_state") == "ABSENT"
      and _p4[0].get("look_diff") is None, str(_p4[:1]))

# ── 5. THE EXISTING ARMS STILL FIRE ─────────────────────────────────────────
# A new arm that shadows the old ones would hide what they catch.
_p5, _r5 = plan(11.7)
check("the adjacent-footage arm still fires", bool(_r5) and "plays right after"
      in _r5[0]["why"], (_r5[0]["why"][:60] if _r5 else "no reject"))

if fails:
    print("CUTAWAY-LOOKS-DIFFERENT: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CUTAWAY-LOOKS-DIFFERENT: PASS — the plan asks the candidate finder's own "
      "question, refuses the same shot, admits a different one, and stays quiet "
      "when there is nothing to compare")
