// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/PillMarquee/PillMarquee.tsx
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
function isLightSurface(surface) {
  return relativeLuminance(surface) > 0.5;
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

// src/motion-graphics/PillMarquee/PillMarquee.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var PILL_TEXT_SHADOW = "0 0 12px rgba(0,0,0,0.72), 0 0 30px rgba(0,0,0,0.45), 1px 2px 5px rgba(0,0,0,0.5)";
var NEUTRAL_FILL = "linear-gradient(180deg, rgba(34,37,47,0.62) 0%, rgba(15,17,23,0.66) 100%)";
var CHAR_W = 0.6;
var DEFAULT_PALETTE = [
  "#5B8DEF",
  "#22C55E",
  "#F59E0B",
  "#EF4444",
  "#A855F7",
  "#06B6D4",
  "#EC4899",
  "#F5D90A"
];
var rotate = (arr, by) => {
  const n = arr.length;
  if (n === 0) return arr;
  const k = (by % n + n) % n;
  return arr.slice(k).concat(arr.slice(0, k));
};
var PillMarquee = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  pills,
  rows = 3,
  hashtag = true,
  speed = 2.2,
  firstDirection = 1,
  fontKey = "inter",
  fontSize = 46,
  uppercase = false,
  textColor,
  colorMode = "single",
  accentColor = "#FF6A3D",
  palette = DEFAULT_PALETTE,
  pillColor,
  glass = true,
  gap = 18,
  rowGap = 24,
  paddingX = 34,
  paddingY = 20,
  edgeFade = 200,
  offsetY = 0
}) => {
  const { width } = useVideoConfig2();
  const { visible, localFrame, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 16 }
  );
  if (!visible) return null;
  if (pills.length === 0) return null;
  const estPillW = (label) => {
    const text = hashtag ? `#${label}` : label;
    const m = mgTextMetrics(text);
    const charW = m.script === "latin" ? CHAR_W : m.advanceEm;
    return Math.ceil(text.length * fontSize * charW) + paddingX * 2 + 4;
  };
  const opacity = easeOutCubic(enterProgress) * interpolate2(exitProgress, [0, 0.9], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const derivedDarkInk = textColor == null && pillColor != null && isLightSurface(pillColor);
  const ink = textColor ?? (derivedDarkInk ? "#0F1117" : "#FFFFFF");
  const renderPill = (label, key, hue) => {
    const accent = colorMode === "varied" ? hue : accentColor;
    const pillFont = mgTextFont(label, fontKey);
    const pillMetrics = mgTextMetrics(label);
    return <div
      key={key}
      style={{
        flexShrink: 0,
        width: estPillW(label),
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        whiteSpace: "nowrap",
        padding: `${paddingY}px 0`,
        borderRadius: 999,
        background: pillColor ?? NEUTRAL_FILL,
        border: "1px solid rgba(255,255,255,0.22)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.16), inset 0 -1px 1px rgba(0,0,0,0.3)",
        ...glass ? {
          backdropFilter: "blur(8px) saturate(120%)",
          WebkitBackdropFilter: "blur(8px) saturate(120%)"
        } : {}
      }}
    >
        <span
      style={{
        fontFamily: pillFont,
        fontSize,
        fontWeight: 600,
        color: ink,
        textTransform: uppercase && pillMetrics.uppercaseSafe ? "uppercase" : "none",
        letterSpacing: uppercase ? "0.06em" : "-0.01em",
        lineHeight: Math.max(1, pillMetrics.lineHeight),
        textShadow: derivedDarkInk ? undefined : PILL_TEXT_SHADOW
      }}
    >
          {hashtag ? <span style={{ color: accent }}>#</span> : null}
          {label}
        </span>
      </div>;
  };
  const fadeMask = `linear-gradient(90deg, transparent 0, #000 ${edgeFade}px, #000 calc(100% - ${edgeFade}px), transparent 100%)`;
  const pillH = fontSize + paddingY * 2;
  const bandH = rows * pillH + (rows - 1) * rowGap + 96;
  const scrimBg = "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.5) 26%, rgba(0,0,0,0.5) 74%, rgba(0,0,0,0) 100%)";
  return <AbsoluteFill style={{ opacity }}>
      {
    /* Single soft backing shadow behind every row */
  }
      <div
    style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      transform: `translateY(${offsetY}px)`
    }}
  >
        <div
    style={{
      height: bandH,
      background: scrimBg,
      filter: "blur(7px)",
      maskImage: fadeMask,
      WebkitMaskImage: fadeMask
    }}
  />
      </div>

      <div
    style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "stretch",
      gap: rowGap,
      transform: `translateY(${offsetY}px)`,
    }}
  >
        {Array.from({ length: rows }).map((_, r) => {
    const dir = (r % 2 === 0 ? 1 : -1) * firstDirection;
    const rowPills = rotate(pills, r * 2);
    const unitW = rowPills.reduce((acc, p) => acc + estPillW(p) + gap, 0);
    const copies = Math.ceil(width / unitW) + 2;
    const scroll = localFrame * speed % unitW;
    const baseX = dir > 0 ? scroll - unitW : -scroll;
    return <div
      key={r}
      style={{
        position: "relative",
        width: "100%",
        overflow: "hidden",
        maskImage: fadeMask,
        WebkitMaskImage: fadeMask
      }}
    >
            <div
      style={{
        display: "flex",
        flexDirection: "row",
        gap,
        width: "max-content",
        transform: `translateX(${baseX.toFixed(2)}px)`,
        willChange: "transform"
      }}
    >
              {Array.from({ length: copies }).flatMap(
      (__, c) => rowPills.map((p, i) => {
        const origIdx = (i + r * 2) % pills.length;
        const hue = palette[origIdx % palette.length];
        return renderPill(p, `${r}-${c}-${i}`, hue);
      })
    )}
            </div>
          </div>;
  })}
      </div>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><PillMarquee {...p} /></div>;
};
