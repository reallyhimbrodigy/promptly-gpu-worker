// ── ported prelude: injected globals re-bound ──
const React2 = React;
const interpolate2 = interpolate;
const useContext = React.useContext;
const useId = React.useId;
const createContext = React.createContext;

// src/motion-graphics/TimelineRoadmap/TimelineRoadmap.tsx
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

// src/motion-graphics/TimelineRoadmap/TimelineRoadmap.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var DEFAULT_TEXT_SHADOW = "0 3px 16px rgba(0,0,0,0.7), 0 1px 3px rgba(0,0,0,0.6)";
var START = 8;
var SEG = 18;
var POP = 16;
var SPINE_W = 9;
var LABEL_OFFSET = 30;
var TICK = 30;
var DEFAULT_ACCENT = "#FF8A1E";
var DEFAULT_STEPS = [
  { label: "Discovery", sublabel: "Week 1" },
  { label: "Design", sublabel: "Week 2" },
  { label: "Build", sublabel: "Weeks 3\u20135" },
  { label: "Launch", sublabel: "Week 6" }
];
var bez = (s, t) => {
  const u = 1 - t;
  return {
    x: u * u * u * s.p0.x + 3 * u * u * t * s.c1.x + 3 * u * t * t * s.c2.x + t * t * t * s.p1.x,
    y: u * u * u * s.p0.y + 3 * u * u * t * s.c1.y + 3 * u * t * t * s.c2.y + t * t * t * s.p1.y
  };
};
var TimelineRoadmap = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  steps = DEFAULT_STEPS,
  accentColor = DEFAULT_ACCENT,
  trackColor = "rgba(255,255,255,0.18)",
  sublabelColor,
  nodeSize = 96,
  width = 1040,
  rowHeight = 312,
  firstSide = "right",
  labelColor = "#FFFFFF",
  indexColor = "#FFFFFF",
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
    { defaultEnterFrames: 18, defaultExitFrames: 54 }
  );
  const gradId = `rmGrad${React2.useId().replace(/:/g, "")}`;
  if (!visible) return null;
  const rendered = steps.slice(0, 6);
  const N = rendered.length;
  if (N === 0) return null;
  const R = nodeSize / 2;
  const inactiveColor = "rgba(255,255,255,0.5)";
  const indexSize = Math.round(nodeSize * 0.4);
  const rh = Math.min(
    rowHeight,
    (SAFE_RECT.height - nodeSize) / Math.max(1, N - 1)
  );
  const blockHeight = (N - 1) * rh + nodeSize;
  const pillInk = sublabelColor ?? (accentColor === DEFAULT_ACCENT ? "#10131A" : inkFor(accentColor, "#10131A"));
  const xLeft = width * 0.27;
  const xRight = width * 0.73;
  const labelOnRight = (i) => firstSide === "right" ? i % 2 === 0 : i % 2 === 1;
  const yFor = (i) => R + i * rh;
  const nodeXFor = (i) => labelOnRight(i) ? xLeft : xRight;
  const pts = rendered.map((_, i) => ({ x: nodeXFor(i), y: yFor(i) }));
  const SWING = 0.62;
  const segs = [];
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 1; i < N; i++) {
    const p0 = pts[i - 1];
    const p1 = pts[i];
    const dy = p1.y - p0.y;
    const c1 = { x: p0.x, y: p0.y + dy * SWING };
    const c2 = { x: p1.x, y: p1.y - dy * SWING };
    d += ` C ${c1.x.toFixed(2)} ${c1.y.toFixed(2)} ${c2.x.toFixed(2)} ${c2.y.toFixed(2)} ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
    segs.push({ p0, c1, c2, p1 });
  }
  const reach = (i) => START + i * SEG;
  const segCount = N - 1;
  let entUnits = 0;
  if (segCount > 0) {
    const si = Math.max(
      0,
      Math.min(segCount - 1, Math.floor((localFrame - START) / SEG))
    );
    const ts = clamp01((localFrame - reach(si)) / SEG);
    entUnits = si + easeInOutCubic(ts);
  }
  const entFrac = segCount > 0 ? clamp01(entUnits / segCount) : localFrame >= START ? 1 : 0;
  const sweep = easeInOutCubic(clamp01(exitProgress));
  const eFrac = entFrac;
  const sFrac = sweep;
  const visLen = Math.max(0, eFrac - sFrac);
  const tipFrac = sweep > 0 ? sFrac : eFrac;
  let sIndex = 0;
  let tSeg = 0;
  if (segCount > 0) {
    const units = tipFrac * segCount;
    sIndex = Math.max(0, Math.min(segCount - 1, Math.floor(units)));
    tSeg = clamp01(units - sIndex);
  }
  const comet = segs.length ? bez(segs[sIndex], tSeg) : pts[0];
  const hp = clamp01(comet.y / blockHeight);
  const lastReach = reach(N - 1);
  const enterOpacity = interpolate2(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const headOpacity = segCount > 0 ? interpolate2(
    localFrame,
    [START, START + 5, lastReach, lastReach + 12],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  ) : 0;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      position: "relative",
      width,
      height: blockHeight,
      opacity: enterOpacity,
      transformOrigin: "center"
    }}
  >
          {
    /* Serpentine beam (SVG): flowing dotted "route ahead" + a glowing
       accent draw-on with a white-hot gradient tip and a gloss core. */
  }
          <svg
    width={width}
    height={blockHeight}
    viewBox={`0 0 ${width} ${blockHeight}`}
    style={{
      position: "absolute",
      left: 0,
      top: 0,
      overflow: "visible",
      zIndex: 0
    }}
  >
            <defs>
              {
    /* White-hot zone tracks the comet's vertical position, fading to
       accent behind it — reads as energy flowing to the leading tip. */
  }
              <linearGradient
    id={gradId}
    gradientUnits="userSpaceOnUse"
    x1={0}
    y1={0}
    x2={0}
    y2={blockHeight}
  >
                {sweep > 0 ? (
    // Exit: flat accent — no white-hot tip (it pooled into a
    // glowing dot at the sweeping tail / start node).
    <>
                    <stop offset={0} stopColor={accentColor} />
                    <stop offset={1} stopColor={accentColor} />
                  </>
  ) : <>
                    <stop offset={0} stopColor={accentColor} />
                    <stop offset={Math.max(0, hp - 0.16)} stopColor={accentColor} />
                    <stop offset={Math.max(1e-3, hp - 0.04)} stopColor="#FFE9C7" />
                    <stop offset={hp} stopColor="#FFFFFF" />
                    <stop offset={Math.min(1, hp + 0.015)} stopColor={accentColor} />
                    <stop offset={1} stopColor={accentColor} />
                  </>}
              </linearGradient>
            </defs>

            {
    /* Route ahead — flowing dots (fade off as the line sweeps away) */
  }
            <path
    d={d}
    fill="none"
    stroke="rgba(255,255,255,0.30)"
    strokeWidth={SPINE_W * 0.7}
    strokeLinecap="round"
    strokeDasharray="0.2 22"
    strokeDashoffset={-localFrame * 1.1}
    style={{ opacity: clamp01(1 - sweep * 5) }}
  />
            {
    /* Soft accent glow underlay */
  }
            <path
    d={d}
    fill="none"
    stroke={accentColor}
    strokeWidth={SPINE_W * 2.8}
    strokeLinecap="round"
    pathLength={1}
    strokeDasharray={`${visLen.toFixed(4)} 2`}
    strokeDashoffset={-sFrac}
    style={{ filter: "blur(8px)", opacity: 0.6 }}
  />
            {
    /* Gradient core (white-hot tip → accent) */
  }
            <path
    d={d}
    fill="none"
    stroke={`url(#${gradId})`}
    strokeWidth={SPINE_W}
    strokeLinecap="round"
    pathLength={1}
    strokeDasharray={`${visLen.toFixed(4)} 2`}
    strokeDashoffset={-sFrac}
  />
            {
    /* Gloss center line */
  }
            <path
    d={d}
    fill="none"
    stroke="rgba(255,255,255,0.6)"
    strokeWidth={1.6}
    strokeLinecap="round"
    pathLength={1}
    strokeDasharray={`${visLen.toFixed(4)} 2`}
    strokeDashoffset={-sFrac}
  />
          </svg>

          {
    /* Comet head riding the curve */
  }
          {headOpacity > 0 ? <div
    style={{
      position: "absolute",
      left: 0,
      top: 0,
      opacity: headOpacity,
      zIndex: 2,
      pointerEvents: "none"
    }}
  >
              <div
    style={{
      position: "absolute",
      left: comet.x,
      top: comet.y,
      width: 46,
      height: 46,
      transform: "translate(-50%, -50%)",
      borderRadius: "50%",
      background: `radial-gradient(circle, ${accentColor}ee 0%, ${accentColor}00 70%)`
    }}
  />
              <div
    style={{
      position: "absolute",
      left: comet.x,
      top: comet.y,
      width: 14,
      height: 14,
      transform: "translate(-50%, -50%)",
      borderRadius: "50%",
      background: "#FFFFFF",
      boxShadow: `0 0 10px ${accentColor}, 0 0 20px ${accentColor}`
    }}
  />
            </div> : null}

          {
    /* Nodes — flat glowing waypoints (no glass) */
  }
          {rendered.map((step, i) => {
    const act = reach(i);
    const reached = localFrame >= act;
    const nodeScale = reached ? interpolate2(localFrame, [act, act + POP], [0.5, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    }) : 0.5;
    const nodeOpacity = reached ? interpolate2(localFrame, [act, act + 6], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : interpolate2(localFrame, [act - 10, act], [0, 0.4], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const colorT = reached ? clamp01((localFrame - act) / 12) : 0;
    const ringColor = interpolateColors(
      colorT,
      [0, 1],
      [inactiveColor, accentColor]
    );
    const idxColor = interpolateColors(
      colorT,
      [0, 1],
      [inactiveColor, indexColor]
    );
    const fillScale = reached ? easeOutBack(clamp01((localFrame - act) / POP)) : 0;
    const idleAmt = reached ? clamp01((localFrame - act - 14) / 14) : 0;
    const idleGlow = idleAmt * (10 + 10 * (0.5 + 0.5 * Math.sin((localFrame - act) * 0.09)) * (1 - sweep));
    const ringScale = interpolate2(localFrame, [act, act + 22], [0.7, 1.8], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const ringOpacity = reached ? interpolate2(localFrame, [act, act + 4, act + 24], [0, 0.55, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : 0;
    const nodeFrac = segCount > 0 ? i / segCount : 0;
    const gone = clamp01((sweep - nodeFrac * 0.8) / 0.18);
    const fa = pts[Math.max(0, i - 1)];
    const fb = pts[Math.min(N - 1, i + 1)];
    const flv = Math.hypot(fb.x - fa.x, fb.y - fa.y) || 1;
    const exitDX = (fb.x - fa.x) / flv * 80 * gone;
    const exitDY = (fb.y - fa.y) / flv * 80 * gone;
    const exitScaleN = 1 - 0.4 * gone;
    return <div
      key={`node-${i}`}
      style={{
        position: "absolute",
        left: nodeXFor(i) - R,
        top: yFor(i) - R,
        width: nodeSize,
        height: nodeSize,
        transform: `translate(${exitDX.toFixed(2)}px, ${exitDY.toFixed(2)}px) scale(${(nodeScale * exitScaleN).toFixed(4)})`,
        transformOrigin: "center",
        opacity: nodeOpacity * (1 - gone),
        zIndex: 4,
        willChange: "transform"
      }}
    >
                {
      /* Arrival orbit ring */
    }
                {ringOpacity > 0 ? <div
      style={{
        position: "absolute",
        inset: -6,
        borderRadius: "50%",
        border: `2px solid ${accentColor}`,
        transform: `scale(${ringScale})`,
        opacity: ringOpacity,
        pointerEvents: "none"
      }}
    /> : null}

                {
      /* Base disc — solid dark, accent ring, glow on activation */
    }
                <div
      style={{
        position: "absolute",
        inset: 0,
        borderRadius: "50%",
        background: "#0E1117",
        border: `3px solid ${ringColor}`,
        boxShadow: `0 10px 24px rgba(0,0,0,0.55), 0 0 ${(idleGlow + 8 * fillScale).toFixed(2)}px ${accentColor}`
      }}
    />

                {
      /* Solid accent fill on reach */
    }
                <div
      style={{
        position: "absolute",
        inset: 0,
        borderRadius: "50%",
        background: `radial-gradient(circle at 38% 32%, ${accentColor}, ${accentColor}d8)`,
        transform: `scale(${fillScale.toFixed(4)})`,
        transformOrigin: "center"
      }}
    />

                {
      /* Index numeral */
    }
                <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center"
      }}
    >
                  <span
      style={{
        fontFamily: MG_FONTS.jetBrainsMono,
        fontSize: indexSize,
        fontWeight: 700,
        color: idxColor,
        letterSpacing: "-0.02em",
        lineHeight: 1,
        fontVariantNumeric: "tabular-nums",
        textShadow: "0 1px 3px rgba(0,0,0,0.55)"
      }}
    >
                    {step.index ?? String(i + 1).padStart(2, "0")}
                  </span>
                </div>
              </div>;
  })}

          {
    /* Labels — light editorial text + accent connector tick + sublabel pill */
  }
          {rendered.map((step, i) => {
    const act = reach(i);
    const onRight = labelOnRight(i);
    const nodeX = nodeXFor(i);
    const labelOpacity = interpolate2(localFrame, [act + 5, act + 18], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const slide = interpolate2(localFrame, [act + 5, act + 22], [26, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const tickGrow = interpolate2(localFrame, [act + 2, act + 16], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const pillPop = interpolate2(localFrame, [act + 12, act + 24], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    });
    const dir = onRight ? 1 : -1;
    const nodeFrac = segCount > 0 ? i / segCount : 0;
    const gone = clamp01((sweep - nodeFrac * 0.8) / 0.18);
    const fa = pts[Math.max(0, i - 1)];
    const fb = pts[Math.min(N - 1, i + 1)];
    const flv = Math.hypot(fb.x - fa.x, fb.y - fa.y) || 1;
    const exitDX = (fb.x - fa.x) / flv * 80 * gone;
    const exitDY = (fb.y - fa.y) / flv * 80 * gone;
    const anchorStyle = onRight ? { left: nodeX + R } : { right: width - (nodeX - R) };
    const labelMetrics = mgTextMetrics(step.label);
    const labelFont = mgTextFont(step.label, "inter");
    const sublabelMetrics = mgTextMetrics(step.sublabel ?? "");
    const sublabelFont = mgTextFont(step.sublabel ?? "", "inter");
    return <div
      key={`label-${i}`}
      style={{
        position: "absolute",
        top: yFor(i),
        ...anchorStyle,
        transform: `translateY(-50%) translateX(${(dir * slide).toFixed(2)}px) translate(${exitDX.toFixed(2)}px, ${exitDY.toFixed(2)}px)`,
        opacity: labelOpacity * (1 - gone),
        zIndex: 3,
        display: "flex",
        flexDirection: onRight ? "row" : "row-reverse",
        alignItems: "center",
        gap: LABEL_OFFSET - TICK + 14
      }}
    >
                {
      /* Connector tick */
    }
                <div
      style={{
        flex: "0 0 auto",
        width: TICK,
        height: 4,
        borderRadius: 2,
        background: accentColor,
        boxShadow: `0 0 10px ${accentColor}aa`,
        transform: `scaleX(${tickGrow.toFixed(3)})`,
        transformOrigin: onRight ? "left center" : "right center"
      }}
    />

                <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: onRight ? "flex-start" : "flex-end",
        gap: 10
      }}
    >
                  <div
      style={{
        fontFamily: labelFont,
        fontSize: 58,
        fontWeight: 800,
        color: labelColor,
        letterSpacing: "-0.015em",
        lineHeight: Math.max(1.02, labelMetrics.lineHeight),
        textTransform: labelMetrics.uppercaseSafe ? "uppercase" : "none",
        whiteSpace: "nowrap",
        textAlign: onRight ? "left" : "right",
        textShadow
      }}
    >
                    {step.label}
                  </div>
                  {step.sublabel ? <div
      style={{
        transform: `scale(${pillPop.toFixed(3)})`,
        transformOrigin: onRight ? "left center" : "right center",
        padding: "6px 18px",
        borderRadius: 999,
        background: accentColor,
        fontFamily: sublabelFont,
        fontSize: 28,
        fontWeight: 700,
        color: pillInk,
        letterSpacing: "0.03em",
        lineHeight: Math.max(1.1, sublabelMetrics.lineHeight),
        textTransform: sublabelMetrics.uppercaseSafe ? "uppercase" : "none",
        whiteSpace: "nowrap",
        boxShadow: `0 4px 14px ${accentColor}66`
      }}
    >
                      {step.sublabel}
                    </div> : null}
                </div>
              </div>;
  })}
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
  return <div style={rootStyle}><TimelineRoadmap {...p} /></div>;
};
