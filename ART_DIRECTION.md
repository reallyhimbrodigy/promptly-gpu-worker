# ART_DIRECTION.md — the look, in numbers

**Status:** the design decision that has never been made in this codebase. The
component inventory found 34 of 37 MG files authored by an agent, zero references
cited, zero commits saying *"this looked wrong, here is a better design."* This
file is that missing layer.

**What this is:** measurements taken off `golden/lumen-refs/`, expressed as
numbers a builder implements. Not prose about editing. Every value is either
`[MEASURED]` from a reference frame or `[DERIVED]` with its reasoning shown.

**Scope:** this governs how components LOOK. It does not govern when the planner
chooses them. The planner picks moments; this file owns the pixels — and once it
is implemented, "did it look right" stops being a question only the owner's eye
can answer.

---

## §1 — THE ONE RULE ABOVE ALL OTHERS

**One system, held for the whole edit.** REF-1 and REF-2 do not look
professional because they contain many components. They look professional
because every element belongs to the same hand: one palette, one type
treatment, one motion law, from first frame to last.

The owner's standard, verbatim: *"you can tell it was made by someone who knows
what they're doing — it's all or nothing."*

**Binding consequence:** a partially-applied treatment reads as amateur, and is
worse than none. Where the current architecture degrades gracefully by stripping
components, it must instead degrade by **dropping to a smaller complete
treatment** — never a full treatment with pieces missing.

### 1.1 One system per EDIT; many styles across the PRODUCT

*"One system"* is a statement about a single video, not about the catalogue.
Within one edit, one type treatment is held from first frame to last. Across the
product, **the variety is the product** — twelve distinct looks a creator can
choose between is a feature, and consolidating to one was considered and
**REJECTED** (owner, 2026-08-17).

This splits the work into two layers, and everything below is filed under one
of them:

| layer | what it governs | where it lives | who may vary it |
|---|---|---|---|
| **INVARIANTS** | geometry, rhythm, legibility, motion law, palette lock | **shared code**, one implementation | nobody — a component that breaks one is a defect |
| **ART DIRECTION** | the distinctive look of each style | per-component, against a **named reference** | each style, deliberately and differently |

The failure this repo actually has is not too many styles. It is **twelve styles
with no art direction layer at all** — and an invariants layer that was never
written down, so each component improvised its own geometry.

---

## §2 — TYPE (the caption system)

*Geometry, contrast floor and palette membership are INVARIANTS (layer 1).
Base colour, case, pairing and decoration belong to each style (layer 2).*

### 2.1 Measured off REF-2 (720x1280 vertical)

| property | value | source |
|---|---|---|
| base colour | `#FEFCFD` — near-pure white, very slightly warm | `[MEASURED]` pixel sample |
| weight | heavy / bold geometric sans, rounded terminals | `[MEASURED]` |
| case | lowercase for prose words; **UPPERCASE for accented keywords** | `[MEASURED]` REF-1 |
| cap height, normal word | **~4.5% of frame height** (~58px at 1280) | `[MEASURED]` |
| cap height, hero number | **~11.5% of frame height** — **2.5x** normal | `[MEASURED]` |
| tracking | tight; slightly negative at large sizes | `[MEASURED]` |
| words per page | **1-3**, never a full sentence | `[MEASURED]` |
| vertical position | **~53% of frame height** — centre-band, NOT lower third | `[MEASURED]` |

**`base colour` and `case` above are STYLE-layer defaults, not invariants**
(resolved 2026-08-17). The binding rules on colour are the contrast floor
(§2.4) and palette membership (§6) — see §8.2.

**The lower-third assumption was wrong and is retired.** Both references place
captions in the centre band, horizontally displaced away from the subject.

### 2.2 Placement law `[DERIVED]`

Captions are placed in **negative space, opposite the subject** — not at a fixed
anchor. REF-1: speaker centre-right -> caption left; speaker bottom-centre ->
caption upper-left; speaker left -> caption right.

- Needs a subject mask (RVM, component C) to do properly.
- **Interim, no mask required:** use the existing face-band detection. Place the
  caption in the horizontal third with the least face coverage, vertical anchor
  53%. This is strictly better than a fixed lower third and ships today.

### 2.3 Emphasis `[MEASURED]`

Two modes, both present in the references:

- **Keyword accent (REF-1):** phrase in white; the load-bearing word in the
  job's accent colour, **UPPERCASE**, same size. One accented word per page, never
  two.
- **Hero number (REF-2):** a stated number renders at **2.5x scale, inline with
  the phrase**, not replacing it — `0 coding`, `13 years old`, `$20,000,000`.
  Trigger: a numeral, currency amount, percentage or multiplier.

**Accent colour comes from the per-job design system** (`#875A45`, `#8B350D`
observed) — the one part of the current system that already responds to the
material. Never a hardcoded brand colour.

### 2.4 Legibility `[DERIVED]`

Both references keep type readable over arbitrary footage. Required: a soft drop
shadow (~2% of cap height offset, ~35% opacity, blur ~4% of cap height), OR a
contrasting outline — never neither. Verified against the darkest and lightest
frame the caption spans, not the frame at its start.

### 2.5 Motion `[MEASURED, already law]`

**Frame-1-is-final.** No opacity fade, no slide, no scale-in. This was
established over four passes by the owner's eye and it stands. Exit is
instantaneous on the page boundary.

---

## §3 — THE HARD PROHIBITION: NEVER DOUBLE THE CAPTIONS

If the source carries burned-in text, **Promptly emits no captions at all.**

The trigger-source render stacked yellow captions on top of the source's own
white ones, in the same band, overlapping. That single defect made the output
read as broken regardless of every other decision in it.

**The signal already exists and already works** — the planner reported
`source_text_regions.text_bands: ["bottom"]` and that correctly suppressed four
zooms. Caption suppression must derive from the same field. There is no
"reduce" or "reposition" option: burned-in text present => `caption_style: none`.

---

## §4 — DESIGNED INSERT SCENES (the Lumen vocabulary)

Measured off REF-2's evidence card (t~2s):

| property | value |
|---|---|
| background | flat near-white `#FEFCFD`, full-bleed |
| photo treatment | **tilted 5-8 degrees**, drop shadow, hard edge — a physical object on a surface |
| layering | 3 depth planes: background type -> photo -> foreground type |
| foreground type | overlaps the photo; heavy shadow for separation |
| the number | full-bleed, cropping off both frame edges, accent-outlined |

**The composition rule that makes these read as designed rather than generated:**
elements overlap and occlude each other. A stack of centred, non-overlapping
boxes reads as a slide. Tilt, overlap and depth read as design.

**Cadence `[MEASURED]`:** REF-2 carries ~6 insert scenes in 43s — one at every
major claim or number, roughly one per 7 seconds.

---

## §5 — RHYTHM `[MEASURED, already calibrated]`

- **Motion density: ~3.5 moving samples/second**, counting every motion kind —
  cut, caption beat, scene, zoom. Held near-identical across a landscape corporate
  promo and a vertical creator doc, so it travels across formats where cut rate
  does not.
- **Stillness ceiling: 3.5s.** No dead stretch longer.
- Cut gaps in the references run 6.1s and 9.5s — **cut rate is not the rhythm**;
  the type and the scenes carry it.

---

## §6 — BRAND SYSTEM

- **Palette lock:** 2-3 colours, derived per job, held across every element in
  the edit. A component using an off-palette colour is a defect.
- **Name plate:** on a spoken name/role. Lower-left, appears within the first
  ~3s, holds 2.5-3s.
- **End card:** CTA -> logo sting -> handle. Must **end with the edit** — a card
  running past the final cut is a black frame with text on it.
- **Watermark:** persistent, low-contrast, corner, never inside the caption band.

---

## §7 — WHAT "GOOD" MEANS, OPERATIONALLY

A Promptly edit is right-looking when, on any frame:

1. every visible element draws from the job's locked palette;
2. type is one system — same family, same weight, same treatment;
3. nothing overlaps anything it wasn't composed to overlap;
4. something has moved within the last 3.5 seconds;
5. no element is a default that was never designed.

These are checkable. #1 and #4 are already machine-measurable today; #3 becomes
measurable with caption bounding boxes.

---

## §8 — IMPLEMENTATION ORDER

**§8.2 as first drafted — "consolidate to one caption style" — is RETRACTED**
(owner, 2026-08-17). The variety is the product. What was missing was never
"too many looks"; it was the absence of BOTH layers: no invariants in shared
code, and no art direction per style.

1. **§3 caption prohibition** — a defect, not a design task. **SHIPPED**
   2026-08-17: one predicate `_burned_text_caption_block()` consumed by every
   caption gate and matched to the zoom gate's breadth;
   `cert_never_double_captions.py`, 6 mutations RED-proven.

2. **The INVARIANTS layer, in shared code.** §2.1 geometry (cap-height band,
   53% vertical anchor, 1-3 words per page), §2.4 legibility floor, §2.5
   frame-1-is-final, §5 rhythm (3.5 samples/s, 3.5s stillness ceiling), §6
   palette lock. One implementation every style imports — so a style CANNOT
   improvise geometry, and the numbers stop being per-component folklore.

   **OWNER CALL RESOLVED 2026-08-17:** `#FEFCFD` and case (lowercase prose /
   UPPERCASE accent) move to the **STYLE layer** — they are identity, and
   forcing them would have flattened TwoTone and Gadzhi into near-copies, which
   is the rejected consolidation arriving through the back door.

   They are replaced by two invariants that constrain the same surface without
   dictating the look:

   | invariant | rule | why it replaces a fixed colour |
   |---|---|---|
   | **contrast floor** | every glyph clears a minimum contrast ratio against the pixels it sits on, measured on the DARKEST and LIGHTEST frame the caption spans — not the frame at its start | a style may use any colour it likes; it may not use one you cannot read |
   | **palette membership** | every colour a component emits is a member of the job's derived palette (or its computed tints/shades) — never a hardcoded brand value | holds §1's "one hand" across the edit while leaving each style free to pair those colours differently |

   A style is therefore free to be white-on-black, two-tone, or accent-heavy.
   It is not free to be illegible, and it is not free to introduce a colour the
   rest of the edit has never seen.

3. **§6 name plate + end card** — deterministic, no model call, immediate lift.
   Triggered off a spoken name/role that the transcript already carries.

4. **§2.2 placement** — face-band interim now, mask-based when C merges.

5. **Per-style art direction, one style at a time, each against a NAMED
   reference.** The inventory found zero references cited across 11 caption
   components; `Gadzhi` is named after a creator and that name is the only trace
   of a reference anywhere in the system. Each style gets a reference and
   measured numbers, exactly as §2.1 does for the system.

6. **§4 insert scenes** — the largest build; blocked on nothing but this spec.

**Deliberately NOT in this file:** when to use each component. That is the
planner's job and it is specified in the prompt already. This file exists so
that when the planner picks something, the thing it picks is good.
