// ── ported prelude: injected globals re-bound ──
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/PillCluster/PillCluster.tsx
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

// src/motion-graphics/PillCluster/PillCluster.tsx
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var DEFAULT_TEXT_SHADOW = "0 2px 10px rgba(0,0,0,0.55), 0 1px 2px rgba(0,0,0,0.5)";
var START = 6;
var STAGGER = 4;
var DEFAULT_ACCENT = "#4F9DF7";
var hash01 = (i) => {
  const x = Math.sin(i * 99.13 + 7.7) * 43758.5453;
  return x - Math.floor(x);
};
var PillCluster = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  tags = [],
  accentColor = DEFAULT_ACCENT,
  accentEvery = 3,
  glass = true,
  // Corpus law 1 (pass #7b): panel measured letterforms at ~2.5% frame height
  // vs the corpus's 5-6% — the cluster read as UI, not a graphic beat.
  // Outermost pills may crop at the frame edges (edge-crop is corpus-legal).
  // 1000, NOT 1160. THE DECLARED WIDTH EXCEEDED THE CANVAS BY 80px AND COULD
  // NEVER BE REALISED — every PillCluster ever rendered has been clipped by the
  // frame. My measured 999 was not "default content not filling the container";
  // it was the container CUT OFF at 1080 minus the root's padding, and I read a
  // clipped box as a content box. Builder 1 read it the same way.
  // 1000 fits 1080 with 40px of margin either side, so the declared width is a
  // number the component can actually draw, and the measured box can finally
  // mean what it says.
  width = 1000,
  fontSize = 78,
  textColor = "#FFFFFF",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  if (!tags || tags.length === 0) return null;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" }
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 24, defaultExitFrames: 16 }
  );
  if (!visible) return null;
  const rendered = tags.slice(0, 12);
  const N = rendered.length;
  if (N === 0) return null;
  const tagFonts = rendered.map((t) => mgTextFont(t, "inter"));
  const tagMetrics = rendered.map((t) => mgTextMetrics(t));
  const orderBySeed = rendered.map((_, i) => i).sort((a, b) => hash01(a) - hash01(b));
  const delayRank = [];
  orderBySeed.forEach((origIdx, pos) => {
    delayRank[origIdx] = pos;
  });
  const exitOpacity = 1 - exitProgress;
  const exitScale = 1 - 0.06 * exitProgress;
  const accentInk = accentColor === DEFAULT_ACCENT ? "#15151E" : inkFor(accentColor);
  const PAD_X = 40;
  const PAD_Y = 21;
  const pillH = fontSize + PAD_Y * 2;
  const rowStep = Math.round(pillH * 0.78);
  const estW = (t, ti) => PAD_X * 2 + Math.max(3, t.length) * fontSize * (tagMetrics[ti].script === "latin" ? 0.56 : tagMetrics[ti].advanceEm);
  const placed = [];
  {
    let x = 0;
    let row = 0;
    rendered.forEach((tag, i) => {
      const w = Math.min(estW(tag, i), width);
      if (x > 0 && x + w > width) {
        row += 1;
        x = row % 2 === 1 ? Math.round(44 + hash01(row) * 36) : Math.round(hash01(row + 7) * 24);
      }
      const rot = (i % 2 === 0 ? -1 : 1) * (3.5 + hash01(i + 31) * 3.5);
      placed.push({ x, y: row * rowStep, rot });
      x += Math.round(w * 0.88);
    });
  }
  const clusterW = Math.min(
    width,
    Math.max(...rendered.map((t, i) => placed[i].x + estW(t, i)))
  );
  const clusterH = placed[placed.length - 1].y + pillH;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      position: "relative",
      width: clusterW,
      height: clusterH,
      opacity: exitOpacity,
      transform: `scale(${exitScale.toFixed(4)})`,
      transformOrigin: "center"
    }}
  >
          {/* PAINT ORDER WITHOUT so
              DOM order costs nothing in layout and only paint order moves.
              Sorted by delayRank, which is exactly what `zIndex: 1 +
              delayRank[i]` said — a pill entering later sits on top of one
              that entered earlier. `i` stays the logical index so every
              position and timing calculation is untouched. */}
            {rendered.map((tag, i) => ({ tag, i }))
              .sort((a, b) => delayRank[a.i] - delayRank[b.i])
              .map(({ tag, i }) => {
    const act = START + delayRank[i] * STAGGER;
    const isAccent = accentEvery > 0 && i === Math.min(accentEvery - 1, N - 1);
    const pop = interpolate2(
      localFrame,
      [act, act + 7, act + 13],
      [1.28, 0.97, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const dropY = interpolate2(localFrame, [act, act + 7], [-16, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const popO = interpolate2(localFrame, [act, act + 5], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const landed = clamp01((localFrame - act - 10) / 12);
    const floatY = landed * (Math.sin(localFrame * 0.045 + i * 1.7) * 4 + Math.sin(localFrame * 0.075 + i * 0.9) * 2);
    const floatX = landed * Math.sin(localFrame * 0.038 + i * 2.3) * 2.5;
    const pulse = isAccent ? interpolate2(
      localFrame,
      [act + 14, act + 20, act + 30],
      [1, 1.07, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    ) : 1;
    const { x: px, y: py, rot } = placed[i];
    const neutralBg = glass ? "linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 50%), rgba(17,19,25,0.38)" : "rgba(22,24,31,0.78)";
    const pillStyle = isAccent ? {
      background: `linear-gradient(180deg, ${accentColor} 0%, ${accentColor}d9 100%)`,
      border: `1.5px solid ${accentColor}`,
      boxShadow: `0 10px 26px rgba(0,0,0,0.4), 0 0 22px ${accentColor}55, inset 0 1px 0 rgba(255,255,255,0.4)`
    } : {
      background: neutralBg,
      backdropFilter: glass ? "blur(16px) saturate(140%)" : undefined,
      WebkitBackdropFilter: glass ? "blur(16px) saturate(140%)" : undefined,
      border: "1.5px solid rgba(255,255,255,0.22)",
      boxShadow: "0 10px 26px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.18)"
    };
    return <div
      key={i}
      style={{
        position: "absolute",
        left: px,
        top: py,

        transform: `translate(${floatX.toFixed(2)}px, ${(floatY + dropY).toFixed(2)}px) scale(${(pop * pulse).toFixed(4)}) rotate(${rot.toFixed(2)}deg)`,
        transformOrigin: "center",
        opacity: popO,
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderRadius: 999,
        whiteSpace: "nowrap",
        ...pillStyle
      }}
    >
                <span
      style={{
        fontFamily: tagFonts[i],
        fontSize,
        fontWeight: 600,
        color: isAccent ? accentInk : textColor,
        letterSpacing: "0.005em",
        lineHeight: Math.max(1, tagMetrics[i].lineHeight),
        // White accent ink keeps the neutral shadow (the dark
        // halo is what makes light ink read on a dark chip).
        textShadow: isAccent && accentInk !== "#FFFFFF" ? undefined : textShadow
      }}
    >
                  {tag}
                </span>
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
  return <div style={rootStyle}><PillCluster {...p} /></div>;
};
