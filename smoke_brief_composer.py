#!/usr/bin/env python3
"""The composer must not quietly edit the user's brief, and must not ban a
family the user actually permitted.

THE FIXTURES ARE SAMPLED, NOT INVENTED. Every constraint sentence below is from
the measured brief corpus — pb-003, pb-009, pb-024 — and three of them are the
exact sentences that broke earlier constraint matchers in this repo. Fixtures
are sampled from production; that is a standing law, and here it is the only
thing that makes L3-L5 mean anything: a matcher tested on sentences I wrote
would pass by construction, because I would write the sentences it handles.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brief_composer as bc                                   # noqa: E402

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-44s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    keys = [k for k, _f, _s in bc.DEFAULTS]

    leg("L0 version_is_stated", bool(bc.COMPOSER_VERSION.strip()),
        "v%s — every run line carries it" % bc.COMPOSER_VERSION)

    # L1 POPULATION FLOOR. Eight defaults, and every one reaches the instruction
    # when nothing is suppressed. A composer that silently dropped half of them
    # would pass every other leg here.
    plain = bc.compose("energetic", "Make it punchy.")
    missing = [k for k, _f, s in bc.DEFAULTS if s not in plain["instruction"]]
    leg("L1 every_default_reaches_the_instruction",
        len(bc.DEFAULTS) >= 8 and not missing and not plain["suppressed"],
        "%d defaults, missing=%s, suppressed=%s"
        % (len(bc.DEFAULTS), missing or "none", plain["suppressed"] or "none"))

    # L2 AN EXPLICIT BAN SUPPRESSES EXACTLY ONE FAMILY. Over-suppression is the
    # failure that silently edits the brief.
    ban = bc.compose("", "No sound effects please.")
    leg("L2 explicit_ban_suppresses_exactly_that_family",
        ban["suppressed"] == ["sfx"],
        "suppressed=%s (want ['sfx'])" % ban["suppressed"])

    # L3 "ONLY WHEN" IS A CONDITION, NOT A BAN. pb-024's shape. A verb-free
    # `only` pattern eats this and bans the family the sentence PERMITS.
    cond = bc.compose("", "Use subtle zoom-ins only when they add emphasis.")
    leg("L3 only_when_is_a_condition_not_a_ban",
        "zooms" not in cond["suppressed"] and "zooms" in cond["ambiguous_kept"],
        "suppressed=%s ambiguous=%s" % (cond["suppressed"], cond["ambiguous_kept"]))

    # L4 A QUANTIFIED NEGATION IS A DENSITY NOTE. pb-009: the line above it asks
    # for "subtle, smooth cuts", so banning the family reverses the brief.
    dens = bc.compose("", "Do not cut every breath or micro-pause.")
    leg("L4 quantified_negation_is_not_a_ban", not dens["suppressed"],
        "suppressed=%s (want none)" % (dens["suppressed"] or "none"))

    # L4b THE QUANTIFIED GUARD, ISOLATED. L4's sentence is protected by the
    # BINDING DISTANCE, not by the quantifier check — "not" sits ~30 characters
    # from "micro-pause", so the guard is never even reached. A case that trips
    # one arm proves nothing about the other, and I only found that because two
    # mutations aimed at L4 both came back NOT RED. This sentence binds CLOSELY
    # and is quantified, so it reaches the guard and only the guard stops it.
    many = bc.compose("", "Don't add too many zooms.")
    leg("L4b quantified_guard_is_actually_reached",
        "zooms" not in many["suppressed"] and "zooms" in many["ambiguous_kept"],
        "suppressed=%s ambiguous=%s" % (many["suppressed"], many["ambiguous_kept"]))

    # L4c OVER-SUPPRESSION BY PROXIMITY. A negation and an UNRELATED family in
    # one sentence must not ban the family the user asked for. This is what the
    # 24-character binding buys, and nothing else tests it.
    mixed = bc.compose("", "No music, but add plenty of captions.")
    leg("L4c negation_does_not_reach_across_a_sentence",
        "captions" not in mixed["suppressed"] and "captions" in mixed["kept"],
        "suppressed=%s captions kept=%s"
        % (mixed["suppressed"] or "none", "captions" in mixed["kept"]))

    # L5 A CATEGORY-SCOPED `only` LIMITS A CATEGORY, NOT THE BRIEF. pb-003, and
    # the measured cost of getting this wrong: FOUR of the corpus's five `only`
    # sentences are category-scoped, so the wider rule fails a correct run 4
    # times in 5.
    scoped = bc.compose("", "Allowed visual edits: Only zoom in / zoom out "
                            "effects. Add clean, accurate captions.")
    leg("L5 category_scoped_only_bans_nothing",
        not scoped["suppressed"] and "captions" in scoped["kept"],
        "suppressed=%s captions kept=%s"
        % (scoped["suppressed"] or "none", "captions" in scoped["kept"]))

    # L6 IT NEVER TELLS THEIR AGENT NOT TO ASK. A question relays to the user;
    # suppressing it is how a brief gets guessed at instead of clarified.
    bad = [p for p in ("do not ask", "don't ask", "no questions", "without asking")
           if p in plain["instruction"].lower()]
    leg("L6 never_forbids_questions", not bad and "ask" in plain["instruction"].lower(),
        "forbidding phrases: %s" % (bad or "none"))

    # L7 THE USER'S WORDS ARE CARRIED VERBATIM AND WIN. Precedence is stated in
    # the instruction, which is what covers every constraint no matcher catches.
    txt = "Only trim and combine the strongest original soundbites."
    v = bc.compose("", txt)
    leg("L7 brief_verbatim_and_precedence_stated",
        txt in v["instruction"] and "wins wherever it disagrees" in v["instruction"],
        "verbatim=%s precedence=%s"
        % (txt in v["instruction"], "wins wherever it disagrees" in v["instruction"]))

    # L8 A SUPPRESSION IS ALWAYS REPORTED WITH ITS EVIDENCE. A default dropped
    # with nothing said is a silent edit to the user's brief.
    leg("L8 suppression_carries_its_evidence",
        bool(ban["suppressed"]) and all(ban["evidence"].get(k) for k in ban["suppressed"]),
        "evidence=%s" % {k: ban["evidence"].get(k) for k in ban["suppressed"]})

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
