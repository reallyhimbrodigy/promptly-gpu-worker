# Cards ask the agent to do the one thing the zoom design refuses to ask

**Round 42 gave the incumbency question a control group, and it is not the one
anybody set up.** Same round, same cached prefix, same agent, same fixture:

    zoom    DepthPull@hook, SnapReframe@build, FocusWindow@mid_peak
            3 distinct types, 6 placements, 6 moved, 0 inert
    card    StatCard x3
            1 distinct of 29

So "the agent can only pick one thing per family" is refuted. Whatever holds
cards to StatCard is specific to cards.

## The difference is WHO CHOOSES, and it is deliberate on the zoom side

The agent **never names a zoom type**. It names what the beat IS in the arc —
`zoom_arc: hook|build|mid_peak|payoff|breather|close` — and the harness looks the
move up in `ZOOM_ARC_HOMES` plus the vibe. The schema says so in as many words:

    ARC POSITION IS JUDGEMENT; THE MOVE IS A LOOKUP. Which beat is the payoff
    cannot be derived from timing — but once you say so, WHICH of the seven
    zooms goes there is production's ZOOM_ARC_HOMES plus the vibe, and the
    harness does it. Naming the move yourself would let a snap land on a payoff.

Cards do the exact opposite. `card_type` is a 29-name enum and the agent picks
the component directly.

**So the zoom mix is not evidence that the agent selects well. It is evidence
that DERIVED selection produces a mix where DIRECT selection does not** — from
the same model, on the same prefix, in the same round.

## Why this outranks the two interventions already tried

Both previous attempts made components easier to CHOOSE:
  round 39   a claim line for all 29 in the cached prefix (visibility)
  round 41   the prop shape for 25 of them (usability)
Neither changed the count. Both left the agent doing the naming.

This is not a third attempt at the same thing. It changes who does the naming,
which is the variable the zoom side already controls and the card side never has.

## What it does NOT do

It does not resolve the prediction. On a corpus whose card beats all quote
figures, a correct derivation still yields StatCard every time — rightly. The
measurement still needs a card-worthy beat that does not quote a figure, which
Zac has now located: probably product shots and screen recordings, both missing
from v3.

What it does is replace "the agent is not choosing well" with a mechanism that
has a control group, and point at a change whose success does not depend on
persuading a model to browse a catalogue.

## The raw material already exists

`MG_CLAIM_INDEX` carries a one-line claim for all 29 components, added in
fe3a544 and never used for anything but the prompt:

    AnnotationArrow   Look at THIS thing on screen.
    ChatThread        This is the literal exchange — both sides.
    BarRace           Watch these values race — the biggest wins.
    DropBanner        Here's the framework, one point at a time.

Those read as beat kinds already. The zoom analogue would be a `card_moment`
vocabulary — a figure, a quote, an exchange, a list, a comparison, a device view
— ruled by the agent, with the component derived from it.

## Why I am filing this rather than building it

The STRUCTURE (derive, do not name) is an engineering call and the evidence above
supports it. The VOCABULARY — which beat kinds exist, and which component belongs
to each — is a taste call about what suits a moment, and this lane's rule is to
ask Zac for those rather than invent them. Inventing a mapping and shipping it
would also be a fourth intervention on a prediction I have said I will stop
intervening on until it can be measured.

Two questions for Zac:
1. Is `card_moment` the right shape — should the agent rule what the beat IS and
   let the harness pick the card, exactly as it already does for zoom?
2. If so, the beat-kind vocabulary and its component homes are yours to set. The
   29 claim lines are a starting draft, not an answer.

## Denominator

One round, one fixture, 3 card beats and 6 zoom placements. The zoom/card
contrast is within-round and within-prefix, which is what makes it worth
reporting at n=1; the incumbency count is not, and stays unresolved.
