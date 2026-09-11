# Joining on PURPOSE instead of duration — scoped, with the measurement first

Zac: the agent names a purpose per beat from the corpus's seven-value
vocabulary, and retrieval joins on purpose rather than duration. Duration is not
a craft signal; a beat is a hook or a claim or a payoff, and that is what decides
what belongs on it.

## MEASURED FIRST — and it corrects something I have been saying

I have described the current retrieval as "k=3 matched beats injected per beat".
**It is not per-beat.** Measured on the shipped `_reference_block`:

    7 beats @2.5s      1132 chars   sha e0237dcb69
    36 beats @2.5s     1132 chars   sha e0237dcb69     <-- BYTE-IDENTICAL
    7 beats @0.8s      1100 chars   sha f8276cc784
    7 beats @6.0s      1152 chars   sha 48b984d71e

**A 36-beat fixture and a 7-beat fixture get exactly the same block.** The
per-beat loop dedupes on `read[:40]`, and with 39 beats in the index and k=3
nearest-by-duration, the same handful always wins. The block varies with the
fixture's DURATION PROFILE and with nothing else — not beat count, not content,
not what the beats are about.

So this is not a choice between per-beat retrieval and a fixed block. **It is
already a fixed block, selected by the weakest available key.** The question is
only which key organises it.

## THE ORDERING PROBLEM, and why purpose-indexing dissolves it

Retrieval runs when the BRIEF is built, before the agent has ruled anything. Our
beats carry no purpose and the agent has not named one yet — which is exactly
why the shipped code matches on duration and says so in its own comment.

A naive purpose join is therefore impossible: the join key does not exist at the
moment the block is written. Three ways out, and only one is cheap:

  A  TWO PASS — the agent names purposes, then retrieval joins, then it rules.
     Costs a turn on every run and invalidates the cached prefix between them.
  B  DERIVE a provisional purpose mechanically (position, duration, has_number,
     shot change) and let the agent override. Derived rather than invented, and
     it is the ZOOM_ARC_HOMES move — but position-and-duration IS the weak key
     wearing a craft word, and a wrong provisional purpose is worse than none
     because it looks authoritative.
  C  INDEX THE BLOCK BY PURPOSE and show all seven. The block does not need OUR
     purpose at all — it shows what a hook looks like, what a payoff looks like,
     and the agent names its beat's purpose while ruling, with the exemplars in
     front of it.

**C is the one to build.** It removes the ordering problem rather than paying for
it, and it is the mechanism Zac has been describing: the examples decide, not a
prompt describing them.

## COST, priced before building

    current  duration-selected block      1132 chars   ~283 tokens
    proposed purpose-indexed, 2 each      3614 chars   ~903 tokens
    delta                                 +2482 chars  ~+620 tokens

~620 extra tokens on a prefix that already carries ~3,275 of material measured
at about half a cent across five fixtures — so roughly +19% of that, on the
order of a tenth of a cent per run. It is written once and read every turn.

Corpus per purpose: hook 9, evidence 7, claim 6, turn 5, payoff 5, close 4,
breath 3. Two exemplars each is 14 of 39 beats; three each would be 21 and about
1350 tokens. **Start at two** and let the round say whether the third earns its
place — an exemplar count is a knob, and knobs get tuned by evidence.

## THE BUILD

1. `beat_verdict` and `rule_all_beats` gain `purpose`, an enum of the seven.
   REQUIRED, because an optional field on a ruling surface is a field that does
   not get used — that is the cutaway finding and the card_hero finding.
2. `_reference_block` becomes purpose-indexed: seven sections, each naming the
   purpose, its corpus count, and two exemplars with `treat`, `card_text` and
   the editor's `read`.
3. The purpose reaches the ledger per beat, so the placement judgment sheet can
   finally join OUR beat to a reference beat OF THE SAME PURPOSE rather than
   reporting the reference purpose as information.
4. `reference_examples_for(purpose, ...)` already takes purpose as its first
   argument and already prefers same-purpose beats. **It was built for this and
   is currently called with None.** Nothing new is needed there.

## WHAT WOULD MAKE THIS WRONG

- If the seven values do not fit real beats, the agent will pick one anyway and
  the join will be confident and meaningless. The check is the DISTRIBUTION: if
  a round rules 90% of beats one purpose, the vocabulary is not discriminating
  and the join is decoration.
- If purpose becomes a TARGET — "you have too few payoffs" — it is the density
  rubric again. Purpose names what a moment IS; it must never say what a beat
  should become.
- An agent that names purpose from the exemplars rather than from the beat is
  matching on style, not reading its own footage. Worth watching in the whys.
