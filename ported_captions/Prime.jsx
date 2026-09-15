// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/Prime/Prime.tsx
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

// ../../src/remotion/src/captions/Prime/Prime.tsx
var PrimeWord = ({
  token,
  pageStartMs,
  wordIndex,
  windowMs,
  isLine2,
  isSpecial,
  line1Color,
  line2Color,
  line1FontSize,
  line2FontSize,
  line1FontWeight,
  line2FontWeight,
  fontFamily,
  specialFontFamily,
  specialColor,
  letterSpacing,
  textShadow,
  fitFloored
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const activateFrame = Math.round((token.fromMs - pageStartMs) / 1e3 * fps);
  const slideY = 0;
  const wordOpacity = frame >= activateFrame ? 1 : 0;
  const color = isSpecial ? specialColor : line1Color;
  const fontSize = isSpecial ? line2FontSize : isLine2 ? line2FontSize : line1FontSize;
  const fontWeightVal = isLine2 ? line2FontWeight : line1FontWeight;
  return <span
    style={{
      display: "inline-block",
      fontFamily: isSpecial ? specialFontFamily : fontFamily,
      fontSize,
      fontWeight: isSpecial ? 600 : fontWeightVal,
      fontStyle: isSpecial ? "italic" : "normal",
      color,
      letterSpacing,
      lineHeight: 1.1,
      textShadow,
      textTransform: "lowercase",
      whiteSpace: "nowrap",
      transform: `translateY(${slideY}px)`,
      opacity: wordOpacity,
      marginRight: 12,
      // F4 last resort: below the fit floor, let the glyph run break
      // rather than ever cross a margin.
      ...fitFloored ? CHARWRAP_FALLBACK_STYLE : {}
    }}
  >
      {token.text}
    </span>;
};
var PrimePage = ({
  page,
  maxWordsPerLine,
  lineGap,
  specialWords,
  ...wordProps
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const isSpecial = (text) => specialWords.some((w) => w.toLowerCase() === text.toLowerCase());
  const lines = [];
  let buffer = [];
  for (const token of page.tokens) {
    if (isSpecial(token.text)) {
      if (buffer.length > 0) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
      lines.push({ tokens: [token], hasSpecial: true });
    } else {
      buffer.push(token);
      if (buffer.length >= maxWordsPerLine) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
    }
  }
  if (buffer.length > 0) {
    lines.push({ tokens: buffer, hasSpecial: false });
  }
  const fit = useMemo(() => {
    let normalCount = 0;
    const items = lines.map((line) => {
      const isL2 = !line.hasSpecial && normalCount++ >= 1;
      return {
        parts: line.tokens.map((t) => ({
          text: t.text,
          fontSize: line.hasSpecial ? wordProps.line2FontSize * 2 : isL2 ? wordProps.line2FontSize : wordProps.line1FontSize,
          font: {
            fontFamily: line.hasSpecial ? wordProps.specialFontFamily : wordProps.fontFamily,
            fontWeight: line.hasSpecial ? 600 : isL2 ? wordProps.line2FontWeight : wordProps.line1FontWeight,
            letterSpacingEm: 0.01,
            lowercase: true
            // PrimeWord renders textTransform:"lowercase"
          }
        })),
        extraPx: 12 * line.tokens.length
        // marginRight 12 on every word
      };
    });
    return fitScale(items, width * 0.85, "Prime");
  }, [page, specialWords, width]);
  if (frame < 0) return null;
  const pageLocalMs = frame / fps * 1e3;
  const pageFadeOutMs = boundedFade(120, page.durationMs);
  const fadeOut = interpolate(
    pageLocalMs,
    [page.durationMs - pageFadeOutMs, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  let globalWordIdx = 0;
  return <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      opacity: fadeOut
    }}
  >
      {(() => {
    let normalLineCount = 0;
    return lines.map((line, lineIdx) => {
      const isLine2 = !line.hasSpecial && normalLineCount++ >= 1;
      return <div
        key={lineIdx}
        style={{
          display: "flex",
          alignItems: "baseline",
          marginTop: lineIdx > 0 ? lineGap : 0,
          ...line.hasSpecial ? { justifyContent: "center" } : {},
          ...fit.floored ? { flexWrap: "wrap", justifyContent: "center" } : {}
        }}
      >
            {line.tokens.map((token, idx) => {
        const wi = globalWordIdx++;
        const specialMul = line.hasSpecial ? 2 : 1;
        const nextTok = page.tokens[wi + 1];
        const windowMs = (nextTok ? nextTok.fromMs : page.startMs + page.durationMs) - token.fromMs;
        return <PrimeWord
          key={idx}
          token={token}
          pageStartMs={page.startMs}
          wordIndex={wi}
          windowMs={windowMs}
          isLine2={isLine2}
          isSpecial={line.hasSpecial}
          {...wordProps}
          line2FontSize={wordProps.line2FontSize * specialMul * fit.scale}
          line1FontSize={wordProps.line1FontSize * specialMul * fit.scale}
          fitFloored={fit.floored}
        />;
      })}
          </div>;
    });
  })()}
    </div>;
};
var Prime = ({
  pages,
  fontFamily = CAPTION_FONTS.inter,
  position = "bottom",
  anchor,
  line1Color = "#FFFFFF",
  line2Color = "#3BA5FF",
  line1FontSize = 52,
  line2FontSize = 66,
  line1FontWeight = 600,
  line2FontWeight = 800,
  maxWordsPerLine = 3,
  letterSpacing = "0.01em",
  // Positive gap so the oversized italic "break-out" keyword line and the
  // regular sans line below it don't visibly overlap. Prior value of -30
  // pulled them on top of each other on long keywords.
  lineGap = 12,
  textShadow = "0 2px 8px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.4)",
  specialWords = [],
  specialFontFamily = CAPTION_FONTS.playfairDisplay,
  specialColor = "#5ED4E8"
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
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
    >
            <div
      style={{
        position: "absolute",
        left: "50%",
        maxWidth,
        // SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): a per-page
        // anchor pins the block top at `topPx` (still horizontally
        // centred via translateX). Absent → fixed-slot branches below run
        // byte-identically.
        ...anchor ? { top: anchor.topPx, transform: "translateX(-50%)" } : position === "top" ? { top: CAPTION_PADDING.top, transform: "translateX(-50%)" } : position === "center" ? { top: "50%", transform: "translate(-50%, -50%)" } : { bottom: CAPTION_PADDING.bottomSafe, transform: "translateX(-50%)" }
      }}
    >
              <PrimePage
      page={page}
      maxWordsPerLine={maxWordsPerLine}
      lineGap={lineGap}
      specialWords={specialWords}
      line1Color={line1Color}
      line2Color={line2Color}
      line1FontSize={line1FontSize}
      line2FontSize={line2FontSize}
      line1FontWeight={line1FontWeight}
      line2FontWeight={line2FontWeight}
      fontFamily={fontFamily}
      specialFontFamily={specialFontFamily}
      specialColor={specialColor}
      letterSpacing={letterSpacing}
      textShadow={textShadow}
    />
            </div>
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
  return <div style={rootStyle}><Prime {...p} /></div>;
};
