# Transition Effects — Style Catalog

11 transition effects for Remotion. Each takes two video clips and a 0→1 progress value, producing a seamless animated cut between them. Self-contained — feed it two clips, drive the progress, render.

---

## Quick Start

Every component follows the same progress-driven pattern via `TransitionProps`:

```tsx
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SlideOver } from "./transitions/SlideOver";

export const MyTransition = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <SlideOver
        clipA="clip-a.mp4"
        clipB="clip-b.mp4"
        progress={progress}
        direction="left"
      />
    </AbsoluteFill>
  );
};
```

Several components export a `PEAK_PROGRESS` constant — the exact progress value where the visual peak occurs (typically 0.5). Use this to sync sound effects.

---

## Base Props

### TransitionProps (all components)

| Prop | Type | Description |
|------|------|-------------|
| `clipA` | `string` | **Required.** Source URL or `staticFile()` path for the outgoing clip. |
| `clipB` | `string` | **Required.** Source URL or `staticFile()` path for the incoming clip. |
| `progress` | `number` | **Required.** Normalized transition progress, 0 (clip A) to 1 (clip B). |
| `style` | `CSSProperties` | Optional style override on the outer container. |

---

## Components

### CardSwipe

Clip A swipes off-screen with 3D tilt like dismissing an app card, clip B rises from behind.

**Best for:** App-style UIs, swipe-to-dismiss moments, casual mobile-first edits.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `direction` | `"left" \| "right"` | `"left"` | Which way clip A swipes off. |

---

### ZoomThrough

Clip A rapidly scales up past the camera, clip B emerges from behind at smaller scale and grows to fill.

**Best for:** Energetic forward motion, "diving in" transitions, fast-paced content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. |

---

### SlideOver

Clip B slides over clip A with a contact shadow, pushing it aside. Clip A shifts slightly in the opposite direction and scales down.

**Best for:** Clean editorial cuts, side-by-side reveals, presentation-style slides.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `direction` | `"left" \| "right"` | `"left"` | Which way clip B slides in from. |

---

### Stack

Full iOS-style task-switcher visual. Dark wallpaper background with stacked cards, clip A shrinks to a card and slides off while clip B comes forward from the stack.

**Best for:** Phone UI aesthetics, app showcase reels, tech content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. |

---

### CrossfadeZoom

Clip A zooms in slightly and fades, clip B fades in and zooms out slightly. Premium cross-dissolve with motion. Supports both video and still images for either clip.

**Best for:** Cinematic dissolves, photo slideshows, elegant B-roll transitions.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. Accepts image paths (jpg/png/webp) in addition to video. |

---

### ShutterFlash

CRT TV power-off → power-on transition. Clip A collapses vertically into a thin beam, the beam contracts to a bright dot, then clip B powers on in reverse: dot → beam → full picture.

**Best for:** Retro tech aesthetics, channel-switching moments, dramatic hard cuts.

**Exports:** `SHUTTER_FLASH_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `flashColor` | `string` | `"#ffffff"` | Color of the central dot and beam glow. |
| `blades` | `"single" \| "dual"` | — | Reserved for API compatibility. |
| `bladeColor` | `string` | — | Reserved for API compatibility. |
| `chromaticAberrationOnReveal` | `boolean` | — | Reserved for API compatibility. |

---

### LightLeak

A warm glow sweeps across the frame like sunlight hitting a camera lens, bridging two clips. Three layered radial gradients with screen/soft-light blend modes. The hard cut is hidden at the peak of the brightest layer.

**Best for:** Warm cinematic transitions, golden hour edits, dreamy B-roll bridges.

**Exports:** `LIGHT_LEAK_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `palette` | `"warm" \| "gold" \| "cool" \| "magenta"` | `"warm"` | Color palette for the leak layers. |
| `direction` | `"tl-br" \| "tr-bl" \| "left-right" \| "top-down"` | `"tl-br"` | Sweep direction across the frame. |
| `intensity` | `number` | `1.0` | Overall glow intensity multiplier. |

---

### StepPush

Keynote-style slide push. Both panels travel together in the same direction: clip A exits, clip B enters to take its place. Cubic ease-in-out matches real presentation software.

**Best for:** Presentation decks, corporate content, clean forward-step editorial cuts.

**Exports:** `STEP_PUSH_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `direction` | `"left" \| "right" \| "up" \| "down"` | `"left"` | Push direction. "left" = standard forward step. |
| `separatorShadow` | `boolean` | `true` | Subtle shadow gradient on the trailing edge between panels. |

---

### NewspaperWipe

A torn newspaper image slams up from below, fully covers the frame, holds briefly, then rushes off the top. The clip swap happens at peak coverage. Stepped keyframes preserve a punchy, staccato feel.

**Best for:** News-style intros, editorial punch cuts, vintage paper aesthetics.

**Exports:** `NEWSPAPER_WIPE_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `assetPath` | `string` | `"torn-newspaper.png"` | Path under `/public` for the newspaper image asset. |

---

### FilmStrip

Device-frame film-reel transition. Clip A morphs from full viewport into a rounded tile, a strip scrolls upward by one pitch to reveal clip B in the next tile position, then clip B expands back to full viewport. Grid background, ghost tiles, and optional bookmark/caption.

**Best for:** Gallery reveals, portfolio showcases, curated content presentations.

**Exports:** `FILM_STRIP_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `frameBackground` | `string` | `"#0b0b0b"` | Background color inside the device frame. |
| `caption` | `string` | — | Optional static caption text rendered below the tile. |
| `showBookmark` | `boolean` | `false` | Render a small bookmark icon in the top-right. |
| `showGrid` | `boolean` | `true` | Render the perspective grid pattern. |
| `advanceFrames` | `number` | `1` | How many tile pitches to scroll between A and B. |

---

### SceneTitle

Chapter-break transition. A typographic title panel wipes across the frame, holds long enough to read, then wipes back out to reveal clip B. The A→B cut is hidden behind the panel at peak coverage. Uses Inter (label) and DM Serif Display (title) via Google Fonts.

**Best for:** Chapter breaks, act titles, documentary section headers.

**Exports:** `SCENE_TITLE_PEAK_PROGRESS` (0.5)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | `string` | — | **Required.** Main title text. Use `\n` to split onto multiple lines. |
| `label` | `string` | — | Optional small uppercase section label (e.g. "PART 01"). |
| `variant` | `"full" \| "half-top" \| "half-bottom"` | `"full"` | Panel coverage area. |
| `theme` | `"dark" \| "light"` | `"dark"` | "dark" = ink-black panel / cream type. "light" = cream panel / ink type. |
| `accentColor` | `string` | `"#C8551F"` | Accent divider color. |
| `titleColor` | `string` | theme default | Title color override. |
| `labelColor` | `string` | theme default | Label color override. |
| `showDivider` | `boolean` | `true` | Show the thin horizontal divider (only visible when label is present). |

---

## Shared Dependencies

Zero external dependencies beyond Remotion core:

**Peer dependencies:**
- `remotion` (AbsoluteFill, interpolate, Easing, OffthreadVideo, Img, useVideoConfig, staticFile)
- `@remotion/google-fonts` (Inter, DMSerifDisplay — used only by SceneTitle)

**Static assets:**
- `torn-newspaper.png` — required by NewspaperWipe (place in `/public`)

**Video source:** Must be constant frame-rate (CFR) 30fps matching your composition. Use `staticFile()` for local files or a direct URL for remote.
