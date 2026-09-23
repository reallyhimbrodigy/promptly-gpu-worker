// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/Timeline/Timeline.tsx
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

// src/motion-graphics/shared/schedule.ts
var mgSchedule = (opts) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, settleBy * Math.max(1, window) / scaledEnd);
  return (f60) => f60 * scale * c;
};

// src/motion-graphics/Timeline/Timeline.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var DEFAULT_TEXT_SHADOW = "none";
var START = 8;
var SEG = 18;
var POP = 16;
var RAIL_W = 6;
var DEFAULT_STEPS = [
  { label: "Research", description: "Find the real problem" },
  { label: "Design", description: "Shape the solution" },
  { label: "Ship", description: "Put it in the world" }
];
var Timeline = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  steps = DEFAULT_STEPS,
  accentColor = "#FF8A1E",
  trackColor = "rgba(255,255,255,0.16)",
  nodeSize = 84,
  // D4: fit the symmetric center box (max 680) — oversize dragged center right
  width = 680,
  rowGap = 210,
  labelColor = "#15171E",
  indexColor = "#FFFFFF",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center", offsetY: 0 }
  );
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 22 }
  );
  if (!visible) return null;
  const rendered = steps.slice(0, 5);
  const N = rendered.length;
  if (N === 0) return null;
  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: START + (N - 1) * SEG + 30
  });
  const k = K(1);
  const R = nodeSize / 2;
  const inactiveColor = "rgba(255,255,255,0.5)";
  const railX = R;
  const yFor = (i) => R + i * rowGap;
  const railLen = (N - 1) * rowGap;
  const indexSize = Math.round(nodeSize * 0.36);
  const cardLeft = nodeSize + 44;
  const cardWidth = width - cardLeft;
  const blockHeight = railLen + nodeSize + 60;
  const reach = (i) => (START + i * SEG) * k;
  const segF = SEG * k;
  const segCount = N - 1;
  let fillDist = 0;
  if (segCount > 0) {
    const sIndex = Math.max(
      0,
      Math.min(segCount - 1, Math.floor((localFrame - START * k) / segF))
    );
    const tSeg = clamp01((localFrame - reach(sIndex)) / segF);
    fillDist = rowGap * (sIndex + easeInOutCubic(tSeg));
  }
  const headY = R + fillDist;
  const lastReach = reach(N - 1);
  const railDraw = interpolate2(localFrame, [0, 12 * k], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const enterOpacity = interpolate2(localFrame, [0, 8 * k], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const eExit = exitProgress * exitProgress;
  const exitOpacity = 1 - eExit;
  const exitScale = 1 - 0.07 * eExit;
  const exitY = -34 * eExit;
  const headOpacity = segCount > 0 ? interpolate2(
    localFrame,
    [START * k, (START + 5) * k, lastReach, lastReach + 12 * k],
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
      opacity: enterOpacity * exitOpacity,
      transform: `translateY(${exitY.toFixed(2)}px) scale(${exitScale.toFixed(4)})`,
      transformOrigin: "center"
    }}
  >
          {
    /* Rail */
  }
          <div
    style={{
      position: "absolute",
      left: railX - RAIL_W / 2,
      top: R,
      width: RAIL_W,
      height: railLen,
      borderRadius: RAIL_W / 2,
      backgroundColor: trackColor,
      transform: `scaleY(${railDraw.toFixed(3)})`,
      transformOrigin: "top center",
      boxShadow: "inset 0 1px 2px rgba(0,0,0,0.35), 0 2px 8px rgba(0,0,0,0.28)",
    }}
  />

          {
    /* Accent fill */
  }
          <div
    style={{
      position: "absolute",
      left: railX - RAIL_W / 2,
      top: R,
      width: RAIL_W,
      height: fillDist,
      borderRadius: RAIL_W / 2,
      backgroundColor: accentColor,
      backgroundImage: `linear-gradient(90deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.10) 42%, rgba(0,0,0,0.12) 100%)`,
      boxShadow: `0 0 16px ${accentColor}aa, 0 1px 4px rgba(0,0,0,0.3)`,

      willChange: "height"
    }}
  />

          {
    /* Comet head — bright core + soft glow + trailing tail */
  }
          {headOpacity > 0 ? <div
    style={{
      position: "absolute",
      left: railX,
      top: 0,
      opacity: headOpacity,

      pointerEvents: "none"
    }}
  >
              {
    /* Tail — clamped to the travelled rail (pass #10, audited):
       a fixed 90px tail painted accent ink ABOVE the rail's top
       end during the first segment. */
  }
              <div
    style={{
      position: "absolute",
      left: -RAIL_W / 2,
      top: headY - Math.min(90, fillDist),
      width: RAIL_W,
      height: Math.min(90, fillDist),
      borderRadius: RAIL_W / 2,
      background: `linear-gradient(180deg, ${accentColor}00 0%, ${accentColor}cc 100%)`
    }}
  />
              {
    /* Soft glow */
  }
              <div
    style={{
      position: "absolute",
      left: 0,
      top: headY,
      width: 40,
      height: 40,
      transform: "translate(-50%, -50%)",
      borderRadius: "50%",
      background: `radial-gradient(circle, ${accentColor}ee 0%, ${accentColor}00 70%)`
    }}
  />
              {
    /* Bright core */
  }
              <div
    style={{
      position: "absolute",
      left: 0,
      top: headY,
      width: 13,
      height: 13,
      transform: "translate(-50%, -50%)",
      borderRadius: "50%",
      background: "#FFFFFF",
      boxShadow: `0 0 10px ${accentColor}, 0 0 18px ${accentColor}`
    }}
  />
            </div> : null}

          {
    /* Cards — flat poster blocks: a solid accent slab offset behind a
       flat dark slab. No blur, hard graphic edges. */
  }
          {rendered.map((step, i) => {
    const act = reach(i);
    const cardOpacity = interpolate2(
      localFrame,
      [act + 3 * k, act + 16 * k],
      [0, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    const cardX = interpolate2(localFrame, [act + 3 * k, act + 22 * k], [50, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    });
    const offset = interpolate2(localFrame, [act + 6 * k, act + 22 * k], [0, 14], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    });
    const titleRise = interpolate2(localFrame, [act + 5 * k, act + 24 * k], [108, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const descOpacity = interpolate2(localFrame, [act + 16 * k, act + 28 * k], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const descY = interpolate2(localFrame, [act + 16 * k, act + 30 * k], [14, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const ruleGrow = interpolate2(localFrame, [act + 10 * k, act + 26 * k], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const ghostOpacity = interpolate2(localFrame, [act + 8 * k, act + 26 * k], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const ghostX = interpolate2(localFrame, [act + 8 * k, act + 28 * k], [40, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const labelText = String(step.label ?? "");
    const labelMetrics = mgTextMetrics(labelText);
    const labelFont = mgTextFont(labelText, "inter");
    const descFont = step.description ? mgTextFont(step.description, "inter") : undefined;
    const advance = labelMetrics.script === "latin" ? 0.62 : labelMetrics.advanceEm;
    const titleChars = Math.max(1, [...labelText].length);
    const titleSize = Math.min(48, (cardWidth - 60) / (titleChars * advance));
    const ghostNum = step.index ?? String(i + 1).padStart(2, "0");
    return <div
      key={`card-${i}`}
      style={{
        position: "absolute",
        left: cardLeft,
        top: yFor(i),
        width: cardWidth,
        height: 138,
        transform: `translate(${cardX.toFixed(2)}px, -50%)`,
        opacity: cardOpacity,
      }}
    >
                {
      /* Offset accent slab — gradient for depth */
    }
                <div
      style={{
        position: "absolute",
        inset: 0,
        transform: `translate(${offset.toFixed(2)}px, ${offset.toFixed(2)}px)`,
        background: `linear-gradient(135deg, ${accentColor} 0%, ${accentColor} 58%, rgba(0,0,0,0.22) 100%)`,
        borderRadius: 8
      }}
    />
                {
      /* Front flat slab */
    }
                <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        background: "#FFFFFF",
        borderRadius: 8,
        borderLeft: `7px solid ${accentColor}`,
        boxShadow: "0 12px 30px rgba(0,0,0,0.42)"
      }}
    >
                  {
      /* Oversized editorial ghost numeral filling the right space */
    }
                  <span
      style={{
        position: "absolute",
        right: -6,
        top: "50%",
        transform: `translate(${ghostX.toFixed(1)}px, -50%)`,
        fontFamily: MG_FONTS.inter,
        fontSize: 168,
        fontWeight: 900,
        lineHeight: 1,
        color: "rgba(20,22,28,0.05)",
        letterSpacing: "-0.04em",
        opacity: ghostOpacity,
        pointerEvents: "none",
        userSelect: "none"
      }}
    >
                    {ghostNum}
                  </span>

                  {
      /* Text column */
    }
                  <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: step.description ? 8 : 0,
        padding: "0 30px"
      }}
    >
                    {
      /* Title — clip-mask rise */
    }
                    <span style={{ display: "block", overflow: "hidden", paddingBottom: 2 }}>
                      <span
      style={{
        display: "block",
        transform: `translateY(${titleRise.toFixed(2)}%)`,
        fontFamily: labelFont,
        fontSize: titleSize,
        fontWeight: 800,
        color: labelColor,
        letterSpacing: "-0.015em",
        lineHeight: Math.max(1, labelMetrics.lineHeight),
        textTransform: labelMetrics.uppercaseSafe ? "uppercase" : "none",
        whiteSpace: "nowrap",
        textShadow
      }}
    >
                        {step.label}
                      </span>
                    </span>

                    {
      /* Accent rule under the title */
    }
                    <div
      style={{
        width: 56,
        height: 5,
        borderRadius: 3,
        background: accentColor,
        transform: `scaleX(${ruleGrow.toFixed(3)})`,
        transformOrigin: "left center"
      }}
    />

                    {step.description ? <span
      style={{
        fontFamily: descFont,
        fontSize: 26,
        fontWeight: 500,
        color: "rgba(20,22,28,0.6)",
        letterSpacing: "0.005em",
        lineHeight: 1.2,
        opacity: descOpacity,
        transform: `translateY(${descY.toFixed(2)}px)`
      }}
    >
                        {step.description}
                      </span> : null}
                  </div>
                </div>
              </div>;
  })}

          {
    /* Nodes — flat rotated-diamond markers (drawn above cards so the rail
       reads as continuous). Solid accent on reach, ghost outline before. */
  }
          {rendered.map((step, i) => {
    const act = reach(i);
    const reached = localFrame >= act;
    const nodeScale = reached ? interpolate2(localFrame, [act, act + POP * k], [0.5, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    }) : 0.5;
    const nodeOpacity = reached ? interpolate2(localFrame, [act, act + 6 * k], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : interpolate2(localFrame, [act - 10 * k, act], [0, 0.4], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const colorT = reached ? clamp01((localFrame - act) / (12 * k)) : 0;
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
    const fillScale = reached ? easeOutBack(clamp01((localFrame - act) / (POP * k))) : 0;
    const fillRot = reached ? interpolate2(localFrame, [act, act + POP * k], [0, 45], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutBack
    }) : 0;
    const ringScale = interpolate2(localFrame, [act, act + 20 * k], [0.9, 1.9], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easeOutCubic
    });
    const ringOpacity = reached ? interpolate2(localFrame, [act, act + 4 * k, act + 22 * k], [0, 0.5, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    }) : 0;
    const shapeSize = nodeSize * 0.72;
    const shapeInset = (nodeSize - shapeSize) / 2;
    return <div
      key={`node-${i}`}
      style={{
        position: "absolute",
        left: railX - R,
        top: yFor(i) - R,
        width: nodeSize,
        height: nodeSize,
        transform: `scale(${nodeScale.toFixed(4)})`,
        transformOrigin: "center",
        opacity: nodeOpacity,

        willChange: "transform"
      }}
    >
                {
      /* Arrival diamond ring-pulse */
    }
                {ringOpacity > 0 ? <div
      style={{
        position: "absolute",
        left: shapeInset,
        top: shapeInset,
        width: shapeSize,
        height: shapeSize,
        border: `2px solid ${accentColor}`,
        transform: `rotate(45deg) scale(${ringScale})`,
        opacity: ringOpacity,
        pointerEvents: "none"
      }}
    /> : null}

                {
      /* Ghost diamond outline */
    }
                <div
      style={{
        position: "absolute",
        left: shapeInset,
        top: shapeInset,
        width: shapeSize,
        height: shapeSize,
        transform: "rotate(45deg)",
        border: `3px solid ${ringColor}`,
        background: "rgba(10,11,15,0.30)",
        boxShadow: "0 8px 20px rgba(0,0,0,0.45)"
      }}
    />

                {
      /* Solid accent diamond fill on reach */
    }
                <div
      style={{
        position: "absolute",
        left: shapeInset,
        top: shapeInset,
        width: shapeSize,
        height: shapeSize,
        transform: `rotate(${fillRot.toFixed(2)}deg) scale(${fillScale.toFixed(4)})`,
        transformOrigin: "center",
        background: accentColor
      }}
    />

                {
      /* Index numeral (kept upright) */
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
        textShadow: "0 1px 3px rgba(0,0,0,0.5)"
      }}
    >
                    {step.index ?? String(i + 1).padStart(2, "0")}
                  </span>
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
  return <div style={rootStyle}><Timeline {...p} /></div>;
};
