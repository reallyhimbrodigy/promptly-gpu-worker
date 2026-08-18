#!/usr/bin/env python3
"""PROMPT V2 EXEMPLARS — the bar, demonstrated. `[DARK]`

Prose doctrine tells the model what good looks like. An exemplar SHOWS it. These
are the two reference edits the product is measured against, each paired with the
plan that would generate it — so "one hand", "density is not the enemy" and "a
stated number gets shown" stop being adjectives and become a worked example.

REF-2 IS AN EXEMPLAR HERE, NOT A TEST INPUT. It is retired as something we RUN
(owner ruling 2026-08-17: it is already fully edited, so the planner's decline
was correct and measured nothing). Using it to DEMONSTRATE the bar is the
opposite act, and it is the reason golden/lumen-refs/ was kept rather than
deleted. cert_ref2_not_a_test_input.py permits this file by name.

TWO DELIVERY MODES, because token cost lands on EVERY editorial call:

  PLAN_ONLY    the plans alone (~1.2k tokens). Cheapest. Shows the SHAPE of a
               good plan — density, specificity, field discipline — but the
               model never sees the pixels it describes.
  FRAMES_PLAN  the plans plus a handful of stills (~4-6k tokens). Shows the LOOK
               as well as the shape.
  INLINE_VIDEO the full reference videos inline (~80-200k tokens EACH). Shows
               everything and is almost certainly unaffordable per call — it is
               here so the A/B can price it rather than assume.

The A/B measures which of these actually changes the output, because the
cheapest one that moves the number is the one that ships.
"""

# ─────────────────────────────────────────────────────────────────────────────
# REF-1 — corporate/legal promo, landscape. The restrained end of the bar.
# ─────────────────────────────────────────────────────────────────────────────
REF1_PLAN = {
    "analysis": (
        "A separation manager at a law-services firm explaining what his team "
        "does for a client mid-divorce. The ACT is reassurance — he is talking "
        "to someone frightened, not selling to someone curious, so the register "
        "is calm and the treatment stays out of his way.\n\n"
        "Hook: 'most people call us on the worst day of their year' — that is "
        "the line a stranger stops on. Turn: where he stops describing the "
        "problem and starts describing the process. Landing: the promise that "
        "they handle the paperwork so the client does not have to.\n\n"
        "The list: his name and role (spoken, first 4s). 'Twelve years' "
        "(number). 'Three things we take off your plate' (list — free "
        "structure). 'Four to six weeks' (number). The firm's name (twice). "
        "Nothing physical; he never holds anything.\n\n"
        "What I do about each: name and role get the plate, immediately, "
        "because a stranger needs to know who is talking before they trust "
        "reassurance. Twelve years is his credential — it gets set large. The "
        "three things are a list the viewer can hold, so they get a card, not "
        "three separate graphics. Four to six weeks is the concrete answer to "
        "the question the viewer actually has, so it lands as type on the "
        "landing. The firm's name I leave alone in the body and use once, at "
        "the close, as the end card — repeating it mid-video would read as an "
        "ad and break the reassurance register.\n\n"
        "Register: calm, one accent off his tie against the grey office, type "
        "in the left negative space because he sits camera-right throughout. "
        "What would break it: any kinetic move. No snap zooms in this video."
    ),
    "video_identity": "A separation manager who opens by naming the worst day of your year, then answers the only question a frightened client actually has: how long.",
    "caption_style": "Cove",
    "components_summary": {
        "name_plate": {"name": "Jaden Koh", "role": "Separation Manager",
                       "at_word": 3, "why": "spoken in the first four seconds"},
        "hero_number": [{"value": "12", "label": "YEARS", "at_word": 41},
                        {"value": "4-6", "label": "WEEKS", "at_word": 118}],
        "list_card": {"items": ["Filing", "Disclosure", "Negotiation"], "at_word": 74},
        "end_card": {"kind": "cta", "title": "Legalsoft", "lines": ["legalsoft.com"]},
        "zooms": [{"at_word": 3, "type": "SnapReframe", "arc": "hook"},
                  {"at_word": 118, "type": "StepZoom", "arc": "payoff"}],
        "transitions": [{"at_boundary": 2, "type": "SlideOver",
                         "why": "problem->process, the one real turn"}],
    },
    "what_this_demonstrates": (
        "Six placements in a 40s corporate promo, every one pointing at a "
        "spoken word, and it still reads calm. Restraint here is the ABSENCE "
        "OF COLLISION and the single accent — not a low count."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# REF-2 — viral creator doc, vertical. The dense end of the bar.
# ─────────────────────────────────────────────────────────────────────────────
REF2_PLAN = {
    "analysis": (
        "A young founder walking through how he built a company without "
        "writing code. The ACT is proof — he is pre-empting disbelief, so every "
        "claim wants evidence on screen the moment it is spoken. That single "
        "read is what makes this edit dense: the density is not style, it is "
        "the act.\n\n"
        "Hook: 'zero coding'. Turn: from what he built to how. Landing: the "
        "revenue number.\n\n"
        "The list, and it is long: 'zero coding', '13 years old', "
        "'$20,000,000', the product name, three tools by name, 'six months', "
        "'four people'. He also holds a phone at 00:19 showing the dashboard — "
        "a physical object the camera CAN show, so that one does not need a "
        "graphic, it needs a hold.\n\n"
        "Every number here gets shown, and shown BIG — this is a claim video, "
        "and a claim the viewer only hears is a claim they discount. '13 years "
        "old' set at two and a half times the caption size, inline with the "
        "phrase, is the whole hook. The three tools become one card, not three "
        "— they are a set, and splitting them would read as three interruptions "
        "instead of one fact. The dashboard shot gets a hold and NO graphic: "
        "putting type over the evidence he is physically showing would be "
        "covering the proof with a description of the proof.\n\n"
        "Six insert scenes across 43 seconds, roughly one every seven, each on "
        "a claim. Register: flat near-white cards, one accent, photos tilted "
        "and overlapping so they read as objects on a surface rather than "
        "slides. What would break it: a centred non-overlapping box."
    ),
    "video_identity": "A 13-year-old founder proving a $20M product was built with zero coding, one piece of evidence per claim.",
    "caption_style": "TwoTone",
    "components_summary": {
        "hero_number": [{"value": "0", "label": "CODING", "at_word": 2},
                        {"value": "13", "label": "YEARS OLD", "at_word": 27},
                        {"value": "$20,000,000", "label": "REVENUE", "at_word": 96}],
        "insert_scenes": [
            {"at_word": 27, "kind": "evidence_card",
             "composition": "tilted photo 6deg, drop shadow, foreground type overlapping the photo, number cropping off both edges"},
            {"at_word": 61, "kind": "tool_set", "items": 3},
        ],
        "hold_no_graphic": {"at_word": 78,
                            "why": "he is physically showing the dashboard; type over it would cover the proof"},
        "zooms": [{"at_word": 2, "type": "SnapReframe", "arc": "hook"},
                  {"at_word": 96, "type": "StepZoom", "arc": "payoff"}],
    },
    "what_this_demonstrates": (
        "Every spoken number on screen, at scale, inline with the phrase. Six "
        "inserts in 43s. One decision NOT to place — over the one moment the "
        "camera already proves — which is what restraint looks like when it is "
        "a read rather than a budget."
    ),
}


def exemplar_block(mode="PLAN_ONLY"):
    """The exemplar text injected into the system instruction.

    `mode` is the A/B axis. INLINE_VIDEO returns the plans plus a marker; the
    caller attaches the actual video parts, because only it knows the request
    shape — this module never builds a Gemini request.
    """
    import json
    if mode == "NONE":
        return ""
    head = (
        "=== TWO EDITS AT THE BAR ===\n\n"
        "These are the two reference edits this product is measured against, "
        "with the plan that generates each. They are not templates and you are "
        "not copying them — the first is calm and the second is dense, and both "
        "are correct, because each read its own footage. What they share is the "
        "only thing you should carry across: every placement points at a spoken "
        "word, and each edit is one hand from first frame to last.\n\n"
        "Read the `analysis` on each. That is the thinking you are being asked "
        "for.\n"
    )
    body = []
    for nm, plan in (("REF-1 — corporate promo, landscape, CALM", REF1_PLAN),
                     ("REF-2 — creator doc, vertical, DENSE", REF2_PLAN)):
        body.append(f"\n--- {nm} ---\n" + json.dumps(plan, indent=1, ensure_ascii=False))
    tail = ""
    if mode == "FRAMES_PLAN":
        tail = ("\n\nStills from each reference are attached. Look at the TYPE "
                "SCALE and where type sits relative to the speaker.\n")
    elif mode == "INLINE_VIDEO":
        tail = ("\n\nBoth reference videos are attached in full. Watch the "
                "rhythm — how often something moves.\n")
    return head + "\n".join(body) + tail


MODES = ("NONE", "PLAN_ONLY", "FRAMES_PLAN", "INLINE_VIDEO")
