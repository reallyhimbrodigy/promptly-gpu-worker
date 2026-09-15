// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const React2 = React;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/ProgressBar/ProgressBar.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// src/motion-graphics/shared/springs.ts
var SPRING_SNAPPY = {
  damping: 10,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false
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

// src/motion-graphics/shared/schedule.ts
var mgSchedule = (opts) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, settleBy * Math.max(1, window) / scaledEnd);
  return (f60) => f60 * scale * c;
};

// src/motion-graphics/ProgressBar/ProgressBar.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var DEFAULT_TEXT_SHADOW_LARGE = "0 4px 20px rgba(0,0,0,0.65), 0 2px 4px rgba(0,0,0,0.5)";
var DEFAULT_TEXT_SHADOW_SMALL = "0 2px 10px rgba(0,0,0,0.75), 0 1px 2px rgba(0,0,0,0.55)";
var FILL_START = 8;
var FILL_END = 34;
var PULSE_END = 40;
var DEFAULT_TRACK = "rgba(255,255,255,0.14)";
var ProgressBar = (props) => {
  const {
    startMs,
    durationMs,
    enterFrames,
    exitFrames,
    label,
    // D4: 860 predates the symmetric center box (max 680) — the overflow
    // dragged the whole card right of center on Zac's render.
    width = 680,
    trackHeight = 18,
    fillColor,
    // §6 palette lock (pass #10, audited): the old default "#D4A12A" was
    // component-INVENTED gold — the live placement sent no accentColor and
    // rendered chroma no palette selected. An unspecified accent is neutral
    // chrome; jobs that want chroma pass their palette's accent.
    accentColor = "rgba(255,255,255,0.72)",
    trackColor = DEFAULT_TRACK,
    milestones = [],
    formatValue,
    textShadowLarge = DEFAULT_TEXT_SHADOW_LARGE,
    textShadowSmall = DEFAULT_TEXT_SHADOW_SMALL,
    anchor,
    offsetX,
    offsetY,
    scale
  } = props;
  const effFillColor = fillColor ?? (trackColor === DEFAULT_TRACK ? "#FFFFFF" : inkFor(trackColor));
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    undefined,
    "ProgressBar"
  );
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 40, defaultExitFrames: 12 }
  );
  if (!visible) return null;
  const K = mgSchedule({ fps, window: exitStartFrame, authoredEnd: PULSE_END });
  const k = K(1);
  const isValueMode = "value" in props && props.value !== undefined;
  const targetPercent = isValueMode ? Math.max(0, Math.min(1, props.value / props.total)) : Math.max(0, Math.min(1, (props.percentage ?? 0) / 100));
  const trackSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: Math.max(2, Math.round(8 * k))
  });
  const trackScaleX = trackSpring;
  const eyebrowFadeIn = interpolate2(localFrame, [0, 6 * k], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const heroFadeIn = interpolate2(localFrame, [6 * k, 12 * k], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const fillRaw = interpolate2(localFrame, [K(FILL_START), K(FILL_END)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const fillEased = easeOutCubic(fillRaw);
  const currentPercent = targetPercent * fillEased;
  const currentValue = isValueMode ? props.value * fillEased : (props.percentage ?? 0) * fillEased;
  const heroText = isValueMode ? formatValue ? formatValue(currentValue) : Math.round(currentValue).toLocaleString() : `${Math.round(currentValue)}%`;
  const totalText = isValueMode ? formatValue ? formatValue(props.total) : Math.round(props.total).toLocaleString() : null;
  const pulsePhase = interpolate2(localFrame, [K(FILL_END), K(PULSE_END)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const pulseTri = pulsePhase < 0.5 ? pulsePhase * 2 : (1 - pulsePhase) * 2;
  const fillScaleY = 1 + pulseTri * 0.08;
  const exitOpacity = 1 - exitProgress;
  const exitDriftY = exitProgress * -8;
  const fillWidth = width * currentPercent;
  const radius = trackHeight / 2;
  const labelFont = mgTextFont(label ?? "", "inter");
  const labelMetrics = mgTextMetrics(label ?? "");
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
    style={{
      opacity: exitOpacity,
      transform: `translateY(${exitDriftY}px)`,
      width,
      display: "flex",
      flexDirection: "column",
      alignItems: "center"
    }}
  >
        {label ? <div
    style={{
      fontFamily: labelFont,
      fontSize: 24,
      fontWeight: 600,
      color: accentColor,
      letterSpacing: "0.28em",
      textTransform: labelMetrics.uppercaseSafe ? "uppercase" : "none",
      lineHeight: Math.max(1, labelMetrics.lineHeight),
      opacity: eyebrowFadeIn,
      textShadow: textShadowSmall,
      whiteSpace: "nowrap",
      marginBottom: 22
    }}
  >
            {label}
          </div> : null}

        <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "baseline",
      justifyContent: "center",
      opacity: heroFadeIn,
      color: "#FFFFFF",
      lineHeight: 0.9,
      fontVariantNumeric: "tabular-nums",
      textShadow: textShadowLarge,
      whiteSpace: "nowrap"
    }}
  >
          <span
    style={{
      fontFamily: MG_FONTS.anton,
      fontSize: 140,
      fontWeight: 400,
      letterSpacing: "-0.02em",
      lineHeight: 0.9,
      fontVariantNumeric: "tabular-nums"
    }}
  >
            {heroText}
          </span>
          {totalText ? <span
    style={{
      fontFamily: MG_FONTS.anton,
      fontSize: 60,
      fontWeight: 400,
      letterSpacing: "-0.01em",
      color: "rgba(255,255,255,0.55)",
      marginLeft: 18,
      lineHeight: 0.9,
      fontVariantNumeric: "tabular-nums"
    }}
  >
              / {totalText}
            </span> : null}
        </div>

        <div
    style={{
      width: 48,
      height: 2,
      backgroundColor: accentColor,
      marginTop: 22,
      marginBottom: 24,
      opacity: heroFadeIn,
      boxShadow: "0 2px 6px rgba(0,0,0,0.5)"
    }}
  />

        <div
    style={{
      position: "relative",
      width: "100%",
      height: trackHeight,
      transform: `scaleX(${trackScaleX})`,
      transformOrigin: "left center",
      opacity: eyebrowFadeIn
    }}
  >
          <div
    style={{
      position: "absolute",
      inset: 0,
      backgroundColor: trackColor,
      borderRadius: radius,
      boxShadow: "inset 0 1px 2px rgba(0,0,0,0.35)"
    }}
  />

          <div
    style={{
      position: "absolute",
      left: 0,
      top: 0,
      height: trackHeight,
      width: fillWidth,
      backgroundColor: effFillColor,
      borderRadius: radius,
      transform: `scaleY(${fillScaleY})`,
      transformOrigin: "center",
      boxShadow: `0 4px 12px ${withAlpha(effFillColor, 0.35)}`
    }}
  />

          {milestones.map((m, i) => {
    const x = width * m.at;
    const reached = currentPercent >= m.at;
    const msFont = mgTextFont(m.label ?? "", "inter");
    const msUppercaseSafe = mgTextMetrics(m.label ?? "").uppercaseSafe;
    return <React2.Fragment key={i}>
                <div
      style={{
        position: "absolute",
        left: x - 1,
        top: -4,
        width: 2,
        height: trackHeight + 8,
        backgroundColor: reached ? "#FFFFFF" : "rgba(255,255,255,0.3)",
        borderRadius: 1
      }}
    />
                {m.label ? <div
      style={{
        position: "absolute",
        left: x,
        bottom: -38,
        transform: "translateX(-50%)",
        fontFamily: msFont,
        fontSize: 18,
        fontWeight: 600,
        color: reached ? "#FFFFFF" : "rgba(255,255,255,0.5)",
        letterSpacing: "0.2em",
        textTransform: msUppercaseSafe ? "uppercase" : "none",
        whiteSpace: "nowrap",
        textShadow: textShadowSmall
      }}
    >
                    {m.label}
                  </div> : null}
              </React2.Fragment>;
  })}
        </div>
      </div>
      </div>
    </AbsoluteFill>;
};
function withAlpha(color, alpha) {
  if (color.startsWith("#")) {
    const h = color.replace("#", "");
    const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  if (color.startsWith("rgb(")) {
    return color.replace("rgb(", "rgba(").replace(")", `, ${alpha})`);
  }
  return color;
}


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><ProgressBar {...p} /></div>;
};
