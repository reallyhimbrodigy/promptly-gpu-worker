// ── ported prelude: injected globals re-bound ──
const useCurrentFrame2 = useCurrentFrame;
const React3 = React;
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const AbsoluteFill3 = AbsoluteFill;
const useContext = React.useContext;
const useContext2 = React.useContext;
const useId = React.useId;
const createContext = React.createContext;
const createContext2 = React.createContext;
const __ch = (p) => (p && p.children !== undefined ? p.children : undefined);
const jsx = (t, p) => React.createElement(t, p, __ch(p));
const jsxs = (t, p) => React.createElement(t, p, __ch(p));

// src/motion-graphics/Stamp/Stamp.tsx
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

// src/motion-graphics/Stamp/Stamp.tsx
var easeInCubic = (t) => t * t * t;
var DEFAULT_TEXT_SHADOW = "0 1px 2px rgba(0,0,0,0.35)";
var BADGE_SHADOW = "drop-shadow(0 6px 18px rgba(0,0,0,0.45)) drop-shadow(0 2px 4px rgba(0,0,0,0.35))";
var GRAIN = "repeating-linear-gradient(28deg, rgba(0,0,0,0.05) 0 1px, transparent 1px 3px)";
var STYLE_DEFAULTS = {
  // §4 presence (2026-08-24): REF-2's mark commands the frame — the previous
  // sizes read as a lone sticker floating mid-frame (render-proven). Sized so
  // the default stamp spans ~70% of a 1080 frame the way the reference's
  // number does.
  // Corpus law 1 (pass #7b): a card that lands alone OWNS the frame — REF-2's
  // number runs ~95% width and clips the edge; the 2026-08-25 panel measured
  // ours at ~58% floating in symmetric margins. Tilted corners now approach
  // the 1080 frame edges.
  seal: { fontKey: "oswald", fontSize: 64, mark: "star", distress: false, size: 900 },
  stamp: { fontKey: "anton", fontSize: 84, mark: "none", distress: true, size: 1e3 },
  ribbon: { fontKey: "anton", fontSize: 72, mark: "none", distress: false, size: 1040 }
};
var FONT_WEIGHT = {
  oswald: 700,
  anton: 400,
  inter: 800
};
var Star = ({ size, color }) => <svg width={size} height={size} viewBox="0 0 24 24">
    <path
  d="M12 3.2l2.6 5.27 5.81.84-4.2 4.1.99 5.79L12 16.9l-5.2 2.73.99-5.79-4.2-4.1 5.81-.84z"
  fill={color}
/>
  </svg>;
var renderMark = (mark, color, size) => {
  if (mark === "none") return null;
  if (mark === "check") {
    return <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
        <path d="M4.5 12.5l5 5 10-11" />
      </svg>;
  }
  if (mark === "stars") {
    return <div style={{ display: "flex", gap: 8 }}>
        {[0, 1, 2].map((i) => <Star key={i} size={size * 0.42} color={color} />)}
      </div>;
  }
  return <Star size={size} color={color} />;
};
var rectFontFit = (len) => len <= 6 ? 122 : len <= 8 ? 104 : len <= 10 ? 88 : len <= 12 ? 74 : 64;
var Stamp = (props) => {
  const style = props.style ?? "seal";
  const d = STYLE_DEFAULTS[style];
  const {
    startMs,
    durationMs,
    enterFrames,
    exitFrames,
    text,
    subtextTop,
    subtextBottom,
    mark = d.mark,
    color = "#C8321F",
    textColor,
    markColor,
    rotation = -9,
    entryScale = 1.28,
    fontKey = d.fontKey,
    fontSize: fontSizeProp,
    size = d.size,
    doubleRing = true,
    distress = d.distress,
    textShadow = DEFAULT_TEXT_SHADOW,
    anchor,
    offsetX,
    offsetY,
    scale
  } = props;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" }
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 30, defaultExitFrames: 16 }
  );
  const uid = React3.useId().replace(/:/g, "");
  const { fps } = useVideoConfig2();
  if (!visible) return null;
  const ink = textColor ?? color;
  const markInk = markColor ?? color;
  const restRot = rotation;
  const smoothEntrance = useSmoothGraphics();
  const pressSpring = spring({
    fps,
    frame: localFrame,
    config: { damping: 10, mass: 0.8, stiffness: 150 }
  });
  const press = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 12 }) : pressSpring;
  const appear = interpolate2(press, [0, 1], [entryScale, 1]);
  const rotSettle = interpolate2(press, [0, 1], [restRot - 4, restRot]);
  const opacityIn = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 5 }) : interpolate2(localFrame, [0, 5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const ex = easeInCubic(exitProgress);
  const exitScaleV = 1 + 0.06 * ex;
  const exitY = -12 * ex;
  const exitRot = -2 * ex;
  const exitOpacity = interpolate2(exitProgress, [0, 0.85], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const finalScale = appear * exitScaleV;
  const finalRot = rotSettle + exitRot;
  const groupOpacity = opacityIn * exitOpacity;
  const stampFont = fontSizeProp ?? (text.length > 14 ? 78 : text.length > 11 ? 94 : d.fontSize);
  const textFont = mgTextFont(text, fontKey);
  const textMetrics = mgTextMetrics(text);
  const subTopFont = mgTextFont(subtextTop ?? "", "oswald");
  const subTopMetrics = mgTextMetrics(subtextTop ?? "");
  const subBottomFont = mgTextFont(subtextBottom ?? "", "oswald");
  const subBottomMetrics = mgTextMetrics(subtextBottom ?? "");
  let badge;
  if (style === "seal") {
    const W = 560;
    const H = 280;
    const mainFont = fontSizeProp ?? rectFontFit(text.length);
    const grungeId = `grunge-${uid}`;
    const hasSub = Boolean(subtextTop || subtextBottom);
    badge = <svg
      width={size}
      height={size * H / W}
      viewBox={`0 0 ${W} ${H}`}
      style={{ overflow: "visible", display: "block" }}
    >
        <defs>
          <filter
      id={grungeId}
      x="-15%"
      y="-15%"
      width="130%"
      height="130%"
      filterUnits="objectBoundingBox"
    >
            {
      /* roughen the edges */
    }
            <feTurbulence
      type="fractalNoise"
      baseFrequency="0.022"
      numOctaves={2}
      seed={5}
      result="warp"
    />
            <feDisplacementMap
      in="SourceGraphic"
      in2="warp"
      scale={2.5}
      xChannelSelector="R"
      yChannelSelector="G"
      result="rough"
    />
            {
      /* lightly erode the ink into a few worn patches */
    }
            <feTurbulence
      type="fractalNoise"
      baseFrequency="0.3"
      numOctaves={2}
      seed={9}
      result="speck"
    />
            <feColorMatrix
      in="speck"
      type="matrix"
      values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 4 -0.78"
      result="mask"
    />
            <feComposite in="rough" in2="mask" operator="in" />
          </filter>
        </defs>

        <g filter={`url(#${grungeId})`}>
          <rect
      x={12}
      y={12}
      width={W - 24}
      height={H - 24}
      rx={14}
      fill="none"
      stroke={ink}
      strokeWidth={12}
    />
          {doubleRing ? <rect
      x={30}
      y={30}
      width={W - 60}
      height={H - 60}
      rx={8}
      fill="none"
      stroke={ink}
      strokeWidth={3.5}
    /> : null}

          {subtextTop ? <text
      x={W / 2}
      y={72}
      textAnchor="middle"
      fontFamily={subTopFont}
      fontWeight={700}
      fontSize={27}
      letterSpacing={9}
      fill={ink}
    >
              {subTopMetrics.uppercaseSafe ? subtextTop.toUpperCase() : subtextTop}
            </text> : null}

          <text
      x={W / 2}
      y={hasSub ? 186 : 176}
      textAnchor="middle"
      fontFamily={textFont}
      fontWeight={FONT_WEIGHT[fontKey]}
      fontSize={mainFont}
      letterSpacing={2}
      fill={ink}
    >
            {textMetrics.uppercaseSafe ? text.toUpperCase() : text}
          </text>

          {subtextBottom ? <text
      x={W / 2}
      y={242}
      textAnchor="middle"
      fontFamily={subBottomFont}
      fontWeight={700}
      fontSize={27}
      letterSpacing={9}
      fill={ink}
    >
              {subBottomMetrics.uppercaseSafe ? subtextBottom.toUpperCase() : subtextBottom}
            </text> : null}
        </g>
      </svg>;
  } else if (style === "ribbon") {
    badge = <div
      style={{
        minWidth: size,
        height: 96,
        background: color,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 64px",
        clipPath: "polygon(0 0, 100% 0, calc(100% - 28px) 50%, 100% 100%, 0 100%, 28px 50%)"
      }}
    >
        <div
      style={{
        fontFamily: textFont,
        fontWeight: FONT_WEIGHT[fontKey],
        fontSize: stampFont,
        color: textColor ?? "#FFFFFF",
        letterSpacing: "0.04em",
        textTransform: textMetrics.uppercaseSafe ? "uppercase" : "none",
        lineHeight: Math.max(1, textMetrics.lineHeight),
        textShadow
      }}
    >
          {text}
        </div>
      </div>;
  } else {
    badge = <div
      style={{
        minWidth: size,
        border: `7px solid ${color}`,
        borderRadius: 4,
        padding: "18px 30px",
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
        // Corpus law 2: shock fragments hit at FULL ink — 0.95 read as a
        // watermark on the panel's frames. Distress erodes; alpha doesn't.
        opacity: 1,
        overflow: "hidden"
      }}
    >
        {distress ? <div
      style={{
        position: "absolute",
        inset: 0,
        background: GRAIN,
        pointerEvents: "none"
      }}
    /> : null}
        {doubleRing ? <div
      style={{
        position: "absolute",
        inset: 6,
        border: `2px solid ${color}`,
        borderRadius: 2,
        pointerEvents: "none"
      }}
    /> : null}
        {mark !== "none" ? <div style={{ lineHeight: 0 }}>
            {renderMark(mark, markInk, Math.round(stampFont * 0.6))}
          </div> : null}
        <div
      style={{
        fontFamily: textFont,
        fontWeight: FONT_WEIGHT[fontKey],
        fontSize: stampFont,
        color: ink,
        letterSpacing: "0.04em",
        textTransform: textMetrics.uppercaseSafe ? "uppercase" : "none",
        lineHeight: textMetrics.script === "latin" ? 0.95 : textMetrics.lineHeight,
        textShadow,
        whiteSpace: "nowrap"
      }}
    >
          {text}
        </div>
        {subtextBottom ? <div style={subStyle(ink, textShadow, subBottomFont, subBottomMetrics)}>
            {subtextBottom}
          </div> : null}
      </div>;
  }
  return <AbsoluteFill3 style={containerStyle}>
      <div style={wrapperStyle}>
        {
    /* The bounce-in press (scale overshoot + rotation settle) renders through
       the film-shutter blur. Wraps the WHOLE self-contained stamp group (the
       only child of wrapperStyle) — never a single flex child, per the
       MotionBlurWrap subtree constraint. */
  }
        <MotionBlurWrap>
          <div
    style={{
      position: "relative",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      transform: `translate(0px, ${exitY.toFixed(2)}px) scale(${finalScale.toFixed(4)})`,
      transformOrigin: "center",
      opacity: groupOpacity
    }}
  >
            {
    /* Rotation group. §4 second plane (2026-08-24): a stamp struck
       once is a graphic; struck twice it's a physical act. The ghost
       impression sits BEHIND at an offset + its own small rotation,
       soft and inkier; the crisp strike occludes it. Both live inside
       the press group so they land as one object. Shadow moved onto
       the crisp strike only — the ghost is ink, not an object. */
  }
            <div
    style={{
      position: "relative",
      transform: `rotate(${finalRot}deg)`,
      transformOrigin: "center"
    }}
  >
              <div
    aria-hidden
    style={{
      position: "absolute",
      inset: 0,
      // Scaled-up rather than laterally offset: a lateral offset
      // puts the ghost's frame BORDER through the crisp glyphs
      // (render-proven: "SOLD" read as "$OLD"). Scaling keeps the
      // ghost frame outside the crisp frame on every side.
      transform: "translate(7px, 12px) scale(1.05) rotate(2.2deg)",
      transformOrigin: "center",
      opacity: 0.14,
      filter: "blur(1.4px)"
    }}
  >
                {badge}
              </div>
              <div style={{ position: "relative", filter: BADGE_SHADOW }}>
                {badge}
              </div>
            </div>
          </div>
        </MotionBlurWrap>
      </div>
    </AbsoluteFill3>;
};
function subStyle(color, textShadow, fontFamily, metrics) {
  return {
    fontFamily,
    fontWeight: 600,
    fontSize: 26,
    color,
    letterSpacing: "0.2em",
    textTransform: metrics.uppercaseSafe ? "uppercase" : "none",
    lineHeight: Math.max(1, metrics.lineHeight),
    opacity: 0.92,
    textShadow
  };
}
