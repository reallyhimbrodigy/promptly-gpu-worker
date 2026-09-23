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
import re
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
    # A DEFAULT WITH NO SENTENCE OF ITS OWN STILL HAS TO ARRIVE. zooms, sfx and
    # transitions are ruled individually and RENDERED INSIDE the shared
    # placeable bullet, so checking only for a printed sentence would let all
    # three vanish from that bullet while the floor of eight stayed green —
    # a floor on a sum hiding which contributor went. For those, the FAMILY
    # LABEL is what must reach the instruction.
    plain = bc.compose("energetic", "Make it punchy.")
    missing = [k for k, _f, s in bc.DEFAULTS
               if (s or dict(bc.PLACEABLE).get(k, k)) not in plain["instruction"]]
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
    # The precedence SENTENCE changed with the shape and the leg moved with it.
    # It used to be a separate paragraph at the bottom — "which wins wherever it
    # disagrees with anything above" — introducing a brief that sat AFTER eight
    # defaults. Now the user's words are first and "Do exactly that. Where they
    # didn't say, use these defaults" carries the precedence in the same breath,
    # so there is no case where a default must be weighed against the user.
    # Asserting the old wording here would have been a check defending a
    # DECISION that had been correctly reversed.
    txt = "Only trim and combine the strongest original soundbites."
    v = bc.compose("", txt)
    verbatim = txt in v["instruction"]
    prec = ("Do exactly that." in v["instruction"]
            and "Where they didn't say" in v["instruction"])
    order = (prec
             and v["instruction"].index(txt)
             < v["instruction"].index("Do exactly that."))
    leg("L7 brief_verbatim_and_precedence_stated",
        verbatim and prec and order,
        "verbatim=%s precedence=%s user_comes_first=%s" % (verbatim, prec, order))

    # L8 A SUPPRESSION IS ALWAYS REPORTED WITH ITS EVIDENCE. A default dropped
    # with nothing said is a silent edit to the user's brief.
    leg("L8 suppression_carries_its_evidence",
        bool(ban["suppressed"]) and all(ban["evidence"].get(k) for k in ban["suppressed"]),
        "evidence=%s" % {k: ban["evidence"].get(k) for k in ban["suppressed"]})

    # L12 THE USER SLOT IS NEVER EMPTY AND NEVER A PLACEHOLDER.
    #
    # The old shape wrote "(none given)" into the brief block whenever the app
    # sent only a vibe. That is not a neutral marker: it tells their agent the
    # user asked for NOTHING, and a request that arrives saying nothing is a
    # request the agent is free to invent — the same control as Probe A, one
    # level up. A vibe-only submission is not an empty brief; it is a short one,
    # and the vibe is the user's own choice made in the app.
    #
    # DRIVEN OVER EVERY INPUT COMBINATION, not just the one the app usually
    # sends. Three of the four cases produced "(none given)" or an empty slot
    # under the old shape, and the one that did not is the one anyone would
    # test by hand.
    PLACEHOLDERS = ("(none given)", "(none)", "n/a", "none given", "not specified",
                    "unspecified", "no brief", "null", "undefined", "tbd")
    cases = [("punchy", "Cut it tight and add captions."), ("punchy", ""),
             ("", "Cut it tight and add captions."), ("", "")]
    bad = []
    for v, t in cases:
        r = bc.compose(v, t)
        slot = (r.get("user_slot") or "").strip()
        head = r["instruction"].splitlines()[0]
        low = (slot + " " + head).lower()
        if not slot or any(ph in low for ph in PLACEHOLDERS):
            bad.append((v, t, head))
    leg("L12 user_slot_is_never_empty_or_a_placeholder", not bad,
        "%d/%d input combinations produce a placeholder%s"
        % (len(bad), len(cases), ("  <<< " + bad[0][2][:52]) if bad else ""))

    # L13 THE USER'S WORDS COME FIRST AND CARRY THEIR OWN PRECEDENCE.
    # "Do exactly that. Where they didn't say, use these defaults" states the
    # precedence in the same breath as the request, so there is no case in which
    # a default has to be weighed against the user. The old shape put the brief
    # LAST, after eight defaults, with a separate paragraph explaining that it
    # won — precedence as a footnote to the thing it governs.
    r = bc.compose("punchy", "Cut it tight.")
    first = r["instruction"].splitlines()[0]
    leg("L13 user_first_and_precedence_in_the_same_breath",
        first.startswith("The user asked for:") and "Cut it tight." in first
        and "Do exactly that" in r["instruction"]
        and "Where they didn't say" in r["instruction"],
        "first line: %s" % first[:66])

    # L14 THE TIER LINE IS EMITTED ONLY FOR A RULED TIER, AND CLAIMS ONLY WHAT
    # WAS RULED. A billing claim is the worst thing to get loose: their agent
    # restates whatever the line says as fact and acts on it, and "unlimited
    # exports" licenses different behaviour from "this is a paid account".
    #
    # AN UNKNOWN TIER MUST SAY NOTHING. A default of "paid" would make every
    # unconfigured caller assert a billing fact about somebody's account —
    # absent is not paid, which is the absent-as-a-value rule applied to a
    # claim rather than a measurement.
    paid = bc.compose("", "Cut it tight.", tier="paid")
    for t in (None, "", "free", "unknown", "pro", "PAID "):
        r = bc.compose("", "Cut it tight.", tier=t)
        expected = bool(bc.tier_line(t))
        got = bool(r["tier_line"])
        if expected != got:
            FAILS.append("L14 tier %r" % t)
    unruled = [t for t in (None, "", "free", "unknown", "pro")
               if bc.compose("", "x", tier=t)["tier_line"]]
    # AND THE DEFAULT ITSELF, called with NO tier argument. Every check above
    # passes tier explicitly, so changing the parameter's default changes real
    # bytes and no verdict — the wrong-population vacuity, caught by its own
    # mutation. A caller that never learned about tiers is exactly the caller
    # that must not assert one.
    omitted = bc.compose("", "x")["tier_line"]
    leg("L14 tier_line_only_for_a_ruled_tier",
        bool(paid["tier_line"]) and not unruled and omitted is None,
        "paid=emitted  unruled emitting: %s  omitted-arg emits: %r"
        % (unruled or "none", omitted))

    # L15 IT DOES NOT CLAIM WHAT WAS NEVER READ. Export limits, caps and
    # per-tier entitlements are surfaces I have not measured; a sourceless
    # claim is one their agent will act on anyway. And "paid" alone reads as
    # permission to spend, so the credit guard travels WITH it — the two halves
    # are one sentence or neither.
    line = paid["tier_line"]
    overclaims = [w for w in ("unlimited", "no limit", "as many", "free of charge",
                              "at no cost", "unmetered") if w in line.lower()]
    leg("L15 tier_line_claims_only_what_was_ruled",
        not overclaims and "spend credits" in line and "only use them if" in line,
        "overclaims=%s  credit guard present=%s"
        % (overclaims or "none", "spend credits" in line))

    # L9 THE BRIEF IS NEUTRAL ABOUT WHAT MAY BE USED. Ruled by Zac 2026-09-22,
    # first for sounds and then widened: components and caption styles too. "No
    # favorite or better option — as simple as possible for them."
    #
    # FOUR CLASSES, NOT TWO, and PREFERS is the one worth having. A restriction
    # announces itself; a PREFERENCE does not, and it steers just as hard. "Use
    # the project's own graphics where possible" forbids nothing and will still
    # produce a run that never touches their library — and it reads as helpful
    # guidance in review, which is how it would survive a reader looking only
    # for the word "only".
    #
    # CLASSIFY EVERY SENTENCE THAT MENTIONS ANY OF THE FOUR FAMILIES, rather
    # than grepping for the phrasing that happened to be there when the rule was
    # written. The clause this replaced said "use only the components, sounds
    # and caption styles already registered" while ANOTHER said "from the
    # project's registered components" — two spellings in one instruction, and a
    # needle aimed at either would have missed the other.
    #
    # FREES is tested FIRST because the neutrality sentence itself mentions all
    # three families and the word "own"; the classes must be told apart rather
    # than counted.
    FAMILY = (r"\bcomponents?\b|\bmotion graphics?\b|\bgraphics?\b|\boverlays?\b"
              r"|\bcaptions?\b|\bcaption styles?\b|\bsubtitles?\b"
              r"|\bsounds?\b|\bsound ?effects?\b|\bsfx\b")
    PREFERS = (r"\bprefer\b|\bpreferr?ed\b|\bfavou?r\b|\bfavou?rite\b|\bbest\b"
               r"|\bbetter\b|\bideally\b|\brecommend|\bwhere possible\b"
               r"|\bwhen possible\b|\bwherever possible\b|\bdefault to\b"
               r"|\bstick to\b|\bprimarily\b|\brather than\b|\binstead of\b"
               r"|\blean on\b|\bstart with\b")
    RESTRICTS = (r"\bonly\b|\brestrict|\bmust use\b|\blimited to\b|\bconfined to\b"
                 r"|\bregistered sounds\b|from the project's registered")

    def _family_sentences(text):
        out = []
        for raw in re.split(r"(?<=[.!?])\s+|\n", text):
            s2 = raw.strip().lstrip("- ").strip()
            if not s2 or not re.search(FAMILY, s2, re.I):
                continue
            low = s2.lower()
            if ("not restricted" in low or "choose freely" in low
                    or "are open" in low):
                out.append(("FREES", s2))
            elif re.search(RESTRICTS, low):
                out.append(("RESTRICTS", s2))
            elif re.search(PREFERS, low):
                out.append(("PREFERS", s2))
            else:
                out.append(("NEUTRAL", s2))
        return out

    rows = _family_sentences(plain["instruction"])
    restricts = [t for k, t in rows if k == "RESTRICTS"]
    prefers = [t for k, t in rows if k == "PREFERS"]
    frees = [t for k, t in rows if k == "FREES"]
    # THE POPULATION IS ASSERTED. A leg over an empty set passes and says
    # nothing — if the instruction ever stops naming these families at all, this
    # must go red rather than quietly succeed.
    leg("L9 brief_is_neutral_about_what_may_be_used",
        bool(rows) and not restricts and not prefers and bool(frees),
        "%d family sentence(s): %d RESTRICTS %d PREFERS %d FREES%s"
        % (len(rows), len(restricts), len(prefers), len(frees),
           ("  <<< " + (restricts + prefers)[0][:56]) if (restricts or prefers) else ""))

    # L10 EVERY FAMILY IS NAMED IN THE SENTENCE THAT OPENS IT — scoped to the
    # FREES rows, not to the instruction at large.
    #
    # THE FIRST VERSION SEARCHED EVERY FAMILY SENTENCE AND ITS MUTATION PASSED.
    # Dropping "caption styles" from the neutrality sentence left captions
    # covered by "Add captions for the whole video", so the leg went green while
    # caption styles had quietly lost their explicit freedom — a check passing
    # for a reason other than the one it claims, found only because the mutation
    # was aimed at the property rather than at the wording. A count over the
    # whole set lets one family lose its neutrality while the total stays put,
    # and the family that loses it is the one nobody sees go.
    covered = {f: any(re.search(pat, t, re.I) for k, t in rows if k == "FREES")
               for f, pat in (("components", r"components?"),
                              ("caption styles", r"caption styles?"),
                              ("sounds", r"sounds?|sfx"))}
    leg("L10 every_family_is_named_in_the_opening_sentence",
        all(covered.values()) and bool(covered), "%s" % covered)

    # L11 SIMPLE MEANS SHORT, AND THE LENGTH IS REPORTED RATHER THAN CAPPED.
    # A hard ceiling would be a number pulled from nowhere; what matters is that
    # the figure is visible, so a clause creeping back in is seen the next time
    # anyone reads this output.
    nwords = len(plain["instruction"].split())
    leg("L11 brief_length_is_reported", nwords > 0, "%d words" % nwords)

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
