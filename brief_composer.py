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
     "Add captions for the whole video."),
    ("graphics",    "motion graphics",
     "Place motion graphics from the project's registered components where they "
     "fit — every one carries real default text, so none needs copy written "
     "before it is placed."),
    ("zooms",       "zooms",
     "Zoom on moments of emphasis."),
    ("sfx",         "sound effects",
     # RULED BY ZAC 2026-09-22: their agent chooses FREELY between our thirteen
     # and their own library. The old wording — "from the project's registered
     # sounds" — was a pool restriction nobody had ruled, written in when the
     # thirteen were the only sounds that existed. A sentence that narrows the
     # menu is the opposite of the whole programme: the point of the 32 lines is
     # that every sound is SEEN, not that no other sound may be used.
     "Place sound effects where the moment wants one — the project's sounds or "
     "your own library."),
    ("transitions", "transitions",
     "Put transitions on scene changes."),
    ("aspect",      "aspect ratio",
     "Keep the source aspect ratio."),
    ("registered",  "registered components",
     # SOUNDS COME OUT OF THE "ONLY" AND ARE NAMED AS FREE, rather than merely
     # dropped. Deleting the word "sounds" from this sentence would leave the
     # restriction unstated and the freedom unstated too, and an unstated
     # freedom is indistinguishable from an oversight — the same reason a
     # suppression is reported with its evidence instead of silently applied.
     "Use only the components and caption styles already registered in this "
     "project. Sounds are not restricted — choose freely between the project's "
     "sounds and your own library."),
]

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
    "registered":  r"registered components?",
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


def compose(vibe, user_brief):
    """-> dict. The instruction is ONE message; everything else is the record."""
    states = classify(user_brief)
    lines = []
    if vibe:
        lines.append("Vibe: %s." % str(vibe).strip().rstrip("."))
    lines.append("")
    lines.append("Edit this video. Unless the brief below says otherwise:")
    kept = []
    for key, _family, sentence in DEFAULTS:
        if states[key][0] == "SUPPRESSED":
            continue
        kept.append(key)
        lines.append("  - " + sentence)
    lines.append("")
    lines.append("THE USER'S BRIEF, which wins wherever it disagrees with anything "
                 "above:")
    lines.append((user_brief or "").strip() or "(none given)")
    lines.append("")
    # Not "do not ask questions". The opposite.
    lines.append("If something in the brief is unclear or you need a decision "
                 "only the user can make, ask — the question is relayed to them.")
    return {
        "composer_version": COMPOSER_VERSION,
        "instruction": "\n".join(lines),
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
