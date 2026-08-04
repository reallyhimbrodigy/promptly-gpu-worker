# WHY THE COVERAGE GATE IS NOT PROTECTING SPANISH

Spanish: **0.41 median keep-ratio, 53% of jobs losing more than half the video.**
Russian 0.50. This is half of the original "cuts out HALF the video" complaint.

## THE GATE IS NOT BROKEN. IT IS MEASURING A DIFFERENT THING THAN THE COMPLAINT.

Two mechanisms, and only one of them has a gate.

**1. What deletes the video** (`build_clips_from_words`, documented at
`handler.py:22046`):

> *"The output is assembled only from `[first kept word .. last kept word]`, so
> EDGE speech outside that envelope is DROPPED at any duration."*

Everything before the first transcribed word and after the last is gone — **at
any size, with no floor.** If transcription starts late and ends early, the
video is trimmed to the transcript's envelope.

**2. What the gate measures** (`_transcription_coverage_check`):

```
frac         = reject_speech / speech          # denominator is VAD SPEECH
reject_speech = edge_deletable + interior_reject
ok           = not (reject_speech >= 2.0s AND frac >= 0.10)
```

**`edge_deletable` counts untranscribed SPEECH at the edges. It does not count
edge material that is not speech.**

So a video whose edges are music, ambience, a title card, b-roll or a held shot
loses all of it to mechanism 1, while mechanism 2 correctly reports that **no
speech was destroyed** and passes. The gate is doing exactly what it says on the
tin; the tin does not say "keep-ratio".

This matches the earlier Spanish finding directly: the missing half is **EDGES,
not transcription dropout.** Dropout is what the gate is for. Edges that carry no
speech are ungated by construction.

## AND THE `AND` MAKES IT NARROWER STILL

`reject_speech >= 2.0s` **AND** `frac >= 0.10` — both must trip. Because the
denominator is VAD *speech* rather than source duration, a clip that is mostly
non-speech has a small `speech` value, so `frac` is computed against a small
base. A clip can lose 59% of its **duration** while the fraction of its **speech**
that was destroyed is near zero.

The gate is live and firing — `TRANSCRIPTION_INCOMPLETE` appears on 134 of 3,000
rows since 2026-07-20, so this is not a dark-flag story. It fires on the class it
was built for and is silent on this one.

## WHAT IS ACTUALLY MISSING

**There is no gate on the ratio the complaint is about.** Nothing compares output
duration to source duration. The coverage gate protects *speech integrity*; the
complaint is about *material loss*. Those are different quantities and only one
is guarded.

The honest fix is a second, separate check — a keep-ratio floor measured on
duration, independent of speech — not a loosening of this gate. Loosening the
speech gate to catch duration loss would make it over-fire on the class it
already handles correctly.

⚠️ **What I cannot yet show:** that the deleted Spanish edges are in fact
non-speech. The field that proves it — `vad_coverage` — has persisted on **0 of
3,000 rows**, because it was written to `edit_plan["_lang_bundle"]` under a
comment claiming it "flows into the success result payload" when the leading
underscore is exactly what the recipe sanitizer strips. **Fixed this turn**: it
now rides `stage_timings.lang_bundle`, the same nested pattern as `gemini_tokens`
and `lean_arm`, and is gated so it cannot silently regress.

So the mechanism above is read from code and is exact; the confirmation that
Spanish specifically hits it becomes measurable from the next deploy onward.

## Method and cost

Source read of `_transcription_coverage_check`, `build_clips_from_words` and
`_coverage_gate_enabled`; error-class counts over 3,000 rows since 2026-07-20.
**Spend: zero.**
