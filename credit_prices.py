#!/usr/bin/env python3
"""What ChatCut charges, and what we must charge to cover it.

SOURCE IS /docs/credits-policy, NOT /pricing. The pricing page quotes seconds
per plan and HIDES THE RESOLUTION, so a plan that reads as generous at its
implied rate is 5.5x more expensive at 1080p: Seedance 2.5 is 0.3982/sec at
480p and 2.2175/sec at 1080p. A price keyed on the model alone is a price for
whichever resolution the quote happened to assume, and the agent picks the
resolution.

SO EVERY ROW IS KEYED BY MODEL x RESOLUTION. A single number per model would
be the two-numbers-with-the-same-name defect with money attached.

OUR PRICE IS ceil(rate * 10). Ten of our credits to one of theirs, rounded UP
at every row: a rounded-down row is a row we lose money on every time it is
used, and the loss is invisible because the edit succeeds.

A RATE THE PAGE DOES NOT STATE IS ABSENT, AND THE FEATURE IS OFF. Avatar has
no published rate. Image generation is "variable — by model, output quality,
resolution, and image count". Top-up price per credit is not published at all.
Guessing any of them prices a real charge from an invented number, which is
the one error that costs money rather than credibility — so they are not in
the table, and `is_priceable()` refuses them by their absence rather than by a
list I would have to remember to update.
"""
import math

SOURCE = "https://chatcut.io/docs/credits-policy"
READ_ON = "2026-09-23"
OUR_PER_THEIRS = 10

# (feature, model, resolution) -> (their rate, unit, the page's own words)
CHATCUT_RATES = {
    ("video", "Seedance 2.5", "480p"):
        (0.3982, "per second", "about 0.3982/sec"),
    ("video", "Seedance 2.5", "720p"):
        (0.896, "per second", "0.896/sec"),
    ("video", "Seedance 2.5", "1080p"):
        (2.2175, "per second", "about 2.2175/sec"),
    ("video", "Seedance 2.0", "480p"):
        (0.28, "per second", "0.28/sec"),
    ("video", "Seedance 2.0", "720p"):
        (0.60, "per second", "0.60/sec"),
    ("video", "Seedance 2.0", "1080p"):
        (1.32, "per second", "1.32/sec"),
    ("video", "Seedance 2.0 Fast", "480p"):
        (0.165, "per second", "0.165/sec"),
    ("video", "Seedance 2.0 Fast", "720p"):
        (0.36, "per second", "0.36/sec"),
    ("video", "Kling 3.0 Standard", "720p"):
        (0.60, "per second", "0.60/sec"),
    ("video", "Kling 3.0 Pro", "1080p"):
        (0.80, "per second", "0.80/sec"),
    ("video", "Gemini Omni", "720p"):
        (0.40544, "per second", "0.40544 per actual generated second"),
    # VOICEOVER IS A RANGE AND WE TAKE THE TOP OF IT. 0.28-0.80 per 1,000
    # characters: pricing the bottom means every call above 0.28 is sold below
    # cost, and which end a given call lands on is not something we control or
    # can see. The per-second alternative the page also offers is NOT used —
    # one unit per feature, or two rows disagree about the same call.
    ("voiceover", "AI Voiceover", "per 1,000 characters"):
        (0.80, "per 1,000 characters",
         "Usually 0.28-0.80 credits per 1,000 characters"),
    ("sfx", "AI Sound Effects", "per generated second"):
        (0.12, "per generated second", "0.12 credits per generated second"),
    ("music", "AI Music", "per song"):
        (0.18, "per song", "0.18 credits per generated song"),
}

# IMAGE HAS NO STATED RATE — "variable, by model, output quality, resolution
# and image count" — so it gets a FLOOR rather than a price, ruled by Zac at 5
# of our credits. A floor is honest about being a floor: it is the least we
# will charge, not a claim about what they charge.
IMAGE_FLOOR = 5

# Stated by the page as variable with no number: no row, feature off.
UNPRICED = {
    "avatar": "no rate published on the credits-policy page at all",
    "image": 'VARIABLE — "By model, output quality, resolution, and image count"',
    "motion_graphics": 'VARIABLE — "Based on the AI model usage required"',
    "agent_messages": 'VARIABLE — "Model, input and output tokens, cached '
                      'context, conversation length, and project context"',
    "top_up": "top-ups exist (Avatar -> Credits history -> Buy Credits) but no "
              "price per credit is published on any docs page",
}


def our_price(feature, model, resolution):
    """-> (credits, why) or (None, why-not). ceil(rate * 10), never rounded down."""
    key = (feature, model, resolution)
    row = CHATCUT_RATES.get(key)
    if row is None:
        if feature in UNPRICED:
            return None, "UNPRICED: %s" % UNPRICED[feature]
        return None, "NOT IN THE TABLE: %r — the page states no rate for it" % (key,)
    rate, unit, words = row
    return math.ceil(rate * OUR_PER_THEIRS), '%s %s ("%s")' % (rate, unit, words)


def is_priceable(feature):
    """A feature is offerable only if at least one row states a rate for it.

    BY ABSENCE, NOT BY A LIST. A hand-kept "off" list is a list someone has to
    remember to update when a rate is published; this answers from the table
    itself, so publishing a rate turns the feature on and nothing else has to
    move.
    """
    return any(k[0] == feature for k in CHATCUT_RATES)


def table():
    out = []
    for (feature, model, res), (rate, unit, words) in sorted(CHATCUT_RATES.items()):
        out.append((feature, model, res, rate, unit, math.ceil(rate * OUR_PER_THEIRS),
                    words))
    return out


if __name__ == "__main__":
    print("%-10s %-20s %-22s %10s  %-22s %6s" %
          ("feature", "model", "resolution/unit", "theirs", "unit", "OURS"))
    for f, m, r, rate, unit, ours, words in table():
        print("%-10s %-20s %-22s %10s  %-22s %6d   <- %s"
              % (f, m, r, rate, unit, ours, words))
    print("\nimage floor: %d (no stated rate)" % IMAGE_FLOOR)
    for k, v in sorted(UNPRICED.items()):
        print("  OFF  %-16s %s" % (k, v))
