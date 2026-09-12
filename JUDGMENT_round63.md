# Round 63 — judgment

Round 63 is the newest round on disk (`/tmp/fixtures/round63`); there is no
round 64 yet. Five fixtures, all completed.

**Read this first: the tree that ran round 63 predates the card wiring.** So the
two counters Zac named are answers about the ROUND, not about the wiring.

## The two counters he asked for

| fixture | `card_conditions_named` | `card_props_seen` |
|---|---|---|
| car_mid | **KEY ABSENT** | **KEY ABSENT** |
| car_short | **KEY ABSENT** | **KEY ABSENT** |
| motion | **KEY ABSENT** | **KEY ABSENT** |
| screen_recording | **KEY ABSENT** | **KEY ABSENT** |
| talking_head | **KEY ABSENT** | 3 — all `from: "hero/label shorthand"` |

**ABSENT, not null and not zero.** My first read of these printed `None` for
both, because `dict.get()` returns `None` for a key that was never written and
for a key written as null, and those are different facts: the first says this
tree had no instrumentation, the second would say the instrumentation ran and
found nothing. Only the first is true here. This is the absent-as-zero family
inside my own reader, and it is the third time in one session (see below).

So: **15 reachable components remain unobserved.** `card_props_seen` fired only
where cards were actually placed, and 3 of 3 came from the `hero/label`
shorthand — **0 from the 25-type prop table**, which is still never exercised.
The number that would say whether 15 components got reached does not exist yet
and the next round is the first that can produce it.

## The registered prediction: CONFIRMED, on the fixture it was about

> round 63's single zoom ruled `build` (the mask position) on a fixture with no
> splice — the round-46 pattern

`talking_head`: exactly one zoom, `zoom_arc = "build"`, on beat 3
(`purpose: "turn"`), `keep_spans = 1` — **no splice**. Confirmed.

Stated precisely, because "the single zoom" was true of that fixture and not of
the round: the round executed **6 zoom rulings across 3 fixtures**.

| executed arc | count |
|---|---|
| hook | 2 |
| payoff | 1 |
| close | 1 |
| **build** | **1** |
| **breather** | **0** |

`car_mid` and `screen_recording` ruled zero zooms — and `car_mid` is the only
fixture in the round with a real splice (5 keep spans). The two unguided arc
values account for 1 of 6; `breather` has still never been ruled.

## MEASURED: `cost_usd`'s first reading on a real round — 2.0x the cost law

All five MEASURED, container and model both attributed.

| fixture | total | container | model | container share | source s |
|---|---|---|---|---|---|
| car_mid | $0.189 | $0.077 | $0.112 | 41% | 13.8 |
| car_short | $0.146 | $0.112 | $0.034 | 77% | 10.0 |
| motion | $0.165 | $0.116 | $0.049 | 70% | 28.0 |
| screen_recording | $0.314 | $0.209 | $0.105 | 67% | 90.5 |
| talking_head | $0.166 | $0.104 | $0.062 | 63% | 20.4 |
| **round** | **$0.981** | **$0.618** | **$0.363** | **63%** | |

**Mean $0.196/job = 2.0x the $0.10 law, and every fixture is over it** — the
cheapest is 1.5x. **Container time is 63% of the bill, not the model.** At
Haiku's cache rate the prefix is nearly free, so the lever is wall clock, and
this now says so in dollars rather than by inference.

Caveat on the population: five fixtures, not real traffic, and `source_duration`
runs 10–90s where production p50 is ~19s. Cut by fixture, not blended, for
exactly that reason.

## A second ruling pass that is ruled, ledgered, and discarded

`motion` has 12 `beat_verdicts` for 10 beats — beats 0 and 9 ruled TWICE.
`screen_recording` has the same shape (2 duplicates over 38 beats).

I hypothesised a field-level merge where a later ruling wins per field and null
does not clobber. **REFUTED by beat 9:** ruling 2 said `treatment: ["sfx"]`,
ruling 1 said `["none"]`, and the executed verdict is `["none"]` — ruling 1 won
whole. Beat 0 likewise kept ruling 1's `zoom_arc: "hook"` over ruling 2's null.

**The second pass is discarded wholesale.** It costs tokens and wall clock, it
disagreed with the first on beat 9, and nothing downstream can see that it
disagreed. `execute_plan_calls = 2` on three of five fixtures, with
`refused_second_execute = 1` on each — so the guard is catching the second
EXECUTE and nothing is catching the second RULING.

## Three reader failures of my own, caught before any of this reached Zac

1. **A filter on a field that does not exist.** I filtered verdicts on
   `v.get("zoom")`. There is no `zoom` field — zoom is ruled by `"zoom"` in
   `treatment`. The reader printed `zoom: NONE` for all five fixtures: a clean,
   tidy, wrong zero that would have said round 63 placed no zooms at all. Caught
   only because an earlier sloppier reader disagreed with it. The authoritative
   reader now ASSERTS the key exists, so an absent field raises instead of
   reading as empty.
2. **Absent read as null** (the counters above).
3. **A hypothesis stated before it was tested** (the field-level merge), which
   the data then refuted.

Two readers disagreeing is what caught the first one. That is the fourth
reader-defect-before-product-claim of the week, and the rule that keeps earning
itself: **a clean zero is guilty until proven innocent**, and my own readers are
not exempt.
