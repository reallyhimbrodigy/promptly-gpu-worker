// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const Easing2 = Easing;
const useContext = React.useContext;
const useState = React.useState;
const useEffect = React.useEffect;
const createContext = React.createContext;

// src/motion-graphics/ChatThread/ChatThread.tsx
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

// src/motion-graphics/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
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
function isLightSurface(surface) {
  return relativeLuminance(surface) > 0.5;
}

// src/motion-graphics/shared/useMGPhase.ts
// [ported] import removed — ChatCut injects these: remotion
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

// src/motion-graphics/ChatThread/ChatThread.tsx
var ENTRANCE_FRAMES = 5;
var DEFAULT_TYPING_MS_INCOMING = 900;
var DEFAULT_HOLD_MS = 450;
var CARD_ENTER_FRAMES = 14;
var CARD_EXIT_FRAMES = 12;
var CARD_ENTER_OFFSET = 12;
var DOT_CYCLE_FRAMES = 42;
var DOT_STAGGER_FRAMES = 6;
function dotPulse(frame, dotIndex) {
  const phase = (frame - dotIndex * DOT_STAGGER_FRAMES) * Math.PI * 2 / DOT_CYCLE_FRAMES;
  const wave = (Math.sin(phase) + 1) / 2;
  return { opacity: 0.3 + wave * 0.7, scale: 0.85 + wave * 0.15 };
}
function buildSchedule(messages, fps, startOffset = 0) {
  let cursor = startOffset;
  return messages.map((m) => {
    const defaultTyping = m.sender === "them" ? DEFAULT_TYPING_MS_INCOMING : 0;
    const typingFrames = msToFrames(m.typingMs ?? defaultTyping, fps);
    const holdFrames = msToFrames(m.holdMs ?? DEFAULT_HOLD_MS, fps);
    const typingStart = cursor;
    const typingEnd = typingStart + typingFrames;
    const bubbleAppear = typingEnd;
    const bubbleSettled = bubbleAppear + ENTRANCE_FRAMES;
    cursor = bubbleSettled + holdFrames;
    return { typingStart, typingEnd, bubbleAppear, bubbleSettled };
  });
}
var SignalBars = ({ color }) => <svg width={34} height={22} viewBox="0 0 34 22" fill={color}>
    <rect x="0" y="14" width="5" height="8" rx="1.2" />
    <rect x="8" y="10" width="5" height="12" rx="1.2" />
    <rect x="16" y="5" width="5" height="17" rx="1.2" />
    <rect x="24" y="0" width="5" height="22" rx="1.2" />
  </svg>;
var WifiIcon = ({ color }) => <svg width={30} height={22} viewBox="0 0 30 22" fill={color}>
    <path d="M15 3.5C21 3.5 26 5.6 29 8.4L26.7 11C24.3 8.7 20 7 15 7S5.7 8.7 3.3 11L1 8.4C4 5.6 9 3.5 15 3.5Z" />
    <path d="M15 10.2c3.6 0 6.7 1.3 8.6 3.2L21.3 16C19.8 14.7 17.7 13.7 15 13.7S10.2 14.7 8.7 16L6.4 13.4C8.3 11.5 11.4 10.2 15 10.2Z" />
    <circle cx="15" cy="18.3" r="2.5" />
  </svg>;
var BatteryIcon = ({
  level = 1,
  color
}) => {
  const fillWidth = 38 * Math.max(0, Math.min(1, level));
  return <svg width={52} height={22} viewBox="0 0 52 22" fill="none">
      <rect
    x="1"
    y="1"
    width="42"
    height="20"
    rx="5"
    stroke={color}
    strokeOpacity="0.5"
    strokeWidth="1.5"
    fill="none"
  />
      <rect
    x="44"
    y="7"
    width="3"
    height="8"
    rx="1"
    fill={color}
    fillOpacity="0.5"
  />
      <rect
    x="3"
    y="3"
    width={fillWidth}
    height="16"
    rx="3"
    fill={color}
  />
    </svg>;
};
var StatusBar = ({ time, color }) => <div
  style={{
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: 56,
    paddingRight: 56,
    paddingTop: 24,
    paddingBottom: 14,
    height: 88,
    boxSizing: "border-box"
  }}
>
    <div
  style={{
    fontFamily: MG_FONTS.inter,
    fontSize: 34,
    fontWeight: 600,
    color,
    letterSpacing: "-0.01em",
    lineHeight: 1
  }}
>
      {time}
    </div>
    <div
  style={{
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  }}
>
      <SignalBars color={color} />
      <WifiIcon color={color} />
      <BatteryIcon level={1} color={color} />
    </div>
  </div>;
var BackChevron = () => <svg width={22} height={38} viewBox="0 0 22 38" fill="none">
    <path
  d="M20 2L3 19L20 36"
  stroke="#0A84FF"
  strokeWidth="4.5"
  strokeLinecap="round"
  strokeLinejoin="round"
/>
  </svg>;
var FaceTimeIcon = () => <svg width={44} height={28} viewBox="0 0 44 28" fill="#0A84FF">
    <rect x="0" y="4" width="28" height="20" rx="5" />
    <path d="M30 10L44 4V24L30 18Z" />
  </svg>;
var MessageHeader = ({
  name,
  subtitle,
  avatarSrc,
  initials,
  avatarColor,
  chromeColor,
  onLightSurface
}) => {
  const secondaryChrome = onLightSurface ? "rgba(11,11,15,0.55)" : "rgba(255,255,255,0.55)";
  const faintChrome = onLightSurface ? "rgba(11,11,15,0.4)" : "rgba(255,255,255,0.4)";
  const hairline = onLightSurface ? "rgba(11,11,15,0.1)" : "rgba(255,255,255,0.1)";
  const fallbackLetter = [...initials ?? name].slice(0, 2).join("").toUpperCase();
  const nameMetrics = mgTextMetrics(name);
  return <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "stretch",
      paddingBottom: 14,
      borderBottom: `1px solid ${hairline}`
    }}
  >
      <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingLeft: 32,
      paddingRight: 40,
      paddingTop: 12,
      paddingBottom: 8
    }}
  >
        <BackChevron />
        <FaceTimeIcon />
      </div>

      <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: 4
    }}
  >
        <div
    style={{
      width: 110,
      height: 110,
      borderRadius: "50%",
      overflow: "hidden",
      backgroundColor: avatarColor,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "#FFFFFF",
      fontFamily: mgTextFont(fallbackLetter, "inter"),
      fontSize: 48,
      fontWeight: 600,
      letterSpacing: "-0.01em",
      marginBottom: 10
    }}
  >
          {avatarSrc ? <SafeImg
    role="decoration"
    label="ChatThread.avatar"
    src={avatarSrc}
    style={{
      width: "100%",
      height: "100%",
      objectFit: "cover",
      display: "block"
    }}
  /> : fallbackLetter}
        </div>
        <div
    style={{
      fontFamily: mgTextFont(name, "inter"),
      fontSize: 28,
      fontWeight: 600,
      color: chromeColor,
      letterSpacing: "-0.01em",
      // 1.1 clips matras/hooks on non-Latin names; 1.1 exactly for latin.
      lineHeight: Math.max(1.1, nameMetrics.lineHeight)
    }}
  >
          {name}
        </div>
        <div
    style={{
      fontFamily: mgTextFont(subtitle, "inter"),
      fontSize: 22,
      fontWeight: 400,
      color: secondaryChrome,
      letterSpacing: "0.01em",
      marginTop: 2,
      display: "flex",
      alignItems: "center",
      gap: 4
    }}
  >
          <span>{subtitle}</span>
          <svg
    width={12}
    height={16}
    viewBox="0 0 12 16"
    fill={faintChrome}
    style={{ marginTop: 1 }}
  >
                        {/* EXPLICIT COLOUR, NOT currentColor. ChatCut rasterizes every
                <svg> as an image cached by its markup plus the INHERITED
                colour, so a colour that changes per frame forces a fresh
                decode of every SVG on every frame — their note measured a
                grid of a few hundred taking an export from 10 fps to a
                standstill. This chevron inherits `faintChrome`, which is
                exactly what the parent <svg> already sets as `fill`, so
                naming it changes no pixel and removes the cache key. */}
            <path d="M2 2L10 8L2 14" stroke={faintChrome} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>;
};
var HomeIndicator = ({ color }) => <div
  style={{
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    height: 44,
    paddingBottom: 14
  }}
>
    <div
  style={{
    width: 280,
    height: 8,
    borderRadius: 4,
    backgroundColor: color
  }}
/>
  </div>;
var MessageBubble = ({
  text,
  sender,
  bgColor,
  textColor,
  entranceProgress
}) => {
  const scale = 0.85 + entranceProgress * 0.15;
  const opacity = entranceProgress;
  return <div
    style={{
      display: "flex",
      justifyContent: sender === "me" ? "flex-end" : "flex-start",
      width: "100%",
      padding: "6px 22px"
    }}
  >
      <div
    style={{
      maxWidth: "75%",
      backgroundColor: bgColor,
      color: textColor,
      padding: "16px 22px",
      borderRadius: 30,
      // Message text is user/model text — script-routed face + emoji
      // tail (font census 2026-08-26).
      fontFamily: mgTextFont(text, "inter"),
      fontSize: 34,
      fontWeight: 400,
      lineHeight: 1.28,
      letterSpacing: "-0.005em",
      transform: `scale(${scale})`,
      transformOrigin: sender === "me" ? "bottom right" : "bottom left",
      opacity,
      wordBreak: "break-word"
    }}
  >
        {text}
      </div>
    </div>;
};
var TypingBubble = ({
  sender,
  bgColor,
  localFrame,
  entranceProgress
}) => {
  const scale = 0.85 + entranceProgress * 0.15;
  const opacity = entranceProgress;
  return <div
    style={{
      display: "flex",
      justifyContent: sender === "me" ? "flex-end" : "flex-start",
      width: "100%",
      padding: "6px 22px"
    }}
  >
      <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "20px 26px",
      backgroundColor: bgColor,
      borderRadius: 30,
      transform: `scale(${scale})`,
      transformOrigin: sender === "me" ? "bottom right" : "bottom left",
      opacity
    }}
  >
        {[0, 1, 2].map((i) => {
    const { opacity: dotOpacity, scale: dotScale } = dotPulse(
      localFrame,
      i
    );
    return <div
      key={i}
      style={{
        width: 16,
        height: 16,
        borderRadius: 8,
        backgroundColor: "#8E8E93",
        opacity: dotOpacity,
        transform: `scale(${dotScale})`
      }}
    />;
  })}
      </div>
    </div>;
};
var ChatThread = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  header,
  messages,
  // D4: fit the symmetric center box (max 680) — oversize dragged center right
  width = 680,
  minHeight = 1320,
  borderRadius = 56,
  statusBarTime = "9:41",
  showStatusBar = true,
  showHomeIndicator = true,
  backgroundColor = "#000000",
  incomingColor = "#26252A",
  incomingTextColor,
  outgoingColor = "#0A84FF",
  outgoingTextColor,
  anchor,
  offsetX,
  offsetY,
  scale
}) => {
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    {
      defaultEnterFrames: CARD_ENTER_FRAMES,
      defaultExitFrames: CARD_EXIT_FRAMES
    }
  );
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    undefined,
    "ChatThread"
  );
  const chromeOnLight = isLightSurface(backgroundColor);
  const chromeColor = inkFor(backgroundColor, "#0B0B0F", "#FFFFFF");
  const effIncomingTextColor = incomingTextColor ?? inkFor(incomingColor);
  const effOutgoingTextColor = outgoingTextColor ?? inkFor(outgoingColor);
  const effMinHeight = Math.min(minHeight, SAFE_RECT.height);
  if (!visible) return null;
  const enterProgress = interpolate2(
    localFrame,
    [0, CARD_ENTER_FRAMES],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing2.out(Easing2.cubic)
    }
  );
  const enterScale = interpolate2(enterProgress, [0, 1], [0.88, 1]);
  const enterOpacity = interpolate2(
    localFrame,
    [0, CARD_ENTER_FRAMES * 0.75],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const enterTranslateY = interpolate2(enterProgress, [0, 1], [24, 0]);
  const exitEased = Easing2.in(Easing2.cubic)(exitProgress);
  const exitScale = interpolate2(exitEased, [0, 1], [1, 0.94]);
  const exitOpacityEased = 1 - exitEased;
  const exitTranslateY = exitEased * 14;
  const isExiting = exitProgress > 0;
  const cardScale = isExiting ? exitScale : enterScale;
  const cardOpacity = isExiting ? exitOpacityEased : enterOpacity;
  const cardTranslateY = isExiting ? exitTranslateY : enterTranslateY;
  const schedule = buildSchedule(messages, fps, CARD_ENTER_OFFSET);
  const messageStates = messages.map((m, i) => {
    const s = schedule[i];
    const entranceProgress = interpolate2(
      localFrame,
      [s.bubbleAppear, s.bubbleSettled],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const hasArrived = localFrame >= s.bubbleAppear;
    return { message: m, hasArrived, entranceProgress };
  });
  let activeTypingIndex = null;
  for (let i = 0; i < messages.length; i++) {
    const s = schedule[i];
    const typingFrames = s.typingEnd - s.typingStart;
    if (typingFrames > 0 && localFrame >= s.typingStart && localFrame < s.typingEnd) {
      activeTypingIndex = i;
      break;
    }
  }
  const typingEntrance = activeTypingIndex !== null ? interpolate2(
    localFrame,
    [
      schedule[activeTypingIndex].typingStart,
      schedule[activeTypingIndex].typingStart + 4
    ],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  ) : 0;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
    style={{
      width,
      minHeight: effMinHeight,
      backgroundColor,
      borderRadius,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      opacity: cardOpacity,
      transform: `translateY(${cardTranslateY}px) scale(${cardScale})`,
      transformOrigin: "center center",
      boxShadow: "0 28px 80px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4)"
    }}
  >
          {showStatusBar ? <StatusBar time={statusBarTime} color={chromeColor} /> : null}

          {header ? <MessageHeader
    name={header.name}
    subtitle={header.subtitle ?? "iMessage"}
    avatarSrc={header.avatarSrc}
    initials={header.initials}
    avatarColor={header.avatarColor ?? "#636366"}
    chromeColor={chromeColor}
    onLightSurface={chromeOnLight}
  /> : null}

          <div
    style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      justifyContent: "flex-end",
      overflow: "hidden",
      paddingTop: 16,
      paddingBottom: 16
    }}
  >
            {messageStates.map(
    (state, i) => state.hasArrived ? <MessageBubble
      key={`msg-${i}`}
      text={state.message.text}
      sender={state.message.sender}
      bgColor={state.message.sender === "me" ? outgoingColor : incomingColor}
      textColor={state.message.sender === "me" ? effOutgoingTextColor : effIncomingTextColor}
      entranceProgress={state.entranceProgress}
    /> : null
  )}

            {activeTypingIndex !== null ? <TypingBubble
    sender={messages[activeTypingIndex].sender}
    bgColor={messages[activeTypingIndex].sender === "me" ? outgoingColor : incomingColor}
    localFrame={localFrame}
    entranceProgress={typingEntrance}
  /> : null}
          </div>

          {showHomeIndicator ? <HomeIndicator color={chromeColor} /> : null}
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
  return <div style={rootStyle}><ChatThread {...p} /></div>;
};
