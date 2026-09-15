// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/SpeechBubble/IMessageBubble.tsx
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

// src/SafeImg.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// src/motion-graphics/SpeechBubble/shared.tsx
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

// src/motion-graphics/shared/schedule.ts
var mgSchedule = (opts) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, settleBy * Math.max(1, window) / scaledEnd);
  return (f60) => f60 * scale * c;
};

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/SpeechBubble/IMessageBubble.tsx
var OUTGOING_GRADIENT = "linear-gradient(180deg, #1E9BF0 0%, #0479D9 100%)";
var OUTGOING_FALLBACK = "#0479D9";
var INCOMING_COLOR = "#2C2C2E";
var TYPING_PHASE_FRAMES = 30;
var TYPE_REVEAL_FRAMES = 60;
var IMessageBubble = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  anchor,
  offsetX,
  offsetY,
  scale,
  width = 620,
  messageType,
  text,
  status,
  typewriter = false
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    // The 820 default was AUTHORED for the default "top" anchor (bubble in
    // the lower half). It must not survive an anchor-only override — the live
    // "center" placement rendered 615px below center with the status line in
    // the TikTok nav zone (pass #11, audited).
    { anchor: "top", offsetY: anchor == null ? 820 : 0 },
    "IMessageBubble"
  );
  const { fps } = useVideoConfig2();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 }
  );
  if (!visible) return null;
  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: typewriter ? TYPING_PHASE_FRAMES + TYPE_REVEAL_FRAMES : 22
  });
  const k = K(1);
  const isOutgoing = messageType === "outgoing";
  const bubbleFill = isOutgoing ? OUTGOING_GRADIENT : INCOMING_COLOR;
  const tailColor = isOutgoing ? OUTGOING_FALLBACK : INCOMING_COLOR;
  const smoothEntrance = useSmoothGraphics();
  const enterF = Math.max(3, Math.round(12 / 60 * fps));
  const springProgress = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: enterF
  });
  const enterProgress = smoothEntrance ? cappedEntranceProgress({ localFrame, fps, authoredFrames: enterF }) : springProgress;
  const { transform, opacity } = composeBubbleTransform(
    enterProgress,
    exitProgress
  );
  const showTypingIndicator = typewriter && localFrame < K(TYPING_PHASE_FRAMES);
  let displayedText = text;
  if (typewriter) {
    const clusters = Array.from(
      new Intl.Segmenter().segment(text),
      (s) => s.segment
    );
    const typeFrame = localFrame - K(TYPING_PHASE_FRAMES);
    const shown = Math.max(
      0,
      Math.floor(
        interpolate2(
          typeFrame,
          [0, K(TYPE_REVEAL_FRAMES)],
          [0, clusters.length],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp"
          }
        )
      )
    );
    displayedText = clusters.slice(0, shown).join("");
  }
  const msgChars = Math.max(1, [...asText(text)].length);
  const msgAdvanceEm = mgTextMetrics(asText(text)).advanceEm;
  const msgFontSize = msgChars <= 20 ? Math.min(64, Math.max(30, Math.round(480 / (msgChars * msgAdvanceEm)))) : 30;
  return <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
    style={{
      width,
      transform,
      opacity,
      transformOrigin: "center center",
      fontFamily: MG_FONTS.inter,
      display: "flex",
      justifyContent: isOutgoing ? "flex-end" : "flex-start",
      flexDirection: "column",
      alignItems: isOutgoing ? "flex-end" : "flex-start",
      WebkitFontSmoothing: "antialiased"
    }}
  >
        {showTypingIndicator ? <TypingIndicatorBubble
    isOutgoing={isOutgoing}
    bubbleFill={bubbleFill}
    tailColor={tailColor}
    frame={localFrame}
  /> : <MessageBubble
    isOutgoing={isOutgoing}
    bubbleFill={bubbleFill}
    tailColor={tailColor}
    text={displayedText}
    fontSize={msgFontSize}
  />}

        {isOutgoing && status && !showTypingIndicator ? <div
    style={{
      fontSize: 18,
      fontWeight: 600,
      color: "#8E8E93",
      marginTop: 6,
      marginRight: 4,
      letterSpacing: "-0.01em"
    }}
  >
            {status}
          </div> : null}
      </div>
      </div>
    </AbsoluteFill>;
};
var MessageBubble = ({ isOutgoing, bubbleFill, tailColor, text, fontSize = 30 }) => {
  return <div
    style={{
      position: "relative",
      maxWidth: 480
    }}
  >
      <div
    style={{
      background: bubbleFill,
      borderRadius: "0.87em",
      paddingLeft: "0.6em",
      paddingRight: "0.6em",
      paddingTop: "0.47em",
      paddingBottom: "0.47em",
      color: "#FFFFFF",
      // User/model text routes by script + emoji tail (font census
      // 2026-08-26); the status line keeps the root Inter (chrome).
      fontFamily: mgTextFont(text, "inter"),
      fontSize,
      fontWeight: 400,
      lineHeight: 1.3,
      letterSpacing: "-0.005em",
      wordBreak: "break-word",
      boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
      minHeight: "1.3em"
    }}
  >
        {text}
      </div>
      <Tail isOutgoing={isOutgoing} color={tailColor} />
    </div>;
};
var TypingIndicatorBubble = ({ isOutgoing, bubbleFill, tailColor, frame }) => {
  const dotPhase = (offset) => Math.sin((frame + offset) * 0.35) * 4;
  return <div
    style={{
      position: "relative"
    }}
  >
      <div
    style={{
      background: bubbleFill,
      borderRadius: 22,
      paddingLeft: 20,
      paddingRight: 20,
      paddingTop: 16,
      paddingBottom: 16,
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      boxShadow: "0 2px 8px rgba(0,0,0,0.18)"
    }}
  >
        {[0, 4, 8].map((offset) => <div
    key={offset}
    style={{
      width: 10,
      height: 10,
      borderRadius: 5,
      backgroundColor: "rgba(255,255,255,0.7)",
      transform: `translateY(${dotPhase(offset)}px)`
    }}
  />)}
      </div>
      <Tail isOutgoing={isOutgoing} color={tailColor} />
    </div>;
};
var Tail = ({
  isOutgoing,
  color
}) => {
  const tailPath = "M0 0 C6 8 12 14 18 16 C12 18 6 20 0 22 Z";
  return <svg
    width={18}
    height={22}
    viewBox="0 0 18 22"
    style={{
      position: "absolute",
      bottom: 0,
      [isOutgoing ? "right" : "left"]: -6,
      transform: isOutgoing ? "scaleX(1)" : "scaleX(-1)"
    }}
  >
      <path d={tailPath} fill={color} />
    </svg>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><IMessageBubble {...p} /></div>;
};
