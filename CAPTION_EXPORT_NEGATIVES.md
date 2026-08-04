# CAPTION TYPOGRAPHY DOES NOT EXPLAIN EXPORT — three hypotheses, three negatives

Captions reach ~8× more moments than any component, so this was the right place
to look. It is not the place to spend. Reporting the negatives because each one
would otherwise have cost a week.

## H1 — "the most-used style is the worst" → real, but does not survive grouping

| caption_style | n | share | export % | default fontSize | % of 1920 frame |
|---|---|---|---|---|---|
| CleanCut | 224 | 27.4% | **15.2%** | 100 | 5.2% |
| Gadzhi | 169 | 20.7% | 19.5% | 90 | 4.7% |
| Pulse | 107 | 13.1% | 19.6% | 80 | 4.2% |
| Cove | 99 | 12.1% | 17.2% | 76 | 4.0% |
| Prime | 64 | 7.8% | 20.3% | computed | — |
| none | 57 | 7.0% | 14.0% | — | — |
| Lumen | 55 | 6.7% | **27.3%** | **70** | **3.6%** |
| TwoTone | 30 | 3.7% | 23.3% | 110 (allCaps) | 5.7% |
| Quintessence | 10 | 1.2% | 20.0% | 160 | 8.3% |

CleanCut vs Lumen is z≈2.11 — marginal, and it is the comparison I went looking
for, which is exactly when a marginal result is least trustworthy.

**The safe-recipe confound is dead**: `CleanCut` is the mechanical fallback's
default (`handler.py:12762`), so the gap could have been "fell back" rather than
"looks worse". It is not — **0.0% of the 224 CleanCut jobs are safe recipes.**
All carry emphasis moments, SFX and keywords. It is a real editorial choice.

## H2 — "keyword-highlighting styles win" → NOT SUPPORTED

| group | n | export % |
|---|---|---|
| highlights keywords (Prime, Cove, Lumen, Pulse, Gadzhi) | 494 | 20.0% |
| ignores keywords (CleanCut, TwoTone, Quintessence, TypewriterReveal) | 267 | 16.1% |

**z = 1.33.** Not significant. This is the better-powered test and it kills H1:
the CleanCut gap does not generalise to the property that was supposed to
explain it.

Still true and still worth fixing on its own terms: **1,372 caption keywords
were computed and then discarded** across those 267 jobs. That is waste
regardless of whether it moves export.

## H3 — "captions are too small" → NOT SUPPORTED BY EXPORT

I watched twenty videos and wrote down "too small to read". The sizes above say
the opposite of what that predicts: **Lumen has the SMALLEST default (70px,
3.6% of frame height) and the HIGHEST export rate (27.3%).** CleanCut is nearly
the largest and nearly the worst. There is no monotone relationship.

`MIN_FIT_SCALE = 0.6` (`captions/shared/fit.ts:34`) can shrink a word to 60% —
60px, 3.1% of frame. But with `maxWidth = width * 0.85` (918px) a word only
overflows past ~15 characters, so the floor almost never fires in English. It is
a real risk for long Devanagari tokens and worth a targeted check, not a
redesign.

## WHAT I NOW BELIEVE

The legibility complaint from the video watch is a genuine perceptual defect —
one word at a time, thin type over busy footage. **But none of style,
keyword-highlighting, or default size predicts whether the user exports.** At
n=761 the caption-typography lever is not measurable in the funnel.

⚠️ All three tests are observational: Gemini picks the style from the content, so
style is confounded with content. A negative here is much stronger evidence than
a positive would have been — and all three came back negative.

**Where that points instead:** the faults that are decidable rather than
aesthetic. Rotation (2 of 20 delivered sideways), the light routes that make no
editorial call (37% of completions), and the plans that never fire an instrument
at all.

## Corrected: the "three dead families" are two

Measured on 778 planned jobs since 07-28, and on today's 159:

| family | jobs with ≥1 | mean/25s |
|---|---|---|
| motion_graphics | **32.9%** | 0.68 |
| text_overlays | **39.2%** | 0.82 |
| tight_cut_overlays | 38.7% | 0.66 |
| **transitions** | **4.9%** | 0.05 |
| **generated_scenes** | **0.0%** | 0.00 |
| **color_effect** | **0.0%** | — |
| **cut_refinements** | **0.0%** | — |

MGs and text overlays are NOT dead — a third of jobs get them. My earlier
"0.00 per 25s for every vibe" was the MEDIAN, and I let a median read as "never
fires". The genuinely dead list is transitions, generated_scenes, color_effect
and — newly — **cut_refinements**, which I had not reported before.

`zooms` reading 0.0% in my first pass was a wrong key name; zooms live inside
`emphasis_moments`. Caught before reporting.

## d98cd8d

**Its content is 100% live.** All six MG blocks are byte-identical to it and all
six handler.py additions are present, shipped in `fe15996` as `1ffa718`. The
commit object is not an ancestor of HEAD — re-applied rather than merged — so
"unmerged" is true of the commit and false of the code.

## Method and cost

`video_jobs.result.edit_recipe.plan` joined to `analytics_events.export_completed`
on `props.job_id`, 2026-07-25 onward. Two-proportion z-tests. Font sizes read
from the shipped components.

**Spend: zero.** DB reads and source reads. No render.
