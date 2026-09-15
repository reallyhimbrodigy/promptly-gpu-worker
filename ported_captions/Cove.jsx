// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/Cove/Cove.tsx
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

// ../../src/remotion/src/captions/Cove/Cove.tsx
var Cove = ({
  pages,
  fontSize = 76,
  position = "bottom",
  anchor,
  boxedWords = [],
  boxPaddingX = 14,
  boxPaddingY = 8,
  maxWordsPerLine = 4,
  lineGap = 14,
  wordGap = 14
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const currentTimeMs = frame / fps * 1e3;
  const boxedSet = useMemo(
    () => new Set(boxedWords.map((w) => w.toLowerCase())),
    [boxedWords]
  );
  const maxWidth = width * 0.85;
  const anchored = !!anchor;
  let positionStyles;
  if (anchor) {
    positionStyles = {
      position: "absolute",
      left: CAPTION_PADDING.sidesSafe,
      right: CAPTION_PADDING.sidesSafe,
      top: anchor.topPx,
      display: "flex",
      justifyContent: "center"
    };
  } else
    switch (position) {
      case "top":
        positionStyles = {
          position: "absolute",
          left: CAPTION_PADDING.sides,
          top: CAPTION_PADDING.top
        };
        break;
      case "center":
        positionStyles = {
          position: "absolute",
          left: CAPTION_PADDING.sides,
          top: "50%",
          transform: "translateY(-50%)"
        };
        break;
      case "bottom":
      default:
        positionStyles = {
          position: "absolute",
          left: CAPTION_PADDING.sidesSafe,
          right: CAPTION_PADDING.sidesSafe,
          bottom: CAPTION_PADDING.bottomSafe,
          display: "flex",
          justifyContent: "center"
        };
        break;
    }
  return <AbsoluteFill>
      {pages.map((page, pageIndex) => {
    const startFrame = msToFrames(page.startMs, fps);
    const durationFrames = msToFrames(page.durationMs, fps);
    if (durationFrames <= 0) return null;
    const lines = [];
    for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
      lines.push(page.tokens.slice(i, i + maxWordsPerLine));
    }
    const fitBox = position === "bottom" || anchored ? width - 2 * CAPTION_PADDING.sidesSafe : Math.min(maxWidth, width - 2 * CAPTION_PADDING.sides);
    const fit = fitScale(
      page.tokens.map((t) => {
        const boxed = boxedSet.has(t.text.toLowerCase());
        return {
          parts: [
            {
              text: t.text,
              fontSize: boxed ? fontSize * 1.8 : fontSize,
              font: boxed ? {
                fontFamily: CAPTION_FONTS.playfairDisplay,
                fontWeight: 400,
                letterSpacingEm: -0.02
              } : { fontFamily: CAPTION_FONTS.montserrat, fontWeight: 700 }
            }
          ],
          extraPx: boxed ? 2 * boxPaddingX : 0
        };
      }),
      fitBox,
      "Cove"
    );
    return <Sequence
      key={pageIndex}
      from={startFrame}
      durationInFrames={durationFrames}
    >
            <AbsoluteFill>
              <div style={{ ...positionStyles, maxWidth }}>
                <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: lineGap,
        position: "relative"
      }}
    >
                  {lines.map((lineTokens, lineIdx) => {
      return <div
        key={lineIdx}
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "baseline",
          columnGap: wordGap,
          rowGap: lineGap,
          position: "relative",
          zIndex: lineIdx + 1
        }}
      >
                        {lineTokens.map((token, tokenIdx) => {
        const isSpecial = boxedSet.has(
          token.text.toLowerCase()
        );
        const isSpoken = currentTimeMs >= token.fromMs;
        const wordOpacity = isSpoken ? 1 : 0;
        const color = !isSpoken ? "transparent" : isSpecial ? "#F0E8DD" : "#FFFFFF";
        return <span
          key={tokenIdx}
          style={{
            fontFamily: isSpecial ? CAPTION_FONTS.playfairDisplay : CAPTION_FONTS.montserrat,
            fontSize: (isSpecial ? fontSize * 1.8 : fontSize) * fit.scale,
            fontWeight: isSpecial ? 400 : 700,
            fontStyle: isSpecial ? "italic" : "normal",
            letterSpacing: isSpecial ? "-0.02em" : "normal",
            color,
            opacity: wordOpacity,
            lineHeight: isSpecial ? 0.8 : 1,
            whiteSpace: "nowrap",
            display: "inline-block",
            position: "relative",
            ...fit.floored ? CHARWRAP_FALLBACK_STYLE : {},
            padding: isSpecial ? `${boxPaddingY}px ${boxPaddingX}px` : undefined,
            textShadow: !isSpoken ? "none" : isSpecial ? "0 0 12px rgba(255,255,255,0.7), 0 0 28px rgba(255,245,230,0.4), 0 0 50px rgba(255,240,220,0.2), 0 -20px 30px rgba(0,0,0,0.45), 0 -12px 20px rgba(0,0,0,0.35), 0 -6px 10px rgba(0,0,0,0.25), 0 0 6px rgba(0,0,0,0.15)" : "none"
          }}
        >
                              {
          /* Word-shaped blurred shadow biased above */
        }
                              {!isSpecial && isSpoken && <span
          aria-hidden="true"
          style={{
            position: "absolute",
            top: isSpecial ? "-30px" : "-20px",
            left: 0,
            right: 0,
            fontFamily: isSpecial ? CAPTION_FONTS.playfairDisplay : CAPTION_FONTS.montserrat,
            fontSize: (isSpecial ? fontSize * 1.8 : fontSize) * fit.scale,
            fontWeight: isSpecial ? 400 : 700,
            fontStyle: isSpecial ? "italic" : "normal",
            letterSpacing: isSpecial ? "-0.02em" : "normal",
            lineHeight: isSpecial ? 0.8 : 1,
            color: "rgba(0,0,0,0.6)",
            filter: "blur(18px)",
            clipPath: "none",
            pointerEvents: "none",
            zIndex: -1,
            whiteSpace: "nowrap"
          }}
        >
                                  {token.text}
                                </span>}
                              {isSpecial && isSpoken && <span
          style={{
            position: "absolute",
            inset: "-18px -22px",
            borderRadius: "50%",
            background: "radial-gradient(ellipse at center, rgba(255,245,230,0.12) 0%, rgba(255,245,230,0) 70%)",
            pointerEvents: "none",
            zIndex: -1
          }}
        />}
                              {token.text}
                            </span>;
      })}
                      </div>;
    })}
                </div>
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
  return <div style={rootStyle}><Cove {...p} /></div>;
};
