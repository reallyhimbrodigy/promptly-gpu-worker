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

THREE DELIVERY MODES, because token cost lands on EVERY editorial call:

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
# THE EXEMPLARS, AS BEAT LISTS — the exact shape the model must produce.
#
# This is the input the system has never had. Two weeks of prose about density,
# and not once an example of it. REF-2 carries ~6 insert scenes in 43s; SEEING
# that is worth more than any sentence describing it.
# ─────────────────────────────────────────────────────────────────────────────

# REF-1 — corporate/legal promo. The CALM end of the bar. Six placements across
# 40s, every one on a spoken word, and it still reads restrained: restraint here
# is the absence of collision and a single accent, not a low count.
REF1_BEATS = [
    {"word_index": 3, "says": "most people call us on the worst day of their year",
     "read": "cold open, and it is the hook — a stranger stops on this line",
     "place": [{"component": "NamePlate",
                "props": {"name": "Jaden Koh", "role": "Separation Manager"}}]},
    {"word_index": 19, "says": "we handle the filing, the disclosure, the negotiation",
     "read": "a three-item list the speaker handed me — one card, not three graphics",
     "place": [{"component": "PillCluster",
                "props": {"tags": ["Filing", "Disclosure", "Negotiation"]}}]},
    {"word_index": 41, "says": "twelve years doing only this",
     "read": "his credential, and the only number in the first half",
     "place": [{"component": "StatCard", "props": {"value": 12, "label": "YEARS"}}]},
    {"word_index": 63, "says": "people think it takes a year",
     "read": "setting up the misconception — let it land bare, the correction is next",
     "place": []},
    {"word_index": 118, "says": "four to six weeks, start to finish",
     "read": "THE PAYOFF — the only question a frightened client actually has",
     "place": [{"component": "StatCard", "props": {"value": "4-6", "label": "WEEKS"}}]},
    {"word_index": 131, "says": "we do the paperwork so you do not have to",
     "read": "close; the promise the whole thing was walking toward",
     "place": [{"component": "EndCard",
                "props": {"title": "Legalsoft", "lines": ["legalsoft.com"]}}]},
]

# REF-2 — creator doc. The DENSE end. Every spoken number on screen, ~6 inserts
# in 43s, and ONE deliberate refusal where the camera already proves the claim.
REF2_BEATS = [
    {"word_index": 2, "says": "zero coding",
     "read": "the hook is a number, and it is a claim people disbelieve — show it big",
     "place": [{"component": "StatCard", "props": {"value": 0, "label": "CODING"}}]},
    {"word_index": 14, "says": "I built the whole thing myself",
     "read": "assertion with no figure attached — the cut carries this one",
     "place": []},
    {"word_index": 27, "says": "I'm 13 years old",
     "read": "the disbelief beat; this is the video's centre of gravity",
     "place": [{"component": "StatCard", "props": {"value": 13, "label": "YEARS OLD"}}]},
    {"word_index": 44, "says": "it does about twenty million a year now",
     "read": "the payoff number — biggest treatment in the edit",
     "place": [{"component": "StatCard",
                "props": {"value": 20000000, "prefix": "$", "label": "REVENUE"}}]},
    {"word_index": 61, "says": "three tools, that is the entire stack",
     "read": "a SET, not three facts — splitting it would read as three interruptions",
     "place": [{"component": "PillCluster",
                "props": {"tags": ["Bubble", "Airtable", "Zapier"]}}]},
    {"word_index": 78, "says": "here is the dashboard right now",
     "read": "HE IS PHYSICALLY SHOWING IT. Type over the proof would cover the proof.",
     "place": []},
    {"word_index": 96, "says": "six months from nothing",
     "read": "the last claim before the close",
     "place": [{"component": "StatCard", "props": {"value": 6, "label": "MONTHS"}}]},
    {"word_index": 112, "says": "so that is how it happened",
     "read": "designed ending, not a stop",
     "place": [{"component": "EchoOutro", "props": {}}]},
]

# (The earlier component-major REF plans were removed: the beat lists above are
# the exact output shape, and two shapes for one exemplar teaches the wrong one.)


def exemplar_block(mode="PLAN_ONLY"):
    """The exemplar text injected into the system instruction.

    `mode` is a REAL A/B axis, not a detail: token cost lands on EVERY editorial
    call, so the cheapest mode that moves the number is the one that ships.

        PLAN_ONLY    the beat lists alone            ~1.5k tokens
        FRAMES_PLAN  beat lists + a few stills       ~5k
        INLINE_VIDEO beat lists + both refs in full  ~80-200k EACH

    INLINE_VIDEO is here so the A/B can PRICE it rather than assume it is
    unaffordable. The caller attaches the media parts; this module never builds
    a request.
    """
    import json
    if mode == "NONE":
        return ""
    head = (
        "=== TWO EDITS AT THE BAR ===\n\n"
        "These are the two reference edits this product is measured against, as "
        "BEAT LISTS in exactly the shape you are being asked to produce.\n\n"
        "You are not copying them. The first is calm and the second is dense, "
        "and BOTH ARE CORRECT, because each read its own footage. What carries "
        "across is only this: every placement points at a spoken word, each edit "
        "is one hand from first frame to last, and `place: []` is used "
        "deliberately — REF-2 refuses the one beat where the camera already "
        "proves the claim.\n\n"
        "Read the `read` line on each beat. That is the thinking being asked "
        "for.\n\n"
        "**THESE BEATS SHOW ONE TREATMENT — `place`. THAT IS A LIMIT OF THE "
        "TRANSCRIPTION, NOT THE BAR.** These lists were written down from the "
        "two reference edits by hand, and only their component placements were "
        "recorded; the cuts, camera moves, sound and cutaways those edits "
        "certainly contain are simply not written here. They are NOT absent "
        "from the reference and they are NOT discouraged. Do not read the shape "
        "of these examples as the shape of a good plan — a beat list that is "
        "only placements would be a worse edit than either of these videos. Use "
        "every treatment the moment calls for.\n"
    )
    body = [
        "\n--- REF-1 · corporate promo · CALM · 6 placements / 40s ---\n"
        + json.dumps(REF1_BEATS, indent=1, ensure_ascii=False),
        "\n--- REF-2 · creator doc · DENSE · 6 placements + 2 refusals / 43s ---\n"
        + json.dumps(REF2_BEATS, indent=1, ensure_ascii=False),
    ]
    tail = ""
    if mode == "FRAMES_PLAN":
        tail = ("\n\nStills from each reference are attached. Look at TYPE SCALE "
                "and where type sits relative to the speaker.\n")
    elif mode == "INLINE_VIDEO":
        tail = ("\n\nBoth reference videos are attached in full. Watch how often "
                "something moves.\n")
    return head + "\n".join(body) + tail


MODES = ("NONE", "PLAN_ONLY", "FRAMES_PLAN", "INLINE_VIDEO")
