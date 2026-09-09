# Falsifier — calibrating the three edit-quality proxies on round 44

**Registered before round 44 exists.** No distribution has been read, no
threshold proposed. Same discipline as the localised effect measure and
Builder-1's fourth zoom population.

## The three, and they are NOT the same kind of measurement

This is the part I want on the record before the numbers, because it is the
thing I would otherwise blur afterwards:

    cut_word_intrusions    a CONTINUOUS distribution with NO ground truth
    placement_collisions   a CONTINUOUS distribution WITH constructible truth
    card_beat_alignment    two BOOLEANS — nothing to calibrate, a population to find

Treating all three as "pick a bar from the distribution" is exactly how the
absolute geometry bar, the scale-fit bar and the 3.0 effect bar were set.

---

## 1. cut_word_intrusions — I may not be able to threshold this at all

**What I will report:** every intrusion's `intrusion_ms`, the full distribution,
and the count against total cuts. Per fixture and pooled.

**The one number that is not invented:** a cut lands on a frame boundary, so at
30fps it can sit up to 16.7ms from a word edge for reasons that are quantisation,
not editing. Anything at or below that is arithmetic, not a defect.

**Why a bar may be unreachable.** Above the quantisation floor there is no
measurable ground truth in a round. Whether a 90ms intrusion is audible is a
question about hearing, and I have no instrument for it — the honest answer is
Zac's ear on the finished audio, not a percentile of my own distribution.

**PRE-REGISTERED: if the distribution is continuous with no gap above the
quantisation floor, I will NOT propose a threshold.** I will report the
distribution and say the proxy is measured-only pending a listening judgement. A
bar chosen from a smooth distribution is a bar chosen from nothing, and I would
rather hand over a histogram than a number I cannot defend.

Only a clear bimodal separation — a cluster at quantisation and a distinct
cluster well above it — justifies a bar, and I state that before seeing it.

---

## 2. placement_collisions — the one I can construct truth for

**What I will report:** every collision's `overlap_px` and
`overlap_frac_of_smaller`, and the non-colliding pairs as the negative
population.

**Constructible ground truth, the way the effect measure had arms.** I can render
two placements that genuinely overlap and two that merely abut, and measure both
— so this proxy CAN have a validated separation rather than a percentile.

**Ship criteria, all required:**
1. A constructed swallowed-overlay and a constructed abutting pair separate on
   `overlap_frac_of_smaller`.
2. The window between them is wide enough that a bar carries **>= 2x** the
   fraction on either side — the proportional form of the 2.0 dB standard I
   registered for the zoom bar and honoured for the effect measure.
3. **One bar across BOTH corpora**, which is the criterion three previous bars
   failed.
4. Round 44's real collisions fall on the side the frames say they do. If I have
   to look at a frame and disagree with the number, the number loses.

---

## 3. card_beat_alignment — nothing to calibrate, everything to populate

`on_beat` and `grounded` are booleans. There is no threshold.

**The real risk is a check that cannot fail.** Round 39's four cards were all
grounded and all on-beat; if round 44 is the same, the check has never been shown
to fire on anything and is a green with no evidence behind it.

**PRE-REGISTERED: if round 44 produces 100% on_beat and 100% grounded, I will
report the check as UNEXERCISED, not as passing.** The remedy is a RED proof
against a constructed misaligned card — not a claim that the pipeline is correct
because a check that has never fired did not fire.

`grounded` is None for a hero with no digits. **None is not a pass.** If the
None rate is high, the check is mostly not applicable and I will say what
fraction it actually covered.

---

## Confounds that would make round 44 unreadable, named now

- **Truncated output.** Three of five in round 43. Collisions and cuts measured
  on a video that ends early are measured on a different video.
- **Wrong resolution.** 540x960 and 720x1272 in round 43. A collision fraction
  calibrated on a half-size frame is calibrated against a frame size that is
  itself a defect.
- **motion is VFR** — 59.94 declared, 35.94 actual, and the output rate follows
  the source. A cut-intrusion floor is a function of frame duration, so 30fps and
  59.94fps fixtures have DIFFERENT quantisation floors: 16.7ms and 8.3ms. I will
  compute the floor per fixture from its actual rate, not apply one constant.

**If any of the three is still present in round 44, that fixture is excluded from
calibration and named as excluded** — not silently pooled. Rule 5: state the
window and why it is clean, before reporting a rate.

## What I will not do

Propose a threshold in the same report that first shows its distribution. The
distributions go to Zac first. A bar comes after, in a separate pass, with the
separation shown — or does not come at all, which for cut_word_intrusions is a
live possibility I am naming in advance rather than discovering when it is
convenient.

---

# RE-READ before round 46 — the denominator moves, the criteria hold

Builder-1's `subdivide_beats` splits any beat over ~3s at the strongest REAL
seam, taking talking_head from 4 beats to 8-10. Every family gets more ruling
opportunities at once, so my three distributions land on a **different beat
population** than the one this file registered against. Re-read as instructed.

## What does NOT change

Nothing in the criteria. All three measures are per-PLACEMENT, not per-beat:

    cut_word_intrusions    per cut boundary, against the words
    card_beat_alignment    per card, against its own beat
    placement_collisions   per pair of painted boxes

More beats changes how MANY placements exist; it does not change what any of
them is measured against. A cut still lands inside a word or it does not.

## What DOES change, and it is the reading rather than the rule

1. **The cut denominator grows, which is the point.** Round 45 gave 0 of 8
   boundaries across three fixtures — four cuts. That is not evidence of
   anything, and I said so. A doubled beat count is the first chance this
   measure has to be exercised at all.

2. **Card counts are no longer comparable across rounds.** 7 card beats across 4
   rounds, all on talking_head, all quoting a figure. If round 46 shows more
   cards, the causes are now THREE and this file must not let me pick one:
   subdivide_beats (more beats), the derivation (b13730c), and the
   card-and-text sentence (f7b5808). All three landed together.
   **PRE-REGISTERED: I will not attribute a change in card count to any one of
   them.** The only clean read available is per-beat RATE — cards per card-worthy
   beat — and even that confounds the sentence with the split.

3. **Collisions get more likely by construction.** More placements in the same
   frame means more chances for two painted boxes to coexist. A rise in
   collisions is therefore NOT evidence of worse layout until it is normalised
   by the number of coexisting placements, and I will report the pair count
   alongside.

## The one criterion that needed changing, and why it is not a widening

Criterion 2 for collisions — "a bar carrying >= 2x the fraction either side" —
was already retired in fbef19c: the metric is continuous by construction, so a
constructed separation is meaningless. That correction stands and is unrelated to
the denominator.

Nothing here loosens a bar. The registered outcomes are unchanged: no threshold
from a smooth distribution, UNEXERCISED rather than passing, motion excluded by
its own UNMEASURED floor.

---

# ROUND 47 IS A ONE-VARIABLE EXPERIMENT — a constraint on my own work

Round 46 = Builder-1's beat subdivision + my card derivation (b13730c). The
card-and-text sentence (f7b5808) landed after that freeze, so round 47 adds
exactly one thing.

**That only holds if I add nothing else card-affecting before round 47
collects.** The constraint is on me, and it is easy to break by accident: any
prompt edit, any schema wording, any change to derive_card_type or
derive_card_props lands in the same round and the sentence stops being
separable. I have already registered once for three causes when there were two;
the way to not do that again is to stop adding causes.

## Frozen until round 47 collects

    the treatment description        no edits
    card_hero / card_label wording   no edits
    derive_card_type                 no edits
    derive_card_props                no edits
    the card branch in execute_plan  no edits

ff9311f (card_hero says REQUIRED) is already in and is the last one. If something
in that list turns out to be broken before round 47, the honest move is to fix it
AND say the round is no longer one-variable — not to fix it quietly and read the
result as if it were.

## What is NOT frozen

The three edit-quality measures, because they are per-placement and observational
— they change no ruling and no render. Anything outside the card family.

## What round 47 answers, and only this

Whether telling the agent that card and text are not alternatives changes the
card-vs-text behaviour. Not whether cards are good, not whether the derivation
picked well — one sentence, one behaviour, one round.
