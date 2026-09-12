# Pre-registration — craft pass at 5 fps vs 1 fps

Written BEFORE the 5 fps run exists. The mechanism is named precisely enough
to be wrong, so the prediction is on the record first.

## What changes

`VideoMetadata(fps=5)` on the video Part. Nothing else: same bytes, same
prompt (byte-identical), same weights, same model, same corpus of ten.

## The mechanism being tested

`Part.from_bytes(..., mime_type="video/mp4")` with no `VideoMetadata` sends
the whole container. The AUDIO track arrives continuously; the VIDEO track is
sampled at Gemini's 1 fps default. **Two resolutions from one file.**

A 300 ms dissolve is AUDIBLE and INVISIBLE at 1 fps. So:
- `sfx` survived at 0.82/25s because the hits are HEARD;
- `transition` read exactly 0 of 153 because it exists ONLY in frames that
  were never sampled;
- `punch_in` read 6 of 153 because a sub-second zoom is purely visual and
  1 fps cannot resolve it.

## Predictions (falsifiable, in order of confidence)

1. **transition: 0 -> non-zero.** Zac says they are in all ten and look
   great. If this stays 0 at 5 fps, the sampler was not the cause and the
   annotation hole is somewhere else.
2. **punch_in: up from 6 of 153, and by the largest factor of any family.**
   Purely visual, purely sub-second — it has the most to gain from seeing
   five frames a second instead of one.
3. **sfx: roughly stable.** It was already audible. IF SFX MOVES A LOT, the
   audio channel was carrying less than the analyses suggested, and my
   account of why the two families split is wrong.
4. **cut REASONS change more than the cut RATE.** An annotator that can see
   both sides of a cut and hear the beat under it describes the same cut
   differently. Rate is a count of a visible event at a boundary; the reason
   needs the frames either side.
5. **text/overlay_text: roughly stable.** On screen for seconds, visible at
   1 fps.

## The control

A family that does NOT move is what says the rest is not simply an artefact
of running a second annotation pass. If EVERY family moves, the difference is
the re-run and not the rate, and nothing here is attributable.

## What 5 fps still cannot see

A single-frame flash (33 ms at 30 fps). If the new pass reports flashes, they
are HEARD-NOT-SEEN until a higher rate confirms them, and will be labelled so.

## Price

Ten videos. Video tokens scale with sampled frames, audio tokens do not:
~5x the video input of the 1 fps pass, which cost ~$0.30 for the ten.
Estimated $0.15-0.25 — lower than the first pass because that one also paid
for two quota-failed retries.
