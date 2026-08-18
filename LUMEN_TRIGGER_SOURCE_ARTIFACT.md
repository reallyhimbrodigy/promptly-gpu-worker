# LUMEN EDIT ON A TRIGGER-BEARING SOURCE — artifact ledger

`[§3.1, §6.1, Rule 2, Rule 5]`

**The first Lumen artifact that can be judged against the bar rather than
confused with it.** The previous one rendered REF-2, which the owner has since
watched and confirmed is *already fully edited* — so the planner's refusal to
decorate it was correct, and that run could never have answered the question it
was run to answer. REF-2 is now retired as an input and kept as the bar
(`cert_ref2_not_a_test_input.py`).

## The source — chosen BECAUSE it can trigger the components

| | |
|---|---|
| job | `047c083b` · 57.8s · 12.4 MB · **raw phone upload, 476×848 @ 1.56 Mbps** |
| sha256 | `d17f67d661bec260c5919490b69ee5320889764492346a08b2abe3faec9a5a27` |
| spoken name | **"Hey, Clippers team. My name is Sujay Ahmad."** |
| stated number | **"I'm 21 years old."** |

Both triggers were read out of the transcript **by eye**, not trusted from a
regex — because the regex was wrong. The self-introduction pattern was being
matched with `re.I`, which makes `[A-Z]` match lowercase, so "I'm paying" and
"I'm sure" scored as spoken names. Every "name" in the first corpus was a false
positive; fixed and the corpus rebuilt before this render was chosen.

## The artifact

| | |
|---|---|
| bucket/key | `thisismybucketagainwooo` / `build-lane/lumen-first/lumen-first-4472e2b09cdf/edit.mp4` |
| bytes | **34,376,603** — matches the run's reported `video_bytes` exactly |
| probed | 54.93s · 1080×1920 · h264 + aac · valid `moov` |
| build_sha | `5d43df567cad` **dirty=False** |

Verified by probing the downloaded file, not by reading a field.

## Wall clock

| stage | seconds |
|---|---|
| transcribe | 3.30 |
| **editorial_plan** | **103.12** |
| normalize | 13.68 |
| render | 113.37 |
| upload | 13.92 |
| **total** | **247.93** |

Still an **upper bound** — the build lane sends the source inline and has no
prewarm. But note the shape held from the REF-2 run: **the planner, not the
render, is the single largest term** (103s), on a source 6× smaller.

## What the edit contains

6 clips · 4 SFX placed on beats (`punchsfx` 0.6s, `popsfx` 11.4s,
`swoosh` 19.1s, `boom` 38.4s at the payoff) · CleanCut captions ·
design system live, accent `#875A45` · static reframe, faces found in 3/3
sampled frames.

## THE FINDING — and this time it is not a correct decline

```
generated_scenes : 0
brand_specs      : {'name_plate': False, 'end_card': False}
```

On a source where the speaker **says his own name in the first six words** and
**states his age**. Editorial gate open, `premium=True`, design system attached,
`build_dirty=False`.

REF-2's zero was defensible: nothing was left to add. **This zero is not.** The
trigger the `_BrandCopy` directive describes is present, spoken, and unmissable,
and the planner still emitted no name plate.

That is the difference between an instrument and a mirror, and it is the whole
reason the corpus was built.

## Corroboration from the same corpus

The 11-source plan-only probe at production config (3.7-flash, thinking=2048)
independently found:

- `generated_scenes` **0/11** on sources carrying stated numbers — a real decline
- `payoff` **fires on 10/11** — the 0/253 figure this campaign was built on no
  longer describes the planner
- the planner **states its reasons**: *"Removed full-canvas StatCards in favor of
  crisp kinetic typography and SFX"* — a deliberate taste choice, not a wiring
  failure

## Known limits of this artifact

- **The source is 476×848.** It is representative of real user uploads and is
  upscaled to 1080×1920, so it is NOT a like-for-like quality comparison against
  REF-2's production-grade footage. Judge the EDIT DECISIONS here; judge the
  pixel bar elsewhere.
- 1 of 11 corpus cells fell to safe-edit on
  `RECIPE_INVALID: emphasis_moments[4] derived t=73.217s is outside video` — on a
  74.8s source. Filed (`FILING_EMPHASIS_OUTSIDE_VIDEO.md`) and named a Step-C
  precondition.
