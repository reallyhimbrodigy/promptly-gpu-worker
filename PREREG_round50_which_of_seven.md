# Round 50 — WHICH OF THE SEVEN. Registered before round 49 reports.

No round-49 arm numbers seen. Two `both_on` rows and one `no_examples` row have
been reported to me as APPARATUS proofs (the in-container marker, and REMOVED
where `both_on` says ON); **no placement counts from any removal arm**. This
document is written so the design is not shaped by the result, which is the
whole reason Zac asked for it now.

## The seven, named

From `PREREG_round48_two_variable.md` (cffc983 + 444c4b8):

    1  reference examples          k=3 matched beats into the cached brief
    2  ruling-time knowledge       the four judgement documents in SYSTEM
    3  the card derivation         derive_card_type / derive_card_props
    4  the card/text sentence      "cards and text are not alternatives"
    5  card_hero REQUIRED          the schema requirement
    6  the acceptance-gate fix     the orphaned gate demanding card_type
    7  the derived cutaway filter  444c4b8, replacing the hardcode

Round 49 tests **1 and 2**. This document is about the remaining five.

## FIRST: the condition under which round 50 SHOULD NOT RUN

Registered in advance so it is a decision rule and not a rationalisation.

**If round 49 shows the effect collapses in `no_examples` on all three clean
fixtures, the attribution is the examples and round 50 is moot.** Spend nothing.
The same holds for `no_knowledge`. Round 50 becomes live only if the effect
SURVIVES both removals — i.e. the doubling is carried by something in 3-7, or by
the bundle as a unit.

I would rather register the condition for not spending than discover it after
designing nine more runs.

## THREE OF THE FIVE ARE NOT CLEANLY ABLATABLE, and that is a finding, not an
## obstacle

This is the part that must be said before numbers exist, because afterwards it
will look like an excuse for whichever member the data implicates.

**6 — the acceptance-gate fix. NOT AN ARM.** Removing it reintroduces a gate
demanding a field the schema no longer offers, which is a GUARANTEED-REJECTION
loop: the agent retries, burns turns, and places nothing. That is precisely the
confound that made talking_head (22 rejections) and motion (3) unmeasurable in
round 48. An arm that recreates the confound produces UNMEASURABLE, not a null,
and it would corrupt the clean cohort — the only cohort that can answer anything.

**7 — the derived cutaway filter. NOT AN INDEPENDENT ARM.** Removing it restores
the hardcode, which drops the reference corpus to 17/40 card examples and 69/124
text. That does not remove feature 7; it DEGRADES feature 1 to 43% of its card
material. An arm testing "no cutaway filter" is an arm testing "reference
examples at 43% strength", and its result would be attributed to the wrong member.

**5 — card_hero REQUIRED. EXPECTED UNMEASURABLE.** It exists because the agent
invented prop names and three rounds built zero cards. Removing it is expected to
return cards to zero, which by my own standing registration is UNMEASURABLE, NOT
NULL. I am registering that expectation now so that if it happens it is a
confirmed prediction rather than a post-hoc excuse — and so that if cards DO
build without it, that is a real and surprising result about which mechanism
actually fixed them.

**So the cleanly ablatable members are 3 and 4.** Two arms, not five.

## The design

    arms        both_on  ·  no_card_derivation  ·  no_card_text_sentence
    cohort      car_short, screen_recording, car_mid   (the clean cohort only)
    reporting   THREE FIXTURES SEPARATELY. Never pooled: screen_recording is 36
                of the 44 beats and any pooled figure is one fixture wearing
                three.
    size        3 arms x 3 fixtures = 9 runs, ~$0.36 at round 49's rate
    switches    the same removal parameter, applied in-container, with each
                run's own PREFIX-MATERIAL-style row read from the LEDGER. A row
                that does not say REMOVED for the thing it was asked to remove
                voids that arm.

Members 5, 6 and 7 get NO arm. If the effect is not in 1, 2, 3 or 4, the honest
report is that **no single member carries it and the bundle is the unit** — see
below.

## The decision rule, stated before the numbers

n=1 per cell and **no estimate of run-to-run variance exists**. Round 48's
`both_on` and round 49's `both_on` ran on DIFFERENT trees (fingerprints
8c74fffe2bb17f2a -> 15ccf9dbe7cc6290 -> 91f4d58c3c1c0e51), so their difference
conflates tree change with noise and does not bound it. I will make no
significance claim.

**A member is implicated only if removing it reduces per-beat placement rate on
ALL THREE fixtures.** Directional consistency across three independent contents
is a criterion n=3 can actually support; a per-fixture threshold is not, and any
threshold I picked now would be fitted to nothing.

**A member is exonerated only if removing it leaves all three within the noise
we cannot measure** — which means exoneration is WEAK by construction and I will
say so rather than reporting "member X does not matter".

## What "no member carries it" would mean, registered as an acceptable answer

Individual removal effects need not sum to the bundle effect. If no single
removal reduces the rate on all three fixtures, the answer is **the bundle is
the unit** — the members interact, and the doubling is not attributable to a
member by removal. That is a legitimate scientific result and I am registering
it now as reportable rather than as a failed round, so it cannot later be
dressed up by attributing the effect to whichever member happened to move most.

The follow-up in that case is NOT more removal arms. It is a knock-IN design
against a bare control, which measures standalone effect rather than marginal
contribution — a different and more expensive question, to be scoped separately.

## What would invalidate this design

- If round 49's arms do not carry a REMOVED row from the ledger, 49 is
  apparatus-only and 50 has nothing to build on.
- If any of 3 or 4 turns out to be entangled with 1 the way 7 is, its arm is
  measuring degraded examples and must be withdrawn rather than reported.
- If the clean cohort stops being clean — any of the three fixtures showing
  rejections in the control — that fixture leaves the cohort and the round
  reports on what remains, with the denominator stated.
