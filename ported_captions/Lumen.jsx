// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/Lumen/Lumen.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// ../../src/remotion/src/captions/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
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
var KEYWORD_CONTRAST_TRIGGER = 40;
var KEYWORD_CONTRAST_LAYERS = [
  "0 0 1px rgba(20,12,4,0.95)",
  "0 0 3px rgba(20,12,4,0.9)",
  "0 2px 5px rgba(0,0,0,0.9)"
];
var KEYWORD_CONTRAST_STEPUP_LAYERS = [
  "0 0 2px rgba(10,6,2,0.95)",
  "0 0 5px rgba(10,6,2,0.9)",
  "0 3px 7px rgba(0,0,0,0.95)"
];
var lumaOf = (hex) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return 128;
  const v = parseInt(m[1], 16);
  const r = v >> 16 & 255, g = v >> 8 & 255, b = v & 255;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
var keywordContrastShadow = (keywordColor, bandLuma) => bandLuma !== undefined && Math.abs(lumaOf(keywordColor) - bandLuma) < KEYWORD_CONTRAST_TRIGGER ? [...KEYWORD_CONTRAST_STEPUP_LAYERS] : [];

// ../../src/remotion/src/captions/Lumen/Lumen.tsx
var LumenWord = ({
  token,
  pageStartMs,
  fontSize,
  isKw,
  hasShine,
  textColor,
  keywordColor,
  sweepDuration,
  bandLuma,
  fitFloored
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const activateFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const elapsed = frame - activateFrame;
  const hasAppeared = elapsed >= 0;
  const scale = 1;
  const fastOpacity = hasAppeared ? 1 : 0;
  const sweepPosition = hasShine && hasAppeared ? interpolate(elapsed, [0, sweepDuration], [-100, 200], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  }) : -100;
  const wordFontSize = hasShine ? fontSize * 1.6 : isKw ? fontSize * 1.3 : fontSize;
  const color = isKw ? keywordColor : textColor;
  const fontProps = {
    fontFamily: isKw ? CAPTION_FONTS.playfairDisplay : CAPTION_FONTS.montserrat,
    fontWeight: isKw ? 400 : 600,
    fontStyle: isKw ? "italic" : "normal",
    fontSize: wordFontSize,
    lineHeight: 1.1,
    whiteSpace: "nowrap",
    letterSpacing: isKw ? "-0.02em" : "0.01em",
    // F4 last resort: below the fit floor, char-break instead of overflow.
    ...fitFloored ? CHARWRAP_FALLBACK_STYLE : {}
  };
  const w = 15;
  const skew = 20;
  const p = sweepPosition;
  const showSweep = hasShine && hasAppeared && p > -w - skew && p < 100 + w + skew;
  const polyClip = `polygon(${p - w}% ${-skew}%, ${p + w}% ${-skew - 10}%, ${p + w + skew}% ${100 + 10}%, ${p - w + skew}% ${100 + skew}%)`;
  const diffusedShadow = [
    ...LEGIBILITY_ANCHOR_LAYERS,
    "0 0 12px rgba(0,0,0,0.7)",
    "0 0 30px rgba(0,0,0,0.4)",
    "0 0 50px rgba(0,0,0,0.2)",
    "1px 2px 5px rgba(0,0,0,0.4)"
  ];
  const kwContrast = [
    ...KEYWORD_CONTRAST_LAYERS,
    ...keywordContrastShadow(keywordColor, bandLuma)
  ];
  const kwGlow = [
    "0 0 20px rgba(212,162,76,0.5)",
    "0 0 40px rgba(212,162,76,0.3)"
  ];
  return <span
    style={{
      display: "inline-block",
      position: "relative",
      ...fontProps,
      color: hasAppeared ? color : "transparent",
      opacity: fastOpacity,
      transform: `scale(${scale})`,
      transformOrigin: "center bottom",
      textShadow: hasAppeared ? isKw ? [...kwContrast, ...diffusedShadow, ...kwGlow].join(", ") : diffusedShadow.join(", ") : "none"
    }}
  >
      {token.text}
      {
    /* Shine sweep */
  }
      {showSweep && <span
    aria-hidden="true"
    style={{
      ...fontProps,
      position: "absolute",
      top: 0,
      left: 0,
      color: "#FFFFFF",
      textShadow: "0 0 10px rgba(255,255,255,0.8)",
      clipPath: polyClip,
      pointerEvents: "none"
    }}
  >
          {token.text}
        </span>}
    </span>;
};
var Lumen = ({
  pages,
  fontSize = 70,
  position = "bottom",
  anchor,
  keywords = [],
  shineWords = [],
  maxWordsPerLine = 4,
  lineGap = 0,
  wordGap = 14,
  textColor = "#FFFFFF",
  keywordColor = "#D4A24C",
  sweepDuration = 15,
  bandLuma = undefined
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const shineSet = useMemo(() => buildKeywordSet(shineWords), [shineWords]);
  const positionStyle = getCaptionPositionStyle(position, anchor);
  return <AbsoluteFill>
      {pages.map((page, pageIndex) => {
    const startFrame = msToFrames(page.startMs, fps);
    const durationFrames = msToFrames(page.durationMs, fps);
    if (durationFrames <= 0) return null;
    const lines = [];
    for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
      lines.push(page.tokens.slice(i, i + maxWordsPerLine));
    }
    const fit = fitScale(
      page.tokens.map((t) => {
        const kw = isKeyword(t.text, keywordSet);
        const shine = isKeyword(t.text, shineSet);
        return {
          parts: [
            {
              text: t.text,
              fontSize: shine ? fontSize * 1.6 : kw ? fontSize * 1.3 : fontSize,
              font: kw ? {
                fontFamily: CAPTION_FONTS.playfairDisplay,
                fontWeight: 400,
                letterSpacingEm: -0.02
              } : {
                fontFamily: CAPTION_FONTS.montserrat,
                fontWeight: 600,
                letterSpacingEm: 0.01
              }
            }
          ]
        };
      }),
      Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
      "Lumen"
    );
    return <Sequence
      key={pageIndex}
      from={startFrame}
      durationInFrames={durationFrames}
      premountFor={10}
    >
            <AbsoluteFill
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
        gap: lineGap,
        maxWidth,
        width: "100%"
      }}
    >
                {lines.map((lineTokens, lineIdx) => <div
      key={lineIdx}
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "baseline",
        justifyContent: "center",
        columnGap: wordGap,
        rowGap: lineGap
      }}
    >
                    {lineTokens.map((token, tokenIdx) => <LumenWord
      key={tokenIdx}
      token={token}
      pageStartMs={page.startMs}
      fontSize={fontSize * fit.scale}
      isKw={isKeyword(token.text, keywordSet)}
      hasShine={isKeyword(token.text, shineSet)}
      textColor={textColor}
      keywordColor={keywordColor}
      sweepDuration={sweepDuration}
      bandLuma={bandLuma}
      fitFloored={fit.floored}
    />)}
                  </div>)}
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
  return <div style={rootStyle}><Lumen {...p} /></div>;
};
