#!/usr/bin/env python3
"""The brief is three parts and nothing else.

Ruled by Zac 2026-09-23: the user's words verbatim, one sentence offering the
project's assets alongside their own, and the tier line. No defaults, no ask
line, no aspect line.

WHAT THE OLD LEGS WERE DEFENDING IS GONE, AND THAT IS NOT THE SAME AS THEM
BEING WRONG. Eight legs asserted that eight defaults reached the instruction,
that a ban suppressed exactly one family, that "only WHEN" was a condition and
not a limit. Every one was correct about the composer it was written for. They
are removed rather than loosened, because a leg kept alive over content that
no longer exists is a leg asserting nothing while still printing ok.
"""
import os
import hashlib
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brief_composer as bc                                    # noqa: E402

FAILS, NLEGS = [], 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    plain = bc.compose("Cut it tight and keep the best soundbites.", "paid")
    text = plain["instruction"]

    # L1 THREE PARTS, AND NOTHING ELSE. The floor is what stops a default
    # creeping back one plausible sentence at a time — which is exactly how
    # the density rate survived a careful removal once already.
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    leg("L1 exactly_three_parts", len(paras) == 3,
        "%d paragraph(s): %s" % (len(paras), [p[:28] for p in paras]))

    # L2 THE USER'S WORDS ARE FIRST AND VERBATIM.
    txt = "Only trim and combine the strongest original soundbites."
    v = bc.compose(txt, "paid")["instruction"]
    leg("L2 user_words_first_and_verbatim",
        v.startswith("The user asked for:") and txt in v.splitlines()[0],
        "first line: %s" % v.splitlines()[0][:62])

    # L3 NO DEFAULTS, NO ASK LINE, NO ASPECT LINE. Named individually, because
    # a count would let one come back while another went.
    gone = {
        "a defaults block": "Where they didn't say",
        "the ask line": "your question reaches them",
        "the aspect line": "aspect ratio",
        "a dead-air default": "Cut dead air",
        "a captions default": "Caption the whole video",
    }
    back = [k for k, needle in gone.items() if needle in text]
    leg("L3 nothing_but_the_three_parts", not back,
        "%d returned: %s" % (len(back), back or "none"))

    # L9 THE BRIEF IS NEUTRAL ABOUT WHAT MAY BE USED. RESTRICTS / PREFERS /
    # FREES / NEUTRAL over every sentence naming an asset family. The open
    # line offers; it never restricts and never steers.
    FAMILY = (r"\bcomponents?\b|\bgraphics?\b|\bcaption styles?\b|\bcaptions?\b"
              r"|\bsounds?\b|\bsfx\b")
    PREFERS = (r"\bprefer\b|\bfavou?r\b|\bbest\b|\bbetter\b|\bideally\b"
               r"|\bwhere possible\b|\bdefault to\b|\bstick to\b|\brather than\b"
               r"|\binstead of\b|\bprimarily\b")
    RESTRICTS = r"\bonly\b|\brestrict|\bmust use\b|\blimited to\b|\bconfined to\b"
    rows = []
    for raw in re.split(r"(?<=[.!?])\s+|\n", text):
        s2 = raw.strip()
        if not s2 or not re.search(FAMILY, s2, re.I):
            continue
        low = s2.lower()
        # RESTRICTS IS CHECKED FIRST, AND THE ORDER WAS THE HOLE. FREES used
        # to win, so a sentence that said "use ONLY our graphics ... here for
        # you alongside your own" was classified as an offer: the friendly
        # tail masked the limit, and the leg passed the exact defect it
        # exists to catch. Found by a red-proof mutation that applied
        # cleanly and changed no verdict — the mutation was fine and the
        # CHECK was wrong, which is the harder of the two to notice.
        if re.search(RESTRICTS, low):
            rows.append(("RESTRICTS", s2))
        elif "alongside your own" in low or "here for you" in low:
            rows.append(("FREES", s2))
        elif re.search(PREFERS, low):
            rows.append(("PREFERS", s2))
        else:
            rows.append(("NEUTRAL", s2))
    bad = [t for k, t in rows if k in ("RESTRICTS", "PREFERS")]
    frees = [t for k, t in rows if k == "FREES"]
    leg("L9 brief_is_neutral_about_what_may_be_used",
        bool(rows) and not bad and bool(frees),
        "%d family sentence(s), %d offending, %d FREES%s"
        % (len(rows), len(bad), len(frees), ("  <<< " + bad[0][:48]) if bad else ""))

    # L10 ALL THREE FAMILIES ARE NAMED IN THE SENTENCE THAT OPENS THEM. A
    # family missing from the offer is a family their agent has no reason to
    # think it may touch, and it is the one nobody sees go.
    covered = {f: any(re.search(pat, t, re.I) for k, t in rows if k == "FREES")
               for f, pat in (("graphics", r"graphics?"),
                              ("caption styles", r"caption styles?"),
                              ("sounds", r"sounds?"))}
    leg("L10 every_family_is_named_in_the_open_line",
        bool(covered) and all(covered.values()), "%s" % covered)

    # L12 THE USER SLOT IS NEVER EMPTY AND NEVER A PLACEHOLDER. Driven over
    # every input shape, because the one anyone tests by hand is the one that
    # was never broken.
    PLACEHOLDERS = ("(none given)", "(none)", "n/a", "not specified", "unspecified",
                    "no brief", "null", "undefined", "tbd")
    bad12 = []
    for w in ("Cut it tight.", "", None, "   "):
        r = bc.compose(w, "paid")
        slot = (r.get("user_slot") or "").strip()
        low = (slot + " " + r["instruction"].splitlines()[0]).lower()
        if not slot or any(ph in low for ph in PLACEHOLDERS):
            bad12.append(repr(w))
    leg("L12 user_slot_is_never_empty_or_a_placeholder", not bad12,
        "%d input(s) produce a placeholder: %s" % (len(bad12), bad12 or "none"))

    # L14 A TIER LINE ONLY FOR A RULED TIER, and the DEFAULT is exercised by
    # calling with the argument OMITTED — every other check passes tier
    # explicitly, so the default would otherwise never be on the path.
    unruled = [t for t in (None, "", "unknown", "pro")
               if bc.compose("x", tier=t)["tier_line"]]
    omitted = bc.compose("x")["tier_line"]
    leg("L14 tier_line_only_for_a_ruled_tier",
        bc.compose("x", "paid")["tier_line"] and bc.compose("x", "free")["tier_line"]
        and not unruled and omitted is None,
        "unruled emitting: %s | omitted-arg: %r" % (unruled or "none", omitted))

    # L15 NO TIER LINE CLAIMS ANYTHING ABOUT AN ACCOUNT — the leg Zac kept.
    # Driven over EVERY ruled tier, because a tier added later is written by
    # someone whose only model is the existing ones.
    offenders = {t: [w for w in bc.ACCOUNT_CLAIMS if w in line.lower()]
                 for t, line in bc.TIER_LINES.items()}
    offenders = {t: v for t, v in offenders.items() if v}
    leg("L15 no_tier_line_claims_anything_about_an_account",
        bool(bc.TIER_LINES) and not offenders,
        "%d ruled tier(s), offending: %s" % (len(bc.TIER_LINES), offenders or "none"))

    # L16 AND EVERY TIER LINE STILL INSTRUCTS. Stripping the claims must not
    # strip the instruction: a line that asserts nothing and instructs nothing
    # looks like a guard and does nothing.
    silent = [t for t, line in bc.TIER_LINES.items() if "generate" not in line.lower()]
    leg("L16 every_tier_line_still_instructs", not silent,
        "tiers saying nothing about generation: %s" % (silent or "none"))

    # L17 SIMPLE MEANS SHORT, AND THE LENGTH IS REPORTED RATHER THAN CAPPED.
    n = len(text.split())
    leg("L17 brief_length_is_reported", n > 0, "%d words" % n)

    # L18 THE BRIEF HAS A PIN, AND THE PIN IS A FUNCTION.
    #
    # Two shas failed to reproduce across two trees in one exchange. The first
    # hashed the whole composed instruction, so it carried the USER'S WORDS
    # and pinned one composition of one input. The second was this pin
    # described in PROSE — B1 tried EIGHT constructions of the sentence and
    # none matched, because the sentence omitted that each tier line is
    # rendered as `key=value`.
    #
    # So the leg CALLS brief_pin() rather than rebuilding it. A check that
    # reconstructs the thing it checks is a second implementation that agrees
    # with the first only until someone edits one of them — which is how the
    # prose recipe failed, one level up.
    _pin = bc.brief_pin()
    leg("L18 brief_wording_is_pinned_without_the_user_slot",
        _pin == "83d8019f2cb57a45" and "asked for" not in bc.brief_pin_material(),
        "%s (expected 83d8019f2cb57a45; material excludes the user slot)" % _pin)

    # L19 AND THE MATERIAL IS OBTAINABLE, WHICH IS WHAT MAKES A MISMATCH
    # DEBUGGABLE. Two trees comparing digests can only say "different"; two
    # trees comparing brief_pin_material() can diff two strings and see WHERE.
    leg("L19 the_pinned_material_is_readable_not_described",
        callable(getattr(bc, "brief_pin_material", None))
        and bc.OPEN_LINE in bc.brief_pin_material()
        and all(v in bc.brief_pin_material() for v in bc.TIER_LINES.values()),
        "%d chars, open line + %d tier line(s)"
        % (len(bc.brief_pin_material()), len(bc.TIER_LINES)))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
