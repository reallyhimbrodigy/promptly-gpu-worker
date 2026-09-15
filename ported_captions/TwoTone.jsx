// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/TwoTone/TwoTone.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
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

// ../../src/remotion/src/captions/TwoTone/TwoTone.tsx
function buildDepth(strokeWidth, strokeColor, extrudeColor) {
  const s = Math.ceil(strokeWidth / 2);
  const contour = [
    `${-s}px ${-s}px 0 ${strokeColor}`,
    `${s}px ${-s}px 0 ${strokeColor}`,
    `${-s}px ${s}px 0 ${strokeColor}`,
    `${s}px ${s}px 0 ${strokeColor}`,
    `0 ${-s}px 0 ${strokeColor}`,
    `0 ${s}px 0 ${strokeColor}`,
    `${-s}px 0 0 ${strokeColor}`,
    `${s}px 0 0 ${strokeColor}`
  ];
  const extrude = [];
  for (let i = 1; i <= 6; i++) {
    extrude.push(`${Math.round(i * 0.6)}px ${i * 2}px 0 ${extrudeColor}`);
  }
  const ambient = "0 16px 26px rgba(0,0,0,0.5)";
  return [...contour, ...extrude, ambient].join(", ");
}
var TwoToneWord = ({
  token,
  globalIndex,
  pageStartMs,
  color,
  fontFamily,
  fontSize,
  allCaps,
  textShadow,
  localFrame,
  fitFloored
}) => {
  const { fps } = useVideoConfig();
  const entry = msToFrames(token.fromMs - pageStartMs, fps) + globalIndex;
  const scale = 1;
  const y = 0;
  const opacity = localFrame >= entry ? 1 : 0;
  return <span
    style={{
      display: "inline-block",
      fontFamily,
      fontSize,
      fontWeight: 900,
      color,
      textTransform: allCaps ? "uppercase" : "none",
      letterSpacing: "-0.02em",
      lineHeight: 0.9,
      textShadow,
      transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(3)})`,
      transformOrigin: "center bottom",
      opacity,
      whiteSpace: "nowrap",
      padding: "0 0.1em",
      ...fitFloored ? CHARWRAP_FALLBACK_STYLE : {}
    }}
  >
      {token.text}
    </span>;
};
var TwoToneLine = ({
  tokens,
  startIndex,
  pageStartMs,
  color,
  fontFamily,
  fontSize,
  allCaps,
  textShadow,
  localFrame,
  fitFloored
}) => <div
  style={{
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "center",
    alignItems: "flex-end",
    columnGap: "0.16em"
  }}
>
    {tokens.map((token, i) => <TwoToneWord
  key={i}
  token={token}
  globalIndex={startIndex + i}
  pageStartMs={pageStartMs}
  color={color}
  fontFamily={fontFamily}
  fontSize={fontSize}
  allCaps={allCaps}
  textShadow={textShadow}
  localFrame={localFrame}
  fitFloored={fitFloored}
/>)}
  </div>;
var TwoTone = ({
  pages,
  topColor = "#FFFFFF",
  accentColor = "#FFC53D",
  fontFamily = CAPTION_FONTS.montserrat,
  fontSize = 110,
  position = "center",
  anchor,
  strokeWidth = 6,
  strokeColor = "#101014",
  allCaps = true
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.88;
  const positionStyle = getCaptionPositionStyle(position, anchor);
  const topShadow = useMemo(
    () => buildDepth(strokeWidth, strokeColor, "rgba(8,10,16,0.92)"),
    [strokeWidth, strokeColor]
  );
  const accentShadow = useMemo(
    () => buildDepth(strokeWidth, strokeColor, "rgba(92,42,0,0.94)"),
    [strokeWidth, strokeColor]
  );
  return <AbsoluteFill>
      {pages.map((page, pageIndex) => {
    const startFrame = msToFrames(page.startMs, fps);
    const durationFrames = msToFrames(page.durationMs, fps);
    if (durationFrames <= 0) return null;
    if (frame < startFrame || frame >= startFrame + durationFrames) {
      return null;
    }
    const localFrame = frame - startFrame;
    const n = page.tokens.length;
    const splitAt = Math.ceil(n / 2);
    const line1 = page.tokens.slice(0, splitAt);
    const line2 = page.tokens.slice(splitAt);
    const fit = fitScale(
      page.tokens.map((t) => ({
        parts: [
          {
            text: t.text,
            fontSize,
            font: {
              fontFamily,
              fontWeight: 900,
              letterSpacingEm: -0.02,
              uppercase: allCaps
            }
          }
        ],
        extraPx: 0.2 * fontSize
      })),
      maxWidth,
      "TwoTone"
    );
    const fittedFontSize = fontSize * fit.scale;
    return <AbsoluteFill
      key={pageIndex}
      style={{ display: "flex", alignItems: "center", ...positionStyle }}
    >
            <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        rowGap: "0.02em",
        maxWidth,
        width: "100%"
      }}
    >
              <TwoToneLine
      tokens={line1}
      startIndex={0}
      pageStartMs={page.startMs}
      color={topColor}
      fontFamily={fontFamily}
      fontSize={fittedFontSize}
      allCaps={allCaps}
      textShadow={topShadow}
      localFrame={localFrame}
      fitFloored={fit.floored}
    />
              {line2.length > 0 ? <TwoToneLine
      tokens={line2}
      startIndex={line1.length}
      pageStartMs={page.startMs}
      color={accentColor}
      fontFamily={fontFamily}
      fontSize={fittedFontSize}
      allCaps={allCaps}
      textShadow={accentShadow}
      localFrame={localFrame}
      fitFloored={fit.floored}
    /> : null}
            </div>
          </AbsoluteFill>;
  })}
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><TwoTone {...p} /></div>;
};
