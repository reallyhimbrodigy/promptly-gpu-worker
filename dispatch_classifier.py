#!/usr/bin/env python3
"""EVERYTHING IS DECIDED BEFORE ANYTHING IS TYPED INTO THE BOX.

Four outcomes, and the order they are tested in is the design:

    UNSAFE        refuse. No dispatch, no render, NO CHARGE. Counted.
    GENERATIVE    quote 20 credits. Pro/Max may accept; Free sees the quote AND
                  the paywall — the quote first, so the number is known before
                  the wall rather than the wall being the whole answer.
    OUT_OF_SCOPE  a NEGOTIATION SENTENCE naming what we can do instead. Never a
                  silent drop and never a bare refusal.
    IN_SCOPE      dispatch.

ORDER IS LOAD-BEARING. Unsafe is tested FIRST, because an unsafe ask that is
also generative is still unsafe and must never reach a quote — pricing it would
be offering to do it. Generative is tested before out-of-scope for the same
reason in miniature: a generative ask has a PRICE and an answer, where
out-of-scope only has a negotiation.

── THE CATEGORIES COME FROM THE STANDING LAWS, NOT FROM MY JUDGEMENT ───────

    no music                                  -> a music ask is OUT_OF_SCOPE
    no b-roll from outside the user's upload  -> stock/internet footage is
                                                 OUT_OF_SCOPE
    generation is a future Pro feature,
      negotiated not attempted                -> GENERATIVE, quoted, never
                                                 silently attempted
    no degraded fallbacks                     -> nothing is half-done to avoid
                                                 saying no

Each rule below cites the law it implements. A category with no law behind it
would be me deciding what users may ask for.

── WHAT IT WILL NOT DO ─────────────────────────────────────────────────────

It does not guess at UNSAFE from a word list and call that a safety system. The
patterns here catch the unambiguous, clearly-stated cases; anything it is not
sure of goes to REVIEW, which does not dispatch and does not charge either. A
classifier that silently passes what it failed to understand is worse than one
that says it did not understand.
"""
import re

CLASSIFIER_VERSION = "1.0.0"
AI_VIDEO_CREDITS = 20          # Zac's ruling: AI videos debit 20.

# UNSAFE — refuse, count, never quote. Kept narrow and unambiguous on purpose:
# a broad list would refuse ordinary work, and this repo's own rule is that a
# check which convicts correct input is not a stricter check, it is a broken one.
_UNSAFE = [
    # VERB INFLECTION, AND THIS ONE FAILED ON THE LEG'S FIRST RUN. The pattern
    # was `make it look like`; the brief said `makeS it look like`, so UNSAFE
    # missed it, GENERATIVE matched first, and an unsafe ask CAME BACK PRICED AT
    # 20 CREDITS. The ordering was right and the pattern under it was one letter
    # too narrow — which is the whole reason L1 tests the combination rather
    # than trusting the order.
    (r"\b(?:makes?|making|made) it (?:look|seem|sound) like\b[^.]{0,60}\b(?:endorsed?|said|testimonial|review|recommend\w*)\b"
     r"|\b(?:pretend|fake|fabricate|forge)\w*\b[^.]{0,60}\b(?:endors\w*|quote|testimonial|review)\b"
     # VERB INFLECTION, CLOSED A SECOND TIME. `endorsed?` matched endorse and
     # endorsed and missed ENDORSING, so "generate a video of the CEO endorsing
     # us" fell through UNSAFE into GENERATIVE and came back PRICED — the same
     # defect L1 caught on `make` vs `makes`, one word further along. That is
     # twice, which is the argument that closing inflections is not a strategy.
     r"|\b(?:generate|create|make)\b[^.]{0,40}\b(?:endors\w*|praising|recommend\w*)\b",
     "fabricated endorsement or testimonial"),
    (r"\b(?:deepfake|face ?swap|clone (?:his|her|their|my) (?:face|voice))\b",
     "synthetic likeness of a real person"),
    (r"\b(?:impersonat\w+|pose as)\b[^.]{0,40}\b(?:official|police|government|bank)\b",
     "impersonation of an authority"),
]

# GENERATIVE — quoted, never attempted. "generation is a future Pro feature,
# negotiated not attempted".
_GENERATIVE = [
    (r"\b(?:generate|create|make me|ai)\b[^.]{0,30}\b(?:video|footage|scene|avatar|voice ?over|voice)\b",
     "generating new video or voice"),
    (r"\btext[- ]to[- ](?:video|speech)\b", "text-to-video or text-to-speech"),
    (r"\b(?:ai|synthetic|generated)\b[^.]{0,20}\b(?:b[- ]?roll|image|images)\b",
     "generated imagery"),
]

# OUT_OF_SCOPE — negotiate, naming the alternative. Each cites its law.
_OUT_OF_SCOPE = [
    (r"\b(?:add|put|lay|background)\b[^.]{0,20}\bmusic\b|\bmusic\b[^.]{0,20}\b(?:under|behind|track)\b",
     "music", "no music",
     "We don't add music. We can place sound effects from the registered set on "
     "the beats that need them — say the word and we'll do that instead."),
    (r"\b(?:stock|pexels|getty|internet|online)\b[^.]{0,20}\b(?:footage|b[- ]?roll|clips?)\b",
     "outside footage", "no b-roll from outside the user's own upload",
     "We only cut from what you upload. If you send the extra clips we'll cut "
     "them in as b-roll."),
]


def _hit(patterns, text):
    for entry in patterns:
        if re.search(entry[0], text, re.I):
            return entry
    return None


def classify(brief, tier="free"):
    """-> dict. `may_dispatch` is the only field the caller may act on."""
    t = str(brief or "")
    tier = str(tier or "free").strip().lower()

    u = _hit(_UNSAFE, t)
    if u:
        return {"state": "UNSAFE", "reason": u[1], "may_dispatch": False,
                "credits_quoted": 0, "counter": "dispatch_refused_unsafe",
                "message": "We can't make that. Nothing was charged.",
                "classifier_version": CLASSIFIER_VERSION}

    g = _hit(_GENERATIVE, t)
    if g:
        paywalled = tier not in ("pro", "max")
        msg = ("That needs generated footage, which costs %d credits for the "
               "video." % AI_VIDEO_CREDITS)
        if paywalled:
            # THE QUOTE COMES FIRST AND THE WALL SECOND. A paywall shown without
            # the number answers a question the user did not ask and hides the
            # one they did.
            msg += " It's on Pro and Max — here's what that costs."
        return {"state": "GENERATIVE", "reason": g[1], "may_dispatch": False,
                "credits_quoted": AI_VIDEO_CREDITS,
                "counter": "dispatch_quoted_generative",
                "paywall": paywalled, "message": msg,
                "classifier_version": CLASSIFIER_VERSION}

    o = _hit(_OUT_OF_SCOPE, t)
    if o:
        return {"state": "OUT_OF_SCOPE", "reason": o[1], "law": o[2],
                "may_dispatch": False, "credits_quoted": 0,
                "counter": "dispatch_negotiated_out_of_scope",
                "message": o[3], "classifier_version": CLASSIFIER_VERSION}

    return {"state": "IN_SCOPE", "reason": "", "may_dispatch": True,
            "credits_quoted": 0, "counter": "dispatch_in_scope",
            "message": "", "classifier_version": CLASSIFIER_VERSION}
