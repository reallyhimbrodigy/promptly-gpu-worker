#!/usr/bin/env python3
"""THE ONE PROMPT WE STILL WRITE. vibe + standing defaults -> one instruction.

Every other prompt in this lane was removed when ChatCut's agent became the
editor. This is what is left: the thing typed into their box.

── WHY PRECEDENCE IS STATED, NOT MOSTLY PARSED ─────────────────────────────

Zac's rule is "a user's explicit constraint overrides the default it names".
The obvious build is a matcher that finds the constraint and drops the default.
I have already been wrong about that matcher twice, on measured corpora:

  * `only` is a LIMIT four times out of five on a CATEGORY INSIDE the brief, not
    on the brief. "Allowed visual edits: only zoom in / zoom out" sits above
    four caption items. A wider pattern would have failed a CORRECT run four
    times in five.
  * "use subtle zoom-ins ONLY WHEN they add emphasis" is a CONDITION. Any
    verb-free `only` pattern eats it and bans the family the sentence permits.
  * "Do not cut EVERY breath or micro-pause" is a density note in a brief whose
    line above asks for cuts. The first negation matcher fired on it.

The separating property was never the sentence's shape. So the composer does the
robust thing FIRST and the clever thing second: it states the precedence rule in
the instruction itself, where their agent reads both the defaults and the user's
own words and resolves the conflict with the user's words in front of it. That
works for every constraint, including the ones no matcher of mine would catch.

Suppression is then a NARROW EXTRA: only an unambiguous, directly-bound negation
of a named family drops its default, because leaving "add sound effects" in the
instruction beside a user saying "no sound" is sloppy even when precedence
resolves it. Everything else is KEPT, and anything that looks like a constraint
but is not unambiguous is KEPT AND REPORTED as ambiguous rather than guessed at.

Three states, and the run line carries all three: SUPPRESSED / KEPT /
AMBIGUOUS_KEPT. A suppression nobody can see is a silent edit to the user's
brief.

── AND IT NEVER TELLS THEIR AGENT NOT TO ASK ───────────────────────────────

No "do not ask questions". A question is not a failure mode; it is the agent
doing the thing we cannot do from here, and the answer relays to the user.
"""
import re

COMPOSER_VERSION = "1.0.0"

# Each default names ONE family. The family is what a user constraint can
# override, and the name is what the override has to match.
DEFAULTS = [
    ("deadair",     "dead air and filler words",
     "Cut dead air and filler words."),
    ("captions",    "captions",
     "Caption the whole video."),
    # FOUR FAMILIES IN ONE LINE. They were four bullets saying the same thing
    # four times — place X where it fits — and four bullets read as four
    # obligations to discharge rather than as four things available. Each family
    # keeps its own suppression key, so "no sound effects please" still drops
    # sfx alone; the SENTENCE is shared, the RULING is not.
    # The sentence here is a TEMPLATE, filled from the families that survive
    # classification — see PLACEABLE below.
    ("graphics",    "motion graphics", None),
    # Ruled individually, rendered inside the graphics bullet by
    # placeable_sentence(). A None sentence means "this family is ruled but does
    # not print a line of its own".
    ("zooms",       "zooms", None),
    ("sfx",         "sound effects", None),
    ("transitions", "transitions", None),
    ("aspect",      "aspect ratio",
     "Keep the source aspect ratio."),
    ("open",        "what may be used",
     "The project's components, caption styles and sounds and your own are all "
     "open — choose freely."),
]

# THE FOUR PLACEABLE FAMILIES, IN ONE SENTENCE, EACH STILL RULED SEPARATELY.
# They were four bullets saying the same thing four times — place X where it
# fits — and four bullets read as four obligations to discharge rather than as
# four things available. But collapsing them into one STRING would have taken
# their suppression with them: "no sound effects please" must still drop sfx and
# nothing else. So the sentence is BUILT from the survivors, and a user who
# bans one gets a sentence naming the other three.
#
# This is the half of the collapse that is easy to lose, because the instruction
# looks right either way — the bullet is present, it reads well, and the only
# symptom of getting it wrong is a suppression that silently stops working.
PLACEABLE = [("graphics", "motion graphics"), ("zooms", "zooms"),
             ("sfx", "sound effects"), ("transitions", "transitions")]


def placeable_sentence(states):
    """-> the graphics bullet naming only the families not suppressed, or None."""
    live = [label for key, label in PLACEABLE if states[key][0] != "SUPPRESSED"]
    if not live:
        return None
    if len(live) == 1:
        return "Add %s where they fit." % live[0]
    return "Add %s and %s where they fit." % (", ".join(live[:-1]), live[-1])

# Words that name each family in a user's own vocabulary. Deliberately WIDE for
# DETECTION and narrow for ACTION: a hit here only makes the sentence a
# candidate; the guards below decide whether it is a limit at all.
FAMILY_WORDS = {
    "deadair":     r"dead ?air|silences?|pauses?|fillers?|ums?\b",
    "captions":    r"captions?|subtitles?|titles?",
    "graphics":    r"motion graphics?|graphics?|overlays?|text cards?",
    "zooms":       r"zooms?|zooming|punch ?ins?",
    "sfx":         r"sound ?effects?|sfx|sounds?",
    "transitions": r"transitions?",
    "aspect":      r"aspect ratio|vertical|horizontal|square|9:16|16:9",
    # "open" is the neutrality sentence. Its family words are deliberately the
    # ones a user reaches for when they want to LIMIT what may be used — if they
    # say "only use my own graphics", the sentence telling their agent
    # everything is open must be the one that drops.
    "open":        r"registered|own (?:graphics|components?|sounds?|library)"
                   r"|your library|my library",
}

NEGATION = r"(?:no|not|don't|do not|never|without|skip|avoid|leave out|omit)"

# A sentence that CONDITIONS a family is not a sentence that bans it.
CONDITIONAL = re.compile(r"\bonly (?:when|if|where)\b", re.I)
# A negation qualified by a quantifier is a DENSITY note, not a ban:
# "do not cut EVERY breath", "not too many zooms".
QUANTIFIED = re.compile(r"\b(?:every|all|too many|so many|constant(?:ly)?)\b", re.I)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text or "") if s.strip()]


def classify(user_brief):
    """-> {key: (state, evidence)} over every default. Never invents a limit."""
    out = {}
    for key, _family, _sentence in DEFAULTS:
        words = FAMILY_WORDS[key]
        state, evidence = "KEPT", ""
        for s in _sentences(user_brief):
            if not re.search(words, s, re.I):
                continue
            if CONDITIONAL.search(s):
                # The sentence PERMITS the family under a condition. Banning it
                # here is the exact inversion that would have failed a correct
                # run: "use subtle zoom-ins only when they add emphasis".
                state, evidence = "AMBIGUOUS_KEPT", s
                continue
            # The negation must bind the family DIRECTLY — within a short span,
            # not merely co-occurring in a long sentence.
            near = re.search(NEGATION + r"[^.;!?]{0,24}?(?:" + words + r")", s, re.I)
            if not near:
                continue
            if QUANTIFIED.search(s):
                state, evidence = "AMBIGUOUS_KEPT", s
                continue
            state, evidence = "SUPPRESSED", s
            break
        out[key] = (state, evidence)
    return out


def user_slot(vibe, user_brief):
    """-> the ONE quoted line that stands for what the user asked. Never empty.

    ONE SLOT, NOT TWO. The old shape had a vibe line at the top and a brief
    block at the bottom, so a request arrived as two fragments in two places
    with the defaults between them, and the agent had to work out that they were
    one request. Composing them here means the instruction has exactly one
    place where the user speaks.

    NEVER A PLACEHOLDER. The old shape wrote "(none given)" into the brief slot,
    which reads as a user who asked for nothing — and a request that arrives
    saying nothing is a request the agent is free to invent. A vibe-only
    submission is not an empty brief; it is a short one.
    """
    v = str(vibe or "").strip().rstrip(".")
    t = str(user_brief or "").strip()
    if v and t:
        return 'a %s edit: "%s"' % (v, t)
    if t:
        return '"%s"' % t
    if v:
        # THE VIBE IS THE QUOTE. It is the user's own choice, made in the app.
        return "a %s edit" % v
    # NEITHER, which the app should not send. The slot still says something
    # TRUE rather than something empty: they submitted a video to be edited,
    # and that is the whole of what is known. Anything more specific here
    # would be words put in their mouth.
    return "an edit of this video"


# THE TIER LINE SAYS WHAT TO DO, NEVER WHAT THE ACCOUNT IS.
#
# MY FIRST VERSION OPENED "This is a paid account — you won't hit a plan
# limit." Both halves are claims about an ACCOUNT, and every one of them is a
# billing fact their agent will restate and act on. Ruled out entirely by Zac
# 2026-09-23: no sentence may claim anything about an account, a plan, a limit
# or exports. The goal is that every sentence their AI reads is TRUE, and a
# claim about someone's plan is the class I am least able to keep true — it
# changes without anything here changing, and I cannot see it change.
#
# WHAT SURVIVES IS THE INSTRUCTION, which is the only part that was ever doing
# work: whether to spend on generation. Same information for the agent, no
# assertion about the account it is running in.
TIER_LINES = {
    "paid": ("Only generate new images, video, voiceover or music if the user "
             "asked for it."),
    "free": "Don't generate new images, video, voiceover or music.",
}

# Words that would make the line a claim about the account rather than an
# instruction about the edit. L15 refuses any of them, and the two Zac named
# are the ones my own first draft used.
ACCOUNT_CLAIMS = ("plan limit", "unlimited", "plan", "account", "export",
                  "subscription", "tier", "upgrade", "billing", "quota",
                  "no limit", "limitless")


def tier_line(tier):
    """-> the generation instruction for this tier, or None.

    UNKNOWN TIER SAYS NOTHING. A default would make every unconfigured caller
    assert something about an account it knows nothing about — absent is not
    paid, and it is not free either.
    """
    return TIER_LINES.get(str(tier or "").strip().lower())


def compose(vibe, user_brief, tier=None):
    """-> dict. The instruction is ONE message; everything else is the record."""
    states = classify(user_brief)
    kept = [k for k, _f, _s in DEFAULTS if states[k][0] != "SUPPRESSED"]

    # THE USER FIRST, AND PRECEDENCE IN THE SAME BREATH. "Do exactly that"
    # carries the precedence without a paragraph about precedence: the defaults
    # are introduced as what to do WHERE THEY DID NOT SAY, so there is no case
    # in which a default has to be weighed against the user's words.
    lines = ['The user asked for: %s' % user_slot(vibe, user_brief), ""]
    lines.append("Do exactly that. Where they didn't say, use these defaults:")
    for key, _family, sentence in DEFAULTS:
        if key == "graphics":
            ps = placeable_sentence(states)
            if ps:
                lines.append("  - " + ps)
            continue
        if sentence is None or states[key][0] == "SUPPRESSED":
            continue
        lines.append("  - " + sentence)
    tl = tier_line(tier)
    if tl:
        # AFTER the defaults and BEFORE the invitation to ask: it is account
        # CONTEXT, not a thing to do to the video, and putting it among the
        # defaults would read as an instruction.
        lines.append("")
        lines.append(tl)
    lines.append("")
    # Not "do not ask questions". The opposite.
    lines.append("If anything is unclear or needs a decision only the user can "
                 "make, ask — your question reaches them.")
    return {
        "composer_version": COMPOSER_VERSION,
        "instruction": "\n".join(lines),
        "user_slot": user_slot(vibe, user_brief),
        "tier_line": tl,
        "suppressed": sorted(k for k, (s, _) in states.items() if s == "SUPPRESSED"),
        "ambiguous_kept": sorted(k for k, (s, _) in states.items() if s == "AMBIGUOUS_KEPT"),
        "kept": kept,
        "evidence": {k: e for k, (s, e) in states.items() if e},
    }


if __name__ == "__main__":
    import json, sys
    r = compose(sys.argv[1] if len(sys.argv) > 1 else "",
                sys.argv[2] if len(sys.argv) > 2 else "")
    print(r["instruction"])
    print("\n--- composer v%s  suppressed=%s ambiguous=%s ---"
          % (r["composer_version"], r["suppressed"], r["ambiguous_kept"]))
