# Caption Components — Style Catalog

18 caption styles for Remotion. Each is a self-contained React component — feed it timed caption data, drop it over your video, render.

---

## Quick Start

Every component follows the same pattern:

```tsx
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import { Prime } from "./captions/Prime";

// Your timed caption data (from @remotion/captions or any transcription service)
const pages: TikTokPage[] = [
  {
    text: "your caption text",
    startMs: 0,
    durationMs: 2000,
    tokens: [
      { text: "your", fromMs: 0, toMs: 400 },
      { text: "caption", fromMs: 400, toMs: 1000 },
      { text: "text", fromMs: 1000, toMs: 2000 },
    ],
  },
];

export const MyVideo = () => (
  <AbsoluteFill>
    <Video src="your-video.mp4" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    <Prime pages={pages} specialWords={["caption"]} />
  </AbsoluteFill>
);
```

All components accept `position?: "top" | "center" | "bottom"` to control vertical placement. All widths are responsive to your composition size.

---

## Base Props (inherited by all components)

| Prop | Type | Description |
|------|------|-------------|
| `pages` | `TikTokPage[]` | **Required.** Timed caption pages with word-level tokens. |
| `fontFamily` | `string` | Base font family override. |
| `fontSize` | `number` | Base font size in px. |
| `fontWeight` | `number \| string` | Font weight. |
| `position` | `"top" \| "center" \| "bottom"` | Vertical position on screen. |

---

## Components

### 1. HormoziPopIn

Bold uppercase words that spring-pop onto screen one at a time. Highlight words scale up with a custom color. Thick black stroke for maximum readability over any footage. The go-to for high-energy talking-head content.

**Best for:** Motivational clips, business advice, podcast highlights, talking-head content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `highlightWords` | `HormoziHighlightWord[]` | `[]` | Words to highlight with specific colors. Each entry: `{ text, color }`. |
| `highlightScale` | `number` | `1.45` | Scale multiplier for highlighted words. |
| `allCaps` | `boolean` | `true` | Force uppercase text. |
| `maxWordsPerLine` | `number` | `4` | Words per line before wrapping. |
| `springConfig` | `SpringConfig` | Hormozi-tuned | Spring physics for the pop-in animation. |
| `staggerDelayFrames` | `number` | `1` | Delay between each word's entrance. |
| `letterSpacing` | `number` | `0.05` | Letter spacing in em. |
| `enableSoftShadow` | `boolean` | `true` | Soft drop shadow behind stroke. |

---

### 2. EmojiPop

Words appear with automatic Lottie emoji animations that pop in alongside the captions. Active word gets a color highlight. 48 built-in emoji animations mapped to common words.

**Best for:** Fun/casual content, storytelling, social media clips, content aimed at younger audiences.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `activeColor` | `string` | `"#FF0000"` | Color for the currently spoken word. |
| `inactiveColor` | `string` | `"#FFFFFF"` | Color for other words. |
| `emojiSize` | `number` | `110` | Emoji animation size in px. |
| `maxWidthPercent` | `number` | `0.85` | Max width as fraction of frame. |

---

### 3. PaperII

Clean Lora serif text where words smoothly transition from dim to bright as they're spoken. Minimal, no background by default — just text over footage with heavy shadow for readability. The strip-based layout stacks naturally.

**Best for:** Storytelling, narrative content, poetry, journal-style reflections, calm/thoughtful tone.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `paperColor` | `string` | `"transparent"` | Strip background color. |
| `upcomingColor` | `string` | `"rgba(255,255,255,0.45)"` | Color for unspoken words. |
| `activeColor` | `string` | `"#FFFFFF"` | Color for spoken words. |
| `allCaps` | `boolean` | `false` | Uppercase text. |
| `maxWordsPerLine` | `number` | `4` | Words per strip line. |
| `stripPaddingX` | `number` | `0` | Horizontal padding in each strip. |
| `stripPaddingY` | `number` | `0` | Vertical padding in each strip. |
| `stripGap` | `number` | `10` | Gap between strips. |
| `borderRadius` | `number` | `0` | Strip corner radius. |
| `colorTransitionMs` | `number` | `60` | Word color transition duration. |
| `letterSpacing` | `string` | `"-0.01em"` | Letter spacing. |

---

### 4. Prime

Two-tier text system: regular words in Inter, special words break out into oversized italic Playfair Display on their own line. Words spring in one at a time with a subtle slide. The font contrast between sans-serif body and serif specials creates a premium editorial feel.

**Best for:** Aspirational content, self-improvement, premium branding, lifestyle, anything that needs elegance with impact.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `specialWords` | `string[]` | `[]` | Words that get the italic serif treatment. |
| `specialColor` | `string` | `"#5ED4E8"` | Color for special words. |
| `specialFontFamily` | `string` | `playfairDisplay` | Font for special words. |
| `line1Color` | `string` | `"#FFFFFF"` | Top line color. |
| `line2Color` | `string` | `"#3BA5FF"` | Bottom line color. |
| `line1FontSize` | `number` | `52` | Top line font size. |
| `line2FontSize` | `number` | `66` | Bottom line font size. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |
| `lineGap` | `number` | `-30` | Gap between lines (negative = overlap). |
| `letterSpacing` | `string` | `"0.01em"` | Letter spacing. |

---

### 5. TypewriterReveal

Character-by-character typewriter reveal with a blinking cursor in Space Mono. Each character appears precisely timed to the word's audio duration. Three built-in color schemes (classic white, green terminal, amber) plus full custom colors.

**Best for:** Tech/coding content, thoughtful narration, documentary, anything that benefits from deliberate pacing.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `scheme` | `string` | `"classic"` | Color scheme: `classic`, `terminal`, `amber`, or `custom`. |
| `customColors` | `Partial<TypewriterColorScheme>` | — | Custom `{ textColor, bgColor, cursorColor }` when scheme is `custom`. |
| `showCursor` | `boolean` | `true` | Show blinking cursor. |
| `cursorBlinkMs` | `number` | `530` | Cursor blink interval. |
| `enableBox` | `boolean` | `false` | Show background box behind text. |
| `lowercase` | `boolean` | `true` | Force lowercase. |
| `letterSpacing` | `string` | `"0.03em"` | Letter spacing. |
| `maxWidthPercent` | `number` | `0.85` | Max width as fraction of frame. |

---

### 6. CinematicLetterpress

Words emerge from blur into sharp focus — a cinematic "focus pull" effect. Cormorant Garamond serif at light weight with wide letter-spacing creates a film title card feel. Pages exit with a reverse blur dissolve.

**Best for:** Documentary, film-style intros, cinematic narration, atmospheric storytelling, art house aesthetic.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `textColor` | `string` | `"#F5F0EB"` | Warm ivory text color. |
| `blurAmount` | `number` | `8` | Max blur in px at word start. |
| `blurDurationMs` | `number` | `200` | Blur-to-sharp transition time per word. |
| `enableScale` | `boolean` | `true` | Subtle scale-up on entry. |
| `scaleFrom` | `number` | `0.95` | Starting scale. |
| `letterSpacing` | `string` | `"0.12em"` | Wide letter spacing. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |
| `exitDurationMs` | `number` | `250` | Page exit blur duration. |
| `lowercase` | `boolean` | `false` | Force lowercase. |

---

### 7. Cove

Bold Montserrat base with special words that switch to oversized italic Playfair Display with a warm ethereal glow above them. Special words are nearly 2x the size of body text, creating a dramatic scale contrast. Non-special words have a dark blurred shadow above for depth.

**Best for:** Premium/luxury content, brand storytelling, wellness, any content where key words deserve a spotlight moment.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `boxedWords` | `string[]` | `[]` | Words that get the oversized serif + glow treatment. |
| `boxPaddingX` | `number` | `14` | Horizontal padding on special words. |
| `boxPaddingY` | `number` | `8` | Vertical padding on special words. |
| `maxWordsPerLine` | `number` | `4` | Words per line. |
| `lineGap` | `number` | `14` | Gap between lines. |
| `wordGap` | `number` | `14` | Gap between words. |

---

### 8. Dimidium

Heavy Montserrat with thick black stroke (14px), staggered left-aligned lines that drift with organic offsets. Highlight words alternate between 1.55x and 1x scale. A subtle floating sine-wave animation gives the text a breathing quality. Bold, urban, in-your-face.

**Best for:** Street style, urban content, bold statements, hip-hop/rap lyrics, high-contrast visuals.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `color` | `string` | `"#FFFFFF"` | Normal word color. |
| `highlightColor` | `string` | `"#E8D44D"` | Keyword highlight color. |
| `highlightWords` | `string[]` | `[]` | Words to highlight. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |
| `lineGap` | `number` | `8` | Gap between lines. |

---

### 9. EditorialPop

All Playfair Display — keywords scale up to 1.7x with bold italic treatment while body text stays light weight. Two-line staggered reveal where the second line appears timed to the audio. Pure typographic hierarchy, no color tricks.

**Best for:** Magazine-style content, editorial fashion, interview quotes, text-heavy reels that need visual hierarchy.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words that get the bold-italic pop. |
| `keywordScale` | `number` | `1.7` | Scale multiplier for keywords. |
| `textColor` | `string` | `"#FFFFFF"` | Text color. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |

---

### 10. Gadzhi

Montserrat uppercase with words that slide up from below with a smooth cubic ease-out. Words transition from gray to their final color as they settle. Keywords land in gold. Left-aligned with tight 2-word lines for punchy delivery.

**Best for:** Business/hustle content, agency-style reels, Gadzhi/SMMA aesthetic, confident delivery.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `textColor` | `string` | `"#FFFFFF"` | Body text color. |
| `highlightColor` | `string` | `"#F5C518"` | Keyword color (gold). |
| `keywords` | `string[]` | `[]` | Words to highlight. |
| `maxWordsPerLine` | `number` | `2` | Words per line. |
| `wordGap` | `number` | `14` | Gap between words. |

---

### 11. Illuminate

Playfair Display with a diagonal light sweep that reveals each word from dark to fully lit. Keywords keep a warm lingering glow after the sweep passes. Cinematic spotlight feel — like a beam of light crossing the text.

**Best for:** Cinematic narration, atmospheric storytelling, inspirational content, nighttime/moody visuals.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words that get the golden glow. |
| `textColor` | `string` | `"#FFFFFF"` | Text color. |
| `glowColor` | `string` | `"#D4A853"` | Glow color for keywords. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |

---

### 12. Lumen

Montserrat body with keywords that switch to Playfair Display serif with an amber glow and gold underline sweep. Shine words get an additional brightness flash that sweeps across them. Warm, golden, editorial.

**Best for:** Warm inspirational content, golden-hour aesthetics, wellness/mindfulness, storytelling with emotional weight.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words that get amber serif + glow. |
| `shineWords` | `string[]` | `[]` | Subset of keywords with extra shine sweep + gold underline. |
| `textColor` | `string` | `"#FFFFFF"` | Body text color. |
| `keywordColor` | `string` | `"#D4A24C"` | Keyword amber color. |
| `sweepDuration` | `number` | `15` | Brightness flash duration in frames. |
| `maxWordsPerLine` | `number` | `4` | Words per line. |
| `lineGap` | `number` | `0` | Gap between lines. |
| `wordGap` | `number` | `14` | Gap between words. |

---

### 13. MagazineCutout

Words appear as individually cut-out paper pieces — each with a cream background, slight random rotation, and size variation. Like a ransom note or magazine collage but clean. Words snap into place timed to audio.

**Best for:** Creative/art content, collage aesthetic, DIY/craft, zine-style, playful editorial.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `cutoutBg` | `string` | `"#FDF8F0"` | Background color for each cutout. |
| `inkColor` | `string` | `"#0D0D0D"` | Text color. |
| `maxRotation` | `number` | `6` | Max random rotation in degrees (±). |
| `sizeVariation` | `number` | `10` | Font size variation in px (±). |
| `cutoutPaddingX` | `number` | `14` | Horizontal padding per cutout. |
| `cutoutPaddingY` | `number` | `8` | Vertical padding per cutout. |
| `allCaps` | `boolean` | `true` | Uppercase text. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |

---

### 14. Passage

Cormorant Garamond serif with keywords that expand their letter-spacing (tracking) as they're revealed — a subtle typographic emphasis. Keywords also switch to italic with a warm gold color. The tracking shift is the signature move: letters physically spread apart to draw the eye.

**Best for:** Literary content, book quotes, thoughtful narration, essay-style voiceover, long-form storytelling.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words with tracking expansion. |
| `textColor` | `string` | `"#F1EADB"` | Body text color (warm ivory). |
| `keywordColor` | `string` | `"#D4A76A"` | Keyword color (warm gold). |
| `keywordTrackingFrom` | `number` | `-0.015` | Starting letter-spacing for keywords (em). |
| `keywordTrackingTo` | `number` | `0.09` | Ending letter-spacing (wider = louder). |
| `trackingShiftDurationMs` | `number` | `520` | Tracking expansion duration. |
| `fadeDurationMs` | `number` | `360` | Word fade-in duration. |
| `maxWordsPerLine` | `number` | `5` | Words per line. |
| `maxWidthPercent` | `number` | `0.78` | Max width as fraction of frame. |

---

### 15. Pulse

Two-slot paired display — words appear in pairs (one on top, one below) that fade in together. Keywords get a cyan accent color. Simple, clean, rhythmic. No spring physics, just crisp opacity transitions.

**Best for:** Music content, rhythmic narration, fast-paced dialogue, paired-word emphasis, lyric videos.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words that get cyan accent. |
| `textColor` | `string` | `"#FFFFFF"` | Default text color. |
| `keywordColor` | `string` | `"#00BFFF"` | Keyword accent color. |
| `fadeDurationFrames` | `number` | `5` | Opacity transition duration. |

---

### 16. Quintessence

Single word at a time, centered, in Playfair Display with dramatic vertical stretch (scaleY). Gold text on a spring entrance. Pure one-word-at-a-time impact — nothing else on screen.

**Best for:** Single-word emphasis, dramatic pauses, poetry, mantra/affirmation content, bold punctuation moments.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `color` | `string` | `"#E8D44D"` | Text color (gold). |
| `stretchY` | `number` | `1.6` | Vertical stretch multiplier. |

---

### 17. Serif

DM Serif Display body with keywords that scale up (1.35x) in italic with a distinct blue accent and tighter letter-spacing. Words enter with a subtle spring scale-up from 0.96. Clean editorial hierarchy.

**Best for:** Premium editorial, interview quotes, news-style overlays, professional content, brand messaging.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `keywords` | `string[]` | `[]` | Words in italic DM Serif Display. |
| `textColor` | `string` | `"#F0EEE9"` | Body text color (cream). |
| `keywordColor` | `string` | `"#5A9FD4"` | Keyword color (blue). |
| `bodyFontSize` | `number` | `62` | Body font size. |
| `keywordSizeMultiplier` | `number` | `1.35` | Keyword scale multiplier. |
| `maxWordsPerLine` | `number` | `4` | Words per line. |
| `letterSpacing` | `string` | `"0.01em"` | Body letter spacing. |
| `keywordLetterSpacing` | `string` | `"-0.02em"` | Keyword letter spacing. |
| `scaleFrom` | `number` | `0.96` | Spring entrance starting scale. |

---

### 18. StaggerWave

Montserrat uppercase with words that spring in with a staggered delay and float on a gentle sine wave. The currently spoken word lights up in yellow (accent color) while upcoming words sit at low opacity. Energetic but controlled.

**Best for:** Dynamic content, workout/fitness, fast narration, energetic reels, any content with rhythm and momentum.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `accentColor` | `string` | `"#FFED00"` | Active word color. |
| `upcomingOpacity` | `number` | `0.38` | Opacity for unspoken words. |
| `staggerFrames` | `number` | `3` | Delay between word entrances. |
| `waveAmplitude` | `number` | `3` | Floating wave height in px. |
| `waveHz` | `number` | `0.7` | Wave frequency. |
| `allCaps` | `boolean` | `true` | Uppercase text. |
| `maxWordsPerLine` | `number` | `3` | Words per line. |
| `letterSpacing` | `number` | `0.02` | Letter spacing in em. |

---

## Shared Dependencies

These components depend on the following utilities (included in delivery):

- **`utils/fonts.ts`** — Font family constants (Montserrat, Playfair Display, Inter, Cormorant Garamond, etc.)
- **`utils/timing.ts`** — `msToFrames()` conversion utility
- **`utils/captionPosition.ts`** — Position helpers and safe-area padding constants
- **`types/captions.ts`** — Base `CaptionStyleProps`, `TikTokToken`, `TikTokPage` types

All components require `remotion` and `@remotion/captions` as peer dependencies. EmojiPop additionally requires `@remotion/lottie` and `lottie-web`.
