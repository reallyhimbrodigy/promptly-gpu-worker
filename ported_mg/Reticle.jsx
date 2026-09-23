// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/Reticle/Reticle.tsx
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

// src/motion-graphics/Reticle/Reticle.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var DEFAULT_TEXT_SHADOW = "0 2px 10px rgba(0,0,0,0.7), 0 1px 2px rgba(0,0,0,0.55)";
var SPREAD0 = 130;
var LOCK = 18;
var REC_COLOR = "#FF3B30";
var CORNERS = ["tl", "tr", "bl", "br"];
var Reticle = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  label,
  regionWidth = 620,
  regionHeight = 720,
  bracketColor = "#FFFFFF",
  accentColor = "#36E27A",
  showScanline = true,
  showCrosshair = false,
  armLength = 64,
  thickness = 5,
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
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 16, defaultExitFrames: 16 }
  );
  if (!visible) return null;
  const smoothEntrance = useSmoothGraphics();
  const focus = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: LOCK }) : easeOutBack(clamp01(localFrame / LOCK));
  const exitDefocus = easeOutCubic(exitProgress);
  const spread = (1 - focus) * SPREAD0 + exitDefocus * SPREAD0;
  const bracketsOpacity = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 10 }) : interpolate2(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const lockPulse = interpolate2(
    localFrame,
    [LOCK - 1, LOCK + 1, LOCK + 3, LOCK + 5, LOCK + 7],
    [1, 0.96, 1, 0.985, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const lockT = clamp01((localFrame - LOCK) / 6);
  const lockedColor = interpolateColors(
    lockT,
    [0, 1],
    [bracketColor, accentColor]
  );
  const liveColor = interpolateColors(
    clamp01(exitProgress * 1.3),
    [0, 1],
    [lockedColor, bracketColor]
  );
  const lockGlow = interpolate2(
    localFrame,
    [LOCK, LOCK + 3, LOCK + 14],
    [0, 14, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const tagFont = mgTextFont(label ?? "", "inter");
  const tagMetrics = mgTextMetrics(label ?? "");
  const tagScale = easeOutBack(clamp01((localFrame - LOCK) / 28));
  const tagOpacity = interpolate2(localFrame, [LOCK, LOCK + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const recPulse = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(localFrame * 0.11));
  const scanY = interpolate2(localFrame, [10, 48, 86], [0, regionHeight, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic
  });
  const scanOpacity = showScanline ? interpolate2(localFrame, [10, 16, 78, 86], [0, 0.55, 0.55, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  }) : 0;
  const crossOpacity = showCrosshair ? interpolate2(localFrame, [6, 14], [0, 0.8], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  }) : 0;
  const exitOpacity = 1 - clamp01(exitProgress * 1.15);
  const exitScale = 1 + 0.05 * exitDefocus;
  const arm = Math.max(
    0,
    Math.min(
      armLength,
      regionWidth / 2 - thickness,
      regionHeight / 2 - thickness
    )
  );
  const cornerStyle = (c) => {
    const base = {
      position: "absolute",
      width: arm,
      height: arm,
      boxSizing: "border-box"
    };
    const dx = c === "tl" || c === "bl" ? -spread : spread;
    const dy = c === "tl" || c === "tr" ? -spread : spread;
    const border = `${thickness}px solid ${liveColor}`;
    const edges = c === "tl" ? { left: 0, top: 0, borderTop: border, borderLeft: border } : c === "tr" ? { right: 0, top: 0, borderTop: border, borderRight: border } : c === "bl" ? { left: 0, bottom: 0, borderBottom: border, borderLeft: border } : { right: 0, bottom: 0, borderBottom: border, borderRight: border };
    return {
      ...base,
      ...edges,
      transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px)`,
      filter: lockGlow > 0.1 ? `drop-shadow(0 0 ${lockGlow.toFixed(1)}px ${accentColor})` : undefined
    };
  };
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      position: "relative",
      width: regionWidth,
      height: regionHeight,
      opacity: exitOpacity,
      transform: `scale(${(lockPulse * exitScale).toFixed(4)})`,
      transformOrigin: "center"
    }}
  >
          {
    /* §4-for-footage (2026-08-25): the WINDOW plane. A viewfinder is
       axis-aligned by nature — tilt/overlap read as error here. The
       depth device for this family is selection: everything OUTSIDE
       the region dims as the lock lands (box-shadow spill — one node,
       no four-rect math), so the HUD occludes the footage around the
       subject and the region reads as a window, not four floating
       corners. Releases with the exit defocus. */
  }
          {
    /* THE WINDOW PLANE IS GONE (2026-09-23). It dimmed everything OUTSIDE the
       region with a single node — `boxShadow: 0 0 0 9999px rgba(0,0,0,.26)` —
       and the comment above called that a feature: "one node, no four-rect
       math". THEIR RENDERER PAINTS THAT SPILL INSIDE THE ELEMENT, so the
       window plane became a translucent grey slab filling the box, across the
       subject's face, in ChatCut's own export.

       Not reimplemented as four rects. It is DECORATION — the brackets and
       the scanline are what make this a reticle — and this is the third
       decorative layer this week to render as a defect (SectionDivider's
       scrim and vignette, StickyNotes' fog). A layer that exists to add
       atmosphere and can arrive as an opaque panel is not worth the
       geometry to keep. */
  }

          {
    /* Corner brackets */
  }
          <div style={{ position: "absolute", inset: 0, opacity: bracketsOpacity }}>
            {CORNERS.map((c) => <div key={c} style={cornerStyle(c)} />)}
            {
    /* Restrained HUD furniture: midpoint edge ticks — the marks a
       real viewfinder carries. Corpus register is fragments, so the
       furniture stays minimal: four ticks, no readouts. */
  }
            {[
    { left: "50%", top: -1, width: 2, height: 14, translate: "-50% 0" },
    { left: "50%", bottom: -1, width: 2, height: 14, translate: "-50% 0" },
    { left: -1, top: "50%", width: 14, height: 2, translate: "0 -50%" },
    { right: -1, top: "50%", width: 14, height: 2, translate: "0 -50%" }
  ].map((t, i) => <div
    key={`tick-${i}`}
    style={{
      position: "absolute",
      ...t,
      backgroundColor: liveColor,
      opacity: 0.75
    }}
  />)}
          </div>

          {
    /* Scanline */
  }
          {scanOpacity > 0 ? <div
    style={{
      position: "absolute",
      left: 0,
      top: scanY,
      width: "100%",
      height: 2,
      background: `linear-gradient(90deg, ${accentColor}00, ${accentColor}, ${accentColor}00)`,
      boxShadow: `0 0 12px ${accentColor}`,
      opacity: scanOpacity,
      pointerEvents: "none"
    }}
  /> : null}

          {
    /* Center crosshair */
  }
          {crossOpacity > 0 ? <div
    style={{
      position: "absolute",
      left: "50%",
      top: "50%",
      transform: "translate(-50%, -50%)",
      opacity: crossOpacity,
      pointerEvents: "none"
    }}
  >
              <div
    style={{
      position: "absolute",
      left: -16,
      top: -1,
      width: 32,
      height: 2,
      backgroundColor: liveColor
    }}
  />
              <div
    style={{
      position: "absolute",
      left: -1,
      top: -16,
      width: 2,
      height: 32,
      backgroundColor: liveColor
    }}
  />
            </div> : null}

          {
    /* REC tag at the top-left corner */
  }
          {label ? <div
    style={{
      position: "absolute",
      // INSIDE THE REGION, NOT ABOVE IT (2026-09-23). The tag was at top:0
      // with `translateY(calc(-100% - 14px))`, which puts it ENTIRELY ABOVE
      // the bracket region — its own height plus 14px clear of the top edge.
      // In our renderer that is fine, and a local frame shows "REC" sitting
      // over the box. In CHATCUT THE REGISTERED BOX IS A CLIP BOX, so
      // everything above the region's top edge is cut, and the label never
      // appears on any frame of its life. inspect_item shows the override
      // arriving because it DOES arrive; it is drawn and then cropped.
      //
      // `armLength + 14` clears the corner bracket, so the tag sits under the
      // top-left arm rather than on it.
      left: 14,
      top: armLength + 14,
      transform: `scale(${tagScale.toFixed(4)})`,
      transformOrigin: "top left",
      opacity: tagOpacity,
      display: "inline-flex",
      alignItems: "center",
      gap: 12,
      padding: "12px 22px",
      borderRadius: 14,
      // BACKDROP-FILTER IS NOT DRAWN BY THEIR RENDERER, and what it leaves is
      // not nothing — it is this element's own fill, painted flat. At 42%
      // opacity the "glass" tag becomes a translucent grey slab. It only
      // draws when `label` is set, so it is not today's defect; it is today's
      // defect waiting for the first caller who sets one. A solid fill
      // renders the same everywhere, so the look is chosen rather than left
      // to whatever each renderer happens to support.
      background: "rgba(16,18,24,0.88)",
      border: "1.5px solid rgba(255,255,255,0.18)",
      boxShadow: "0 12px 30px rgba(0,0,0,0.42)",
      whiteSpace: "nowrap"
    }}
  >
              <div
    style={{
      width: 12,
      height: 12,
      borderRadius: "50%",
      backgroundColor: REC_COLOR,
      boxShadow: `0 0 12px ${REC_COLOR}`,
      opacity: recPulse
    }}
  />
              <span
    style={{
      fontFamily: tagFont,
      fontSize: 30,
      fontWeight: 700,
      color: "#FFFFFF",
      letterSpacing: "0.12em",
      textTransform: tagMetrics.uppercaseSafe ? "uppercase" : "none",
      lineHeight: Math.max(1, tagMetrics.lineHeight),
      textShadow
    }}
  >
                {label}
              </span>
            </div> : null}
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
  return <div style={rootStyle}><Reticle {...p} /></div>;
};
