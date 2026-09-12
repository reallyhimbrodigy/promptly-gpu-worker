# PRE-REGISTRATION — reference corpus re-read
Written 2026-09-11, BEFORE the run. Nothing below is informed by any number
from it.

## What was asked, and why the asked-for version cannot answer

> "the decision surface currently tells the agent transitions are never used,
> and that sentence came from a sampler that couldn't see them. Register your
> expectations before the numbers land, re-derive the index, rebuild the
> offered sets."

The premise is wrong, and I can show it for $0. The sampler is not why.

`build_reference_records.py`'s annotator prompt declared

    "treatment": ["cut"|"punch_in"|"cutaway"|"card"|"text_placement"|"sfx"]

a CLOSED enum of six. `REFERENCE_CORPUS_SPEC.md:111` declares the same six
under one different name (`overlay_text` for `text_placement`). **Neither
contains `transition`.** The annotator could not have written the word if every
beat had one. `transition: 0 of 153` is the enum's shape, not the corpus's
behaviour, and a re-read at 5 fps with the same schema would have returned 0
again — at $4 — and I would have reported "the rate is not the cause."

So this run changes the SCHEMA, not just the rate. Two arms would be
uninterpretable together, so the rate change rides along and I do not claim any
result for it on its own.

## Three instrument defects found while preparing the run

1. **The enum had no transition** (above). Already recorded in
   `FILING_GROUNDING_AUDIT.md:67` — "the schema has no transition" — and the
   decision surface was built on the zero anyway.
2. **The frame cap truncated the video, it did not subsample it.**
   `sorted(files)[:200]` keeps the FIRST 200 frames. At FPS=2 that is 100s,
   longer than every reference, so it never bound and was invisible. At 5 fps it
   binds on 5 of 10 and cuts the longest reference to its first 40.0s of 59.5s.
   Timestamps come from the frame index, so the truncated prefix would have
   carried correct-looking times and the missing tail would have looked like a
   stretch of video with no beats. Fixed: it now refuses rather than truncates.
3. **The shipped index cannot have come from the shipped annotator.** The index
   contains `overlay_text`, a name the current prompt cannot emit (it says
   `text_placement`); `text_placement` appears nowhere in the index; and
   0 of 153 beats are bare while the current prompt says bare "should be COMMON"
   and records the pass it was written to FIX at 126/175 = 72% overlay_text.
   The shipped index is 124/153 = **81%**. That is worse than the broken pass.

## Registered predictions

Scored against the new run's own output. I am wrong if the direction is wrong,
not merely if the magnitude is off.

| # | Prediction | Refuted if |
|---|---|---|
| P1 | `transition` > 0. Zac says all ten examples have them; the craft pass at 5 fps found 11 over the same 10 videos. | transition == 0 with the field offered |
| P2 | `transition` lands in **8–30** of ~150 beats — decorated shot changes are a minority of shot changes even in edits that use them. Below 8 or above 30 is a miss. | outside 8–30 |
| P3 | **`overlay_text`/`text_placement` COLLAPSES**, from 124/153 (81%) to under 50%, because the caption fix in the current prompt moves running captions to `caption_layer`. This is the biggest predicted move and it has nothing to do with transitions. | text family stays above 50% |
| P4 | **Bare beats stop being zero** — at least 15 beats come back `treatment: []`. The current prompt demands it; the shipped index has 0 of 153. | fewer than 15 bare |
| P5 | `punch_in` RISES from 6. Six zooms in 153 beats is implausibly low for this corpus and the 5 fps craft pass found punch_in on 4 of 10 videos. | punch_in <= 6 |
| P6 | `cutaway` stays roughly flat (72/153 = 47%, ±10pp). Cutaways are whole shots and are visible at any sample rate. | moves more than 10pp |
| P7 | Beat COUNT changes by less than 25% (153 → 115–191). Beats are driven by mechanically-detected cuts, which do not change. | outside that range |
| P8 | The decision surface's per-purpose "never here" lists SHRINK. More families recorded means fewer families absent. | any purpose gains a never-here family |

## What I expect to be unable to conclude

- **Nothing about the sample rate on its own.** Schema and rate move together.
  If I want the rate isolated later it needs a third arm at 2 fps with the new
  schema, and I will say so rather than attribute P1–P8 to the rate.
- **Nothing about inter-rater reliability.** Still one annotator, one pass, no
  second rater — the same caveat `reference_provenance` already carries.
- **Whether the OLD index's distortion is fully explained by the caption bug.**
  P3/P4 landing would be consistent with it, not proof of it.

## Cost, stated in advance

10 videos, 426.1s, claude-sonnet-5, WIDTH=512, TOK_PER_FRAME=621.

| arm | frames | in | out | cost |
|-----|-------|----|-----|------|
| 2 fps (shipped corpus) | 847 | ~551k | ~35k | $2.18 |
| 5 fps, no truncation (this run) | 2131 | ~1349k | ~35k | **$4.57** |

Anthropic API, not Modal. Running total for this arm: $4.57.
