// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/TypewriterReveal/TypewriterReveal.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// ../../src/remotion/src/captions/TypewriterReveal/types.ts
var TYPEWRITER_SCHEMES = {
  classic: {
    textColor: "#FFFFFF",
    bgColor: "#0a0a0a",
    cursorColor: "#FFFFFF"
  },
  terminal: {
    textColor: "#33FF33",
    bgColor: "rgba(0, 0, 0, 0.85)",
    cursorColor: "#33FF33"
  },
  amber: {
    textColor: "#FFB000",
    bgColor: "rgba(0, 0, 0, 0.85)",
    cursorColor: "#FFB000"
  }
};

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

// ../../src/remotion/src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// ../../src/remotion/src/captions/TypewriterReveal/TypewriterReveal.tsx
function resolveScheme(scheme, custom) {
  if (scheme === "custom" && custom) {
    return {
      textColor: custom.textColor ?? "#FFFFFF",
      bgColor: custom.bgColor ?? "rgba(0,0,0,0.8)",
      cursorColor: custom.cursorColor ?? custom.textColor ?? "#FFFFFF"
    };
  }
  const key = scheme ?? "classic";
  if (key === "custom") return TYPEWRITER_SCHEMES.classic;
  return TYPEWRITER_SCHEMES[key];
}
function buildCharTimings(page, lowercase) {
  const parts = [];
  const timings = [];
  for (let ti = 0; ti < page.tokens.length; ti++) {
    const token = page.tokens[ti];
    const word = lowercase ? token.text.toLowerCase() : token.text;
    if (ti > 0) {
      parts.push(" ");
      timings.push(page.tokens[ti - 1].toMs);
    }
    const charCount = word.length;
    for (let ci = 0; ci < charCount; ci++) {
      parts.push(word[ci]);
      timings.push(
        token.fromMs + ci / charCount * (token.toMs - token.fromMs)
      );
    }
  }
  return { text: parts.join(""), timings };
}
var TypewriterPage = ({
  page,
  colors,
  fontSize,
  fontFamily,
  letterSpacing,
  lineHeight,
  lowercase,
  showCursor,
  cursorBlinkMs,
  enableBox,
  boxBorderRadius,
  maxWidth,
  fadeInDurationMs,
  fadeOutDurationMs
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < 0) return null;
  const currentTimeMs = page.startMs + frame / fps * 1e3;
  const { text, timings } = useMemo(
    () => buildCharTimings(page, lowercase),
    [page, lowercase]
  );
  const fit = fitScale(
    asText(text).split(/\s+/).filter(Boolean).map((w) => ({
      parts: [
        {
          text: w,
          fontSize,
          font: { fontFamily, fontWeight: 600, letterSpacingEm: 0.03 }
        }
      ]
    })),
    maxWidth,
    "TypewriterReveal"
  );
  const fittedFontSize = fontSize * fit.scale;
  const pageLocalMs = frame / fps * 1e3;
  const fadeOutMs = boundedFade(fadeOutDurationMs, page.durationMs);
  const fadeOutStart = page.durationMs - fadeOutMs;
  const fadeOut = interpolate(
    pageLocalMs,
    [fadeOutStart, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const pageOpacity = fadeOut;
  let lastRevealedIdx = -1;
  for (let i = 0; i < timings.length; i++) {
    if (currentTimeMs >= timings[i]) {
      lastRevealedIdx = i;
    } else {
      break;
    }
  }
  const blinkCycleFrames = Math.max(2, Math.round(cursorBlinkMs / 1e3 * fps));
  const cursorVisible = showCursor && frame % blinkCycleFrames < blinkCycleFrames / 2;
  const charStyle = {
    fontFamily,
    fontSize: fittedFontSize,
    fontWeight: 600,
    // directive #12: was 400
    letterSpacing,
    lineHeight,
    whiteSpace: "pre-wrap",
    textShadow: [
      // directive #12: real stroke under the mono glyphs (4-direction)
      "-1.5px -1.5px 0 rgba(0,0,0,0.9)",
      "1.5px -1.5px 0 rgba(0,0,0,0.9)",
      "-1.5px 1.5px 0 rgba(0,0,0,0.9)",
      "1.5px 1.5px 0 rgba(0,0,0,0.9)",
      "0 2px 4px rgba(0,0,0,0.9)",
      "0 0 8px rgba(0,0,0,0.8)",
      "0 0 20px rgba(0,0,0,0.6)",
      "0 0 40px rgba(0,0,0,0.4)",
      "0 4px 12px rgba(0,0,0,0.5)"
    ].join(", ")
  };
  return <div style={{ opacity: pageOpacity, display: "flex", justifyContent: "center", width: "100%" }}>
      <div
    style={{
      ...enableBox ? { background: colors.bgColor, borderRadius: boxBorderRadius, padding: "16px 24px" } : {},
      maxWidth,
      textAlign: "center",
      ...fit.floored ? CHARWRAP_FALLBACK_STYLE : {}
    }}
  >
        {asText(text).split("").map((char, i) => {
    const isRevealed = i <= lastRevealedIdx;
    const isCursorPos = i === lastRevealedIdx + 1;
    return <React.Fragment key={i}>
              {isCursorPos && showCursor && <span style={{ ...charStyle, color: colors.cursorColor, opacity: cursorVisible ? 1 : 0 }}>|</span>}
              <span style={{ ...charStyle, color: colors.textColor, opacity: isRevealed ? 1 : 0 }}>{char}</span>
            </React.Fragment>;
  })}
        {lastRevealedIdx === text.length - 1 && showCursor && <span style={{ ...charStyle, color: colors.cursorColor, opacity: cursorVisible ? 1 : 0 }}>|</span>}
      </div>
    </div>;
};
var TypewriterReveal = ({
  pages,
  scheme = "classic",
  customColors,
  fontSize = 62,
  // directive #12: bumped from 48 — mono identity was too faint at phone scale
  fontFamily = CAPTION_FONTS.spaceMono,
  position = "bottom",
  anchor,
  showCursor = true,
  cursorBlinkMs = 530,
  enableBox = false,
  lowercase = true,
  letterSpacing = "0.03em",
  lineHeight = 1.4,
  fadeInDurationMs = 90,
  // WS2 faster base (was 150); further capped to 25% of the page window
  fadeOutDurationMs = 90,
  // WS2 faster base (was 150)
  boxBorderRadius = 8,
  maxWidthPercent = 0.85
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * maxWidthPercent;
  const colors = useMemo(
    () => resolveScheme(scheme, customColors),
    [scheme, customColors]
  );
  const positionStyle = getCaptionPositionStyle(position, anchor);
  return <AbsoluteFill>
      {pages.map((page, pageIndex) => {
    const startFrame = msToFrames(page.startMs, fps);
    const durationFrames = msToFrames(page.durationMs, fps);
    if (durationFrames <= 0) return null;
    return <Sequence
      key={pageIndex}
      from={startFrame}
      durationInFrames={durationFrames}
      premountFor={10}
      name={page.tokens.map((t) => t.text).join(" ")}
    >
            <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        ...positionStyle
      }}
    >
              <div style={{ position: "absolute", width: "calc(100% - 120px)" }}>
                <TypewriterPage
      page={page}
      colors={colors}
      fontSize={fontSize}
      fontFamily={fontFamily}
      letterSpacing={letterSpacing}
      lineHeight={lineHeight}
      lowercase={lowercase}
      showCursor={showCursor}
      cursorBlinkMs={cursorBlinkMs}
      enableBox={enableBox}
      boxBorderRadius={boxBorderRadius}
      maxWidth={maxWidth}
      fadeInDurationMs={fadeInDurationMs}
      fadeOutDurationMs={fadeOutDurationMs}
    />
              </div>
            </AbsoluteFill>
          </Sequence>;
  })}
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><TypewriterReveal {...p} /></div>;
};
