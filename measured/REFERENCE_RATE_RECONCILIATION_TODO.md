# Re-deriving the five reference rates against wall time — what is already established

**Builder 2, 2026-09-21, queued for tomorrow before the dark read.** Written now
so the derivation starts from facts rather than re-finding them at 21:00Z.

## 1. THE 294 BEATS ARE TWO PASSES OVER TEN VIDEOS, NOT 294 BEATS OF FOOTAGE

`reference_index.json` carries `readings: 2`, and the beats confirm it
mechanically. Grouping by `i` resetting gives **twenty runs**, and they are two
halves of ten:

```
pass A   45.9  52.6  25.5  59.3  28.6  37.9  38.6  43.6  37.4  66.1
pass B   43.2  52.6  25.5  59.3  28.6  37.9  38.6  43.6  37.4  59.5
```

Eight of the ten agree EXACTLY between passes. Only the first and the last
differ. So the corpus is the same ten videos annotated twice, and the total beat
span is **≈430.8s of footage, not 861.6s**.

**THIS MAKES LAST NIGHT'S PUBLISHED RATES SUSPECT IN THEIR DENOMINATOR.** Those
were cut 3.22, card 3.22, text 1.92, sfx 1.31, zoom 0.23 per 25s over "861.6s,
294 beats". Numerator and denominator are both doubled, so the RATIO largely
survives — but only if both passes assigned treatments at the same density, and
two of the ten runs already disagree on span. The per-pass rates must be
computed separately and compared; their agreement is itself a measurement, and
if they disagree the single number was never one number.

## 2. WALL TIME IS NOT IN THE INDEX, AND THE INDEX CANNOT NAME ITS VIDEOS

No beat carries a video id, filename or source key — only `i`, which restarts.
So beats can be grouped into runs, but a run cannot be matched to a video from
this file alone. Wall time has to come from the **reference project
`74036980` ("Reference — Zac's ten")**, whose assets carry `durationMs`.

Matching run→video then needs an ordering assumption or a join on beat span. An
assumed ordering is exactly the kind of thing that produces a confident wrong
number, so the join must be stated and checked, not assumed.

## 3. THREE FIGURES ALREADY EXIST FOR TEXT, FROM THREE PASSES

| figure | source | denominator |
|---|---|---|
| 124 placements / 10 videos | the beat index | beat-span |
| 220 placements / 10 videos | the CONTROL RE-READ | its own pass |
| 66 mapped | my five-family keyword mapping over all 294 | two passes |

The atlas already warns that the beat index and the control re-read are
different passes whose totals do not reconcile. Publishing ONE set means
choosing a pass and a denominator and SAYING WHICH — not averaging three
numbers that count different things.

## What tomorrow does, in order

1. Read the ten durations from project `74036980`; state how run→video was joined.
2. Compute the five rates PER PASS against wall time; report the two passes'
   agreement as a number.
3. Reconcile against the atlas's 124 and the control re-read's 220 by naming the
   pass and denominator of each, not by averaging.
4. Publish one set with provenance, and supersede the 861.6s figures explicitly
   rather than quietly replacing them.

The rates GRADE and never instruct, before and after this.
