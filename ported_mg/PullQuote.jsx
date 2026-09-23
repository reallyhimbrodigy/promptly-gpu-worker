// ── ported prelude: injected globals re-bound ──
const interpolate2 = interpolate;
const useContext = React.useContext;
const useMemo = React.useMemo;
const createContext = React.createContext;

// src/motion-graphics/PullQuote/PullQuote.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// gfont:@remotion/google-fonts/Inter
var loadFont = () => ({ fontFamily: "Inter" });

// gfont:@remotion/google-fonts/Anton
var loadFont2 = () => ({ fontFamily: "Anton" });

// gfont:@remotion/google-fonts/DMSerifDisplay
var loadFont3 = () => ({ fontFamily: "DMSerifDisplay" });

// gfont:@remotion/google-fonts/PlayfairDisplay
var loadFont4 = () => ({ fontFamily: "PlayfairDisplay" });

// gfont:@remotion/google-fonts/CaveatBrush
var loadFont5 = () => ({ fontFamily: "CaveatBrush" });

// gfont:@remotion/google-fonts/Oswald
var loadFont6 = () => ({ fontFamily: "Oswald" });

// gfont:@remotion/google-fonts/Roboto
var loadFont7 = () => ({ fontFamily: "Roboto" });

// gfont:@remotion/google-fonts/JetBrainsMono
var loadFont8 = () => ({ fontFamily: "JetBrainsMono" });

// gfont:@remotion/google-fonts/NotoSansDevanagari
var loadFont9 = () => ({ fontFamily: "NotoSansDevanagari" });

// gfont:@remotion/google-fonts/NotoSansBengali
var loadFont10 = () => ({ fontFamily: "NotoSansBengali" });

// gfont:@remotion/google-fonts/NotoSansTelugu
var loadFont11 = () => ({ fontFamily: "NotoSansTelugu" });

// gfont:@remotion/google-fonts/NotoSansArabic
var loadFont12 = () => ({ fontFamily: "NotoSansArabic" });

// src/motion-graphics/shared/fonts.ts
var SUBSETS = ["latin", "latin-ext"];
var inter = loadFont("normal", { weights: ["400", "500", "600", "700", "800", "900"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var anton = loadFont2("normal", { weights: ["400"], subsets: [...SUBSETS] });
var dmSerifDisplay = loadFont3("normal", { weights: ["400"], subsets: [...SUBSETS] });
var playfairDisplay = loadFont4("normal", { weights: ["400", "700"], subsets: [...SUBSETS] });
var caveatBrush = loadFont5("normal", { weights: ["400"], subsets: [...SUBSETS] });
var oswald = loadFont6("normal", { weights: ["400", "600", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var roboto = loadFont7("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var jetBrainsMono = loadFont8("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS] });
var notoSansDevanagari = loadFont9("normal", { weights: ["400", "700"], subsets: ["devanagari", "latin"] });
var notoSansBengali = loadFont10("normal", { weights: ["400", "700"], subsets: ["bengali", "latin"] });
var notoSansTelugu = loadFont11("normal", { weights: ["400", "700"], subsets: ["telugu", "latin"] });
var notoSansArabic = loadFont12("normal", { weights: ["400", "700"], subsets: ["arabic"] });
var MG_FONTS = {
  inter: inter.fontFamily,
  anton: anton.fontFamily,
  dmSerifDisplay: dmSerifDisplay.fontFamily,
  playfairDisplay: playfairDisplay.fontFamily,
  caveatBrush: caveatBrush.fontFamily,
  oswald: oswald.fontFamily,
  roboto: roboto.fontFamily,
  jetBrainsMono: jetBrainsMono.fontFamily,
  notoSansDevanagari: notoSansDevanagari.fontFamily,
  notoSansBengali: notoSansBengali.fontFamily,
  notoSansTelugu: notoSansTelugu.fontFamily,
  notoSansArabic: notoSansArabic.fontFamily
};

// src/motion-graphics/shared/ink.ts
function relativeLuminance(color) {
  let r = 0, g = 0, b = 0;
  const hex = color.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  const fn = color.match(/^rgba?\(([^)]+)\)$/i);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    r = parseInt(h.slice(0, 2), 16);
    g = parseInt(h.slice(2, 4), 16);
    b = parseInt(h.slice(4, 6), 16);
  } else if (fn) {
    const parts = fn[1].split(",").map((p) => parseFloat(p));
    [r, g, b] = [parts[0] || 0, parts[1] || 0, parts[2] || 0];
  } else {
    return 0;
  }
  const lin = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function inkFor(surface, dark = "#15151E", light = "#FFFFFF") {
  return relativeLuminance(surface) > 0.5 ? dark : light;
}

// src/motion-graphics/shared/text-script.ts
var RANGES = [
  ["devanagari", /[ऀ-ॿ]/],
  ["bengali", /[ঀ-৿]/],
  ["telugu", /[ఀ-౿]/],
  ["arabic", /[؀-ۿݐ-ݿ]/],
  ["cyrillic", /[Ѐ-ӿ]/],
  ["cjk", /[一-鿿぀-ヿ가-힯]/]
];
function detectScript(text) {
  for (const [script, re] of RANGES) {
    if (re.test(text)) return script;
  }
  return "latin";
}
var CYRILLIC_CAPABLE = /* @__PURE__ */ new Set(["inter", "oswald", "roboto"]);
var SCRIPT_FACE_KEY = {
  devanagari: "notoSansDevanagari",
  bengali: "notoSansBengali",
  telugu: "notoSansTelugu",
  arabic: "notoSansArabic"
};
function routeFaceKey(text, preferredKey) {
  const script = detectScript(text);
  if (script === "cyrillic" && !CYRILLIC_CAPABLE.has(preferredKey)) {
    return "oswald";
  }
  return SCRIPT_FACE_KEY[script] ?? preferredKey;
}
function mgTextMetrics(text) {
  const script = detectScript(text);
  const nonLatin = script !== "latin";
  return {
    script,
    lineHeight: nonLatin ? 1.3 : 1,
    uppercaseSafe: !nonLatin,
    advanceEm: script === "latin" ? 0.62 : 0.42
  };
}

// src/motion-graphics/shared/text-font.ts
var EMOJI_TAIL = "'Noto Color Emoji', sans-serif";
function mgTextFont(text, preferred = "inter") {
  const key = routeFaceKey(text, preferred);
  const base = MG_FONTS[key] ?? MG_FONTS[preferred];
  return `${base}, ${EMOJI_TAIL}`;
}

// src/shared/safeZone.ts
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

// src/motion-graphics/shared/positioning.ts
var ANCHOR_FLEX = {
  center: { alignItems: "center", justifyContent: "center" },
  top: { alignItems: "flex-start", justifyContent: "center" },
  bottom: { alignItems: "flex-end", justifyContent: "center" },
  left: { alignItems: "center", justifyContent: "flex-start" },
  right: { alignItems: "center", justifyContent: "flex-end" },
  "top-left": { alignItems: "flex-start", justifyContent: "flex-start" },
  "top-right": { alignItems: "flex-start", justifyContent: "flex-end" },
  "bottom-left": { alignItems: "flex-end", justifyContent: "flex-start" },
  "bottom-right": { alignItems: "flex-end", justifyContent: "flex-end" }
};
var ANCHOR_ORIGIN = {
  center: "center",
  top: "top center",
  bottom: "bottom center",
  left: "center left",
  right: "center right",
  "top-left": "top left",
  "top-right": "top right",
  "bottom-left": "bottom left",
  "bottom-right": "bottom right"
};
var clampNum = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
function clampOffsetForAnchor(anchor, dx, dy) {
  const halfW = SAFE_RECT.width / 2;
  const halfH = SAFE_RECT.height / 2;
  const isTop = anchor === "top" || anchor === "top-left" || anchor === "top-right";
  const isBottom = anchor === "bottom" || anchor === "bottom-left" || anchor === "bottom-right";
  const isLeft = anchor === "left" || anchor === "top-left" || anchor === "bottom-left";
  const isRight = anchor === "right" || anchor === "top-right" || anchor === "bottom-right";
  if (isTop) dy = clampNum(dy, 0, halfH);
  else if (isBottom) dy = clampNum(dy, -halfH, 0);
  else dy = clampNum(dy, -halfH, halfH);
  if (isLeft) dx = clampNum(dx, 0, halfW);
  else if (isRight) dx = clampNum(dx, -halfW, 0);
  else dx = clampNum(dx, -halfW, halfW);
  return { dx, dy };
}
var MG_POSITION_CONFIG = {
  // Horizontal center is the DEFAULT for every resolver type (see above), so the
  // text/number/UI cards (StatCard, ChatThread, ProgressBar, TweetBubble,
  // InstagramComment, IMessageBubble, TikTokComment) need no entry. Only the
  // exceptions are listed.
  Notification: { topExempt: true }
};
var NOTIFICATION_TOP_INSET = 0;
function resolveMGPosition(props, defaults = {}, mgType) {
  const cfg = mgType && MG_POSITION_CONFIG[mgType] || {};
  const anchor = props?.anchor ?? defaults.anchor ?? "center";
  const rawOffsetX = props?.offsetX ?? defaults.offsetX ?? 0;
  const rawOffsetY = props?.offsetY ?? defaults.offsetY ?? 0;
  const scale = clampNum(props?.scale ?? 1, 0.1, 1);
  const { dx: clampedX, dy: clampedY } = clampOffsetForAnchor(
    anchor,
    rawOffsetX,
    rawOffsetY
  );
  const offsetX = cfg.freeHorizontal ? clampedX : 0;
  const offsetY = clampedY;
  const flex = ANCHOR_FLEX[anchor];
  const transformOrigin = ANCHOR_ORIGIN[anchor];
  const justifyContent = cfg.freeHorizontal ? flex.justifyContent : "center";
  const alignItems = cfg.topExempt ? "flex-start" : flex.alignItems;
  const paddingTop = cfg.topExempt ? NOTIFICATION_TOP_INSET : TIKTOK_SAFE_TOP;
  const paddingBottom = cfg.topExempt ? 0 : TIKTOK_SAFE_BOTTOM;
  const paddingLeft = cfg.topExempt ? 0 : cfg.freeHorizontal ? TIKTOK_SAFE_SIDE : TIKTOK_SAFE_RIGHT;
  const maxWidth = cfg.topExempt ? CANVAS_WIDTH - TIKTOK_SAFE_RIGHT : cfg.freeHorizontal ? SAFE_RECT.width : CANVAS_WIDTH - 2 * TIKTOK_SAFE_RIGHT;
  return {
    containerStyle: {
      display: "flex",
      // Force row layout — AbsoluteFill defaults to column, which would
      // swap the meaning of alignItems/justifyContent. Row keeps the mental
      // model simple: justifyContent = horizontal, alignItems = vertical.
      flexDirection: "row",
      alignItems,
      justifyContent,
      // (1) The padded content box IS the TikTok-safe rect (topExempt types
      // override top/bottom/left to sit at the true top, full-width). box-
      // sizing keeps the padding inside the 1080×1920 AbsoluteFill. No
      // overflow:hidden — it would clip slide-in/out animations.
      boxSizing: "border-box",
      paddingTop,
      paddingRight: TIKTOK_SAFE_RIGHT,
      paddingBottom,
      paddingLeft
    },
    wrapperStyle: {
      // (3) Bound the component so a wide or tall card cannot overflow even
      // when correctly anchored.
      maxWidth,
      maxHeight: SAFE_RECT.height,
      // D4 (Zac's render verdict, 2026-07-11): the wrapper was a plain BLOCK
      // div — a fixed-width child wider than maxWidth overflowed RIGHTWARD
      // (ProgressBar width 860 > 680 → its bar rendered [200,1055], center
      // dragged to ~630). A centering flex column makes oversize overflow
      // SYMMETRIC: the structural center holds for EVERY component, not just
      // the ones whose widths happen to fit. freeHorizontal/topExempt types
      // keep their own layouts.
      ...cfg.freeHorizontal || cfg.topExempt ? {} : {
        display: "flex",
        flexDirection: "column",
        alignItems: "center"
      },
      transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
      transformOrigin
    }
  };
}

// src/motion-graphics/shared/useMGPhase.ts
// [ported] import removed — ChatCut injects these: remotion
// src/motion-graphics/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
}

// src/motion-graphics/shared/smooth-graphics-flag.tsx
// [ported] import removed — ChatCut injects these: react
var SmoothGraphicsContext = createContext(false);
var useSmoothGraphics = () => useContext(SmoothGraphicsContext);

// src/zoom/shared/velocity-cap.ts
var MIN_BLEND_FRACTION = 0.5;
var SKEW_NEUTRAL = 0.5;
function trapezoidEasing(blend, skew = SKEW_NEUTRAL) {
  const b = Math.min(Math.max(blend, 0), 1);
  if (b <= 0) return (t) => Math.min(Math.max(t, 0), 1);
  const w = Math.min(Math.max(skew, 0.05), 0.95);
  const bIn = b * w;
  const bOut = b * (1 - w);
  const k = 1 / (1 - b / 2);
  return (tRaw) => {
    const t = Math.min(Math.max(tRaw, 0), 1);
    if (t < bIn) {
      const x2 = t / bIn;
      return k * bIn * (x2 ** 3 - 0.5 * x2 ** 4);
    }
    if (t <= 1 - bOut) {
      return k * (bIn * 0.5 + (t - bIn));
    }
    const x = (1 - t) / bOut;
    return 1 - k * bOut * (x ** 3 - 0.5 * x ** 4);
  };
}

// src/motion-graphics/shared/mg-phase-frames.ts
function resolveMGPhaseFrames({
  localFrame,
  durationFrames,
  enterFrames,
  exitFrames
}) {
  const exitStartFrame = durationFrames - exitFrames;
  const effectiveEnterFrames = Math.min(
    enterFrames,
    Math.max(1, exitStartFrame - 1)
  );
  const visible = localFrame >= -2 && localFrame <= durationFrames + 2;
  let phase;
  if (localFrame < 0) phase = "before";
  else if (localFrame < effectiveEnterFrames) phase = "entering";
  else if (localFrame < exitStartFrame) phase = "holding";
  else if (localFrame < durationFrames) phase = "exiting";
  else phase = "after";
  return { visible, phase, exitStartFrame, effectiveEnterFrames };
}

// src/motion-graphics/shared/useMGPhase.ts
var _REF_FPS = 30;
var _ENTER_FLOOR_MS = 400;
var _EXIT_FLOOR_MS = 350;
var _framesToFlooredMs = (f, floorMs) => Math.max(floorMs, f / _REF_FPS * 1e3);
function useMGPhase(timing, { defaultEnterFrames, defaultExitFrames }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const smooth = useSmoothGraphics();
  const startFrame = msToFrames(timing.startMs, fps);
  const durationFrames = msToFrames(timing.durationMs, fps);
  const rawEnterFrames = timing.enterFrames ?? defaultEnterFrames;
  const rawExitFrames = timing.exitFrames ?? defaultExitFrames;
  const enterFrames = smooth ? msToFrames(_framesToFlooredMs(rawEnterFrames, _ENTER_FLOOR_MS), fps) : rawEnterFrames;
  const exitFrames = smooth ? msToFrames(_framesToFlooredMs(rawExitFrames, _EXIT_FLOOR_MS), fps) : rawExitFrames;
  const localFrame = frame - startFrame;
  const { visible, phase, exitStartFrame, effectiveEnterFrames } = resolveMGPhaseFrames({ localFrame, durationFrames, enterFrames, exitFrames });
  const enterProgress = interpolate(
    localFrame,
    [0, effectiveEnterFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // TRAPEZOID, not ease-out cubic. Measured: ease-out cubic peaks at 3x the
      // linear average ON THE FIRST FRAME, so it made its one consumer
      // (PillMarquee) step WORSE, 0.30 -> 0.41 peak_step. Same finding as the
      // zoom cap, same fix — one profile for all motion in this codebase.
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.25) : undefined
    }
  );
  const exitProgress = interpolate(
    localFrame,
    [exitStartFrame, durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // Departure: the same bounded-velocity profile, skewed late so the exit
      // accelerates away rather than crawling off.
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.75) : undefined
    }
  );
  return {
    visible,
    enterProgress,
    exitProgress,
    phase,
    localFrame,
    durationFrames,
    exitStartFrame
  };
}

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/PullQuote/PullQuote.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
var SIDE_INSET = 90;
var TOP_SAFE = 220;
var TEXT_MAX_WIDTH = 1080 - 2 * SIDE_INSET;
var TEXT_MAX_HEIGHT = 1920 - 2 * TOP_SAFE;
var MIN_FONT = 64;
var MAX_FONT = 320;
var DEFAULT_TEXT_SHADOW = "0 2px 8px rgba(0,0,0,0.6), 0 8px 30px rgba(0,0,0,0.45), 0 0 2px rgba(0,0,0,0.5)";
var CHAR_RATIO = {
  anton: 0.52,
  oswald: 0.55,
  inter: 0.56,
  roboto: 0.56,
  dmSerifDisplay: 0.5,
  playfairDisplay: 0.5
};
var normalize = (w) => w.replace(/[^\p{L}\p{N}]/gu, "").toLocaleLowerCase();
var PullQuote = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  text,
  keywords = [],
  textColor = "#FFFFFF",
  keywordColor,
  accentColor,
  fontKey = "anton",
  fontSize = 150,
  maxWordsPerLine = 3,
  highlightStyle = "color",
  keywordScale = 1.18,
  barColor,
  highlightTextColor,
  align = "center",
  uppercase = true,
  wordStagger = 6,
  wordReveal = 16,
  blurIn = true,
  showQuoteMark = false,
  quoteMarkColor,
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" }
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 40, defaultExitFrames: 30 }
  );
  const resolvedKeywordColor = keywordColor ?? accentColor ?? "#FFD60A";
  const resolvedBarColor = barColor ?? resolvedKeywordColor;
  const resolvedQuoteColor = quoteMarkColor ?? resolvedKeywordColor;
  const resolvedHighlightInk = highlightTextColor ?? (resolvedBarColor === "#FFD60A" ? "#0A0A0A" : inkFor(resolvedBarColor, "#0A0A0A"));
  const keywordSet = useMemo(
    // Empty normalizations are dropped: a keyword that reduces to "" (pure
    // punctuation) must not become a match-everything member — the residual
    // tail of the audited silent-deletion defect.
    () => new Set(keywords.map(normalize).filter(Boolean)),
    [keywords]
  );
  const words = useMemo(
    () => asText(text).trim().split(/\s+/).filter(Boolean),
    [text]
  );
  if (!visible) return null;
  if (words.length === 0) return null;
  const effStyle = highlightStyle === "bar" || highlightStyle === "scale" ? highlightStyle : "color";
  const isKw = (w) => keywordSet.has(normalize(w));
  const kwCount = words.filter(isKw).length;
  const suppressSize = words.length > 0 && kwCount / words.length > 0.6;
  const effKeywordScale = suppressSize ? 1 : keywordScale;
  const lines = [];
  if (maxWordsPerLine == null) {
    lines.push(words);
  } else {
    const m = Math.max(1, maxWordsPerLine);
    for (let i = 0; i < words.length; i += m) lines.push(words.slice(i, i + m));
  }
  const quoteText = words.join(" ");
  const quoteFont = mgTextFont(quoteText, fontKey);
  const quoteMetrics = mgTextMetrics(quoteText);
  const ratio = quoteMetrics.script === "latin" ? CHAR_RATIO[fontKey] : quoteMetrics.advanceEm;
  let maxWeight = 0;
  for (const line of lines) {
    let w = 0;
    for (const word of line) w += word.length * (isKw(word) ? effKeywordScale : 1);
    w += (line.length - 1) * 0.3;
    maxWeight = Math.max(maxWeight, w);
  }
  const widthFit = TEXT_MAX_WIDTH * 0.96 / (Math.max(1, maxWeight) * ratio);
  const heightFit = TEXT_MAX_HEIGHT / (lines.length * 1.04);
  const finalFontSize = clamp(
    Math.min(fontSize, widthFit, heightFit),
    MIN_FONT,
    MAX_FONT
  );
  const N = words.length;
  const effStagger = Math.max(
    0,
    Math.min(wordStagger, (74 - wordReveal) / Math.max(1, N - 1))
  );
  const lastIdx = lines.length - 1;
  const lastWeight = lines[lastIdx].reduce((acc, w2) => acc + w2.length * (isKw(w2) ? effKeywordScale : 1), 0) + (lines[lastIdx].length - 1) * 0.3;
  const payoffScale = lines.length > 1 ? Math.max(1, Math.min(2.8, TEXT_MAX_WIDTH * 0.98 / (Math.max(1, lastWeight) * ratio * finalFontSize))) : 1;
  const RISE = finalFontSize * 0.3;
  const BLUR0 = 12;
  const exitY = -22 * exitProgress;
  const exitScale = 1 - 0.06 * exitProgress;
  const exitBlur = 16 * exitProgress;
  const exitOpacity = interpolate2(exitProgress, [0, 0.94], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const quoteOpacity = interpolate2(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const quoteScale = interpolate2(localFrame, [0, 18], [0.5, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack
  });
  const quoteRise = interpolate2(localFrame, [0, 16], [RISE * 0.5, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const flexAlign = align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center";
  let gi = -1;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      position: "relative",
      maxWidth: TEXT_MAX_WIDTH,
      display: "flex",
      flexDirection: "column",
      alignItems: flexAlign,
      // §4 interlock: adjacent display lines tuck slightly (was +0.06em
      // of air) so ascenders/descenders interleave like a composed title
      // card. lineHeight 0.95 keeps every glyph fully legible.
      gap: -finalFontSize * 0.025,
      transform: `translateY(${exitY}px) scale(${exitScale})`,
      transformOrigin: "center",
      opacity: exitOpacity,
      filter: exitBlur > 0.05 ? `blur(${exitBlur}px)` : undefined
    }}
  >
          {showQuoteMark ? <div
    style={{
      position: "absolute",
      top: -finalFontSize * 0.62,
      left: -finalFontSize * 0.08,
      fontFamily: MG_FONTS.dmSerifDisplay,
      fontSize: finalFontSize * 1.5,
      lineHeight: 0.8,
      color: resolvedQuoteColor,
      opacity: quoteOpacity * 0.92,
      transform: `translateY(${quoteRise}px) scale(${quoteScale})`,
      transformOrigin: "left top",
      textShadow,
    }}
  >
              {"\u201C"}
            </div> : null}
          {lines.map((line, li) => <div
    key={li}
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "baseline",
      justifyContent: flexAlign,
      gap: finalFontSize * 0.26,
      whiteSpace: "nowrap",
      // §4 (2026-08-25): a perfectly-centred stack of straight lines
      // reads as a slide. Alternating ±1.2° per line — restraint is
      // the treatment at display sizes; the interlock below does the
      // rest. Individual rotate property (REMOTION_CONVENTIONS).
      rotate: `${((li % 2 === 0 ? -1 : 1) * 1.2).toFixed(1)}deg`
    }}
  >
              {line.map((word, wi) => {
    gi++;
    const kw = isKw(word);
    const start = effStagger * gi;
    const opacity = interpolate2(
      localFrame,
      [start, start + 10],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const riseY = interpolate2(
      localFrame,
      [start, start + wordReveal],
      [RISE, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    const blur = blurIn ? interpolate2(localFrame, [start, start + 12], [BLUR0, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : 0;
    const scaleIn = interpolate2(
      localFrame,
      [start, start + 12],
      [0.9, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    const pop = kw ? interpolate2(localFrame, [start, start + 16], [0.7, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    }) : 1;
    const stamp = kw ? interpolate2(
      localFrame,
      [start + 14, start + 18, start + 24],
      [1, 1.06, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    ) : 1;
    const wordScale = kw ? pop * stamp : scaleIn;
    const lineScale = li === lastIdx ? payoffScale : 1;
    const restingSize = (kw ? finalFontSize * effKeywordScale : finalFontSize) * lineScale;
    const useColor = kw && effStyle === "color";
    const useBar = kw && effStyle === "bar";
    const color = useBar ? resolvedHighlightInk : useColor ? resolvedKeywordColor : textColor;
    const wordShadow = useColor ? `${textShadow}, 0 0 18px ${resolvedKeywordColor}66, 0 0 40px ${resolvedKeywordColor}33` : textShadow;
    let fontWeight = 400;
    if (fontKey === "inter" || fontKey === "roboto") {
      fontWeight = kw ? 900 : 700;
    } else if (fontKey === "dmSerifDisplay" || fontKey === "playfairDisplay") {
      fontWeight = kw ? 700 : 400;
    }
    const barScaleX = useBar ? interpolate2(localFrame, [start + 2, start + 12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    }) : 0;
    const barTextOpacity = useBar ? interpolate2(localFrame, [start + 6, start + 14], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : 1;
    return <span
      key={wi}
      style={{
        position: "relative",
        display: "inline-block",
        fontFamily: quoteFont,
        fontSize: restingSize,
        fontWeight,
        color,
        textTransform: uppercase && quoteMetrics.uppercaseSafe ? "uppercase" : "none",
        letterSpacing: "-0.01em",
        lineHeight: quoteMetrics.script === "latin" ? 0.95 : quoteMetrics.lineHeight,
        opacity,
        transform: `translateY(${riseY}px) scale(${wordScale})`,
        transformOrigin: "center",
        filter: blur > 0.05 ? `blur(${blur}px)` : undefined,
        textShadow: useBar ? "none" : wordShadow,
        willChange: "transform, opacity"
      }}
    >
                    {useBar ? <span
      style={{
        position: "absolute",
        left: -finalFontSize * 0.08,
        right: -finalFontSize * 0.08,
        top: "0.06em",
        bottom: "0.1em",
        backgroundColor: resolvedBarColor,
        transform: `scaleX(${barScaleX})`,
        transformOrigin: "left center",

        borderRadius: 4,
        // §4: the bar is a physical label slapped over the
        // word — its own small tilt + a hard offset shadow
        // (an axis-aligned glow reads as a UI hover).
        rotate: `${((li % 2 === 0 ? 1 : -1) * 2.2).toFixed(1)}deg`,
        boxShadow: "0 6px 16px rgba(0,0,0,0.4)"
      }}
    /> : null}
                    <span
      style={{
        position: "relative",

        opacity: barTextOpacity
      }}
    >
                      {word}
                    </span>
                  </span>;
  })}
            </div>)}
        </div>
      </div>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><PullQuote {...p} /></div>;
};
