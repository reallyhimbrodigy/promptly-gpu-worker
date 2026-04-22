# Zoom Effects — Style Catalog

7 zoom effects for Remotion. Each wraps your video source and applies cinematic zoom behavior driven by timed events. Self-contained — feed it a video, define when to zoom, render.

---

## Quick Start

Every component follows the same event-driven pattern via `BaseZoomProps`:

```tsx
import { AbsoluteFill } from "remotion";
import { SmoothPush } from "./zoom/SmoothPush";

export const MyVideo = () => (
  <AbsoluteFill>
    <SmoothPush
      src="your-video.mp4"
      events={[
        { startMs: 1000, durationMs: 3000, scale: 1.2, originX: 0.5, originY: 0.4 },
        { startMs: 6000, durationMs: 2000, scale: 1.3 },
      ]}
    />
  </AbsoluteFill>
);
```

Pass an empty `events` array for full-duration mode — the effect spans the entire composition with automatic ramp-in/hold/ramp-out.

---

## Base Props

### ZoomEvent (each entry in the events array)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `startMs` | `number` | — | **Required.** When the zoom begins (ms from composition start). |
| `durationMs` | `number` | — | **Required.** How long the zoom lasts. Includes ramp-in, hold, and ramp-out. |
| `scale` | `number` | varies | Target scale factor. Each effect has its own default (typically 1.2–1.35). |
| `originX` | `number` | `0.5` | Horizontal zoom origin, 0–1. 0 = left edge, 1 = right edge. |
| `originY` | `number` | `0.5` | Vertical zoom origin, 0–1. 0 = top edge, 1 = bottom edge. |

### BaseZoomProps (all components)

| Prop | Type | Description |
|------|------|-------------|
| `src` | `string` | **Required.** Video source URL or `staticFile()` path. |
| `events` | `ZoomEvent[]` | **Required.** Zoom events. Empty array = full-duration mode. |
| `style` | `CSSProperties` | Optional style override on the outer container. |

---

## Components

### SmoothPush

Slow, deliberate forward zoom with refined easing. Starts imperceptibly, accelerates slightly, decelerates to a stop. The most essential zoom in professional editing.

**Best for:** Drawing attention to a subject, emphasis moments, B-roll enhancement.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. `scale` default: 1.2. |

---

### SnapReframe

Fast, precise zoom with a critically-damped spring — no bounce, no overshoot. A quick, clean reframe like a professional camera operator pulling focus.

**Best for:** Beat-synced reframes, reaction shots, editorial cuts within continuous footage.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. `scale` default: 1.3. |

---

### FocusWindow

Background shows the video zoomed in on a detail, a smaller rectangle overlaid shows the video at normal framing. Clean border on the window.

**Best for:** Revealing context around a detail, before/after comparison within the same frame.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `windowScale` | `number` | `0.72` | Size of the inner window as a fraction of the frame. |
| `borderWidth` | `number` | `0` | Border width in px around the window. |
| `borderColor` | `string` | `"transparent"` | Border color. |
| `bgScale` | `number` | `1.8` | How much the background is zoomed in. |

---

### StepZoom

Instant jump cuts between zoom levels. No smooth animation, no easing. Clean, precise editorial reframes that happen on the beat.

**Best for:** Music videos, fast-paced edits, podcast highlight reels, beat-matched content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| Base props only | | | No additional props. `scale` default: 1.3. |

---

### LetterboxPush

Background shows the video at normal scale. A zoomed-in view pushes in from the center, framed by cinematic letterbox bars. Aspect ratio narrows as the zoom deepens.

**Best for:** Cinematic emphasis, dramatic reveals, genre-shifting moments.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `maxBarHeight` | `number` | `0.12` | Maximum bar height as fraction of frame height. |

---

### StageZoom

Zooms in two stages with a pause between them. First push settles, holds, then a second deeper push commits further. Like a camera operator finding focus then pushing in for emphasis.

**Timeline:** ramp1 → hold1 → ramp2 → hold2 → ramp out

**Best for:** Two-beat emphasis, building tension, storytelling beats with escalation.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `firstStage` | `number` | `1.15` | Scale for first stage. |
| `secondStage` | `number` | `1.35` | Scale for second stage. |

---

### DepthPull

Multi-layer cinematic depth zoom. Background zooms slowly while floating bokeh orbs, edge blur, atmospheric haze, and decorative frame lines create perceived depth.

**Best for:** Premium intros, title sequences, cinematic B-roll, high-production moments.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `edgeBlur` | `number` | `4` | Edge depth-of-field blur max in px. |
| `frameLines` | `boolean` | `true` | Show decorative frame lines. |

---

## Shared Dependencies

Zero external dependencies beyond Remotion core:

**Peer dependencies:**
- `remotion` (AbsoluteFill, interpolate, spring, Easing, useCurrentFrame, useVideoConfig, OffthreadVideo)
- `@remotion/media` (Video)

**Static assets:** None required.

**Video source:** Must be constant frame-rate (CFR) 30fps matching your composition. Use `staticFile()` for local files or a direct URL for remote.
