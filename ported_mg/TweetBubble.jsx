// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const useContext = React.useContext;
const useState = React.useState;
const useEffect = React.useEffect;
const createContext = React.createContext;

// src/motion-graphics/SpeechBubble/TweetBubble.tsx
// [ported] import removed — ChatCut injects these: remotion
// src/motion-graphics/shared/springs.ts
var SPRING_SNAPPY = {
  damping: 10,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false
};

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

// src/motion-graphics/SpeechBubble/icons.tsx
var VerifiedIcon = ({
  size,
  color = "#1D9BF0"
}) => {
  const points = [];
  const cx = 12;
  const cy = 12;
  const outerR = 11;
  const innerR = 8.8;
  const count = 12;
  for (let i = 0; i < count * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = i / (count * 2) * Math.PI * 2 - Math.PI / 2;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    points.push(`${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`);
  }
  const starPath = points.join(" ") + " Z";
  return <svg width={size} height={size} viewBox="0 0 24 24">
      <path d={starPath} fill={color} />
      <path
    d="M7.5 12.3 L10.6 15.3 L16.5 9"
    fill="none"
    stroke="#FFFFFF"
    strokeWidth="2.2"
    strokeLinecap="round"
    strokeLinejoin="round"
  />
    </svg>;
};
var ReplyIcon = ({
  size,
  color = "#536471"
}) => <svg width={size} height={size} viewBox="0 0 24 24">
    <path
  d="M4 5 C4 3.9 4.9 3 6 3 L18 3 C19.1 3 20 3.9 20 5 L20 15 C20 16.1 19.1 17 18 17 L13.5 17 L9 21 L9 17 L6 17 C4.9 17 4 16.1 4 15 Z"
  fill="none"
  stroke={color}
  strokeWidth="1.8"
  strokeLinejoin="round"
/>
  </svg>;
var RepostIcon = ({
  size,
  color = "#536471"
}) => <svg width={size} height={size} viewBox="0 0 24 24">
    <path
  d="M4 8 L4 6 C4 4.9 4.9 4 6 4 L17 4 L14 1 M17 4 L14 7"
  fill="none"
  stroke={color}
  strokeWidth="1.8"
  strokeLinecap="round"
  strokeLinejoin="round"
/>
    <path
  d="M20 16 L20 18 C20 19.1 19.1 20 18 20 L7 20 L10 23 M7 20 L10 17"
  fill="none"
  stroke={color}
  strokeWidth="1.8"
  strokeLinecap="round"
  strokeLinejoin="round"
/>
  </svg>;
var HeartIcon = ({
  size,
  color = "#536471",
  filled = false
}) => <svg width={size} height={size} viewBox="0 0 24 24">
    <path
  d="M12 21 C12 21 3 15 3 8.5 C3 5.5 5.2 3.5 7.8 3.5 C9.6 3.5 11.1 4.5 12 6 C12.9 4.5 14.4 3.5 16.2 3.5 C18.8 3.5 21 5.5 21 8.5 C21 15 12 21 12 21 Z"
  fill={filled ? color : "none"}
  stroke={color}
  strokeWidth="1.8"
  strokeLinejoin="round"
/>
  </svg>;
var ViewsIcon = ({
  size,
  color = "#536471"
}) => <svg width={size} height={size} viewBox="0 0 24 24">
    <path
  d="M5 20 L5 14 M11 20 L11 9 M17 20 L17 4"
  fill="none"
  stroke={color}
  strokeWidth="2"
  strokeLinecap="round"
/>
  </svg>;

// src/SafeImg.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
var SAFE_IMG_TIMEOUT_MS = 8e3;
var SafeImg = ({
  src,
  role,
  fallback = null,
  label,
  onUnavailable,
  ...rest
}) => {
  const [state, setState] = useState("probing");
  const [handle] = useState(
    () => delayRender(`SafeImg probing ${String(src).slice(0, 80)}`, {
      timeoutInMilliseconds: SAFE_IMG_TIMEOUT_MS + 4e3
    })
  );
  useEffect(() => {
    let settled = false;
    const site = label || "unlabelled";
    const finish = (next, reason) => {
      if (settled) return;
      settled = true;
      console.log(
        `[SAFEIMG] ${next === "ok" ? "loaded" : "degraded"} role=${role} site=${site} reason=${reason} src=${String(src).slice(0, 120)}`
      );
      if (next === "failed" && role === "primary") {
        if (onUnavailable) {
          setState("failed");
          continueRender(handle);
          onUnavailable();
          return;
        }
        continueRender(handle);
        cancelRender(
          new Error(
            `SAFE_IMG_PRIMARY_UNLOADABLE: site=${site} reason=${reason} src=${String(src).slice(0, 200)}`
          )
        );
        return;
      }
      setState(next);
      continueRender(handle);
    };
    if (!src) {
      finish("failed", "no-src");
      return;
    }
    const timer = setTimeout(() => finish("failed", "timeout"), SAFE_IMG_TIMEOUT_MS);
    const probe = new Image();
    probe.onload = () => {
      clearTimeout(timer);
      finish("ok", "ok");
    };
    probe.onerror = () => {
      clearTimeout(timer);
      finish("failed", "error");
    };
    probe.src = src;
    return () => {
      clearTimeout(timer);
      if (!settled) {
        settled = true;
        continueRender(handle);
      }
    };
  }, [src, handle, role, label, onUnavailable]);
  if (state === "probing") return null;
  if (state === "failed" || !src) return <>{fallback}</>;
  return <Img src={src} {...rest} />;
};

// src/motion-graphics/SpeechBubble/shared.tsx
var Avatar = ({
  size,
  src,
  initials,
  fallbackColor,
  fallbackText
}) => {
  if (src) {
    return <div
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        overflow: "hidden",
        flexShrink: 0
      }}
    >
        <SafeImg
      role="decoration"
      label="SpeechBubble.avatar"
      src={src}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        display: "block"
      }}
    />
      </div>;
  }
  const letters = [...initials ?? fallbackText ?? "?"].slice(0, 2).join("").toUpperCase();
  const lettersMetrics = mgTextMetrics(letters);
  return <div
    style={{
      width: size,
      height: size,
      borderRadius: size / 2,
      backgroundColor: fallbackColor,
      flexShrink: 0,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "#FFFFFF",
      fontFamily: mgTextFont(letters, "inter"),
      fontSize: Math.round(size * 0.42),
      fontWeight: 700,
      letterSpacing: "-0.01em",
      lineHeight: Math.max(1, lettersMetrics.lineHeight)
    }}
  >
      {letters}
    </div>;
};
function formatCount(n) {
  if (n < 1e3) return String(n);
  if (n < 1e4) return `${(n / 1e3).toFixed(1)}K`;
  if (n < 1e5) return `${(n / 1e3).toFixed(1)}K`;
  if (n < 1e6) return `${Math.round(n / 1e3)}K`;
  if (n < 1e7) return `${(n / 1e6).toFixed(1)}M`;
  return `${Math.round(n / 1e6)}M`;
}
function composeBubbleTransform(enterProgress, exitProgress) {
  const enterScale = 0.9 + 0.1 * enterProgress;
  const enterTranslate = 20 * (1 - enterProgress);
  const enterOpacity = enterProgress;
  const exitScaleMult = 1 - 0.05 * exitProgress;
  const exitOpacity = 1 - exitProgress;
  const scale = enterScale * exitScaleMult;
  const opacity = enterOpacity * exitOpacity;
  return {
    transform: `translateY(${enterTranslate}px) scale(${scale})`,
    opacity
  };
}

// src/motion-graphics/SpeechBubble/TweetBubble.tsx
var THEME = {
  light: {
    bg: "#FFFFFF",
    text: "#0F1419",
    muted: "#536471",
    shadow: "0 4px 16px rgba(0,0,0,0.12)"
  },
  dark: {
    bg: "#16181C",
    text: "#E7E9EA",
    muted: "#71767B",
    shadow: "0 4px 16px rgba(0,0,0,0.45)"
  }
};
var TweetBubble = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  anchor,
  offsetX,
  offsetY,
  scale,
  width = 620,
  avatarSrc,
  initials,
  avatarColor = "#C8551F",
  name,
  handle,
  timestamp,
  verified,
  text,
  stats,
  darkMode = false
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    // 2026-08-26 coupled-defaults audit: the 720 default pairs with the default
    // "top" anchor only — it must not survive an anchor-only override (same
    // class as the fixed IMessageBubble/InstagramComment/TikTokComment guard).
    { anchor: "top", offsetY: anchor == null ? 720 : 0 },
    "TweetBubble"
  );
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 }
  );
  if (!visible) return null;
  const smoothEntrance = useSmoothGraphics();
  const springProgress = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 12
  });
  const enterProgress = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 12 }) : springProgress;
  const { transform, opacity } = composeBubbleTransform(
    enterProgress,
    exitProgress
  );
  const theme = darkMode ? THEME.dark : THEME.light;
  const handleLine = timestamp ? `${handle} \xB7 ${timestamp}` : handle;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
    style={{
      width,
      transform,
      opacity,
      transformOrigin: "center center",
      backgroundColor: theme.bg,
      borderRadius: 16,
      padding: 20,
      boxShadow: theme.shadow,
      fontFamily: MG_FONTS.inter,
      WebkitFontSmoothing: "antialiased"
    }}
  >
        <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "flex-start"
    }}
  >
          <Avatar
    size={48}
    src={avatarSrc}
    initials={initials}
    fallbackColor={avatarColor}
    fallbackText={name}
  />

          <div
    style={{
      marginLeft: 12,
      display: "flex",
      flexDirection: "column",
      minWidth: 0,
      flex: 1
    }}
  >
            <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      gap: 4
    }}
  >
              <span
    style={{
      // User text routes by script + emoji tail (font census
      // 2026-08-26); counts/"Reply" chrome keep the root Inter.
      fontFamily: mgTextFont(name, "inter"),
      fontSize: 26,
      fontWeight: 700,
      color: theme.text,
      letterSpacing: "-0.01em",
      lineHeight: 1.15,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }}
  >
                {name}
              </span>
              {verified ? <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      flexShrink: 0
    }}
  >
                  <VerifiedIcon size={22} />
                </span> : null}
            </div>

            <div
    style={{
      fontFamily: mgTextFont(handleLine, "inter"),
      fontSize: 22,
      fontWeight: 400,
      color: theme.muted,
      lineHeight: 1.2,
      marginTop: 2,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }}
  >
              {handleLine}
            </div>
          </div>
        </div>

        <div
    style={{
      fontFamily: mgTextFont(text, "inter"),
      fontSize: 28,
      fontWeight: 400,
      color: theme.text,
      lineHeight: 1.35,
      marginTop: 12,
      letterSpacing: "-0.005em",
      wordBreak: "break-word"
    }}
  >
          {text}
        </div>

        <div
    style={{
      display: "flex",
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginTop: 20,
      paddingRight: 16
    }}
  >
          <InteractionItem
    icon={<ReplyIcon size={22} color={theme.muted} />}
    label={formatCount(stats.replies)}
    color={theme.muted}
  />
          <InteractionItem
    icon={<RepostIcon size={22} color={theme.muted} />}
    label={formatCount(stats.reposts)}
    color={theme.muted}
  />
          <InteractionItem
    icon={<HeartIcon size={22} color={theme.muted} />}
    label={formatCount(stats.likes)}
    color={theme.muted}
  />
          <InteractionItem
    icon={<ViewsIcon size={22} color={theme.muted} />}
    label={formatCount(stats.views)}
    color={theme.muted}
  />
        </div>
      </div>
      </div>
    </AbsoluteFill>;
};
var InteractionItem = ({ icon, label, color }) => <div
  style={{
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  }}
>
    {icon}
    <span
  style={{
    fontSize: 18,
    fontWeight: 400,
    color,
    lineHeight: 1
  }}
>
      {label}
    </span>
  </div>;


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><TweetBubble {...p} /></div>;
};
