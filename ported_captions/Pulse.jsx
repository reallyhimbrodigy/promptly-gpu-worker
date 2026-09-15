// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/Pulse/Pulse.tsx
// [ported] import removed — ChatCut injects these: react
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

// ../../src/remotion/src/captions/shared/keywords.ts
function normalizeWord(text) {
  return text.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}
function buildKeywordSet(words) {
  return new Set(words.map((w) => normalizeWord(w)));
}
function isKeyword(text, keywordSet) {
  return keywordSet.has(normalizeWord(text));
}

// ../../src/remotion/src/captions/shared/legibility.ts
var LEGIBILITY_ANCHOR_LAYERS = [
  "0 0 2px rgba(0,0,0,0.75)",
  "0 2px 6px rgba(0,0,0,0.85)"
];
var LEGIBILITY_ANCHOR = LEGIBILITY_ANCHOR_LAYERS.join(", ");

// ../../src/remotion/src/captions/Pulse/Pulse.tsx
var PulseLine = ({ tokens, keywordSet, textColor, keywordColor, fontSize, opacity, dimmed, fitFloored }) => {
  const dimColor = "#BBBBBB";
  return <div
    style={{
      opacity,
      display: "flex",
      flexWrap: "wrap",
      justifyContent: "center",
      gap: "4px 12px",
      lineHeight: 1.1
    }}
  >
      {tokens.map((token, idx) => {
    const isKw = isKeyword(token.text, keywordSet);
    const color = dimmed ? dimColor : isKw ? keywordColor : textColor;
    return <span
      key={idx}
      style={{
        fontFamily: CAPTION_FONTS.dmSans,
        fontWeight: 700,
        fontSize: isKw ? fontSize * 1.25 : fontSize,
        color,
        textTransform: "none",
        letterSpacing: "-0.02em",
        textShadow: [
          // Shared legibility floor — tight near-glyph anchor.
          ...LEGIBILITY_ANCHOR_LAYERS,
          // Diffused background shadow (all directions)
          "0 0 12px rgba(0,0,0,0.7)",
          "0 0 30px rgba(0,0,0,0.4)",
          "0 0 50px rgba(0,0,0,0.2)",
          // Existing drop shadow
          "1px 2px 5px rgba(0,0,0,0.4)",
          // Keyword glow (only for active keywords)
          ...isKw && !dimmed ? [
            `0 0 10px ${keywordColor}80`,
            `0 0 20px ${keywordColor}40`,
            `0 0 40px ${keywordColor}25`
          ] : []
        ].join(", "),
        whiteSpace: "nowrap",
        // F4 last resort: below the fit floor, char-break.
        ...fitFloored ? CHARWRAP_FALLBACK_STYLE : {}
      }}
    >
            {token.text}
          </span>;
  })}
    </div>;
};
var Pulse = ({
  pages,
  fontSize = 80,
  position = "bottom",
  anchor,
  keywords = [],
  textColor = "#FFFFFF",
  keywordColor = "#FF6B4A",
  // directive #12: recolored off the blue family (was #00BFFF); Prime owns blue
  fadeDurationFrames = 5
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position, anchor);
  let activeIdx = -1;
  for (let i = pages.length - 1; i >= 0; i--) {
    if (frame >= msToFrames(pages[i].startMs, fps)) {
      activeIdx = i;
      break;
    }
  }
  if (activeIdx < 0) return null;
  const pairIdx = Math.floor(activeIdx / 2);
  const isFirstInPair = activeIdx % 2 === 0;
  const slot1PageIdx = pairIdx * 2;
  const slot2PageIdx = pairIdx * 2 + 1;
  const hasSlot2 = !isFirstInPair && slot2PageIdx < pages.length;
  const activeStart = msToFrames(pages[activeIdx].startMs, fps);
  const slot1Start = msToFrames(pages[slot1PageIdx].startMs, fps);
  let slot1Opacity = frame >= slot1Start ? 1 : 0;
  let slot2Opacity = 0;
  if (hasSlot2) {
    slot2Opacity = frame >= activeStart ? 1 : 0;
  }
  const lastVisibleIdx = hasSlot2 ? slot2PageIdx : slot1PageIdx;
  if (lastVisibleIdx === pages.length - 1) {
    const activeEnd = msToFrames(
      pages[lastVisibleIdx].startMs + pages[lastVisibleIdx].durationMs,
      fps
    );
    const lastFadeF = boundedFade(fadeDurationFrames, msToFrames(pages[lastVisibleIdx].durationMs, fps));
    const fadeOut = interpolate(
      frame,
      [activeEnd - lastFadeF, activeEnd],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    if (hasSlot2) {
      slot2Opacity *= fadeOut;
    } else {
      slot1Opacity *= fadeOut;
    }
  }
  const t = frame / fps;
  const floatY = 0;
  const fitTokens = slot2PageIdx < pages.length ? [...pages[slot1PageIdx].tokens, ...pages[slot2PageIdx].tokens] : pages[slot1PageIdx].tokens;
  const fit = fitScale(
    fitTokens.map((tok) => ({
      parts: [
        {
          text: tok.text,
          fontSize: isKeyword(tok.text, keywordSet) ? fontSize * 1.25 : fontSize,
          font: {
            fontFamily: CAPTION_FONTS.dmSans,
            fontWeight: 700,
            letterSpacingEm: -0.02
          }
        }
      ]
    })),
    Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
    "Pulse"
  );
  const fittedFontSize = fontSize * fit.scale;
  return <AbsoluteFill
    style={{
      display: "flex",
      alignItems: "center",
      ...positionStyle
    }}
  >
      <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      width: "100%",
      maxWidth,
      gap: Math.round(fontSize * 0.25),
      transform: `translateY(${floatY.toFixed(2)}px)`,
      willChange: "transform"
    }}
  >
        <PulseLine
    tokens={pages[slot1PageIdx].tokens}
    keywordSet={keywordSet}
    textColor={textColor}
    keywordColor={keywordColor}
    fontSize={fittedFontSize}
    opacity={slot1Opacity}
    dimmed={hasSlot2}
    fitFloored={fit.floored}
  />
        {hasSlot2 && <PulseLine
    tokens={pages[slot2PageIdx].tokens}
    keywordSet={keywordSet}
    textColor={textColor}
    keywordColor={keywordColor}
    fontSize={fittedFontSize}
    opacity={slot2Opacity}
    dimmed={false}
    fitFloored={fit.floored}
  />}
      </div>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><Pulse {...p} /></div>;
};
