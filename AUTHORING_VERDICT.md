# Does component authoring earn its place? — the answer, with the evidence

Zac's ruling of 2026-09-05 asked whether the authoring path earns its keep.
Nobody answered. Asked again 2026-09-11: *either the catalogue genuinely never
fails, in which case authoring is dead weight — or the trigger cannot fire, and
it is the inert-wire class.*

**It is the first, and the trigger IS reachable. But the one condition that
reaches it is a copy fault wearing a catalogue gap's name.**

## What the surface is

| piece | tokens of cached prefix |
|---|---|
| `author_component` tool schema | ~270 |
| `render_components` tool schema | ~219 |
| `WHEN THE CATALOGUE CANNOT SERVE A BEAT` prompt block | ~431 |
| **total** | **~920** |

## Has it ever fired? No — and the keys are ABSENT, not zero

Over 30 ledgers, rounds 51-60:

| key | state |
|---|---|
| `no_catalogue_component` | **ABSENT from every ledger** |
| `catalogue_gap_beats` | **ABSENT from every ledger** |
| `author_component` calls | never called |
| `search_skills` calls | **0 of 30** |

## Why it has never fired

`derive_card_type(hero, ...)` returns `None` — the trigger — in three cases,
and only one is reachable:

| case | reachable? |
|---|---|
| empty hero | **NO.** `if not hero: continue` runs BEFORE the call, and the half-ruling stripper removes `card` from a treatment whose `card_hero` is blank |
| hero carries a figure | never None — always StatCard |
| hero ≤ 5 words | never None — always PullQuote |
| **hero > 5 words, no figure** | **YES. The only path.** |

And the observed population is nowhere near it. **23 card heroes ever ruled, 5
distinct, and the longest is ONE WORD**: `10` ×14, `5` ×6, `void`,
`Connectors`, `five`. The trigger needs six. Nothing in 30 runs came within
five words of it.

## And the remedy was wrong even if it fired

A hero of six words is the agent writing a sentence into a card field. The
refusal's own text says so — *"a card is a few words at reading size, not a
sentence"* — and then it offered `author_component`: a render round-trip and a
bespoke TSX component, to solve a problem that needs **three fewer words**.

That is not a catalogue gap. The catalogue has two components covering every
shape a card can take — a figure (StatCard) and a phrase (PullQuote) — and no
observed hero has ever fallen outside them.

**Fixed 2026-09-11:** the two refusals are separated. `hero_too_long` says
shorten the phrase; `no_catalogue_component` keeps the authoring remedy and is
now, by construction, unreachable. `catalogue_gap_beats` records which kind, so
a copy fault can never be counted as a catalogue failure.

## The one argument that is NOT available: cost

920 tokens read once per turn, ~10 turns per run, at Haiku's cache-read rate:

    920 x 10 = 9,200 cache_read tokens/run  ->  $0.00092/run

Against an observed $0.10-0.25 per run that is **0.6% of cost**. Deleting the
authoring surface saves about a tenth of a cent a job. **Anyone arguing for
deletion on cost grounds is arguing from an impression, and the number refutes
it.**

## What would change the answer

Authoring earns its place the moment a card hero exists that is neither a
figure nor a phrase of five words or fewer — a ranked set, an ordered list, a
comparison. None has been ruled in 30 runs. Two things would make one likely,
and both are already known gaps:

1. **`search_skills` has fired 0 of 30.** An agent authoring TSX without ever
   reading the Remotion API is the exact case K4 exists to forbid, so the
   authoring path's own prerequisite is unused. Authoring cannot be judged
   working until that is not true.
2. **The 25-type prop table has still never been exercised** — every card ever
   built came through the `card_hero` shorthand. A catalogue whose breadth has
   never been reached cannot be shown to have a gap.

**Recommendation, for Zac's ruling:** keep the surface. It costs a tenth of a
cent, the trigger is now honest about which fault it found, and the reason it
has never fired is that the agent writes one-word heroes — which is the
catalogue working, not the catalogue being unnecessary. Delete it only if the
one-word population holds across the next ten rounds AND `search_skills` stays
at zero, because at that point the agent is demonstrably not reaching for
breadth of any kind and authoring is the least of what is unused.
