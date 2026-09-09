# Pre-registration — does material in the prefix change placement?

Written **before the round runs**. No result seen.

Zac's framing, which is the whole point: *if placement doesn't move, the rounds
12–13 evidence is the explanation and pushing more material into the prefix stops
being the answer. If it does move, that's the mechanism proven.*

## The round is NOT one-variable, and I have to say so

I registered round 47 as a clean test of the card-and-text sentence (ce710e0),
with an escape clause: *if something breaks first, the honest move is to fix it
AND say the round is no longer one-variable.* Four agent-facing changes now land
together:

    3083bc8   reference examples in the beats brief      ~989 tok
    0bf8d65   the four judgement documents in the prefix ~2,286 tok
    f7b5808   "card and text are not alternatives"
    ff9311f   card_hero says REQUIRED
    (+ whatever Builder-1 lands from cutaway and vision)

**The one-variable claim is dead.** Saying so is the clause, not an excuse.

## I tried to build a discriminator and it does not exist

The reference examples introduce the corpus's `purpose` vocabulary — hook,
claim, turn, evidence, payoff, breath. If the agent started describing beats in
those terms, that would fingerprint the examples specifically.

**Measured before registering it: it cannot work.** `hook`, `claim`, `turn`,
`payoff` and `evidence` were ALREADY in the prompt before either change, and
`breath` — the one word that was new — appears in the judgement documents too.
So the vocabulary cannot separate examples from documents from prior prompt.

I could find no fingerprint that attributes a positive result to one of the four.
Registering that now, rather than inventing an attribution afterwards.

## So the result is asymmetric, and that asymmetry is the registration

**A NULL RESULT IS ATTRIBUTABLE. A POSITIVE ONE IS NOT.**

    nothing moves    All four failed. ~3,275 tokens of prefix bought no change
                     in placement, and the rounds 12–13 finding generalises from
                     the cut to placement. Pushing material into the prefix stops
                     being the answer, and the next idea has to be structural —
                     the corpus as the decision surface, which is blocked on
                     cutaway, or fine-tuning, which is unavailable.
    something moves  The BUNDLE works. Which of the four did it is unknown and I
                     will not guess. The follow-up is one removal at a time, not
                     a story about which one it probably was.

## What I will measure, with denominators

Per fixture, motion excluded from pooled numbers by its own UNMEASURED floor.

1. **MG CATALOGUE distinct types.** Open since round 37. Needs cards to build at
   all — round 46 built zero to a bare-string treatment, so this may be
   unmeasurable for a fifth round for a fifth distinct reason.
2. **Card-vs-text on figure beats.** The sentence's target. r42 carded three
   figure beats, r45 captioned the same three. Report the treatment list per
   beat, and the count of beats carrying BOTH.
3. **Placements per family per beat**, against round 46's `[sfx=1 text=4 zoom=1]`
   on talking_head — noting the beat count changed under subdivision, so the rate
   is the comparable number and the count is not.
4. **The three edit-quality measures** — cut intrusions, card alignment,
   collisions — which are observational and change no ruling.

## What would make me say the prefix material FAILED

Placement distribution within noise of round 46 on every fixture that ran both
rounds, with cards building. **Cards not building is not a null result** — it is
an unmeasurable one, and I will report it that way rather than count it as
evidence against the material.

## What I will not do

Attribute a positive result to the examples because I built them. Four things
landed; the honest report names four. If it moves and Zac wants to know which,
the answer is a removal experiment, not a narrative.
