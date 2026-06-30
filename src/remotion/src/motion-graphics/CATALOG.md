# Motion Graphics Components — Style Catalog

15 motion graphic components for Remotion. Overlays, cards, annotations, and UI elements that drop over your video. Each is self-contained — configure timing, position, feed data, render.

---

## Quick Start

Every component follows the same timing pattern via `MGTimingProps`:

```tsx
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import { StatCard } from "./motion-graphics/StatCard";

export const MyVideo = () => (
  <AbsoluteFill>
    <Video src="your-video.mp4" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    <StatCard
      startMs={1000}       // appears at 1 second
      durationMs={3000}    // stays for 3 seconds
      value={47}
      suffix="%"
      label="CONVERSION RATE"
    />
  </AbsoluteFill>
);
```

Components automatically handle entrance and exit animations. You just set `startMs` and `durationMs`.

---

## Base Props

### MGTimingProps (all components)

| Prop | Type | Description |
|------|------|-------------|
| `startMs` | `number` | **Required.** When the entrance begins (ms from composition start). |
| `durationMs` | `number` | **Required.** Total on-screen lifespan including entrance and exit. |
| `enterFrames` | `number` | Override entrance animation length in frames. |
| `exitFrames` | `number` | Override exit animation length in frames. |

### MGPositionProps (most components)

9 of 15 components support positioning via anchor + offset:

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `anchor` | `MGAnchor` | varies | Preset position: `"center"`, `"top"`, `"bottom"`, `"left"`, `"right"`, `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"`. |
| `offsetX` | `number` | `0` | Pixel offset from anchor. Positive = right. |
| `offsetY` | `number` | `0` | Pixel offset from anchor. Positive = down. |
| `scale` | `number` | `1` | Uniform scale multiplier. 0.5 = half, 2 = double. |

---

## Components

### 2. AnnotationArrow

Hand-drawn SVG arrow with arrowhead, animated along a bezier path. Supports straight, curved-arc, j-shape, and fully custom SVG paths. Deterministic jitter via seed gives each arrow a unique hand-sketched feel. The arrow draws on during entrance and retracts on exit.

**Best for:** Callouts, pointing to UI elements, tutorial annotations, "look here" moments.

**Supports:** MGTimingProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `start` | `{ x, y }` | — | **Required.** Arrow start point in pixel coordinates. |
| `end` | `{ x, y }` | — | **Required.** Arrow tip in pixel coordinates. |
| `pathType` | `"straight" \| "curved-arc" \| "j-shape" \| "custom"` | `"curved-arc"` | Arrow shape preset. |
| `customPath` | `string` | — | SVG `d` attribute (required when pathType is `"custom"`). |
| `color` | `string` | `"#C8551F"` | Stroke color. |
| `strokeWidth` | `number` | `8` | Stroke width in px. |
| `seed` | `number` | `1` | Deterministic seed for hand-drawn jitter. |
| `arrowheadSize` | `number` | `32` | Arrowhead chevron size in px. |

---

### 5. ChatThread

Full iMessage-style phone conversation with typing indicators, sequential message delivery, status bar, and home indicator. Messages drop in with realistic typing delays. Dark mode by default with full color customization.

**Best for:** Text conversation recreations, testimonials, DM screenshots, storytelling via messages.

**Supports:** MGTimingProps + MGPositionProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `messages` | `ChatMessage[]` | — | **Required.** Each: `{ sender: "me"\|"them", text, typingMs?, holdMs? }`. |
| `header` | `ChatThreadHeader` | — | Top profile: `{ name, subtitle?, avatarSrc?, initials?, avatarColor? }`. |
| `width` | `number` | `820` | Card width in px. |
| `minHeight` | `number` | `1320` | Card minimum height. |
| `borderRadius` | `number` | `56` | Card corner radius. |
| `statusBarTime` | `string` | `"9:41"` | iOS status bar clock. |
| `showStatusBar` | `boolean` | `true` | Show iOS status bar. |
| `showHomeIndicator` | `boolean` | `true` | Show bottom home indicator pill. |
| `backgroundColor` | `string` | `"#000000"` | Card background. |
| `incomingColor` | `string` | `"#26252A"` | Incoming bubble color. |
| `incomingTextColor` | `string` | `"#FFFFFF"` | Incoming bubble text color. |
| `outgoingColor` | `string` | `"#0A84FF"` | Outgoing bubble color. |
| `outgoingTextColor` | `string` | `"#FFFFFF"` | Outgoing bubble text color. |

---

### 7. Notification

iOS/Android notification banner stack. 1-3 notifications drop in sequentially with platform-specific styling. 7 built-in app icons (Apple Pay, Venmo, Stripe, iMessage, Instagram, Email, Bank). Blur backdrop on iOS.

**Best for:** Income/payment proof, social proof, notification montages, "look what just happened" moments.

**Supports:** MGTimingProps + MGPositionProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `notifications` | `NotificationItem[]` | — | **Required.** 1-3 notifications. Each: `{ app, appName, title, body, timestamp? }`. |
| `platform` | `"ios" \| "android"` | `"ios"` | Platform visual style. |

**App options:** `"apple-pay"`, `"venmo"`, `"stripe"`, `"imessage"`, `"instagram"`, `"email"`, `"bank"`

---

### 8. ProgressBar

Animated progress bar with count-up value display. Two modes: value/total (e.g. "$47K / $100K") or percentage (e.g. "73%"). Optional milestone markers along the track with labels. The fill animates from 0 to target during the component's lifespan.

**Best for:** Goal tracking, fundraising progress, completion metrics, skill bars, loading indicators.

**Supports:** MGTimingProps + MGPositionProps

**Value mode:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `number` | — | Current value. |
| `total` | `number` | — | Total value. |

**Percentage mode:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `percentage` | `number` | — | 0-100 percentage. |

**Common props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | `string` | — | Eyebrow label above the bar. |
| `width` | `number` | — | Bar width in px. |
| `trackHeight` | `number` | — | Track height in px. |
| `fillColor` | `string` | `"#FFFFFF"` | Fill color. |
| `accentColor` | `string` | `"#D4A12A"` | Eyebrow label + hairline accent color. |
| `trackColor` | `string` | — | Background track color. |
| `milestones` | `ProgressBarMilestone[]` | — | Markers along the track: `{ at: 0-1, label? }`. |
| `formatValue` | `(n: number) => string` | — | Custom value formatter. |
| `textShadowLarge` | `string` | heavy shadow | Override drop shadow on the hero value. Pass `""` to disable. |
| `textShadowSmall` | `string` | light shadow | Override drop shadow on eyebrow + milestone labels. |

---


### 10. RecordingFrame

Full-screen recording overlay — thin inset border, horizontal scan line, and corner annotations with live counters. Annotations support live timestamp (T+N.Ns), word count, WPM, or static text. Creates a "raw footage" or surveillance aesthetic.

**Best for:** Behind-the-scenes, raw/unfiltered aesthetic, documentary, screen recordings, live session feel.

**Supports:** MGTimingProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `accentColor` | `string` | `"#C5432E"` | Live value readout color. |
| `textColor` | `string` | `"#F0EEE9"` | Muted label color. |
| `annotationFontSize` | `number` | `24` | Annotation value size (labels render at 0.75x). |
| `showFrame` | `boolean` | `true` | Show thin inset border. |
| `frameBorderColor` | `string` | `"rgba(240,238,233,0.08)"` | Border color. |
| `showScanLine` | `boolean` | `false` | Show horizontal scan line. |
| `scanLineColor` | `string` | `"rgba(197,67,46,0.4)"` | Scan line color. |
| `scanLineCycle` | `number` | `90` | Frames per scan cycle. |
| `annotations` | `RecordingFrameAnnotation[]` | 4 defaults | Corner annotations: `{ label, value, corner }`. |

**Special `value` strings:** `"timestamp"` (live T+N.Ns), `"wordcount"` (ticking count), `"wpm"` (words per minute).

---

### 11. SpeechBubble

Platform-specific social media comment/message bubble. 4 variants: Tweet (with engagement stats + verified badge), Instagram comment, iMessage bubble (with typewriter mode), and TikTok comment. Each matches the real platform's visual language.

**Best for:** Social proof, testimonial screenshots, comment highlights, DM recreations.

**Supports:** MGTimingProps + MGPositionProps

Use the `platform` prop to select the variant:

**Tweet** (`platform: "tweet"`):

| Prop | Type | Description |
|------|------|-------------|
| `name` | `string` | Display name. |
| `handle` | `string` | Twitter handle. |
| `text` | `string` | Tweet body. |
| `verified` | `boolean` | Show verified badge. |
| `stats` | `{ replies, reposts, likes, views }` | Engagement numbers. |
| `avatarSrc` | `string` | Avatar image URL. |
| `darkMode` | `boolean` | Dark mode styling. |

**Instagram** (`platform: "instagram"`):

| Prop | Type | Description |
|------|------|-------------|
| `username` | `string` | Username. |
| `comment` | `string` | Comment text. |
| `timestamp` | `string` | Time ago string. |
| `likes` | `number` | Like count. |

**iMessage** (`platform: "imessage"`):

| Prop | Type | Description |
|------|------|-------------|
| `messageType` | `"incoming" \| "outgoing"` | Bubble side. |
| `text` | `string` | Message text. |
| `status` | `"Delivered" \| "Read"` | Status indicator. |
| `typewriter` | `boolean` | Typewriter animation. |

**TikTok** (`platform: "tiktok"`):

| Prop | Type | Description |
|------|------|-------------|
| `username` | `string` | Username. |
| `comment` | `string` | Comment text. |
| `likes` | `number` | Like count. |

---

### 12. StatCard

Animated count-up number with label and accent divider line. Counts from `fromValue` to `value` with optional prefix/suffix formatting. Clean, bold, designed to read at a glance on mobile. No card background — just the number floating over footage.

**Best for:** Revenue stats, subscriber counts, growth metrics, KPIs, any hero number moment.

**Supports:** MGTimingProps + MGPositionProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `number` | — | **Required.** Target number. |
| `fromValue` | `number` | `0` | Starting value for count-up. |
| `prefix` | `string` | — | Prefix (e.g. `"$"`). |
| `suffix` | `string` | — | Suffix (e.g. `"%"`, `"K"`, `"+"`). |
| `decimals` | `number` | — | Decimal places. |
| `label` | `string` | — | **Required.** Label below the number. |
| `numberColor` | `string` | `"#FFFFFF"` | Number color. |
| `labelColor` | `string` | `"#FFFFFF"` | Label color. |
| `accentColor` | `string` | `"#C8551F"` | Divider line + number color. |
| `textShadow` | `string` | heavy shadow | Override drop shadow on number/label. Pass `""` to disable. |

---

### 13. StickyNotes

1-3 sticky notes that slam onto screen with spring physics and settle into a fixed layout (left / center / right). Each note has configurable color, rotation, and handwritten text. Optional white fog gradient behind the notes for readability.

**Best for:** Key takeaways, tip lists, reminders, bullet points with personality, educational content.

**Supports:** MGTimingProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `notes` | `StickyNote[]` | — | **Required.** Up to 3 notes. Each: `{ text, color, rotation }`. |
| `noteSize` | `number` | `300` | Note square size in px. |
| `noteFontSize` | `number` | `50` | Handwriting text size. |
| `noteFontFamily` | `string` | `Caveat Brush` | Handwriting font. |
| `showFog` | `boolean` | `true` | White gradient fog behind notes. |
| `topOffset` | `string` | `"5%"` | Vertical offset from top of frame. |

---

### 14. TornPaper

Two torn paper strips that slam in from opposite sides with stop-motion impact. Each strip has a colored shadow block behind it for depth. Subtle idle jitter after landing. Bold, physical, tactile.

**Best for:** Bold statements, key points, "vs" comparisons, attention-grabbing text overlays, emphasis moments.

**Supports:** MGTimingProps

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `topText` | `string` | — | **Required.** Top strip text. |
| `bottomText` | `string` | — | **Required.** Bottom strip text. |
| `topStripRotation` | `number` | `-10` | Top strip rotation in degrees. |
| `bottomStripRotation` | `number` | `7` | Bottom strip rotation in degrees. |
| `stripColor` | `string` | — | Strip background color. |
| `stripTextColor` | `string` | — | Strip text color. |
| `shadowColor` | `string` | — | Shadow block color behind strips. |
| `shadowOffsetX` | `number` | `10` | Horizontal shadow block offset. |
| `shadowOffsetY` | `number` | `9` | Vertical shadow block offset. |
| `stripFontFamily` | `string` | `Oswald` | Font family. |
| `stripFontSize` | `number` | `72` | Font size. |
| `stripFontWeight` | `number` | `700` | Font weight. |
| `stripLetterSpacing` | `string` | `"0.06em"` | Letter spacing. |
| `stripPadding` | `[number, number]` | `[14, 32]` | Padding [vertical, horizontal]. |
| `stripGap` | `number` | — | Gap between the two strips. |
| `stripsPositionTop` | `string` | `"25%"` | Vertical area height from top. |

---

## Shared Utilities

These are exported from the barrel and available for advanced use:

- **`useMGPhase(timing, defaults)`** — Hook that computes entrance/hold/exit animation state from `MGTimingProps`. Returns `{ visible, enterProgress, exitProgress, phase, localFrame, durationFrames }`.
- **`resolveMGPosition(props, defaults)`** — Converts `MGPositionProps` (anchor + offset + scale) into CSS flex alignment and transform styles.

## Dependencies

**Zero external utilities.** Everything is self-contained inside the `motion-graphics/` folder.

**Peer dependencies (npm install):**

- `remotion` — core framework (all components)
- `@remotion/google-fonts` — the following 8 font packages are loaded automatically:
  - `@remotion/google-fonts/Inter`
  - `@remotion/google-fonts/Anton`
  - `@remotion/google-fonts/DMSerifDisplay`
  - `@remotion/google-fonts/PlayfairDisplay`
  - `@remotion/google-fonts/CaveatBrush`
  - `@remotion/google-fonts/Oswald`
  - `@remotion/google-fonts/Roboto`
  - `@remotion/google-fonts/JetBrainsMono`

**Static assets:**

- `torn-paper.png` — required in your project's `public/` folder (used by TornPaper component only)
