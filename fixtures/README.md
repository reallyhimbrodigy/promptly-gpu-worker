# The five reliability fixtures

Built deterministically by `make_fixtures.sh` — fixed seeds, no wall-clock, no
unseeded randomness — so re-running produces the same bytes. That is what makes
them DURABLE rather than merely saved, and it is why they are generated here
instead of pulled from user media.

| fixture | source | mean motion | beats | exercises |
|---|---|---|---|---|
| `talking_head` | `ab-sources/talking-head-v1` (staged, hash-verified 2026-08-29) | — | transcript | the speech path |
| `music` | generated | 0.312 | 6 | no-speech routing, strong periodic motion |
| `screen_recording` | generated | 0.050 | 4 | near-flat curve → the max-length split path |
| `product_shot` | generated | 0.602 | 5 | smooth sustained motion |
| `pet_video` | generated | 0.056 | 3 | erratic motion, hard direction changes |

Mean motion spans 0.050..0.602 and the four produce 6/4/5/3 beats, so they
exercise genuinely different segmentation rather than four names for one shape.
That was verified with the SHIPPED `moodreel_editor.extract_motion_curve`, not a
lookalike, so the measurement is the one the pipeline will make.

## What these do NOT prove

They are reliability fixtures, not taste fixtures. Synthetic content exercises
the same code paths — no-speech routing, motion curve, scene detection, the
segmentation invariants — but says nothing about whether the resulting edit is
GOOD. A green gate here means "the pipeline did not break on five content
classes", never "the pipeline edited them well".

## They already earned their place

`product_shot` produced a 0.5s beat on the first run, below `min_beat_s=1.2`.
The unit suite asserted that invariant and PASSED, because its curve never
reached the max-length split path. Greedy striding by `max_beat_s` leaves the
remainder as the final piece (6.5s -> 6.0 + 0.5). Fixed by splitting a long run
into ceil(L/max) EQUAL parts, and the regression is now covered for seven
awkward durations.
