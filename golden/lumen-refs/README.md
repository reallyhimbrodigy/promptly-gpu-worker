# golden/lumen-refs — THE BAR `[§7.1, §3.1, §2.1]`

**Drop the two reference mp4s here.** BUILDER commits them as reference goldens.

```
golden/lumen-refs/
  ref1-legalsoft-corporate.mp4     1080x608 LANDSCAPE, 30fps, 52.6s
  ref2-viral-creator-doc.mp4       720x1280 vertical,   30fps, 43.2s
```

These files serve three roles at once, which is why they live in the repo rather
than a drive folder:

1. **The Lumen quality reference** — what "make it viral" must produce
   (`LUMEN_REFERENCE_SPEC.md` decomposes them into eight components).
2. **Harness golden sources** — the differ and the fulfillment judge score
   Lumen output *against this bar*, not against our own past output. Scoring
   against our history only proves we did not regress; scoring against the bar
   is the only thing that proves we arrived.
3. **The §2.1 paywall showcase assets** — the wall carries these. The premium
   model is visible and named, and *this* is what it is offering.

## Why they are committed, not linked

A reference the harness cannot read is not a reference. Goldens must be
byte-stable and versioned with the code that is judged against them — the same
reason `golden/plans/` is committed. If either file is ever replaced, that is a
**deliberate re-baselining** and gets the same treatment as a golden re-freeze:
recorded in the commit that replaces it, with the owner's sign-off, never
silently.

## What is measured from them

`LUMEN_REFERENCE_SPEC.md` §0 already records the measurements taken:

| | REF-1 | REF-2 |
|---|---|---|
| canvas | **1080x608 landscape** | 720x1280 vertical |
| hard cuts | 21 (median shot ~1.8s) | 8 (long takes + inserts every 5-8s) |
| audio master | mean -15.8 dB, peaks 0.0 | mean -15.7 dB, peaks 0.0 |
| insert scenes | b-roll + kinetic type | ~6 designed scenes in 43s |

The **~1s motion rhythm law** (§1.G) is derived from these and is now a measured
harness dimension, not a vibe — see `cert_rhythm_dimension.py`.

## Status

⏳ **Awaiting the owner's drop** (§6 of the reference spec: "two minutes").
Nothing in the Lumen campaign is blocked on the *files* — the anatomy is already
decomposed and the build sheet is written. They are blocked on the **judge
calibration**, which needs the blind-sheet scores (§7.2).
