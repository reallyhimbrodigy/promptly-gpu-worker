# THE FIRST HONEST LOOK — this week's fixes together

`[Rule 2]` Same source, same model, same budget as the 2026-08-17 render. The
only difference is the four fixes.

## The artifact

| | |
|---|---|
| file | `LUMEN_EDIT_FIXES_TOGETHER_2026-08-18.mp4` |
| bytes | **33,927,241** |
| probed | 54.93s · 1080×1920 · h264 + aac |
| build_sha | `804d6c670ee5` **dirty=False** |
| wall | **71.2s** (was 247.9s — a warm image, not a pipeline change) |
| source | `047c083b` — 57.8s, 12.4 MB, raw phone upload, burned-in captions |

## The two fixes, OBSERVED in the log — not inferred

**§3 caption prohibition fired, through the exact branch that was missing:**

```
burned captions: w3_declared signal engaged (Stage-0 read said none)
                 — existing_caption_region=bottom
[captions] caption_style='none' — skipping caption pages
Recipe: 6 clips, 4 sfx, captions=none
```

The model reported Stage-0 = `none` **identically to last time**. What changed is
that its own W3 `source_text_regions: ["bottom"]` declaration now escalates the
decision — the signal that previously existed but was normalised *after* the
suppression ran. That branch only exists because the fix restructured to ONE
predicate instead of adding a fourth `or` clause.

**§6 name plate fired AND reached the renderer — the first time ever:**

```
[brand] name plate from TRANSCRIPT (deterministic): 'Sujay Ahmad' role=None
[brand-mg] NamePlate -> output 0-84f (0.00s +2.80s)
```

Two separate fixes had to both land for that second line to exist: the
transcript trigger (the planner emits `brand_copy` on 0 of 198 jobs, so the
component was unreachable) and the emission seam (the handler never wrote
`_brand_specs` into `motion_graphics_out` at all, so even a built spec produced
no pixels).

## Before / after, same source

| | 2026-08-17 | 2026-08-18 |
|---|---|---|
| captions | **CleanCut, over the source's own burned-in captions** | **none** |
| name plate | absent (spec unreachable) | **`Sujay Ahmad`, 0.00s +2.80s** |
| bytes | 34,376,603 | 33,927,241 |

The caption collision the owner saw is gone, and the plate he never saw is
present.

## What is still zero, and it is now a clean question

```
scene_count : 0
```

Not a collision, not a wiring gap — the planner was asked and did not place any.
That is what the v2 A/B exists to move, and it is now measurable without
confounds: the caption defect that made the last render unjudgeable is fixed, and
the component ledger separates "declined" from "we dropped it".

## Judge the decisions, not the pixels

The source is **476×848 upscaled** — a real phone upload, not production-grade
footage. Edit decisions are judgeable here; the pixel bar is not.
