# FIRST LUMEN EDIT — artifact ledger

`[§3.1, §6.1, Rule 2]`

**The first Lumen edit that exists as a FILE.** Every prior run produced a PLAN;
this one produced 18.2 MB of mp4. Until now nothing about Lumen quality was
judgeable — not by JUDGE's battery, not by the owner's eye.

## The artifact

| | |
|---|---|
| bucket/key | `thisismybucketagainwooo` / `build-lane/lumen-first/lumen-first-b5d036218638/edit.mp4` |
| bytes | **18,212,817** (18.21 MB) |
| HLS | `build-lane/lumen-first/lumen-first-b5d036218638/edit-hls/master.m3u8` |
| presign TTL | 7 days from 2026-08-17T05:55:12Z |
| source | `golden/lumen-refs/ref2-viral-creator-doc-vertical.mp4` |
| build_sha | `036db900529b` **dirty=True** |

**VERIFIED BY FETCHING BYTES, not by reading a field.** Ranged GET returned
HTTP 206, 18,212,817 bytes, a valid MP4 `ftyp` box (brand `iso4`) with `moov`
present. The field-vs-artifact distinction is not pedantry here: an earlier
harness in this same campaign reported `SUCCEEDED in 0.0s video=False` because it
trusted a return value instead of checking a thing.

## Wall clock — the decomposition that did not exist before

| stage | seconds | share |
|---|---|---|
| transcribe | 2.57 | 1.4% |
| **editorial_plan** | **97.11** | **54.3%** |
| normalize | 6.85 | 3.8% |
| render | 60.74 | 34.0% |
| upload | 10.97 | 6.1% |
| **total** | **178.78** | |

**179s against the 120s law — over by 59s.** And the dominant
term is NOT the render: the editorial plan is 54% of the wall. That
inverts the assumption the L1/L2 orchestration split was sized against.

**This is an UPPER BOUND, not a production number.** The build lane sends the
full 75 MB source inline where production sends a small proxy, and there is no
prewarm. Both inflate it.

## What the edit contains

7 clips · 5 SFX on beats · zoom variety with 2 clip splits to preserve it ·
2 B-roll asks with negative constraints · 3 MGs · design system live,
accent `#8B350D`.

## What it does NOT contain — and this is the finding

- `generated_scenes`: **0**
- `brand_specs`: **{'name_plate': False, 'end_card': False}**

On a full render, editorial gate open, `premium=True`, design system attached.
Consistent with 198/198 `no_copy_in_plan` on live traffic. **The mechanism works
end to end and the planner declines to use it** — which is what the model matrix
(Track 1) exists to test.

## Known defects in this run

- `build_dirty=true` — v550's image was built from a tree with uncommitted
  changes; the SHA does not fully describe it. Fixed by the tree-freeze guard in
  `deploy.sh` (commit 4c43e9d), which now REFUSES rather than warns.
- `[plan-persist] failed — invalid input syntax for type uuid: "None"` —
  build-lane only (`_ACTIVE_JOB_ID` is None there). Filed, not chased.
