// ── ported prelude: injected globals re-bound ──
const useMemo = React.useMemo;
const createElement = React.createElement;

// ../../src/remotion/src/captions/Gadzhi/Gadzhi.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// ../../src/remotion/src/captions/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
}
function getCurrentTimeMs(frame, fps) {
  return frame / fps * 1e3;
}

// ../../src/remotion/src/captions/shared/fadeTiming.ts
var MAX_ENTRANCE_MS = 80;

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

// ../../src/remotion/src/captions/shared/legibility.ts
var LEGIBILITY_ANCHOR_LAYERS = [
  "0 0 2px rgba(0,0,0,0.75)",
  "0 2px 6px rgba(0,0,0,0.85)"
];
var LEGIBILITY_ANCHOR = LEGIBILITY_ANCHOR_LAYERS.join(", ");

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
function lineWidth(entries, fontSize, font, wordGap, measure) {
  let w = 0;
  for (let i = 0; i < entries.length; i++) {
    if (i > 0) w += wordGap;
    w += measure(entries[i].text, fontSize, font);
  }
  return w;
}
function greedyWrap(words, fontSize, font, wordGap, safeWidth, measure) {
  const lines = [];
  let line = [];
  let w = 0;
  words.forEach((word, tokenIndex) => {
    const ww = measure(word, fontSize, font);
    const extra = line.length > 0 ? wordGap + ww : ww;
    if (line.length > 0 && w + extra > safeWidth) {
      lines.push(line);
      line = [{ tokenIndex, text: word }];
      w = ww;
    } else {
      line.push({ tokenIndex, text: word });
      w += extra;
    }
  });
  if (line.length > 0) lines.push(line);
  return lines;
}
var _graphemeSeg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;
function toGraphemes(word) {
  if (_graphemeSeg) {
    return Array.from(_graphemeSeg.segment(word), (s) => s.segment);
  }
  return Array.from(word);
}
function charwrapWord(word, tokenIndex, fontSize, font, safeWidth, measure) {
  const frags = [];
  let frag = "";
  for (const ch of toGraphemes(word)) {
    const next = frag + ch;
    if (frag.length > 0 && measure(next, fontSize, font) > safeWidth) {
      frags.push({ tokenIndex, text: frag });
      frag = ch;
    } else {
      frag = next;
    }
  }
  if (frag.length > 0) frags.push({ tokenIndex, text: frag });
  return frags;
}
function fitsWithin(lines, fontSize, font, wordGap, safeWidth, measure) {
  return lines.every(
    (l) => lineWidth(l, fontSize, font, wordGap, measure) <= safeWidth
  );
}
function widestLine(lines, fontSize, font, wordGap, measure) {
  let max = 0;
  for (const l of lines) {
    const w = lineWidth(l, fontSize, font, wordGap, measure);
    if (w > max) max = w;
  }
  return max;
}
var _loggedPages = /* @__PURE__ */ new Set();
function fitPage(req, styleName, measure = canvasMeasurer) {
  const { words, baseFontSize, font, wordGap, maxLines } = req;
  const safeWidth = Math.min(req.availableWidth, SAFE_TEXT_WIDTH);
  const pageText = words.join(" ");
  const finish = (lines2, fontSize, action) => {
    let measuredWidth = widestLine(lines2, fontSize, font, wordGap, measure);
    let scale = fontSize / baseFontSize;
    if (measuredWidth > safeWidth + 0.5) {
      const strict = typeof globalThis !== "undefined" && globalThis.REMOTION_FIT_STRICT;
      const msg = `[caption-fit] INVARIANT VIOLATION style=${styleName} page="${pageText}" measured=${measuredWidth.toFixed(1)} safe=${safeWidth}`;
      if (strict) throw new Error(msg);
      console.error(msg);
      const clamp = safeWidth / measuredWidth;
      fontSize = fontSize * clamp;
      scale = fontSize / baseFontSize;
      measuredWidth = widestLine(lines2, fontSize, font, wordGap, measure);
    }
    if (action !== "none") {
      const logKey = `${styleName}|${pageText}|${action}|${scale.toFixed(2)}`;
      if (!_loggedPages.has(logKey)) {
        _loggedPages.add(logKey);
        const detail = action === "scale" ? `scale(${scale.toFixed(2)})` : action;
        console.log(
          `[caption-fit] style=${styleName} page="${pageText}" action=${detail}`
        );
      }
    }
    return { lines: lines2, fontSize, scale, action, safeWidth, measuredWidth };
  };
  const perLine = req.preferredWordsPerLine && req.preferredWordsPerLine > 0 ? req.preferredWordsPerLine : words.length;
  const preferred = [];
  for (let i = 0; i < words.length; i += perLine) {
    preferred.push(
      words.slice(i, i + perLine).map((text, j) => ({ tokenIndex: i + j, text }))
    );
  }
  if (preferred.length <= maxLines && fitsWithin(preferred, baseFontSize, font, wordGap, safeWidth, measure)) {
    return finish(preferred, baseFontSize, "none");
  }
  const rewrapped = greedyWrap(words, baseFontSize, font, wordGap, safeWidth, measure);
  if (rewrapped.length <= maxLines && fitsWithin(rewrapped, baseFontSize, font, wordGap, safeWidth, measure)) {
    return finish(rewrapped, baseFontSize, "wrap");
  }
  let lo = MIN_FIT_SCALE;
  let hi = 1;
  let best = null;
  for (let iter = 0; iter < 10; iter++) {
    const mid = (lo + hi) / 2;
    const size = baseFontSize * mid;
    const attempt = greedyWrap(words, size, font, wordGap, safeWidth, measure);
    const ok = attempt.length <= maxLines && fitsWithin(attempt, size, font, wordGap, safeWidth, measure);
    if (ok) {
      best = { lines: attempt, scale: mid };
      lo = mid;
    } else {
      hi = mid;
    }
  }
  if (best) {
    return finish(best.lines, baseFontSize * best.scale, "scale");
  }
  const floorSize = baseFontSize * MIN_FIT_SCALE;
  const pieces = [];
  words.forEach((word, tokenIndex) => {
    if (measure(word, floorSize, font) > safeWidth) {
      pieces.push(...charwrapWord(word, tokenIndex, floorSize, font, safeWidth, measure));
    } else {
      pieces.push({ tokenIndex, text: word });
    }
  });
  const lines = [];
  let line = [];
  let w = 0;
  for (const piece of pieces) {
    const ww = measure(piece.text, floorSize, font);
    const extra = line.length > 0 ? wordGap + ww : ww;
    if (line.length > 0 && w + extra > safeWidth) {
      lines.push(line);
      line = [piece];
      w = ww;
    } else {
      line.push(piece);
      w += extra;
    }
  }
  if (line.length > 0) lines.push(line);
  const didSplit = pieces.length > words.length;
  return finish(lines, floorSize, didSplit ? "charwrap" : "scale");
}

// ../../src/remotion/src/captions/Gadzhi/Gadzhi.tsx
var SHADOW = `${LEGIBILITY_ANCHOR}, 0 2px 8px rgba(0,0,0,0.5), 0 4px 20px rgba(0,0,0,0.3)`;
var SLIDE_FRAMES_NORMAL = 10;
var SLIDE_FRAMES_KEYWORD = 16;
var SLIDE_DISTANCE_NORMAL = 35;
var SLIDE_DISTANCE_KEYWORD = 50;
var GadzhiStylePage = ({
  tokens,
  pageStartMs,
  fontSize,
  textColor,
  highlightColor,
  keywordSet,
  maxWordsPerLine,
  wordGap
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const currentTimeMs = getCurrentTimeMs(frame, fps) + pageStartMs;
  const fit = useMemo(
    () => fitPage(
      {
        words: tokens.map((t) => t.text),
        baseFontSize: fontSize,
        font: {
          fontFamily: CAPTION_FONTS.montserrat,
          fontWeight: 700,
          letterSpacingEm: 0.02,
          uppercase: true
        },
        wordGap,
        preferredWordsPerLine: maxWordsPerLine,
        maxLines: Math.max(Math.ceil(tokens.length / Math.max(maxWordsPerLine, 1)), 2) + 1,
        // Gadzhi's own box: 85% of canvas, inside 80px side paddings.
        availableWidth: Math.min(width * 0.85, width - 160)
      },
      "Gadzhi"
    ),
    [tokens, fontSize, wordGap, maxWordsPerLine, width]
  );
  return <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-start",
      gap: 4
    }}
  >
      {fit.lines.map((lineEntries, lineIdx) => <div
    key={lineIdx}
    style={{
      display: "flex",
      alignItems: "baseline",
      gap: wordGap
    }}
  >
          {lineEntries.map((entry, wi) => {
    const token = tokens[entry.tokenIndex];
    const isSpoken = currentTimeMs >= token.fromMs;
    const isKw = isKeyword(token.text, keywordSet);
    const finalColor = isKw ? highlightColor : textColor;
    const slideDuration = Math.min(
      isKw ? SLIDE_FRAMES_KEYWORD : SLIDE_FRAMES_NORMAL,
      Math.max(1, msToFrames(MAX_ENTRANCE_MS, fps))
    );
    const slideDist = isKw ? SLIDE_DISTANCE_KEYWORD : SLIDE_DISTANCE_NORMAL;
    const wordEntryFrame = msToFrames(token.fromMs - pageStartMs, fps);
    const elapsed = frame - wordEntryFrame;
    const yOffset = 0;
    const opacity = 1;
    const color = finalColor;
    return <span
      key={wi}
      style={{
        display: "inline-block",
        fontFamily: CAPTION_FONTS.montserrat,
        fontSize: fit.fontSize,
        fontWeight: 700,
        color,
        textTransform: "uppercase",
        letterSpacing: "0.02em",
        lineHeight: 1.05,
        whiteSpace: "nowrap",
        textShadow: SHADOW,
        opacity: isSpoken ? opacity : 0,
        transform: isSpoken ? `translateY(${yOffset}px)` : `translateY(${slideDist}px)`,
        visibility: isSpoken ? "visible" : "hidden"
      }}
    >
                {entry.text}
              </span>;
  })}
        </div>)}
    </div>;
};
var GadzhiStyle = ({
  pages,
  fontSize = 90,
  position = "bottom",
  anchor,
  textColor = "#FFFFFF",
  highlightColor = "#F5C518",
  keywords = [],
  maxWordsPerLine = 2,
  wordGap = 14
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  return <AbsoluteFill>
      {pages.map((page, pageIndex) => {
    const startFrame = msToFrames(page.startMs, fps);
    const durationFrames = msToFrames(page.durationMs, fps);
    if (durationFrames <= 0) return null;
    return <Sequence
      key={pageIndex}
      from={startFrame}
      durationInFrames={durationFrames}
    >
            <AbsoluteFill
      style={{
        display: "flex",
        // SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): a per-page
        // anchor top-pins the block at `topPx`; absent → the fixed-slot
        // branches below run byte-identically.
        justifyContent: anchor ? "flex-start" : position === "top" ? "flex-start" : position === "center" ? "center" : "flex-end",
        alignItems: "flex-start",
        ...anchor ? { paddingTop: anchor.topPx, paddingLeft: 80, paddingRight: 80 } : position === "top" ? { paddingTop: CAPTION_PADDING.top, paddingLeft: 80, paddingRight: 80 } : position === "center" ? { paddingLeft: 80, paddingRight: 80 } : { paddingLeft: 80, paddingRight: 80, paddingBottom: 300 }
      }}
    >
              <div style={{ maxWidth, width: "100%" }}>
              <GadzhiStylePage
      tokens={page.tokens}
      pageStartMs={page.startMs}
      fontSize={fontSize}
      textColor={textColor}
      highlightColor={highlightColor}
      keywordSet={keywordSet}
      maxWordsPerLine={maxWordsPerLine}
      wordGap={wordGap}
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
  return <div style={rootStyle}><Gadzhi {...p} /></div>;
};
