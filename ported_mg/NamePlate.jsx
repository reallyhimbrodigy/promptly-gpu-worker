// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/NamePlate/NamePlate.tsx
// [ported] import removed — ChatCut injects these: remotion
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

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/NamePlate/NamePlate.tsx
var clamp01 = (t) => Math.max(0, Math.min(1, t));
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var RULE_FRAMES = 8;
var EXIT_FRAMES = 6;
var TEXT_STAGGER = 3;
var NamePlate = ({
  name,
  role,
  accentColor = "#F5A11E",
  nameColor,
  anchor = "lower_third_safe",
  widthPct = 0.42,
  namePx,
  rolePx,
  backdropColor,
  sideMarginPx,
  // Named explicitly rather than collected with `...timing`, matching all 26
  // dispatched MGs: a rest-spread here types as an index signature and stops
  // satisfying MGTimingProps, so the timing contract would go unchecked.
  startMs,
  durationMs,
  enterFrames,
  exitFrames
}) => {
  const { width, height } = useVideoConfig2();
  const { phase, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: RULE_FRAMES, defaultExitFrames: EXIT_FRAMES }
  );
  if (phase === "before" || phase === "after") return null;
  const landscape = width >= height;
  const defaultMargin = landscape ? Math.round(width * 0.05) : 60;
  const sideMargin = Number.isFinite(sideMarginPx) ? Math.max(0, Math.min(Math.round(sideMarginPx), Math.round(width * 0.15))) : defaultMargin;
  const bandY = anchor === "upper_third_safe" ? Math.round(height * (landscape ? 0.1 : 0.14)) : Math.round(height * (landscape ? 0.78 : 0.72));
  const enter = easeOutCubic(clamp01(enterProgress));
  const out = 1 - clamp01(exitProgress);
  const ruleW = interpolate2(enter, [0, 1], [0, Math.round(width * widthPct)]);
  const nameRise = interpolate2(enter, [0, 1], [18, 0]);
  const roleRise = interpolate2(clamp01(enter * 1.25 - 0.25), [0, 1], [14, 0]);
  const nameSize = Number.isFinite(namePx) && namePx > 0 ? Math.round(namePx) : Math.round(height * (landscape ? 0.052 : 0.034));
  const roleSize = Number.isFinite(rolePx) && rolePx > 0 ? Math.round(rolePx) : Math.round(nameSize * 0.52);
  const blockMaxWidth = Math.max(120, width - sideMargin * 2);
  const pad = Math.round(nameSize * 0.28);
  const nameText = asText(name);
  const nameFont = mgTextFont(nameText, "anton");
  const nameMetrics = mgTextMetrics(nameText);
  const roleText = role ? asText(role) : "";
  const roleFont = mgTextFont(roleText, "inter");
  const roleCapsSafe = mgTextMetrics(roleText).uppercaseSafe;
  const resolvedNameColor = nameColor ?? (backdropColor ? inkFor(backdropColor) : "#FFFFFF");
  return <AbsoluteFill style={{ opacity: out }}>
      <div style={{
    position: "absolute",
    left: sideMargin,
    top: bandY,
    maxWidth: blockMaxWidth,
    display: "inline-block",
    padding: backdropColor ? `${pad}px ${Math.round(pad * 1.4)}px` : 0
  }}>
        {
    /* LEGIBILITY SCRIM, only when the palette gave us a base colour. Its
       own opacity — never a colour-with-alpha — so any CSS colour string
       the palette produces works unparsed. Text sits above it. */
  }
        {backdropColor ? <div style={{
    position: "absolute",
    inset: 0,
    background: backdropColor,
    borderRadius: Math.round(pad * 0.6),
    opacity: 0.66 * enter
  }} /> : null}
        <div style={{ position: "relative" }}>
          <div style={{
    width: ruleW,
    height: Math.max(3, Math.round(height * 4e-3)),
    background: accentColor,
    borderRadius: 2
  }} />
          {
    /* TRUNCATION FIX (2026-08-26, live-defect: "Siddharth" rendered
       "Siddhart" + a stray mark in an undelivered artifact): the
       rise-mask's overflow:hidden clipped glyph INK that exceeded the
       text's layout box. Two causes, both removed: fontWeight 800 on
       Anton — a single-weight 400 face, so faux-bold synthesis widens
       ink past advance widths — and -0.02em tracking tucking the final
       glyph's ink outside the box. Plus breathing room on the mask so
       ink can never touch its clip edge. */
  }
          <div style={{
    overflow: "hidden",
    marginTop: Math.round(nameSize * 0.34),
    paddingRight: Math.round(nameSize * 0.12)
  }}>
            <div style={{
    transform: `translateY(${nameRise}px)`,
    color: resolvedNameColor,
    fontFamily: nameFont,
    fontWeight: 400,
    fontSize: nameSize,
    lineHeight: Math.max(1.04, nameMetrics.lineHeight),
    overflowWrap: "break-word"
  }}>
              {nameText}
            </div>
          </div>
          {role ? <div style={{
    overflow: "hidden",
    marginTop: Math.round(roleSize * 0.32) + TEXT_STAGGER
  }}>
              <div style={{
    transform: `translateY(${roleRise}px)`,
    color: accentColor,
    fontFamily: roleFont,
    fontWeight: 600,
    fontSize: roleSize,
    letterSpacing: "0.06em",
    textTransform: roleCapsSafe ? "uppercase" : "none",
    overflowWrap: "break-word"
  }}>
                {roleText}
              </div>
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
  return <div style={rootStyle}><NamePlate {...p} /></div>;
};
