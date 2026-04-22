# Color Effects — Style Catalog

12 color effects for Remotion. Each wraps your video (or any children) and applies a cinematic color grade via CSS filters and blend-mode layers. Self-contained — wrap your footage, configure intensity and timing, render.

---

## Quick Start

Every component follows the same wrapper pattern:

```tsx
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import { CinematicGrade } from "./color-effects/CinematicGrade";

export const MyVideo = () => (
  <AbsoluteFill>
    <CinematicGrade intensity={0.8} timing={{ mode: "persistent" }}>
      <Video src="your-video.mp4" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </CinematicGrade>
  </AbsoluteFill>
);
```

### Timing Modes

All effects support two timing modes via the `timing` prop:

**Persistent** — fades in once and holds the look for the entire clip:
```tsx
timing={{ mode: "persistent" }}
timing={{ mode: "persistent", fadeInFrames: 30 }}
```

**Pulsed** — beat-synced hits that fade in, hold, and fade out:
```tsx
timing={{
  mode: "pulsed",
  pulses: [
    { peakFrame: 40, attackFrames: 3, holdFrames: 4, releaseFrames: 12 },
    { peakFrame: 120, attackFrames: 3, holdFrames: 4, releaseFrames: 12 },
  ],
}}
```

---

## Shared Props

### ColorTimingMode

| Mode | Props | Description |
|------|-------|-------------|
| `"persistent"` | `fadeInFrames?` | Fades in once and holds. |
| `"pulsed"` | `pulses: ColorPulse[]` | Beat-synced hits with envelope control. |

### ColorPulse (each entry in the pulses array)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `peakFrame` | `number` | — | **Required.** Frame at which the pulse reaches peak. |
| `attackFrames` | `number` | component default | Frames to ramp in before peak. |
| `holdFrames` | `number` | component default | Frames to hold at peak. |
| `releaseFrames` | `number` | component default | Frames to fade out after hold. |
| `intensity` | `number` | base intensity | Override peak intensity for this pulse. |

### Common Props (all components)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | — | **Required.** The footage or content to grade. |
| `intensity` | `number` | varies | Effect strength, 0–1. Each effect has its own default. |
| `timing` | `ColorTimingMode` | `{ mode: "persistent" }` | When and how the effect activates. |

---

## Components

### CinematicGrade

Teal-and-orange cinematic grade. Cool shadows, warm highlights, subtle contrast boost. Flat blend-mode overlays bound to pixel luminance, not screen position.

**Best for:** Cinematic footage, interviews, narrative B-roll.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### BleachBypass

Silver retention / bleach bypass look. Desaturated, contrasty, with a soft silver sheen. A contrast-boosted B&W pass composited via soft-light over the original.

**Best for:** Thriller aesthetics, prestige documentary, cold editorial.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### VintageFilm

Warm highlights, green-cast shadows, halation glow, optional procedural grain. Tuned for a Portra/Kodachrome "analog but clean" look.

**Best for:** Nostalgic montages, retro aesthetics, wedding/lifestyle content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |
| `grain` | `boolean` | `true` | Animated grain overlay. |
| `grainStrength` | `number` | `0.12` | Grain opacity at full intensity. |

---

### DreamHaze

Lifted blacks, soft highlight bloom via blurred screen-blend copy, pastel desaturation. Nostalgic diffusion without an "Instagram filter" feel.

**Best for:** Dreamy montages, music videos, lifestyle/travel content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### ChromaSplit

RGB channel split with per-channel color isolation via SVG filters. Three copies of the footage with red, green, blue channels shifted apart. Optional slow angle drift.

**Best for:** Glitch accents, analog monitor aesthetics, beat-synced editorial hits.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `offset` | `number` | `14` | Peak pixel offset at full intensity. |
| `angle` | `number` | `0` | Split direction in degrees. 0 = horizontal. |
| `drift` | `boolean` | `true` | Animate the split direction with slow drift. |
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### VignettePulse

Two-layer vignette: a constant base layer for cinematic framing plus a pulsed darker/tighter layer that breathes with emphasis. The pulsed layer shrinks its inner radius at peak, "closing in" on the subject.

**Best for:** Beat-synced emphasis, dramatic framing, cinematic containment.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `baseDarkness` | `number` | `0.35` | Base vignette darkness, 0–1. |
| `baseInnerPct` | `number` | `55` | Where the base fade starts as % of radius. |
| `color` | `string` | `"#000000"` | Vignette color. |
| `intensity` | `number` | `0.6` | Peak additional darkness at pulse. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### InvertStrike

Color-inverts the footage on beat via CSS `invert()`. Optional contrast punch so the inversion reads as design, not a glitch. Recommended with pulsed timing.

**Best for:** Beat drops, editorial punch moments, music video accents.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Inversion strength. |
| `timing` | `ColorTimingMode` | — | **Required.** Pulsed mode recommended. |
| `punch` | `boolean` | `true` | Add contrast punch at peak. |

---

### CineMono

Cinematic B&W with proper channel-mixed grayscale. Red/green/blue weights control how each color renders in luma. Defaults emulate a red-filter shoot (skin bright, skies dark). Deep contrast shaping + optional fine grain.

**Best for:** Prestige documentary, dramatic B&W sequences, editorial portraits.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `redWeight` | `number` | `0.5` | Red channel weight in B&W mix. |
| `greenWeight` | `number` | `0.35` | Green channel weight. |
| `blueWeight` | `number` | `0.15` | Blue channel weight. |
| `contrastBoost` | `number` | `0.35` | Contrast increase, scaled by intensity. |
| `grain` | `boolean` | `true` | Show grain overlay. |
| `grainStrength` | `number` | `0.1` | Grain opacity at peak. |
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### GoldenHour

Warm amber cast, cream highlights, magenta hint in shadows, preserved contrast. "Sun is about to set and everything glows" — elevated warmth without announcing a filter.

**Best for:** Interviews, lifestyle B-roll, golden-hour simulation.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |
| `sunWash` | `boolean` | `true` | Soft low-angle warm wash from top-left. |

---

### FilmGrain

Authentic cinema film grain with emulsion damage. Two animated grain layers (overlay + soft-light), occasional dust specks, and short hairline scratches. All deterministic per frame.

**Best for:** Film print authenticity, documentary texture, vintage post-production.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `grainStrength` | `number` | `0.3` | Grain layer opacity. |
| `grainScale` | `number` | `0.9` | Grain size — lower = finer, higher = coarser. |
| `grainOctaves` | `number` | `2` | Noise complexity — more = richer. |
| `flicker` | `boolean` | `true` | Subtle exposure flicker each frame. |
| `monochrome` | `boolean` | `true` | Keep grain monochrome. |
| `grainStep` | `number` | `3` | Frames between grain re-seeds. 1 = jittery, 3 = calm. |
| `dustDensity` | `number` | `5` | Average dust specks per frame. |
| `scratchDensity` | `number` | `0.8` | Average emulsion scratches per frame. |
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### Portra

Kodak Portra 400 emulation. Low contrast, lifted shadows, creamy warm-neutral skin tones, muted greens, clean highlight roll-off. Looks "invisibly nice" — the editorial portrait stock.

**Best for:** Portraits, editorial photography feel, subtle everyday grading.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

### NeoNoir

Fincher-style neo-noir grade. Heavy desaturation, crushed blacks, cold sickly greenish-cyan midtone cast, high-contrast roll-off. Technically color footage, emotionally drained of it.

**Best for:** Thriller sequences, moody narratives, dark editorial content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `intensity` | `number` | `1` | Effect strength. |
| `timing` | `ColorTimingMode` | persistent | Timing mode. |

---

## Shared Dependencies

Zero external dependencies beyond Remotion core:

**Peer dependencies:**
- `remotion` (AbsoluteFill, interpolate, useCurrentFrame, random)
- `@remotion/media` (Video — for wrapping footage in your compositions)

**Static assets:** None required.

**Video source:** Must be constant frame-rate (CFR) 30fps matching your composition. Use `staticFile()` for local files or a direct URL for remote.
