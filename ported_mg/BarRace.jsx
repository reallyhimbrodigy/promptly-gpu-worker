// ── ported prelude: injected globals re-bound ──
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/BarRace/BarRace.tsx
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

// src/motion-graphics/BarRace/BarRace.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
var easeOutBack = (t) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
var hexA = (a) => Math.round(clamp01(a) * 255).toString(16).padStart(2, "0");
var DEFAULT_TEXT_SHADOW = "0 2px 12px rgba(0,0,0,0.6), 0 1px 3px rgba(0,0,0,0.5)";
var START = 8;
var STAGGER = 7;
var GROW = 32;
var ROW_H = 162;
var BAR_H = 56;
var LABEL_H = 52;
var LABEL_GAP = 16;
var VALUE_RESERVE = 148;
var SHEEN_W = 82;
var BADGE = 48;
var NEUTRAL = "#FFFFFF";
var BarRace = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  bars = [],
  maxValue,
  mode = "compare",
  valuePrefix = "",
  valueSuffix = "",
  accentColor = "#FFB23E",
  // D4: fit the symmetric center box (max 680) — oversize dragged center right
  width = 680,
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  if (!bars || bars.length === 0) return null;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" }
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 22, defaultExitFrames: 18 }
  );
  if (!visible) return null;
  const rendered = bars.slice(0, 4);
  const N = rendered.length;
  if (N === 0) return null;
  const maxVal = Math.max(
    1,
    maxValue ?? Math.max(...rendered.map((b) => b.value))
  );
  const barAreaW = width - VALUE_RESERVE;
  const blockHeight = N * ROW_H;
  const eps = maxVal * 0.05;
  const affixText = `${valuePrefix}${valueSuffix}`;
  const affixFont = mgTextFont(affixText, "inter");
  const affixLineHeight = Math.max(1, mgTextMetrics(affixText).lineHeight);
  const exitOpacity = 1 - exitProgress;
  const exitY = -10 * exitProgress;
  const curValue = (i) => {
    const act = mode === "race" ? START : START + i * STAGGER;
    const grow = easeOutCubic(clamp01((localFrame - act) / GROW));
    return rendered[i].value * grow;
  };
  const leaderFinalIndex = rendered.reduce(
    (best, b, i) => b.value > rendered[best].value ? i : best,
    0
  );
  const settleFrame = START + (N - 1) * STAGGER + GROW;
  const compareRank = [];
  rendered.map((_, i) => i).sort((a, b) => rendered[b].value - rendered[a].value).forEach((idx, r) => {
    compareRank[idx] = r + 1;
  });
  const fracRank = (i) => {
    const ci = curValue(i);
    let r = 0;
    for (let j = 0; j < N; j++) {
      if (j === i) continue;
      const cj = curValue(j);
      r += clamp01((cj - ci) / eps + 0.5);
    }
    return r;
  };
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      position: "relative",
      width,
      height: blockHeight,
      opacity: exitOpacity,
      transform: `translateY(${exitY.toFixed(2)}px)`
    }}
  >
          {rendered.map((bar, i) => {
    const cur = curValue(i);
    const fillW = barAreaW * clamp01(cur / maxVal);
    const emphasis = mode === "race" ? clamp01(1 - fracRank(i)) : i === leaderFinalIndex ? interpolate2(
      localFrame,
      [settleFrame - 4, settleFrame + 18],
      [0, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeInOutCubic
      }
    ) : 0;
    const isLeaderRow = mode === "race" ? fracRank(i) < 0.5 : i === leaderFinalIndex;
    const rank = mode === "race" ? Math.round(fracRank(i)) + 1 : compareRank[i];
    const fillColor = bar.color ?? interpolateColors(emphasis, [0, 1], [NEUTRAL, accentColor]);
    const glowColor = bar.color ?? accentColor;
    const pulse = mode === "compare" && i === leaderFinalIndex ? interpolate2(
      localFrame,
      [settleFrame, settleFrame + 5, settleFrame + 13],
      [1, 1.04, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    ) : 1;
    const act = mode === "race" ? START : START + i * STAGGER;
    const rowOpacity = interpolate2(localFrame, [act, act + 8], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const sweepStart = act + GROW - 6;
    const sweep = clamp01((localFrame - sweepStart) / 22);
    const sweepX = sweep * (fillW + SHEEN_W) - SHEEN_W;
    const sweepOpacity = sweep > 0 && sweep < 1 ? Math.sin(sweep * Math.PI) * 0.9 : 0;
    const y = mode === "race" ? fracRank(i) * ROW_H : i * ROW_H;
    const valueColor = bar.color ?? interpolateColors(emphasis, [0, 1], ["#FFFFFF", accentColor]);
    const settleAmt = clamp01((emphasis - 0.6) / 0.4);
    const crownScale = easeOutBack(clamp01(emphasis));
    const crownOpacity = clamp01(emphasis * 1.4);
    const crownY = -14 * (1 - clamp01(emphasis)) + Math.sin(localFrame * 0.16) * 5 * settleAmt;
    const crownRot = Math.sin(localFrame * 0.12) * 5 * settleAmt;
    return <div
      key={i}
      style={{
        position: "absolute",
        left: 0,
        top: y,
        width,
        height: ROW_H,
        opacity: rowOpacity,
        willChange: "top"
      }}
    >
                {
      /* Label row: rank badge + name */
    }
                <div
      style={{
        height: LABEL_H,
        display: "flex",
        alignItems: "center",
        gap: 16
      }}
    >
                  <div
      style={{
        width: BADGE,
        height: BADGE,
        borderRadius: BADGE / 2,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: MG_FONTS.inter,
        fontSize: 25,
        fontWeight: 800,
        color: "#0B1220",
        backgroundColor: fillColor,
        boxShadow: `0 5px 18px ${glowColor}${hexA(emphasis * 0.66)}`
      }}
    >
                    {rank}
                  </div>
                  <div
      style={{
        // Bar labels are user text (font census 2026-08-26).
        fontFamily: mgTextFont(bar.label, "inter"),
        fontSize: 40,
        fontWeight: 700,
        // Blends white → accent in step with the bar fill.
        color: valueColor,
        letterSpacing: "0.005em",
        lineHeight: Math.max(1, mgTextMetrics(bar.label).lineHeight),
        textShadow
      }}
    >
                    {bar.label}
                  </div>
                </div>

                {
      /* Track */
    }
                <div
      style={{
        position: "relative",
        marginTop: LABEL_GAP,
        width: barAreaW,
        height: BAR_H,
        borderRadius: BAR_H / 2,
        backgroundColor: "transparent"
      }}
    >
                  {
      /* Fill */
    }
                  <div
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        width: fillW,
        height: BAR_H,
        borderRadius: BAR_H / 2,
        overflow: "hidden",
        backgroundColor: fillColor,
        // Tip-brightening horizontal pass + a vertical gloss.
        backgroundImage: "linear-gradient(90deg, rgba(0,0,0,0.16) 0%, rgba(0,0,0,0) 50%, rgba(255,255,255,0.26) 100%), linear-gradient(180deg, rgba(255,255,255,0.40) 0%, rgba(255,255,255,0) 50%, rgba(0,0,0,0.22) 100%)",
        transform: `scaleY(${pulse.toFixed(4)})`,
        transformOrigin: "center",
        // Warm glow fades in with the leader signal (no snap).
        boxShadow: `0 0 ${(44 * emphasis).toFixed(1)}px ${glowColor}${hexA(emphasis * 0.73)}, inset 0 1px 0 rgba(255,255,255,${(0.5 + 0.15 * emphasis).toFixed(2)})`,
        willChange: "width"
      }}
    >
                    {
      /* Traveling sheen */
    }
                    {sweepOpacity > 0 ? <div
      style={{
        position: "absolute",
        top: 0,
        left: sweepX,
        width: SHEEN_W,
        height: BAR_H,
        transform: "skewX(-18deg)",
        background: "linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.85) 50%, rgba(255,255,255,0) 100%)",
        opacity: sweepOpacity
      }}
    /> : null}
                  </div>

                  {
      /* Tip value */
    }
                  <div
      style={{
        position: "absolute",
        left: fillW + 18,
        top: "50%",
        transform: "translateY(-50%)",
        display: "flex",
        alignItems: "baseline",
        fontFamily: affixFont,
        lineHeight: affixLineHeight,
        whiteSpace: "nowrap"
      }}
    >
                    {
      /* Crown above the leader's percentage */
    }
                    {isLeaderRow && crownOpacity > 0.01 ? <div
      style={{
        position: "absolute",
        left: 8,
        bottom: "100%",
        marginBottom: 10,
        opacity: crownOpacity,
        transformOrigin: "center bottom",
        transform: `translateY(${crownY.toFixed(2)}px) scale(${crownScale.toFixed(3)}) rotate(${crownRot.toFixed(2)}deg)`,
        filter: `drop-shadow(0 4px 9px ${glowColor}aa)`
      }}
    >
                        <svg
      width="58"
      height="46"
      viewBox="0 0 64 50"
      fill="none"
    >
                          <path
      d="M8 43 L4 13 L22 26 L32 7 L42 26 L60 13 L56 43 Z"
      fill={glowColor}
      stroke="rgba(0,0,0,0.28)"
      strokeWidth="2.5"
      strokeLinejoin="round"
    />
                          <rect
      x="8"
      y="39"
      width="48"
      height="8"
      rx="2.5"
      fill={glowColor}
      stroke="rgba(0,0,0,0.28)"
      strokeWidth="2.5"
    />
                          <circle cx="4" cy="13" r="3.4" fill="#FFF6DC" />
                          <circle cx="32" cy="7" r="3.8" fill="#FFF6DC" />
                          <circle cx="60" cy="13" r="3.4" fill="#FFF6DC" />
                        </svg>
                      </div> : null}
                    <span
      style={{
        fontSize: 42,
        fontWeight: 800,
        color: valueColor,
        letterSpacing: "0.01em",
        fontVariantNumeric: "tabular-nums",
        textShadow
      }}
    >
                      {valuePrefix}
                      {Math.round(cur)}
                    </span>
                    {valueSuffix ? <span
      style={{
        fontSize: 26,
        fontWeight: 700,
        marginLeft: 2,
        color: valueColor,
        opacity: 0.72,
        textShadow
      }}
    >
                        {valueSuffix}
                      </span> : null}
                  </div>
                </div>
              </div>;
  })}
        </div>
      </div>
    </AbsoluteFill>;
};
