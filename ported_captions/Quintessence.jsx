// ── ported prelude: injected globals re-bound ──
const createElement = React.createElement;

// ../../src/remotion/src/captions/Quintessence/Quintessence.tsx
// [ported] import removed — ChatCut injects these: remotion
// ../../src/remotion/src/captions/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
}

// ../../src/remotion/src/captions/shared/fadeTiming.ts
var FADE_WINDOW_FRACTION = 0.25;
var MAX_ENTRANCE_MS = 80;
function boundedFade(base, windowLen) {
  if (!(windowLen > 0)) return 0;
  return Math.min(base, windowLen * FADE_WINDOW_FRACTION, MAX_ENTRANCE_MS);
}

// gfont:@remotion/google-fonts/Inter
var loadFont = () => ({ fontFamily: "Inter" });

// gfont:@remotion/google-fonts/Montserrat
var loadFont2 = () => ({ fontFamily: "Montserrat" });

// gfont:@remotion/google-fonts/Poppins
var loadFont3 = () => ({ fontFamily: "Poppins" });

// gfont:@remotion/google-fonts/PlayfairDisplay
var loadFont4 = () => ({ fontFamily: "PlayfairDisplay" });

// gfont:@remotion/google-fonts/DMSerifDisplay
var loadFont5 = () => ({ fontFamily: "DMSerifDisplay" });

// gfont:@remotion/google-fonts/DMSans
var loadFont6 = () => ({ fontFamily: "DMSans" });

// gfont:@remotion/google-fonts/CormorantGaramond
var loadFont7 = () => ({ fontFamily: "CormorantGaramond" });

// gfont:@remotion/google-fonts/Lora
var loadFont8 = () => ({ fontFamily: "Lora" });

// gfont:@remotion/google-fonts/SpaceMono
var loadFont9 = () => ({ fontFamily: "SpaceMono" });

// gfont:@remotion/google-fonts/Teko
var loadFont10 = () => ({ fontFamily: "Teko" });

// ../../src/remotion/src/captions/shared/fonts.ts
var inter = loadFont();
var montserrat = loadFont2();
var poppins = loadFont3();
var playfairDisplay = loadFont4();
var dmSerifDisplay = loadFont5();
var dmSans = loadFont6();
var cormorantGaramond = loadFont7();
var lora = loadFont8();
var spaceMono = loadFont9();
var teko = loadFont10();
var NOTO_FALLBACK = [
  "'Noto Sans'",
  "'Noto Sans Devanagari'",
  "'Noto Sans Arabic'",
  "'Noto Sans Hebrew'",
  "'Noto Sans Thai'",
  "'Noto Sans Bengali'",
  "'Noto Sans Tamil'",
  "'Noto Sans Telugu'",
  "'Noto Sans Kannada'",
  "'Noto Sans Malayalam'",
  "'Noto Sans Gurmukhi'",
  "'Noto Sans Gujarati'",
  "'Noto Sans Sinhala'",
  "'Noto Sans CJK SC'",
  "'Noto Sans CJK JP'",
  "'Noto Sans CJK KR'",
  "'Noto Color Emoji'",
  "sans-serif"
].join(", ");
var withNoto = (family) => `${family}, ${NOTO_FALLBACK}`;
var CAPTION_FONTS = {
  inter: withNoto(inter.fontFamily),
  montserrat: withNoto(montserrat.fontFamily),
  poppins: withNoto(poppins.fontFamily),
  playfairDisplay: withNoto(playfairDisplay.fontFamily),
  dmSerifDisplay: withNoto(dmSerifDisplay.fontFamily),
  dmSans: withNoto(dmSans.fontFamily),
  cormorantGaramond: withNoto(cormorantGaramond.fontFamily),
  lora: withNoto(lora.fontFamily),
  spaceMono: withNoto(spaceMono.fontFamily),
  teko: withNoto(teko.fontFamily)
};

// ../../src/remotion/src/shared/safeZone.ts
var CANVAS_WIDTH = 1080;
var CANVAS_HEIGHT = 1920;
var TIKTOK_SAFE_TOP = 270;
var TIKTOK_SAFE_RIGHT = 200;
var TIKTOK_SAFE_BOTTOM = 420;
var TIKTOK_SAFE_SIDE = 80;
var SAFE_RECT = {
  x: TIKTOK_SAFE_SIDE,
  // 80
  y: TIKTOK_SAFE_TOP,
  // 270
  width: CANVAS_WIDTH - TIKTOK_SAFE_SIDE - TIKTOK_SAFE_RIGHT,
  // 800
  height: CANVAS_HEIGHT - TIKTOK_SAFE_TOP - TIKTOK_SAFE_BOTTOM
  // 1230
};

// ../../src/remotion/src/captions/shared/captionPosition.ts
var CAPTION_PADDING = {
  top: TIKTOK_SAFE_TOP,
  // 270 — clears the top header
  sides: TIKTOK_SAFE_SIDE,
  // 80  — general/left inset
  bottomSafe: TIKTOK_SAFE_BOTTOM,
  // 420 — clears the caption/progress/nav drawer
  sidesSafe: TIKTOK_SAFE_RIGHT
  // 200 — clears the right action rail
};
function getCaptionPositionStyle(position, anchor) {
  if (anchor) {
    return {
      justifyContent: "flex-start",
      paddingTop: anchor.topPx,
      paddingLeft: CAPTION_PADDING.sidesSafe,
      paddingRight: CAPTION_PADDING.sidesSafe
    };
  }
  switch (position) {
    case "top":
      return {
        justifyContent: "flex-start",
        paddingTop: CAPTION_PADDING.top,
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe
      };
    case "bottom":
      return {
        justifyContent: "flex-end",
        paddingBottom: CAPTION_PADDING.bottomSafe,
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe
      };
    case "center":
    default:
      return {
        justifyContent: "center",
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe
      };
  }
}

// ../../src/remotion/src/captions/shared/fit.ts
var H_TEXT_MARGIN = TIKTOK_SAFE_SIDE;
var SAFE_TEXT_WIDTH = CANVAS_WIDTH - 2 * H_TEXT_MARGIN;
var MIN_FIT_SCALE = 0.6;
var _ctx;
var _measureCache = /* @__PURE__ */ new Map();
function getCtx() {
  if (_ctx !== undefined) return _ctx;
  try {
    const canvas = document.createElement("canvas");
    _ctx = canvas.getContext("2d");
  } catch {
    _ctx = null;
  }
  return _ctx;
}
var canvasMeasurer = (word, fontSize, font) => {
  const text = font.uppercase ? word.toUpperCase() : font.lowercase ? word.toLowerCase() : word;
  const spacingPx = (font.letterSpacingEm ?? 0) * fontSize;
  const key = `${font.fontFamily}|${font.fontWeight}|${fontSize}|${spacingPx}|${text}`;
  const hit = _measureCache.get(key);
  if (hit !== undefined) return hit;
  const ctx = getCtx();
  if (!ctx) return text.length * fontSize * 0.62 + spacingPx * text.length;
  ctx.font = `${font.fontWeight} ${fontSize}px ${font.fontFamily}`;
  const anyCtx = ctx;
  let width;
  if ("letterSpacing" in anyCtx) {
    anyCtx.letterSpacing = `${spacingPx}px`;
    width = ctx.measureText(text).width;
  } else {
    width = ctx.measureText(text).width + spacingPx * text.length;
  }
  _measureCache.set(key, width);
  return width;
};
var _graphemeSeg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;
var _loggedPages = /* @__PURE__ */ new Set();
function fitScale(items, availableWidth, styleName, measure = canvasMeasurer) {
  const safeWidth = Math.min(availableWidth, SAFE_TEXT_WIDTH);
  let scale = 1;
  let widestText = "";
  for (const item of items) {
    let textPx = 0;
    for (const p of item.parts) textPx += measure(p.text, p.fontSize, p.font);
    const extraPx = item.extraPx ?? 0;
    if (textPx + extraPx > safeWidth) {
      const s = textPx > 0 ? Math.max(0, (safeWidth - extraPx) / textPx) : 0;
      if (s < scale) {
        scale = s;
        widestText = item.parts.map((p) => p.text).join(" ");
      }
    }
  }
  const floored = scale < MIN_FIT_SCALE;
  if (floored) scale = MIN_FIT_SCALE;
  if (scale < 1) {
    const logKey = `${styleName}|${widestText}|fitScale|${scale.toFixed(2)}|${floored}`;
    if (!_loggedPages.has(logKey)) {
      _loggedPages.add(logKey);
      console.log(
        `[caption-fit] style=${styleName} page="${widestText}" action=${floored ? "charwrap" : `scale(${scale.toFixed(2)})`}`
      );
    }
  }
  return { scale, floored };
}
var CHARWRAP_FALLBACK_STYLE = {
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word"
};

// ../../src/remotion/src/captions/Quintessence/Quintessence.tsx
function toTitleCase(text) {
  return text.replace(/\b\w/g, (c) => c.toUpperCase());
}
function buildWordSlots(pages) {
  const slots = [];
  for (const page of pages) {
    for (let i = 0; i < page.tokens.length; i++) {
      const token = page.tokens[i];
      const next = page.tokens[i + 1];
      slots.push({
        token,
        startMs: token.fromMs,
        endMs: next ? next.fromMs : page.startMs + page.durationMs
      });
    }
  }
  return slots;
}
var Quintessence = ({
  pages,
  fontSize = 160,
  position = "bottom",
  anchor,
  color = "#E8D44D",
  stretchY = 1.6
}) => {
  const { fps, width } = useVideoConfig();
  const frame = useCurrentFrame();
  const maxWidth = width * 0.85;
  const slots = buildWordSlots(pages);
  const activeSlot = slots.find((slot) => {
    const startFrame2 = msToFrames(slot.startMs, fps);
    const endFrame2 = msToFrames(slot.endMs, fps);
    return frame >= startFrame2 && frame < endFrame2;
  });
  if (!activeSlot) return null;
  const startFrame = msToFrames(activeSlot.startMs, fps);
  const endFrame = msToFrames(activeSlot.endMs, fps);
  const elapsed = frame - startFrame;
  const slotWinF = endFrame - startFrame;
  const enteredOpacity = elapsed >= 0 ? 1 : 0;
  const fadeOutFrames = boundedFade(3, slotWinF);
  const fadeOut = interpolate(
    frame,
    [endFrame - fadeOutFrames, endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = enteredOpacity * fadeOut;
  const displayText = toTitleCase(activeSlot.token.text);
  const fit = fitScale(
    [
      {
        parts: [
          {
            text: displayText,
            fontSize,
            font: {
              fontFamily: CAPTION_FONTS.playfairDisplay,
              fontWeight: 700,
              letterSpacingEm: -0.06
            }
          }
        ]
      }
    ],
    maxWidth,
    "Quintessence"
  );
  const fittedFontSize = fontSize * fit.scale;
  const fitFallback = fit.floored ? CHARWRAP_FALLBACK_STYLE : {};
  return <AbsoluteFill
    style={{
      ...getCaptionPositionStyle(position, anchor),
      alignItems: "center",
      opacity
    }}
  >
      <div style={{ position: "relative", display: "inline-block", maxWidth }}>
        {
    /* Word-shaped blurred shadow below */
  }
        <span
    aria-hidden="true"
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      fontFamily: CAPTION_FONTS.playfairDisplay,
      fontWeight: 700,
      fontSize: fittedFontSize,
      lineHeight: 0.9,
      letterSpacing: "-0.06em",
      whiteSpace: "nowrap",
      color: "rgba(0,0,0,0.4)",
      filter: "blur(10px)",
      transform: `scaleY(${stretchY})`,
      transformOrigin: "center bottom",
      textAlign: "center",
      pointerEvents: "none",
      ...fitFallback
    }}
  >
          {displayText}
        </span>
        <span
    style={{
      display: "inline-block",
      position: "relative",
      fontFamily: CAPTION_FONTS.playfairDisplay,
      fontWeight: 700,
      fontSize: fittedFontSize,
      color,
      lineHeight: 0.9,
      letterSpacing: "-0.06em",
      whiteSpace: "nowrap",
      transform: `scaleY(${stretchY})`,
      transformOrigin: "center bottom",
      textAlign: "center",
      ...fitFallback
    }}
  >
          {displayText}
        </span>
      </div>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><Quintessence {...p} /></div>;
};
