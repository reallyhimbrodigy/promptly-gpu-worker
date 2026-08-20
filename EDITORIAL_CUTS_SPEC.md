# EDITORIAL CUTS — a capability spec

**Status: SPEC ONLY. Nothing built. Reported for a decision before any code.**

---

## 0a. AMENDMENT — the population bound (2026-08-20)

Measured over 179 usable transcripts / 159 distinct users:

```
WORDS   median  64   p75 136   p90 210   max 389
SECONDS median  27   p75  53   p90  88   max 175

>=150 words:  41 (22.9%)  latin 22  users 33
>=250 words:   9 ( 5.0%)  latin  5  users  5
```

**The median user video is 27 seconds and 64 words.** There is almost nothing to
cut for pace in 27 seconds. The references are ~45-55s. So:

> **Pace cutting is a TOP-QUARTILE capability. It does not improve the median
> video, and any result from the pace corpus is a result about the tail.**

This bound is not a reason to skip it — 23% of traffic is real, and the long
videos are where an unedited passthrough is most obviously not a product. It is
a reason never to quote a pace-cut rate against a denominator of all jobs.

## 0b. AMENDMENT — the disfluency pass WORKS; this builds on it, not over it

The premise that motivated this spec was that `cut_refinements` came back empty
on 159/159 plans. **Tested on its own textbook case and it FIRES** (build lane,
`c9ad1bbf`, 225 words of phrasal restarts):

```
225 words -> 167 kept (58 removals), 22 clips, 60.31s out of a 117s source
225 words -> 183 kept (42 removals), 25 clips, 67.07s
225 words -> 197 kept (28 removals), 28 clips, 72.70s
```

26% of words removed, output 48% shorter, 22 clips. Compare `cada6a1b`
(89 -> 89 kept, 2 clips, passthrough) — a CLEAN SCRIPTED READ with no disfluency,
where empty was the correct answer.

**So the empties were population, not breakage**: clean reads have no
disfluency, and the 0/160 I measured on live traffic were ROUTE plans
(moodreel/minimal/hype) that never run the standard editorial path at all.
`pace_cuts` is therefore a NEW capability on a WORKING foundation — not a repair,
and not a workaround for a pass that does not fire.

**Correction to §4 of this spec while it was still a draft:** the 25% cap does
NOT reject. Observed live: `component=cut_refinements action=over_cap_logpass
reason=total refinement removal exceeded 25% of kept words (49) — largest ranges
KEPT (log-and-pass)`. The cap already degrades gracefully by keeping the largest
ranges. The binary reject-and-keep applies to the CONTENT-WORD PREDICATE, not to
the cap. §4's ladder still applies to the predicate; the cap needs the amendment
below instead.

## 0c. AMENDMENT — `full_take_retake` is its own unit, with its own cap

Corpus source `0c71a22d` (301 words / 160s) delivers its ENTIRE script twice,
near verbatim. The correct edit removes ~48% of the words — one whole take.
**Every existing cap blocks that**, and they are right to for every other unit:
a pass that can delete half a video on a judgement call is the one irreversible
thing on this board.

So a full-take retake is a SEPARATE unit with a SEPARATE cap, and it is gated on
a mechanical precondition rather than the model's opinion:

```
unit: "full_take_retake"

PRECONDITION (mechanical, verified in code — the model cannot assert its way in):
  near-verbatim match between the removed span and a retained span:
    - normalized token sequence similarity >= 0.85 over the span
    - span length >= 40% of kept words (a real take, not a repeated sentence)
    - the retained twin must survive the cut IN FULL

CAP:  up to 60% of kept words, but ONLY for this unit and ONLY when the
      precondition holds. Every other unit stays inside the 25% union cap, and
      the union of all NON-retake units is still capped at 25%.

LEDGER: the divergence records BOTH spans — removed and retained — with their
        similarity score, so the decision is auditable without the source.
```

**Why mechanical and not taught.** "The speaker said the same thing twice" is
checkable from the transcript with no judgement; "this content is redundant" is
not. Tying the larger cap to a computable near-verbatim match means the only way
to unlock a 60% removal is to actually have a duplicate take. A model that
merely believes a passage is redundant gets the 25% cap like everything else.

---

## 0. What is actually missing

Not a bug. Three layers currently make an editorial cut **impossible**, and only
the first is an absence:

1. **Not asked.** `=== YOUR CUT PASS (cut_refinements) ===` is reachable and
   prominent (11.5% into the assembled prompt, its own section, both premium
   arms — verified 2026-08-20). But its scope is explicit: *"This pass removes
   only the speaker's own STRUCTURAL REDUNDANCY — the restarts, retakes, and
   filler above. It does NOT tighten real speech."*
2. **Actively rejected if emitted.** The prompt states, and the pipeline
   enforces: *"Content words in a flowing sentence are never removable … a
   cut_refinement that is not filler, a verbatim restart, or bounded by real
   dead air (a sentence-final boundary with a ≥0.70s pause) is rejected and the
   words are kept."*
3. **The escape hatch is closed for unpunctuated languages.** The dead-air
   route in (2) requires a *sentence-final boundary*. On an ASR that emits no
   terminal punctuation there is no such boundary, so even that door is shut.
   (Partly addressed by check 413, but the boundary test remains.)

So `cut_refinements` returning empty on 159/159 plans is **correct behaviour for
the pass it is**. A disfluency cleaner finds no disfluency in a scripted read.

**The capability that does not exist: removing CONTENT the video does not need.**

---

## 1. What the model is asked

A **new, separate pass** — `pace_cuts`. Not a widening of `cut_refinements`.

**Why separate, and this is the load-bearing decision.** `cut_refinements` has
an enforced predicate (filler / verbatim restart / dead-air-bounded) that is
*correct for its job* and is the only reason a disfluency cut can be trusted
without a human. Widening that predicate to admit pace cuts destroys the
guarantee for both. Separate field, separate validator, separate ledger — but
the **same emit shape and the same application machinery** (see §3), because the
`_deterministic_reedit` lesson is *reuse, never parallel*.

The ask, in the model's terms:

> You have watched the footage. A lean edit does not keep everything the speaker
> said. Remove what the video does not need: a point made twice, a preamble
> before the real start, a tangent that does not return, an example the previous
> example already covered, a trailing repeat after the line has landed.
>
> This is NOT disfluency (that pass ran) and NOT silence (the mechanical pass
> ran). This is CONTENT. You are deciding what the video is about by deciding
> what it is not about.

**Explicitly taught as distinct from the two existing passes**, because the
model currently has no concept that a third kind of removal exists.

---

## 2. What it emits

Mirrors `_CutRefinement` so the merge path is identical:

```
pace_cuts: List[_PaceCut]        # REQUIRED in the decode schema (see below)

_PaceCut:
  start_word_index : int         # KEPT-space, inclusive
  end_word_index   : int         # KEPT-space, inclusive (single word: start==end)
  unit             : Literal[    # CLOSED ENUM — countable, like drop_reasons
                       "redundant_restatement",
                       "preamble",
                       "tangent",
                       "example_surplus",
                       "trailing_repeat"]
  reason           : str         # <=240 chars, names the SPECIFIC redundancy
  keeps_meaning    : bool        # the model's own assertion the utterance survives
```

**`pace_cuts` is REQUIRED in the schema sent to Vertex, optional on the pydantic
model** — the exact asymmetry shipped for `props` on 2026-08-19 and grammar-
verified against the real schema. Reason: this session hit the same ambiguity
three times (`props`, `preserved_silences`, `cut_refinements`) where an empty or
absent field could mean *declined* or *never engaged*, and Vertex drops empty
optionals so the two are indistinguishable. Required-to-decode forces the field
to exist; it does not force a cut.

Paired with:

```
pace_cuts_declined       : Optional[str]      # prose, verbatim, when none
pace_cuts_decline_class  : Optional[Literal[  # countable
                             "already_lean",
                             "every_line_load_bearing",
                             "too_short_to_cut",
                             "meaning_fragile"]]
```

Same shape as `scenes_declined` / `scenes_decline_class` (shipped this session).
**A refusal must be legible or it is indistinguishable from a broken pass** —
that is the single most expensive lesson of this campaign.

`keeps_meaning` is not decoration: it converts a silent bad cut into an
attributable one. A cut that ships with `keeps_meaning: true` and breaks the
sentence is a *prompt* defect with evidence, not a mystery.

---

## 3. What applies it

**Reuse the mechanical-cut path end to end. No second cut engine.**

1. **Project + union.** At the merge, project kept→src exactly as
   `_CutRefinement` does today and union into `remove_words`, so the existing
   normalization, anchor guards, and clip rebuild treat a pace cut *identically*
   to a mechanical cut. Nothing downstream learns a new concept.
2. **Re-anchor.** `_translate_post_cut_anchors_to_src(post_cut_plan, new_to_src)`
   already translates every component's word index across the cut. Components
   landing inside a removed span re-anchor via `_reanchor_entry_to_survivors`.
   This machinery exists and is gate-pinned ("RE-ANCHORING SURVIVES A WORD-SPACE
   MUTATION"); pace cuts must ride it, not bypass it.
3. **Revalidate.** After the union, the existing post-parse validation span
   re-runs: slot-parity tripwire, integrity gate, caption/word alignment. A pace
   cut that breaks parity fails here like any other cut.
4. **Ledger the removal.** `_ledger_requested("pace_cut", unit)` and
   `_ledger_dropped("pace_cut", unit, reason)` so requested-vs-applied is
   queryable per job, plus `_record_divergence("pace_cut", …)` so it reaches the
   S3 ledger and `read_divergence_rates.py` can report the rate on real traffic
   with a denominator, cut per user.

**Every removed span is ledgered with its `unit` and its verbatim text.** A
product that decides what a user's video is *not about* must be able to show its
work, per job, forever.

---

## 4. The negotiation floor

**Hard floors — never negotiable, enforced in code, not asked of the model:**

- **Protected indices**: hook / payoff / close / key_moments. Unchanged.
- **The 25% cap** on total removal, already enforced for `cut_refinements`,
  applies to the *union* of all removal sources — not per pass. Three passes
  each under 25% must not compose into half the video.
- **Utterance integrity**: the surviving text either side of a cut must be a
  complete utterance. A cut may not orphan a dependent clause or strand a
  pronoun whose referent it removed.
- **Component survival**: a cut may not strand a b-roll clip, motion graphic, or
  caption window with no anchor. If re-anchoring cannot place it, the cut is the
  thing that yields — not the component.

**The negotiation, when a cut violates a floor.** Today the behaviour is binary:
*rejected and the words are kept*. That is the same silent-drop shape that made
`empty_props` invisible. Instead, the **graceful ladder already shipped for
component placement** applies here, in order:

1. **Shrink** — take the largest sub-span of the requested cut that satisfies
   every floor. A three-sentence tangent whose last sentence carries the
   referent becomes a two-sentence cut.
2. **Drop, ledgered, with the reason and the verbatim text.**
3. **Never fail the edit.** K7: one bad cut never costs the video.

Rung 1 is the whole point — the interesting number when this runs is *how often
shrink saves a cut that rung 2 would have dropped*, which is exactly the metric
that made the component ladder worth shipping.

---

## 5. The bar — and an honest caveat about it

Measured from the references by `score_component.py`:

```
REF-1   21 cuts   24.0 cuts/min   mean_change 0.0864
REF-2    8 cuts   11.1 cuts/min   mean_change 0.0596
```

**The caveat, so this is never turned into a quota.** Those are *visible cuts in
the rendered video* — they include b-roll in/out and shot changes, not only
content removal. Pace cuts are **one contributor** to that number, not the whole
of it. Cutting to hit 24/min is how a good edit gets butchered.

So the bar is used two ways, both already implemented:

- **Floor (binary):** `edit contains cuts` — a render with zero is a
  passthrough. This is the check that caught the shipped-nothing render.
- **Band (plausibility):** `mean_change >= 0.6x` the lower reference. An edit
  landing inside the reference band is *plausible*, never *proven good*.

**Neither is a target the model is told.** The model is asked what the video does
not need; the scorecard reads what came out. A cut count in the prompt would
produce cuts for the count's sake.

---

## 6. How it gets verified before anyone believes it

1. **Grammar check first** — `pace_cuts` required-to-decode against the REAL
   `_post_cuts_response_schema()`, with the optional variant as control. The
   props precedent 400'd the whole editorial path once; this call is every job.
2. **Build-lane A/B** on sources with *known* redundancy — the corpus must be
   selected for content that can be cut, or the arm is vacuous in the direction
   this campaign has already been burned by twice.
3. **Per-source report**: requested vs applied per `unit`, which rung fired,
   the verbatim removed text, the decline prose where it declines, and the
   scorecard's `n_cuts` / `mean_change` before and after.
4. **The owner's eye on meaning.** No instrument in this repo can score whether
   an edit still means what the speaker meant. The spec does not pretend
   otherwise: meaning-preservation is a taste call on real pairs, and Rule 3
   applies — no pair reaches him that has not been proven to differ.

---

## 7. What this changes about the product

Today Promptly rearranges and decorates a video it never shortens. With this, it
decides what the video is *about*. That is a different product, and it is the
one the references are.

**It is also the one irreversible thing on the board.** A wrong graphic is
noise; a wrong cut removes something the user said and cannot get back from the
output. That asymmetry is why §4's floors are code-enforced rather than taught,
and why `keeps_meaning` is a required claim rather than an inference.
