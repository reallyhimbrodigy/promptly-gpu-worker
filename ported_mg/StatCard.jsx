// ── ported prelude: injected globals re-bound ──
const useCurrentFrame2 = useCurrentFrame;
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const AbsoluteFill3 = AbsoluteFill;
const useContext = React.useContext;
const useContext2 = React.useContext;
const createContext = React.createContext;
const createContext2 = React.createContext;
const __ch = (p) => (p && p.children !== undefined ? p.children : undefined);
const jsx = (t, p) => React.createElement(t, p, __ch(p));
const jsxs = (t, p) => React.createElement(t, p, __ch(p));

// src/motion-graphics/StatCard/StatCard.tsx
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
var CAP_REFERENCE_FPS = 30;
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

// src/motion-graphics/shared/entrance-cap.ts
var MAX_ENTRANCE_STEP = 1 / 6;
var PEAK_K = 1 / (1 - MIN_BLEND_FRACTION / 2);
var ENTRANCE_FLOOR_FRAMES_30 = Math.ceil(PEAK_K / MAX_ENTRANCE_STEP);
function cappedEntranceProgress(args) {
  const floorAtFps = Math.ceil(
    PEAK_K / (args.maxStep ?? MAX_ENTRANCE_STEP) * (args.fps / CAP_REFERENCE_FPS)
  );
  const frames = Math.max(1, Math.max(args.authoredFrames, floorAtFps));
  const t = Math.min(Math.max(args.localFrame / frames, 0), 1);
  return trapezoidEasing(MIN_BLEND_FRACTION, 0.25)(t);
}

// src/motion-graphics/shared/motion-blur.tsx
// [ported] import removed — ChatCut injects these: react
// node_modules/@remotion/motion-blur/dist/esm/index.mjs
// [ported] import removed — ChatCut injects these: remotion
// [ported] import removed — ChatCut injects these: react/jsx-runtime
// [ported] import removed — ChatCut injects these: remotion
// [ported] import removed — ChatCut injects these: react/jsx-runtime
var getNumberOfSamples = ({
  shutterFraction,
  samples,
  currentFrame
}) => {
  const maxOffset = shutterFraction * samples;
  const maxTimeReverse = currentFrame - maxOffset;
  const factor = Math.min(1, Math.max(0, maxTimeReverse / maxOffset + 1));
  return Math.max(1, Math.round(Math.min(factor * samples, samples)));
};
var CameraMotionBlur = ({
  children,
  shutterAngle = 180,
  samples = 10
}) => {
  const currentFrame = useCurrentFrame2();
  if (typeof samples !== "number" || Number.isNaN(samples) || !Number.isFinite(samples)) {
    throw new TypeError(`"samples" must be a number, but got ${JSON.stringify(samples)}`);
  }
  if (samples % 1 !== 0) {
    throw new TypeError(`"samples" must be an integer, but got ${JSON.stringify(samples)}`);
  }
  if (samples < 0) {
    throw new TypeError(`"samples" must be non-negative, but got ${JSON.stringify(samples)}`);
  }
  if (typeof shutterAngle !== "number" || Number.isNaN(shutterAngle) || !Number.isFinite(shutterAngle)) {
    throw new TypeError(`"shutterAngle" must be a number, but got ${JSON.stringify(shutterAngle)}`);
  }
  if (shutterAngle < 0 || shutterAngle > 360) {
    throw new TypeError(`"shutterAngle" must be between 0 and 360, but got ${JSON.stringify(shutterAngle)}`);
  }
  const shutterFraction = shutterAngle / 360;
  const actualSamples = getNumberOfSamples({
    currentFrame,
    samples,
    shutterFraction
  });
  return /* @__PURE__ */ jsx(AbsoluteFill, {
    style: { isolation: "isolate" },
    children: new Array(actualSamples).fill(true).map((_, i) => {
      const sample = i + 1;
      const sampleFrameOffset = shutterFraction * (sample / actualSamples);
      return /* @__PURE__ */ jsx(AbsoluteFill, {
        style: {
          mixBlendMode: "plus-lighter",
          filter: `opacity(${1 / actualSamples})`
        },
        children: /* @__PURE__ */ jsx(Freeze, {
          frame: currentFrame - sampleFrameOffset + 1,
          children
        })
      }, `frame-${i.toString()}`);
    })
  });
};

// src/motion-graphics/shared/motion-blur.tsx
var MOTION_BLUR_DEFAULTS = {
  samples: 6,
  shutterAngle: 180
};
var DISABLED = {
  enabled: false,
  samples: MOTION_BLUR_DEFAULTS.samples,
  shutterAngle: MOTION_BLUR_DEFAULTS.shutterAngle
};
var MotionBlurContext = createContext2(DISABLED);
var useMotionBlur = () => useContext2(MotionBlurContext);
var MotionBlurWrap = ({
  children
}) => {
  const { enabled, samples, shutterAngle } = useMotionBlur();
  if (!enabled) return <>{children}</>;
  return <CameraMotionBlur samples={samples} shutterAngle={shutterAngle}>
      {children}
    </CameraMotionBlur>;
};

// src/motion-graphics/StatCard/StatCard.tsx
var LABEL_RATIO = 0.14;
var AFFIX_RATIO = 0.55;
var ACCENT_HEIGHT_RATIO = 0.045;
// 150, WAS 210. THE FLOOR IS THE BOUND AND IT BIT ONE DIGIT PAST THE DEFAULT.
//
// numberSize = width * FULL_BLEED_FRAC / totalEm, so numberSize * totalEm is
// constant and the row is EXACTLY width-bounded — until Math.max(NUMBER_MIN, ..)
// stops the shrink, after which the row grows and the card runs off the frame.
//
// FULL_BLEED_FRAC is 1, so the target IS the full 1080 with no margin, and the
// baked default "$20,000,000" computes 223.4 against a floor of 210. THIRTEEN
// PIXELS OF HEADROOM on a component whose entire job is money figures:
//
//    8 digits   20,000,000        223.4   1080  fits
//    9 digits   200,000,000       210.0   1120  OVERFLOWS by 40
//   10 digits   2,000,000,000     210.0   1276  OVERFLOWS by 196
//
// At 150 the shrink continues to twelve digits — 200,000,000,000 lands at
// 152.7 and exactly 1080 — and the DEFAULT IS UNCHANGED, because 223.4 is above
// both floors. Nothing that renders today renders differently.
//
// Builder 1 found this by halving the declared property and reading the box; he
// had tested `label` first, got zero delta, and concluded StatCard was bounded.
// It was `value` — the property he had not varied — and the card is sized by the
// number row. The bound is now 12 digits and that is stated rather than implied.
var NUMBER_MIN = 150;
var NUMBER_MAX = 470;
var FULL_BLEED_FRAC = 1;
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var DEFAULT_TEXT_SHADOW = "0 2px 8px rgba(0,0,0,0.85), 0 12px 40px rgba(0,0,0,0.6)";
var antonCharEm = (c) => c === "," || c === "." ? 0.24 : c === " " ? 0.3 : 0.5;
var estWidthEm = (s) => s.split("").reduce((a, c) => a + antonCharEm(c), 0);
var StatCard = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  value,
  fromValue = 0,
  prefix,
  suffix,
  decimals,
  label,
  numberColor = "#FFFFFF",
  labelColor = "#FFFFFF",
  accentColor = "#C8551F",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    undefined,
    "StatCard"
  );
  const { fps, width } = useVideoConfig2();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 32, defaultExitFrames: 12 }
  );
  if (!visible) return null;
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const smoothEntrance = useSmoothGraphics();
  const enterP = cappedEntranceProgress({ localFrame, fps, authoredFrames: 8 });
  const numberEnterScale = smoothEntrance ? 0.92 + 0.08 * enterP : interpolate2(localFrame, [0, 8], [0.92, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const numberFadeIn = smoothEntrance ? enterP : interpolate2(localFrame, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const countProgress = interpolate2(localFrame, [4, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const easedCount = easeOutCubic(countProgress);
  const currentValue = fromValue + (value - fromValue) * easedCount;
  const display = decimals !== undefined ? currentValue.toFixed(decimals) : Math.round(currentValue).toLocaleString();
  const finalDisplay = decimals !== undefined ? value.toFixed(decimals) : Math.round(value).toLocaleString();
  const prefixMetrics = mgTextMetrics(prefix ?? "");
  const suffixMetrics = mgTextMetrics(suffix ?? "");
  const prefixFont = mgTextFont(prefix ?? "", "anton");
  const suffixFont = mgTextFont(suffix ?? "", "anton");
  const labelMetrics = mgTextMetrics(label);
  const labelFont = mgTextFont(label, "inter");
  const affixEm = (s, m) => m.script === "latin" ? s.length * 0.5 : [...s].length * m.advanceEm;
  const totalEm = estWidthEm(finalDisplay) + (affixEm(prefix ?? "", prefixMetrics) + affixEm(suffix ?? "", suffixMetrics)) * AFFIX_RATIO + (prefix ? 0.08 : 0) + (suffix ? 0.08 : 0);
  const numberSize = Math.max(
    NUMBER_MIN,
    Math.min(NUMBER_MAX, width * FULL_BLEED_FRAC / Math.max(totalEm, 0.5))
  );
  const affixSize = numberSize * AFFIX_RATIO;
  const affixGap = numberSize * 0.04;
  const labelSize = Math.max(24, numberSize * LABEL_RATIO);
  const accentHeight = Math.max(9, numberSize * ACCENT_HEIGHT_RATIO);
  const accentWidth = numberSize * estWidthEm(finalDisplay) * 0.92;
  const numberShadow = `0 ${Math.round(numberSize * 0.012)}px ${Math.round(numberSize * 0.05)}px rgba(0,0,0,0.9), 0 ${Math.round(numberSize * 0.035)}px ${Math.round(numberSize * 0.12)}px rgba(0,0,0,0.5)`;
  const labelShadow = `0 ${Math.round(labelSize * 0.06)}px ${Math.round(labelSize * 0.22)}px rgba(0,0,0,0.85)`;
  const pulseScale = interpolate2(localFrame, [24, 27, 30], [1, 1.06, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const ruleScaleX = interpolate2(localFrame, [24, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const labelFadeIn = interpolate2(localFrame, [26, 32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const labelY = interpolate2(localFrame, [26, 32], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const exitDriftY = exitProgress * -10;
  const exitOpacity = 1 - exitProgress;
  const affixStyle = {
    fontFamily: MG_FONTS.anton,
    fontSize: affixSize,
    fontWeight: 400,
    letterSpacing: "-0.02em",
    lineHeight: 1,
    opacity: 0.9,
    fontVariantNumeric: "tabular-nums"
  };
  return <AbsoluteFill3 style={containerStyle}>
      <div style={wrapperStyle}>
        {
    /* Blur the WHOLE card as one subtree (count-up + scale + rule-draw).
       Wrapping only the number breaks the flex flow — CameraMotionBlur
       re-lays-out whatever it wraps. */
  }
        <MotionBlurWrap>
        <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      transform: `translateY(${exitDriftY}px)`,
      opacity: exitOpacity
    }}
  >
            <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "baseline",
      justifyContent: "center",
      transform: `scale(${numberEnterScale * pulseScale})`,
      transformOrigin: "center",
      opacity: numberFadeIn,
      fontVariantNumeric: "tabular-nums",
      color: numberColor,
      lineHeight: 1,
      textShadow: numberShadow,
      whiteSpace: "nowrap"
    }}
  >
              {prefix ? <span
    style={{
      ...affixStyle,
      fontFamily: prefixFont,
      lineHeight: Math.max(1, prefixMetrics.lineHeight),
      marginRight: affixGap
    }}
  >
                  {prefix}
                </span> : null}
              <span
    style={{
      fontFamily: MG_FONTS.anton,
      fontSize: numberSize,
      fontWeight: 400,
      letterSpacing: "-0.02em",
      lineHeight: 1,
      fontVariantNumeric: "tabular-nums"
    }}
  >
                {display}
              </span>
              {suffix ? <span
    style={{
      ...affixStyle,
      fontFamily: suffixFont,
      lineHeight: Math.max(1, suffixMetrics.lineHeight),
      marginLeft: affixGap
    }}
  >
                  {suffix}
                </span> : null}
            </div>

          {
    /* STRUCTURAL ACCENT — the spine the label hangs from. Draws in on land. */
  }
          <div
    style={{
      width: accentWidth,
      height: accentHeight,
      backgroundColor: accentColor,
      // Small positive gap below the figure — the original stacking that
      // renders correctly; scaled up for the bigger number. The spine reads
      // as the number's baseline, the label hangs off it.
      marginTop: numberSize * 0.03,
      transform: `scaleX(${ruleScaleX})`,
      transformOrigin: "center",
      boxShadow: "0 3px 10px rgba(0,0,0,0.5)",
      borderRadius: accentHeight / 2
    }}
  />

          {
    /* ANCHORED LABEL — tucked tight under the spine; one object, not a stack. */
  }
          <div
    style={{
      fontFamily: labelFont,
      fontSize: labelSize,
      fontWeight: 700,
      color: labelColor,
      letterSpacing: "0.2em",
      textTransform: labelMetrics.uppercaseSafe ? "uppercase" : "none",
      textAlign: "center",
      lineHeight: Math.max(1.1, labelMetrics.lineHeight),
      marginTop: numberSize * 0.03,
      opacity: labelFadeIn,
      transform: `translateY(${labelY}px)`,
      textShadow: labelShadow
    }}
  >
            {label}
          </div>
        </div>
        </MotionBlurWrap>
      </div>
    </AbsoluteFill3>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><StatCard {...p} /></div>;
};
