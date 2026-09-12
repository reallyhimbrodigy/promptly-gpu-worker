# Scope — how open-vocabulary reference material reaches the agent

Asked by Zac 2026-09-11, before Builder-1's index lands. Three classes the
current wiring has no home for: **signature moves**, **per-beat craft notes**,
and **families the pipeline cannot build**. Where each lands, what it costs in
prefix, and what it displaces.

Every number below is MEASURED from this lane today, or named ABSENT.

---

## 0. What the prefix is made of right now — MEASURED

~13,399 tokens of tool schema, from this checkout:

| tool | ~tokens | |
|---|---:|---|
| `rule_all_beats` | 6,302 | the per-beat ruling surface |
| `beat_verdict` | 4,431 | the same thirteen fields, second copy |
| `set_spec` | 972 | **the only video-level call** |
| the other 11 tools | 1,694 | |

Inside `rule_all_beats`, by field:

| field | ~tokens |
|---|---:|
| `zoom_arc` | 1,920 |
| `treatment` | 1,721 |
| `card_condition` | 754 |
| `cut` | 613 |
| `card_props` | 400 |
| everything else | 671 |

Of that, the corpus craft I wired today is **3,026 tokens** — `ARC` 1,157,
`FAMILY` 1,395, `CUT` 474.

## 1. THE DISPLACEMENT BUDGET IS ALREADY ON THE TABLE, and it is large

**`beat_verdict` costs 4,431 tokens — a third of the prefix — and 89% of what it
produces is thrown away.**

Population: 24 runs across 8 rounds that called it, from the turn records.

| | |
|---|---:|
| `beat_verdict` calls | 47 |
| that re-ruled a beat `rule_all_beats` had already ruled | **42** |
| share discarded by first-wins | **89%** |

Read that carefully, because it changed meaning this week. Those 42 are
discarded *under today's rule*. Before `admit_verdict`, they were appended past
the dedup and could win the build's `{beat: v}` lookup — so historically they
were not discarded, they were **silently replacing complete rulings with
stubs**. Either way the surface is not doing the work its size implies.

It is not free to delete: 65% of runs call it, and it is how the agent repairs a
beat after `inspect_output`. But three options exist and Zac should pick one
before new material competes for room:

1. **Delete it.** Recovers 4,431 tokens — more than the entire corpus craft
   wired today — and removes the two-surface divergence class permanently. The
   repair path becomes `rule_all_beats` with one verdict, which admits through
   the same door anyway.
2. **Keep it, drop its prose.** The thirteen descriptions are duplicated
   verbatim from the plural tool. Replace them with one line each plus "the full
   rule is on `rule_all_beats`". Recovers perhaps 3,400 tokens and keeps the
   surface. Risk: an agent reading only this tool gets the thin version.
3. **Keep it as is** and fund new material from elsewhere.

**I have not done any of these** — deleting or thinning a tool surface is a
product decision, and I have already been stopped once this week for treating a
deliberate removal as a stale list.

## 2. Signature moves — they go on `set_spec`, and nowhere else fits

> "warm colour-wash whip-cut at every mode change, masking a hard cut with a
> flash, signalling a new section"

That is a claim about the WHOLE VIDEO: a device, its trigger condition, and its
narrative job. Three reasons it cannot live where the craft I wired today lives:

- **Per-beat fields cannot express recurrence.** `zoom_arc`'s description is
  read while ruling ONE beat. "At every mode change" is a statement about the
  set of beats, and a beat-local field has no way to say it.
- **It spans families.** Colour-wash + whip-cut + flash + section boundary is
  one device across transition, cut and timing. This is the `build` finding and
  the 66-sentence classifier failure again: **one sentence governing several
  families, and a taxonomy that assigns it to one owner produces a confident
  wrong answer.** A signature move is that shape by construction.
- **It is a PLAN-level decision.** Whether this video gets a signature device at
  all is decided once, before any beat is ruled.

`set_spec` is the only call with that scope, it runs first, and at 972 tokens it
is the smallest of the three large surfaces — it has the most headroom in both
senses.

**Shape:** a `signature_moves` block in `set_spec`'s description carrying
device → trigger → job, and a matching optional `signature` field on the spec so
the agent DECLARES the device it intends. Declaring it makes it checkable:
`spec_fidelity` already asks "did what was asked for land" — a declared
signature that never appears in the plan is the same question one level up, and
`reedit_delta` already knows which families moved.

**Cost:** ~60–90 tokens per move at the density of today's craft lines. Ten
moves ≈ 700 tokens, which roughly doubles `set_spec` and is ~5% of the prefix.
Affordable without displacing anything.

**Unknown until the index lands:** how many distinct signature moves the corpus
actually contains. If it is 10 the above holds; if it is 200 this becomes a
retrieval problem like §3 and must not go in prefix.

## 3. Per-beat craft notes — NOT prefix. This is the one that breaks the model.

> why something works, on the 40–65% of beats that have one

**Prefix is a fixed cost paid on every run; this material grows with the
corpus.** At 40–65% of beats, one reference video of 40 beats yields ~20 notes;
a hundred videos yield ~2,000. There is no version of that which belongs in a
tool description, and the failure mode is not "expensive" — it is that the
craft for THIS beat is buried in craft for two thousand others.

Two homes, and they are complementary:

**(a) The beat lines the agent already reads.** Every run already builds a
per-beat brief. A note attached to the beat it is about is retrieved by
construction, costs only what that run's beats need, and arrives at the moment
of the decision rather than 6,000 tokens earlier. This is where condition→action
material keyed to MOMENTS belongs, and it is the closest analogue to how the
per-beat `why` field already works.

**(b) `read_knowledge` — which exists, costs 72 tokens, and has been called ZERO
times in 30 runs.** A retrieval surface that is present and dead. Before
building a second one, that zero has to be diagnosed: it is either a signal (the
agent never needs it) or a broken wire (it cannot tell when it would help), and
**a counter that has never incremented looks identical in both cases**. The
honest sequence is: find out why it is zero, THEN decide whether per-beat notes
go behind it.

**Cost:** near-zero prefix by design. The cost moves to per-run input, which
scales with the video rather than the corpus — the right axis.

**What it displaces:** nothing, if it goes to the beat lines. This is the class
with the best cost profile and the largest volume, which is a happy accident
worth taking.

## 4. Families the pipeline cannot build — these must NOT reach the agent

> `reference_unbuildable()` ranked by evidence: "editors do X in 8 of 10 videos
> and this pipeline can't"

**This is a build list for Zac and it goes in a report, not in a prompt.** I am
confident about this because I made the mistake in the opposite direction four
hours ago and a gate caught me.

The evidence is already on this lane. `cutaway` is ruled and never built:

| round 63 | ruled | built |
|---|---:|---:|
| cutaway | 2 | **0** |

I read that as "the closed set is stale" and added `cutaway` to
`_TREATMENT_FAMILIES`. `smoke_five_families` refused it — cutaway was REMOVED
from this pipeline deliberately, and the ledgers I reasoned from PREDATE the
removal. **Teaching the agent a family with no builder does not produce the
edit; it produces ruled-not-built, a wasted turn, and a ledger that blames the
agent for the pipeline's gap.**

So: `reference_unbuildable()` output is a ranked capability report — family,
count of reference videos using it, share of beats, an example — ordered by how
many of Zac's own videos need it. It is the input to deciding what to BUILD. The
moment one of those families acquires a builder, it joins the enum and §2/§3
wiring picks it up automatically, because both are derived.

## 5. What the open vocabulary breaks in what I shipped today

`enum_craft()` keys every corpus sentence by **an enum value the schema offers**.
That is what made it derivable and drift-proof, and it is exactly the assumption
the new index breaks: **24 distinct treatment names in one video where six were
possible.**

Most of the new material will key to NOTHING under the current extractor, and —
this is the dangerous part — **it will do so silently**, because a value with no
sentences renders as "the catalogue states no rule for this value", which reads
like a corpus gap rather than an extractor miss. That is the heading-sweep
failure that already cost me a wrong count this week, one level up.

So the bridge is a **mapping step, and it must be three-state**:

```
open name  ->  MAPPED    to a family the pipeline builds   -> §2/§3 wiring
           ->  UNBUILDABLE  a real device, no builder       -> §4 report
           ->  UNMAPPED     could not classify              -> MUST BE COUNTED
```

The third arm is the one that keeps it honest. An unmapped remainder that is
silently dropped is how "159" became a number I could not reproduce. It gets a
count, a denominator and a sample — every run.

## 6. Summary — where each lands, and what it costs

| class | home | prefix cost | displaces |
|---|---|---:|---|
| signature moves | `set_spec` description + a declared `signature` field | ~700 for 10 | nothing |
| per-beat craft notes | the per-beat brief; `read_knowledge` only after its zero is diagnosed | ~0 | nothing |
| unbuildable families | a ranked report for Zac | **0 — must not reach the agent** | nothing |
| the mapping itself | code, not prompt | ~0 | nothing |

**Nothing here needs to displace anything** — and if it did, the 4,431-token
duplicated ruling surface at §1 is the first place to look, not the craft.

## 7. Open questions I cannot answer until the index arrives

1. How many distinct signature moves exist. Ten is a prefix block; two hundred
   is a retrieval problem.
2. How many of the 24 treatment names map onto the six the pipeline builds.
   That ratio decides whether §5's mapping is a footnote or the main event.
3. Whether per-beat notes are per-BEAT or per-MOMENT-TYPE. Reusable ones are
   condition→action and could join the closed craft; one-offs cannot.
4. Whether the 154 sentences I wired today survive the re-read, or whether the
   open-vocabulary index supersedes them. **If it supersedes them, the wiring is
   derived and follows automatically — that was the point of extracting rather
   than hand-copying.**
