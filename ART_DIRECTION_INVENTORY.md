# ART-DIRECTION INVENTORY — caption styles and MG components

**On the record, 2026-08-17.** The question asked was whether these components
were designed against a reference, or built to spec-compliance only.

**Answer: spec-compliance only.** Stated plainly because it is the honest
finding, not the flattering one.

---

## What was inventoried

| | count | authored by |
|---|---|---|
| caption styles registered | **12** (+ `none` sentinel) | — |
| caption components implemented | **11** | **Codex** (agent) |
| motion-graphic components | **37 .tsx** | **34 of 37 Codex** |

Five caption styles checked individually — Gadzhi, CleanCut, TwoTone, Prime,
Lumen — **all land in ONE commit**, `de76a40`, 2026-07-26, titled *"SPEAKER-
FOLLOWING CAPTIONS + CAPTION-LESS MOTION ANCHORS (both DARK)"*. They were shipped
as a batch of capability, not designed one at a time against anything.

## What is absent

Searched the entire component tree for design vocabulary:

| term | files |
|---|---|
| art direction | **0** |
| moodboard | **0** |
| kerning | **0** |
| contrast ratio | **0** |
| type scale | 1 |
| typographic | 1 |
| hierarchy | 2 |

- **No component header cites a reference, a designer, or a source.** Checked
  all 11 caption components: not one says "after X", "based on", or names what
  it is trying to look like.
- **No reference imagery or moodboard exists in the repo.** The only reference
  media is `golden/lumen-refs/` (REF-A, REF-B, REF-C) and those are references
  for the OVERALL EDIT — the bar a finished video is judged against — not for
  the look of a caption style or an MG component.
- **`Gadzhi` is named after a real creator** whose caption look it presumably
  imitates. That name is the *only* trace of a reference anywhere in the system:
  there is no clip, no frame grab, no spec citing what it should match.

## What DOES exist — and what it actually is

**1. FITS / FIGHTS clauses — 60 of them, all in `handler.py`.**
These live in the PROMPT, not in the components. They tell the model *when to
pick* a component. They are selection guidance, not art direction:

> **StatCard** (MEDIUM) — hero number (~120-180pt, white) counting up
> digit-by-digit from 0 to target; accent divider drawing in; caps label below.

That is a precise mechanical spec — sizes, weights, colours, motion. It is
exactly what a competent engineer needs to build the thing, and exactly what a
designer would produce *after* deciding what it should look like. The deciding
step is the one that never happened.

**2. `CATALOG.md`** (334 lines) is a props-and-timing API reference. Its own
Quick Start reads *"configure timing, position, feed data, render."* Zero design
rationale.

**3. The per-job design system — the one genuinely generative element.**
The accent palette is DERIVED FROM THE USER'S OWN FOOTAGE (`#875A45` on the
trigger-source run, `#8B350D` on the REF-2 run). This is real, it works, and it
is the only part of the visual system that responds to the material.

**4. Taste input exists, but it is narrow and behavioural.**
The owner's feedback shaped *motion laws*, not looks:

- caption entrance: **frame-1-is-final** — no opacity, slide, or scale. Took
  four passes (`886013d`, `53eddb5`).
- zoom velocity cap 11px/frame, approved by eye.

Those are laws about how things move. Neither is a decision about how a caption
style should *look*.

## The revision history says the same thing

Every commit touching caption components is correctness, cost, i18n, or timing:

```
component_crash: a missing string killed the whole render
EMERGENCY cost cut
Multilingual A2.2: RTL word order for Arabic/Hebrew
caption lateness (frame-align page.startMs)
CAPTION ENTRANCE (final spec) — ZERO entrance animation
```

**Not one commit is "this looked wrong, here is a better design."** The system
has been debugged extensively and art-directed never.

## What this means, stated without softening

The components are **correct against their specs**, and the specs are detailed,
internally consistent, and enforced by a component-completeness gate. That is
real engineering and it is not nothing.

But nobody ever decided what a Promptly video should LOOK like, wrote that down
against a reference, and built to it. Twelve caption styles exist because twelve
were specified; the model picks between them on FITS/FIGHTS prose. When the
planner chose `CleanCut` for the trigger-source render, nothing in the system
could tell it — or us — whether that was the *right-looking* choice, because
there is no standard for right-looking.

**This is why the bar and the artifact kept getting confused.** `golden/lumen-refs/`
is the only statement of taste in the repo, it is at the level of the whole edit,
and there is nothing equivalent one level down at the component.

## The gap this leaves open

Judging component quality is currently impossible by any means except the
owner's eye, one video at a time — which is the most expensive instrument
available and the one that has already had to resolve three corpus-selection
errors and one caption collision.
