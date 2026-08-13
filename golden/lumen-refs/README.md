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

## What is measured from them — CONFIRMED, not quoted `[MEASURED 2026-08-12]`

Both files re-measured on arrival rather than trusting the spec's numbers.
Every §0 figure reproduced exactly:

| | REF-1 landscape | REF-2 vertical |
|---|---|---|
| file | `ref1-legalsoft-corporate-landscape.mp4` | `ref2-viral-creator-doc-vertical.mp4` |
| canvas | **1080×608** | 720×1280 |
| fps / duration | 30 / 52.60s | 30 / 43.20s |
| codec | hevc, 13.9 Mbps | hevc, 14.0 Mbps |
| audio | aac 44.1k stereo, mean **−15.8 dB**, peak **0.0** | aac 44.1k stereo, mean **−15.7 dB**, peak **0.0** |
| hard cuts (scene>0.3) | **21** | **8** |
| median shot | **1.77s** | **6.13s** |
| longest cut-to-cut gap | **6.1s** | **9.5s** |

## THE FINDING THAT CALIBRATES THE RHYTHM LAW

**Cuts alone do not satisfy the ~1s motion law — not remotely.** REF-2 runs
**9.5 seconds** between hard cuts; REF-1 runs 6.1s. Measured on cuts only, *both
references fail* the 2.0s stillness bar in `rhythm_dimension.py`.

The rhythm in these edits is carried by **captions, insert scenes and kinetic
type**, not by cutting. §1.G says exactly this ("REF-2 substitutes caption-beat +
scene-insert rhythm over long takes") and the measurement confirms it.

Two consequences, both binding:

1. `rhythm_dimension.py` must count **every** motion kind (caption, scene, zoom,
   MG, text, transition, b-roll), not just cuts. It does.
2. **Any future implementation that weights cuts heavily is wrong** — it would
   reject the bar itself. This is the calibration check to run against any
   change to that dimension: *if the references fail, the dimension is broken,
   not the references.*

## Size, stated plainly

167 MB of binaries enter git history permanently. Accepted because these are
goldens (byte-stability is the point) and because `golden/` is **not** bundled
into the Modal image — `modal_app.py` mounts only `src/assets/fonts`,
`src/remotion` and `src/assets/sounds`, so deploy size and image build time are
unaffected [MEASURED].

## Status

✅ **Both files present and verified.** The remaining Lumen calibration input is
the blind-sheet scores (§7.2) — the files establish the bar; the scores make
judging *against* it trustworthy.
