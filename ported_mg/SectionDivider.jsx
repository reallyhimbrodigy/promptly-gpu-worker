// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/SectionDivider/SectionDivider.tsx
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
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.25) : void 0
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
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.75) : void 0
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

// src/motion-graphics/shared/schedule.ts
var mgSchedule = (opts) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, settleBy * Math.max(1, window) / scaledEnd);
  return (f60) => f60 * scale * c;
};

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/SectionDivider/SectionDivider.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var CONTENT_MAX_WIDTH = 680;
var NUMBER_SIZE = 110;
var EYEBROW_SIZE = 36;
var RULE_THICKNESS = 3;
var BAND_HEIGHT = 560;
var DEFAULT_TEXT_SHADOW = "0 2px 12px rgba(0,0,0,0.55), 0 14px 48px rgba(0,0,0,0.45)";
var RULE_SHADOW = "0 2px 8px rgba(0,0,0,0.5)";
var FONT_FAMILY = {
  anton: MG_FONTS.anton,
  dmSerifDisplay: MG_FONTS.dmSerifDisplay,
  playfairDisplay: MG_FONTS.playfairDisplay,
  oswald: MG_FONTS.oswald
};
var SectionDivider = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  label,
  number,
  fontKey = "anton",
  align = "center",
  variant = "full",
  titleColor = "#FFFFFF",
  accentColor = "#C8551F",
  eyebrowColor,
  numberColor,
  titleFontSize = 150,
  showRule = true,
  showScrim = true,
  scrimColor = "rgba(0,0,0,0.55)",
  showVignette = true,
  vignetteStrength = 0.6,
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
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 50, defaultExitFrames: 24 }
  );
  if (!visible) return null;
  const ebColor = eyebrowColor ?? "rgba(255,255,255,0.78)";
  const numColor = numberColor ?? accentColor;
  const isSerif = fontKey === "dmSerifDisplay" || fontKey === "playfairDisplay";
  const isLeft = align === "left";
  const titleText = asText(title);
  const lines = titleText.split("\n");
  const titleMetrics = mgTextMetrics(titleText);
  const titleIsLatin = titleMetrics.script === "latin";
  const titleFontFamily = mgTextFont(titleText, fontKey);
  const titleLineHeight = Math.max(isSerif ? 1.08 : 1, titleMetrics.lineHeight);
  const labelFont = mgTextFont(label ?? "", "inter");
  const labelUppercaseSafe = mgTextMetrics(label ?? "").uppercaseSafe;
  let maxChars = 1;
  for (const l of lines) maxChars = Math.max(maxChars, [...l].length);
  const advance = titleIsLatin ? isSerif ? 0.58 : 0.52 : titleMetrics.advanceEm;
  const fitTitleSize = Math.round(
    Math.max(56, Math.min(CONTENT_MAX_WIDTH / (maxChars * advance), 170))
  );
  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: 42 + 8 * (lines.length - 1)
  });
  const scrimEnter = interpolate2(localFrame, [K(0), K(18)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const scrimExit = interpolate2(exitProgress, [0.2, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const scrimOpacity = scrimEnter * scrimExit;
  const ruleEnter = interpolate2(localFrame, [K(4), K(22)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const ruleRetract = interpolate2(exitProgress, [0, 0.55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic
  });
  const ruleScaleX = ruleEnter * (1 - ruleRetract);
  const ruleOpacity = interpolate2(localFrame, [K(4), K(12)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const numScale = interpolate2(localFrame, [K(10), K(28)], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack
  });
  const numEnterO = interpolate2(localFrame, [K(10), K(22)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const numExitO = interpolate2(exitProgress, [0, 0.5], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const numTY = interpolate2(localFrame, [K(10), K(24)], [10, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const ebEnterO = interpolate2(localFrame, [K(16), K(30)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const ebTYenter = interpolate2(localFrame, [K(16), K(30)], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const ebExitO = interpolate2(exitProgress, [0, 0.5], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const ebExitTY = interpolate2(exitProgress, [0, 0.6], [0, -18], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic
  });
  const blockY = interpolate2(exitProgress, [0, 1], [0, -10], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const bandScaleY = interpolate2(localFrame, [K(0), K(16)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const bandOpacity = interpolate2(localFrame, [K(0), K(10)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  }) * scrimExit;
  const crossAlign = isLeft ? "flex-start" : "center";
  const vig = Math.max(0, Math.min(1, vignetteStrength));
  return <AbsoluteFill style={containerStyle}>
      {
    /* Cinematic 4-corner vignette (darkens each corner) */
  }
      {showVignette ? <AbsoluteFill
    style={{
      background: [
        `radial-gradient(circle at top left, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
        `radial-gradient(circle at top right, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
        `radial-gradient(circle at bottom left, rgba(0,0,0,${vig}) 0%, transparent 42%)`,
        `radial-gradient(circle at bottom right, rgba(0,0,0,${vig}) 0%, transparent 42%)`
      ].join(", "),
      opacity: scrimOpacity
    }}
  /> : null}

      {
    /* Full-frame vignette scrim (behind, not anchored/scaled) */
  }
      {showScrim && variant === "full" ? <AbsoluteFill
    style={{
      background: `radial-gradient(135% 62% at 50% 50%, ${scrimColor} 0%, ${scrimColor} 38%, transparent 76%)`,
      opacity: scrimOpacity
    }}
  /> : null}

      {
    /* Centered letterbox band */
  }
      {variant === "band" ? <AbsoluteFill
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }}
  >
          <div
    style={{
      width: "100%",
      height: BAND_HEIGHT,
      backgroundColor: scrimColor,
      opacity: bandOpacity,
      transform: `scaleY(${bandScaleY})`,
      transformOrigin: "center"
    }}
  />
        </AbsoluteFill> : null}

      <div style={wrapperStyle}>
        <div
    style={{
      width: CONTENT_MAX_WIDTH,
      display: "flex",
      flexDirection: "column",
      alignItems: crossAlign,
      transform: `translateY(${blockY}px)`
    }}
  >
          {
    /* Number */
  }
          {number ? <div
    style={{
      fontFamily: FONT_FAMILY[fontKey],
      fontSize: NUMBER_SIZE,
      fontWeight: 400,
      color: numColor,
      lineHeight: 1,
      fontVariantNumeric: "tabular-nums",
      marginBottom: 12,
      opacity: numEnterO * numExitO,
      transform: `translateY(${numTY}px) scale(${numScale})`,
      transformOrigin: isLeft ? "left center" : "center",
      textShadow
    }}
  >
              {number}
            </div> : null}

          {
    /* Eyebrow */
  }
          {label ? <div
    style={{
      fontFamily: labelFont,
      fontSize: EYEBROW_SIZE,
      fontWeight: 600,
      color: ebColor,
      letterSpacing: "0.3em",
      textTransform: labelUppercaseSafe ? "uppercase" : "none",
      lineHeight: 1.2,
      marginBottom: 28,
      opacity: ebEnterO * ebExitO,
      transform: `translateY(${ebTYenter + ebExitTY}px)`,
      textShadow
    }}
  >
              {label}
            </div> : null}

          {
    /* Accent rule */
  }
          {showRule ? <div
    style={{
      width: isLeft ? 200 : 160,
      height: RULE_THICKNESS,
      backgroundColor: accentColor,
      marginBottom: 28,
      opacity: ruleOpacity,
      transform: `scaleX(${ruleScaleX})`,
      transformOrigin: isLeft ? "left center" : "center",
      boxShadow: RULE_SHADOW
    }}
  /> : null}

          {
    /* Title lines (percent-translate masks) */
  }
          {lines.map((line, li) => {
    const revealP = interpolate2(
      localFrame,
      [K(24 + 8 * li), K(42 + 8 * li)],
      [0, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    const enterTY = (1 - revealP) * 100;
    const exitTYp = interpolate2(exitProgress, [0, 0.7], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeInOutCubic
    });
    const lineTY = enterTY - 100 * exitTYp;
    const lineEnterO = interpolate2(
      localFrame,
      [K(24 + 8 * li), K(32 + 8 * li)],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const lineExitO = interpolate2(exitProgress, [0.45, 0.8], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    return <div
      key={li}
      style={{
        // The mask keys off REVEAL COMPLETION, not the phase label
        // (pass #9): 'holding' was unreachable whenever the computed
        // enter window outlived the pre-exit window, so the mask
        // never lifted — fallback-face matras stayed clipped for the
        // component's whole life, and the old holding→exiting flip
        // re-clipped settled text with a visible pop.
        overflow: revealP >= 1 ? "visible" : "hidden",
        maxWidth: CONTENT_MAX_WIDTH
      }}
    >
                <div
      style={{
        fontFamily: titleFontFamily,
        fontSize: fitTitleSize,
        fontWeight: 400,
        color: titleColor,
        letterSpacing: isSerif || !titleIsLatin ? "0" : "-0.01em",
        lineHeight: titleLineHeight,
        textTransform: titleMetrics.uppercaseSafe ? "uppercase" : "none",
        textAlign: isLeft ? "left" : "center",
        whiteSpace: "nowrap",
        opacity: lineEnterO * lineExitO,
        transform: `translateY(${lineTY}%)`,
        textShadow
      }}
    >
                  {line}
                </div>
              </div>;
  })}
        </div>
      </div>
    </AbsoluteFill>;
};
