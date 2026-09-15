// ── ported prelude: injected globals re-bound ──
const interpolate2 = interpolate;
const useContext = React.useContext;
const useMemo = React.useMemo;
const createContext = React.createContext;

// src/motion-graphics/EditorialQuote/EditorialQuote.tsx
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

// src/motion-graphics/EditorialQuote/EditorialQuote.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
var withAlpha = (color, alpha) => {
  const hex = color.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${alpha})`;
  }
  const fn = color.match(/^rgba?\(([^)]+)\)$/i);
  if (fn) {
    const [r, g, b] = fn[1].split(",").map((p) => parseFloat(p));
    return `rgba(${r || 0},${g || 0},${b || 0},${alpha})`;
  }
  return color;
};
var SIDE_INSET = 26;
var TEXT_MAX_WIDTH = 1080 - 2 * SIDE_INSET;
var CHAR_RATIO = {
  playfairDisplay: 0.47,
  // italic serif advance estimate
  dmSerifDisplay: 0.5,
  inter: 0.53,
  oswald: 0.4
};
var EditorialQuote = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  text,
  author,
  role,
  accentColor = "#FFD60A",
  textColor = "#FFFFFF",
  authorColor,
  fontKey = "playfairDisplay",
  fontSize = 108,
  maxWordsPerLine = 3,
  italic = true,
  lineStagger = 8,
  showQuoteMark = true,
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
    { defaultEnterFrames: 40, defaultExitFrames: 26 }
  );
  const words = useMemo(
    () => asText(text).trim().split(/\s+/).filter(Boolean),
    [text]
  );
  if (!visible) return null;
  if (words.length === 0) return null;
  const m = Math.max(1, maxWordsPerLine);
  const lines = [];
  for (let i = 0; i < words.length; i += m) {
    lines.push(words.slice(i, i + m).join(" "));
  }
  const quoteText = words.join(" ");
  const quoteFont = mgTextFont(quoteText, fontKey);
  const quoteMetrics = mgTextMetrics(quoteText);
  const authorFont = mgTextFont(author ?? "", "inter");
  const authorCapsSafe = mgTextMetrics(author ?? "").uppercaseSafe;
  const roleFont = mgTextFont(role ?? "", "inter");
  const resolvedAuthorColor = authorColor ?? withAlpha(textColor, 0.7);
  let maxChars = 0;
  for (const l of lines) maxChars = Math.max(maxChars, l.length);
  const charRatio = quoteMetrics.script === "latin" ? CHAR_RATIO[fontKey] : quoteMetrics.advanceEm;
  const widthFit = (TEXT_MAX_WIDTH - 47) / (Math.max(1, maxChars) * charRatio);
  const finalFontSize = clamp(widthFit, 56, 165);
  const barScaleY = interpolate2(localFrame, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const quoteOpacity = interpolate2(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const quoteScale = interpolate2(localFrame, [0, 16], [0.55, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const authorStart = 10 + lines.length * lineStagger + 8;
  const authorOpacity = interpolate2(
    localFrame,
    [authorStart, authorStart + 14],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const authorX = interpolate2(
    localFrame,
    [authorStart, authorStart + 18],
    [-18, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeOutCubic }
  );
  const authorExitV = clamp(exitProgress / 0.32, 0, 1);
  const quoteExit = easeOutCubic(clamp((exitProgress - 0.04) / 0.42, 0, 1));
  const barExit = easeOutCubic(clamp((exitProgress - 0.14) / 0.5, 0, 1));
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "stretch",
      gap: 38,
      // §4 (2026-08-25): a barely-there editorial tilt on the whole
      // block — the quote keeps its dignity; the depth comes from the
      // giant behind-plane mark below. Individual rotate property.
      rotate: "-1.2deg"
    }}
  >
          {
    /* Left accent bar */
  }
          <div
    style={{
      width: 9,
      flexShrink: 0,
      borderRadius: 5,
      backgroundColor: accentColor,
      boxShadow: `0 0 20px ${accentColor}66`,
      transform: `scaleY(${(barScaleY * (1 - barExit)).toFixed(3)})`,
      transformOrigin: "top center"
    }}
  />

          {
    /* Quote + attribution */
  }
          <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-start",
      position: "relative"
    }}
  >
            {showQuoteMark ? (
    // §4 (2026-08-25): the mark was a small glyph ABOVE the text —
    // its own row in a flat stack. Now it is the BEHIND plane: a
    // giant accent impression the quote lines overlap and occlude
    // (the classic editorial device). Text carries zIndex 1+ below;
    // the mark never touches legibility — it sits under the ink.
    <div
      aria-hidden
      style={{
        position: "absolute",
        // The “ glyph's ink sits in the TOP ~third of its em box —
        // at -0.52em the impression never reached the text
        // (render-caught). Near-zero top puts the ink BEHIND
        // lines 1-2, which is the whole point of the plane.
        // A quote glyph's ink is ~28% of its em (punctuation hangs
        // at cap height) — at 3.4x it rendered a 100px whisper, not
        // an impression (render-caught twice: first too high, then
        // too small). 7x em ≈ two text lines of actual ink.
        top: -finalFontSize * 0.3,
        left: -finalFontSize * 0.15,
        fontFamily: MG_FONTS[fontKey],
        fontSize: finalFontSize * 7,
        lineHeight: 0.66,
        fontStyle: italic ? "italic" : "normal",
        color: accentColor,
        opacity: quoteOpacity * (1 - quoteExit) * 0.45,
        transform: `translateY(${(-finalFontSize * 0.3 * quoteExit).toFixed(2)}px) scale(${(quoteScale * (1 - 0.35 * quoteExit)).toFixed(3)})`,
        transformOrigin: "left top",
        zIndex: 0
      }}
    >
                {"\u201C"}
              </div>
  ) : null}

            {lines.map((line, li) => {
    const start = 10 + li * lineStagger;
    const prog = interpolate2(localFrame, [start, start + 24], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const slideX = interpolate2(
      localFrame,
      [start, start + 22],
      [-32, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    const op = interpolate2(localFrame, [start, start + 14], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const lineExit = easeOutCubic(
      clamp((exitProgress - (0.06 + li * 0.1)) / 0.5, 0, 1)
    );
    const leftClip = lineExit > 0 ? `${(lineExit * 100).toFixed(2)}%` : "-0.06em";
    const reveal = `inset(-0.2em ${(100 - prog * 100).toFixed(2)}% -0.28em ${leftClip})`;
    const tx = slideX + lineExit * 30;
    return <div
      key={li}
      style={{
        fontFamily: quoteFont,
        fontSize: finalFontSize,
        fontStyle: italic ? "italic" : "normal",
        fontWeight: 500,
        color: textColor,
        lineHeight: Math.max(1.16, quoteMetrics.lineHeight),
        letterSpacing: "-0.01em",
        whiteSpace: "nowrap",
        position: "relative",
        zIndex: 1,
        opacity: op,
        transform: `translateX(${tx.toFixed(2)}px)`,
        clipPath: reveal,
        WebkitClipPath: reveal,
        textShadow: "0 2px 16px rgba(0,0,0,0.5)"
      }}
    >
                  {
      /* Corpus law 2: the accent lands on the PAYOFF word — the
         corpus color-codes the emotional peak, never decoration.
         The final word of the quote takes the accent at weight
         600; everything else keeps the ink colour. */
    }
                  {li === lines.length - 1 ? (() => {
      const ws = line.split(" ");
      const head = ws.slice(0, -1).join(" ");
      const last = ws[ws.length - 1] ?? "";
      return <>
                        {head ? head + " " : ""}
                        <span style={{ color: accentColor, fontWeight: 600 }}>{last}</span>
                      </>;
    })() : line}
                </div>;
  })}

            {author ? <div
    style={{
      marginTop: 14,
      position: "relative",
      zIndex: 1,
      display: "flex",
      flexDirection: "column",
      opacity: authorOpacity * (1 - authorExitV),
      transform: `translateX(${(authorX + authorExitV * 24).toFixed(2)}px)`
    }}
  >
                <div
    style={{
      fontFamily: authorFont,
      fontSize: Math.round(finalFontSize * 0.3),
      fontWeight: 700,
      color: textColor,
      letterSpacing: "0.08em",
      textTransform: authorCapsSafe ? "uppercase" : "none"
    }}
  >
                  {author}
                </div>
                {role ? <div
    style={{
      fontFamily: roleFont,
      fontSize: Math.round(finalFontSize * 0.22),
      fontWeight: 500,
      color: resolvedAuthorColor,
      letterSpacing: "0.04em",
      marginTop: 5
    }}
  >
                    {role}
                  </div> : null}
              </div> : null}
          </div>
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
  return <div style={rootStyle}><EditorialQuote {...p} /></div>;
};
