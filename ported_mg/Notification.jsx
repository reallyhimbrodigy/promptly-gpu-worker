// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/Notification/Notification.tsx
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

// src/motion-graphics/Notification/icons.tsx
var Tile = ({
  size,
  background,
  children,
  color = "#FFFFFF"
}) => <div
  style={{
    width: size,
    height: size,
    background,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color,
    lineHeight: 0
  }}
>
    {children}
  </div>;
var ApplePayIcon = ({ size }) => {
  const s = size * 0.58;
  return <Tile size={size} background="#000000">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11" />
      </svg>
    </Tile>;
};
var VenmoIcon = ({ size }) => {
  const s = size * 0.5;
  return <Tile size={size} background="#3D95CE">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M19.27 2c.94 1.55 1.37 3.15 1.37 5.17 0 6.44-5.5 14.81-9.96 20.69H3.44L.56 3.39l6.81-.64 1.69 13.57C11.13 12.68 13.5 7.33 13.5 4.18c0-1.94-.33-3.26-.86-4.3L19.27 2z" />
      </svg>
    </Tile>;
};
var StripeIcon = ({ size }) => {
  const s = size * 0.46;
  return <Tile size={size} background="linear-gradient(135deg, #7A73FF 0%, #553ACF 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-7.076-2.19l-.89 5.592C5.456 23.2 8.865 24 12.045 24c2.58 0 4.71-.636 6.29-1.866C19.953 20.726 21 18.57 21 16.014c0-4.163-2.538-5.88-7.024-6.864z" />
      </svg>
    </Tile>;
};
var IMessageIcon = ({ size }) => {
  const s = size * 0.56;
  return <Tile size={size} background="linear-gradient(180deg, #5BE368 0%, #30C040 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 2C6.477 2 2 5.813 2 10.5c0 2.61 1.39 4.96 3.57 6.53L4.5 21.5l5.03-2.52c.8.16 1.62.27 2.47.27 5.523 0 10-3.813 10-8.75S17.523 2 12 2zm-3 11.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm3 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm3 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" />
      </svg>
    </Tile>;
};
var InstagramIcon = ({ size }) => {
  const s = size * 0.54;
  return <Tile size={size} background="linear-gradient(45deg, #FEDA77 0%, #F58529 25%, #DD2A7B 55%, #8134AF 85%, #515BD4 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
      </svg>
    </Tile>;
};
var EmailIcon = ({ size }) => {
  const s = size * 0.48;
  return <Tile size={size} background="linear-gradient(180deg, #30B8FF 0%, #0A84FF 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
      </svg>
    </Tile>;
};
var BankIcon = ({ size }) => {
  const s = size * 0.52;
  return <Tile size={size} background="linear-gradient(180deg, #4A5560 0%, #1E242C 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 1L1 7v2h22V7L12 1zM3 11v7h3v-7H3zm5 0v7h3v-7H8zm5 0v7h3v-7h-3zm5 0v7h3v-7h-3zM1 20v2h22v-2H1z" />
      </svg>
    </Tile>;
};
var APP_ICONS = {
  "apple-pay": ApplePayIcon,
  venmo: VenmoIcon,
  stripe: StripeIcon,
  imessage: IMessageIcon,
  instagram: InstagramIcon,
  email: EmailIcon,
  bank: BankIcon
};

// src/motion-graphics/Notification/Notification.tsx
var NOTIFICATION_SPRING = {
  mass: 0.6,
  damping: 14,
  stiffness: 220,
  overshootClamping: false
};
var STAGGER_FRAMES = 30;
var NOTIFICATION_GAP = 10;
var STYLES = {
  ios: {
    topOffset: 24,
    sideInset: 24,
    paddingY: 22,
    paddingX: 24,
    radius: 26,
    background: "rgba(36, 36, 40, 0.78)",
    blur: "blur(42px) saturate(180%)",
    border: "1px solid rgba(255,255,255,0.09)",
    shadow: "0 6px 28px rgba(0,0,0,0.32), 0 1px 2px rgba(0,0,0,0.25)",
    iconSize: 84,
    iconRadius: 24,
    fontFamily: MG_FONTS.inter,
    faceKey: "inter",
    appNameOpacity: 0.78
  },
  android: {
    topOffset: 28,
    sideInset: 22,
    paddingY: 24,
    paddingX: 26,
    radius: 32,
    background: "rgba(35, 35, 38, 0.92)",
    blur: "blur(28px)",
    border: "none",
    shadow: "0 10px 28px rgba(0,0,0,0.42)",
    iconSize: 88,
    iconRadius: 26,
    fontFamily: MG_FONTS.roboto,
    faceKey: "roboto",
    appNameOpacity: 0.82
  }
};
var NotificationBanner = ({ item, style }) => {
  // AN UNKNOWN ICON KEY DRAWS NOTHING RATHER THAN CRASHING. `app` became a
  // user-settable text property when notifications were flattened
  // (2026-09-23), so it can now hold anything a placement types — and
  // `<Icon />` with Icon undefined is a React crash, i.e. the whole render
  // dies because a glyph name was misspelled. Absence, not a substitute
  // icon: swapping in a default would draw the WRONG brand mark on a
  // notification, which is worse than a missing one.
  const Icon = APP_ICONS[item.app];
  const timestamp = item.timestamp ?? "now";
  const appNameMetrics = mgTextMetrics(item.appName);
  return <div
    style={{
      borderRadius: style.radius,
      background: style.background,
      backdropFilter: style.blur,
      WebkitBackdropFilter: style.blur,
      border: style.border === "none" ? undefined : style.border,
      boxShadow: style.shadow === "none" ? undefined : style.shadow,
      paddingTop: style.paddingY,
      paddingBottom: style.paddingY,
      paddingLeft: style.paddingX,
      paddingRight: style.paddingX,
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      fontFamily: style.fontFamily
    }}
  >
      <div
    style={{
      width: style.iconSize,
      height: style.iconSize,
      borderRadius: style.iconRadius,
      flexShrink: 0,
      overflow: "hidden",
      boxShadow: "inset 0 0 0 0.5px rgba(255,255,255,0.12)"
    }}
  >
        {Icon ? <Icon size={style.iconSize} /> : null}
      </div>

      <div
    style={{
      flex: 1,
      marginLeft: 18,
      display: "flex",
      flexDirection: "column",
      minWidth: 0
    }}
  >
        <div
    style={{
      display: "flex",
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center"
    }}
  >
          <div
    style={{
      fontFamily: mgTextFont(item.appName, style.faceKey),
      fontSize: 22,
      fontWeight: 600,
      color: `rgba(255,255,255,${style.appNameOpacity})`,
      letterSpacing: "0.06em",
      textTransform: appNameMetrics.uppercaseSafe ? "uppercase" : "none",
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }}
  >
            {item.appName}
          </div>
          <div
    style={{
      fontSize: 22,
      fontWeight: 500,
      color: "rgba(255,255,255,0.55)",
      marginLeft: 12,
      flexShrink: 0,
      letterSpacing: "0.01em"
    }}
  >
            {timestamp}
          </div>
        </div>

        <div
    style={{
      fontFamily: mgTextFont(item.title, style.faceKey),
      fontSize: 34,
      fontWeight: 700,
      color: "#FFFFFF",
      marginTop: 4,
      lineHeight: 1.18,
      letterSpacing: "-0.015em"
    }}
  >
          {item.title}
        </div>

        <div
    style={{
      fontFamily: mgTextFont(item.body, style.faceKey),
      fontSize: 28,
      fontWeight: 400,
      color: "rgba(255,255,255,0.88)",
      marginTop: 2,
      lineHeight: 1.3,
      letterSpacing: "-0.005em",
      display: "-webkit-box",
      WebkitLineClamp: 2,
      WebkitBoxOrient: "vertical",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }}
  >
          {item.body}
        </div>
      </div>
    </div>;
};
var Notification = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  platform = "ios",
  notifications,
  // anchor / offsetX / offsetY are deliberately destructured-but-ignored.
  // The Notification is an iOS / Android notification banner that DROPS
  // DOWN from the top of the screen — placing it anywhere else (center,
  // bottom) makes the entry animation nonsensical. We honor `scale`
  // only because fine-tuning the size is safe; fine-tuning the position
  // breaks the visual metaphor. (Earlier renders shipped Notification at lower_third_safe
  // because Gemini interpreted "LARGE MGs allowed at upper OR lower
  // third" as a green light to place it at the bottom — the prompt has
  // since been tightened to call out Notification specifically, and
  // this component-level lock is the defensive backstop.)
  scale
}) => {
  const platformTopOffset = STYLES[platform].topOffset;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor: "top", offsetY: platformTopOffset, scale },
    undefined,
    "Notification"
  );
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress, phase } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 14, defaultExitFrames: 10 }
  );
  if (!visible) return null;
  const items = Array.isArray(notifications) ? notifications.slice(0, 3) : [];
  if (items.length === 0) return null;
  const style = STYLES[platform];
  const isExiting = phase === "exiting" || phase === "after";
  const exitEased = Math.pow(exitProgress, 3);
  const exitTranslatePct = exitEased * -100;
  const exitFade = interpolate2(exitProgress, [0.6, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const stackWidth = CANVAS_WIDTH - TIKTOK_SAFE_RIGHT - style.sideInset * 2;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
    style={{
      width: stackWidth,
      display: "flex",
      flexDirection: "column",
      gap: NOTIFICATION_GAP
    }}
  >
        {items.map((item, i) => {
    const itemFrame = localFrame - i * STAGGER_FRAMES;
    const dropSpring = spring({
      fps,
      frame: itemFrame,
      config: NOTIFICATION_SPRING,
      durationInFrames: 14
    });
    const enterTranslatePct = interpolate2(dropSpring, [0, 1], [-100, 0]);
    const enterOpacity = interpolate2(itemFrame, [0, 10], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const translateYPct = isExiting ? exitTranslatePct : enterTranslatePct;
    const opacity = isExiting ? exitFade : enterOpacity;
    return <div
      key={i}
      style={{
        position: "relative",

        transform: `translateY(${translateYPct}%)`,
        opacity
      }}
    >
              <NotificationBanner item={item} style={style} />
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
  return <div style={rootStyle}><Notification {...p} /></div>;
};
