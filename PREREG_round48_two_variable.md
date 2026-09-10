# Round 48 is TWO-VARIABLE — registered before it runs

Amends 83d85a4 and the ce710e0 freeze. No result seen.

## What 48 carries

    round 47 (control)
      + my six commits + cffc983     the prefix material, the card derivation,
                                     the card/text sentence, card_hero REQUIRED,
                                     the acceptance-gate fix
      + ONE change of Builder-1's    beat_verdict gains cutaway_from_s,
                                     zoom_arc and text_content

Zac ruled the second in rather than holding it for 49: a guaranteed-rejection
repair path makes the result harder to read, not easier, and my bundle is partly
aimed at rejection loops. **48 losing single-variable purity is the cheaper
cost**, and I argued for the same thing on the same grounds — a confound that is
constant across arms is survivable; one that SCALES WITH THE TREATMENT is not.

## Builder-1's asymmetry is right, with one correction I owe them

Their claim: the change can only REMOVE rejections that were structurally
impossible to satisfy; it cannot add a placement the agent did not rule.

True of the enforcement. **Not quite true of the schema.** Adding three fields to
`beat_verdict` changes the tool schema, which is in the cached prefix, which is
what the agent reads. A model that can now SEE `cutaway_from_s` on the repair
path may rule differently — not because a rejection was removed, but because the
capability became visible. That is the same mechanism as their own cutaway
finding: a family offered as a bare enum value ruled zero until something
explained it.

So their change is *mostly* subtractive and not *purely* so, and I am registering
it as a real alternative explanation rather than a technicality.

## How I will read it

**Null — placement does not move.** My null is STRONGER than the one I
registered, and this is the honest half of the trade: ~3,275 tokens of prefix
bought nothing *even after the doomed repair path was repaired*. The rounds 12–13
finding generalises from cut to placement, prefix material is not the mechanism,
and the next idea has to be structural.

**Positive — placement moves.** Not cleanly mine. Two bundle-level candidates
now, and it was already un-attributable to a member. The follow-up is unchanged:
one removal at a time, which the switches (7ed475e, default ON, nothing
disabled) make three env vars rather than nine code changes.

**Cards still not building is UNMEASURABLE, not null.** Unchanged from 83d85a4
and it now has two live causes on record — the bare-string treatment of round 46
and the orphaned gate of round 47, both fixed, neither yet observed fixed.

## What I am taking on trust, and what would invalidate it

Builder-1 states the `build_zoom` sub-timers are pure instrumentation — they
attribute time inside a stage and touch no decision, schema or prompt — and that
they will say so if that stops being true. I am taking that at their word, which
is a thing worth writing down rather than assuming: **if any sub-timer work
touches a decision path, 48 is unusable for this test** and the comparison
restarts at 49.

## On both of us writing the per-tool check

We are deliberately duplicating. Normally that is the reel-port mistake — twice
now we have both reached for the same fix. Here the failure mode is *a check
looking in one place*, so two checks that disagree is the signal, and one owner
is the risk. Mine landed at 44309f8, per-tool and line-bounded; theirs is
independent. If they agree the invariant holds; if they differ, one of us scoped
it wrong again and that is worth more than the duplicated hour.

## What I will report, per fixture, denominators stated

MG CATALOGUE distinct types · card-vs-text on figure beats including how many
carry BOTH · placements per family per beat as a RATE (subdivision and cutaway
both moved the denominator) · the three edit-quality measures · and the PREFIX
MATERIAL line, which prints in both states so 47's absence is a fact rather than
a missing feature.
