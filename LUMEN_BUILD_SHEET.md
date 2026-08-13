# LUMEN BUILD SHEET — the gap map, costed `[§3.1, §6.1]`

**From `LUMEN_REFERENCE_SPEC.md`'s gap map, turned into a build order.** Two
entries are much cheaper than the map assumed, and both are code findings from
today. Every line cites its section (§8).

---

## THE TWO CORRECTIONS

### Landscape is NOT renderer-blocked `[§3.1]`

The map flags REF-1's 1080×608 as an architecture gap. Measured:

```
src/remotion/src/Root.tsx  calculateOverlayMetadata → { width: i.width, height: i.height }
                           ← the composition is INPUT-DRIVEN. 1080×1920 in Root.tsx
                             is only the studio-preview default.
handler.py:22111           probe_resolution() already reads the SOURCE's real dims
handler.py:28324-28325     "width": 1080, "height": 1920   ← HARDCODED. The whole pin.
```

**The renderer already honours any canvas.** The pin is two literals in the
worker's overlay input.

**But the real work is not those two lines** — it is everything downstream that
assumes vertical, and one of those things is a *doctrine*, not a number:

| assumes vertical | where |
|---|---|
| safe zones x∈[60,1020], y∈[108,1812] | prompt, `handler.py:6822` |
| face reframe target 1080×1920 | `calculate_reframe_crop(..., target_w=1080, target_h=1920)` |
| caption canvas height | `_SPEAKER_CAP_CANVAS_H = 1920` |
| zone→pixel resolution | renderer |

**The doctrine problem:** the safe-zone system exists to dodge *platform UI* —
status bar, caption drawer, engagement rail. A landscape corporate promo has
**no platform UI to dodge**. So for REF-1's canvas the zone system is not merely
mis-dimensioned, it is answering a question that does not apply. Landscape needs
its own zone doctrine (title-safe/action-safe, the broadcast convention), not a
rescaled vertical one. That is the actual design work, and it is a §4.2
no-templating-adjacent call: the *vocabulary* changes with the canvas.

### Person segmentation ALREADY EXISTS `[§3.1]`

The map calls text-behind-subject *"the one genuinely new hard capability."* It
is built, on an unmerged branch:

```
behind-layer-phase1   matting/matting_app.py            sibling Modal app, WebM-alpha
                      src/remotion/src/BehindSpecimen.tsx
                      src/remotion/src/AlphaProbe.tsx
                      04733da "matte ladder round 2: decomposed rungs + bite/lag metrics"
                      430cdc3 "specimen layers separated — true Phase-2 look, zero rig artifacts"
```

**Not unbuilt — unmerged.** Component C is a merge-and-certify job, not a
research project. Its quality ladder (bite/lag metrics) already exists, which is
the expensive half.

---

## THE BUILD ORDER

| # | component | state | the work |
|---|---|---|---|
| **1** | **B · insert scenes** `[§3.1]` | **EXISTS, UNLIT** | campaign #1. Diagnosed: five-way AND, master env var undeclared. Access model staged dark. **Owner: set `PREMIUM_PIPELINE_ENABLED`.** |
| **2** | **H · music bed** `[§7.3]` | **built dark** | mechanism + sidechain duck certified. **Owner: the licensed library.** Both references have a bed — this is not optional for the bar. |
| **3** | **C · text-behind-subject** `[§3.1]` | **built, unmerged** | merge `behind-layer-phase1`, re-cert against current HEAD, wire into the Lumen scene vocabulary |
| **4** | **A · keyword captions + number glorification** `[§3.1]` | partial | 9 caption styles exist; per-keyword colour emphasis and number glorification are new *renderers* in the existing caption system |
| **5** | **F · end-cards + palette lock** `[§3.1]` | missing | end-card renderer + per-video brand extraction. Small once B's design system exists |
| **6** | **D · name-plate** `[§3.1]` | missing | trivial after 5 — same renderer family |
| **7** | **Landscape canvas** `[§3.1]` | gap | 2 literals + a landscape zone doctrine (above). Gate it behind its own flag; REF-1's format is a *second* product surface |
| **8** | **G · rhythm law** `[§4.7]` | **MEASURED TODAY** | `rhythm_dimension.py` — now a number, see below |
| — | E · b-roll | exists | live |

---

## THE RHYTHM LAW, NOW A NUMBER `[§4.7]`

§1.G said *"something animates roughly every second; stillness never exceeds
~2s."* `rhythm_dimension.py` measures it from the **plan alone** — no render, no
Gemini, no spend — so it runs in the gate and on every differ candidate.

**Two numbers, deliberately not one:**

- `events_per_second` — density. **Gameable**: 40 captions in 2s scores well and
  looks like a seizure.
- `max_still_gap_s` — **the law**. The longest stretch with nothing happening.

The gate is on the **gap**; density is reported beside it as context. Proven on
reference-shaped plans:

```
REF-2-like   1.389/s, longest gap 0.9s   → WITHIN BAR
dead-hole    1.531/s, longest gap 6.4s   → TOO STILL
```

**The dead-hole plan has HIGHER density than the reference** and is obviously
worse. A single averaged number would have passed it. That is why §1.G's real
claim is about the gap, and why it is measured that way.

Unit inference is folded in (ms / frames / seconds resolve to the same verdict),
because guessing per-field would silently scale a gap by 1000 and make every
edit look perfect.

---

## COST `[§2.1, §5]`

The reference spec's read is confirmed by the shape of the work: **scene count
is the primary cost lever.** REF-2 carries ~6 insert scenes in 43s; each scene is
1–2 generation calls, so the generation bill scales with scenes, not with
duration or complexity.

Therefore the Lumen budget is enforced where scenes are *chosen*, not where they
are rendered — a scene-count discipline in the plan, priced by the per-render
cost meter (next build), against §2.1's ≤$1 target.

---

## WHAT IS OWNER-BLOCKED, AND WHAT IS NOT

**Blocked on him:** `PREMIUM_PIPELINE_ENABLED` (#1) · the music library (#2) ·
the blind-sheet scores (judge calibration) · the two mp4s
(`golden/lumen-refs/`, landing spot prepared).

**Not blocked — buildable now:** #3 merge segmentation · #4 caption renderers ·
#5/#6 end-card + name-plate · #7 landscape zone doctrine · the cost meter.

The reference files are **not** on the critical path: the anatomy is already
decomposed and this sheet is written from it. What the files unlock is
*scoring against the bar* rather than against our own history — which only the
blind-sheet scores make trustworthy anyway.


---

## BLOCKING PRECONDITION when the vocabulary is lit up `[§3.1, §4.7]`

The deterministic components are built and DARK. Two debts must be paid at the
moment they become emittable, and both are silent failures if skipped:

1. **Re-measure the MG attack table for `NamePlate` and `EndCard`.**
   `_MG_ATTACK_FINGERPRINT` was re-stamped when they landed, but the table maps
   an entrance to the frame its visual hit LANDS on, and it is measured from
   real renders. These two have never rendered. That is safe only while nothing
   can emit them — no schema field, no plan key, no catalogue entry. **Adding
   any of those three without re-measuring makes their SFX land early**, which
   reads as sloppy timing and has no error to point at.

2. **The TSX is UNVERIFIED.** There is no `node_modules` in this checkout, so
   `NamePlate.tsx` and `EndCard.tsx` have never been typechecked or compiled.
   Import shapes were verified by reading (`MG_FONTS.anton/.inter`,
   `useMGPhase`'s return, `SafeImg`'s required `role`) and two real errors were
   caught that way — but reading is not compiling. **First bundle build after
   these land is the real test**, and it must be run before they are lit up, not
   after.

Neither blocks anything today. Both block the flip.
