// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const useCurrentFrame2 = useCurrentFrame;
const interpolate2 = interpolate;
const useContext = React.useContext;
const useState = React.useState;
const useEffect = React.useEffect;
const createContext = React.createContext;

// src/motion-graphics/EndCard/EndCard.tsx
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

// src/motion-graphics/EndCard/EndCard.tsx
var clamp01 = (t) => Math.max(0, Math.min(1, t));
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var GLYPH = {
  globe: "\u25CB",
  phone: "\u2706",
  mail: "\u2709",
  at: "@"
};
var ENTER_FRAMES = 10;
var EXIT_FRAMES = 6;
var EndCard = ({
  kind,
  title,
  lines = [],
  palette,
  logoUrl,
  titlePx,
  linePx,
  sideMarginPx,
  // Named explicitly, not `...timing` — see the note in NamePlate.
  startMs,
  durationMs,
  enterFrames,
  exitFrames
}) => {
  const { width, height, fps } = useVideoConfig2();
  const frame = useCurrentFrame2();
  const { phase, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: ENTER_FRAMES, defaultExitFrames: EXIT_FRAMES }
  );
  if (phase === "before" || phase === "after") return null;
  const landscape = width >= height;
  const enter = easeOutCubic(clamp01(enterProgress));
  const out = 1 - clamp01(exitProgress);
  const titleSize = Number.isFinite(titlePx) && titlePx > 0 ? Math.round(titlePx) : Math.round(height * (landscape ? 0.085 : 0.055));
  const lineSize = Number.isFinite(linePx) && linePx > 0 ? Math.round(linePx) : Math.round(titleSize * 0.34);
  const sidePad = Number.isFinite(sideMarginPx) ? Math.max(0, Math.min(Math.round(sideMarginPx), Math.round(width * 0.2))) : Math.round(width * 0.08);
  const stingScale = spring({ frame, fps, config: { damping: 14, mass: 0.7 } });
  const titleText = asText(title ?? "");
  const titleFont = mgTextFont(titleText, "anton");
  const titleMetrics = mgTextMetrics(titleText);
  const renderLine = (l, i) => {
    const li = clamp01(enter * 1.6 - i * 0.12);
    const lineText = asText(l.text);
    const glyph = l.icon ? GLYPH[l.icon] ?? "" : "";
    return <div key={i} style={{
      display: "flex",
      alignItems: "center",
      gap: Math.round(lineSize * 0.5),
      opacity: li,
      transform: `translateY(${interpolate2(li, [0, 1], [12, 0])}px)`,
      color: palette.fg,
      fontFamily: mgTextFont(lineText, "inter"),
      fontWeight: 600,
      fontSize: lineSize,
      letterSpacing: "0.02em"
    }}>
        {l.icon ? <span style={{
      color: palette.accent,
      fontFamily: mgTextFont(glyph, "inter")
    }}>{glyph}</span> : null}
        <span>{lineText}</span>
      </div>;
  };
  return <AbsoluteFill style={{
    background: palette.bg,
    opacity: out,
    alignItems: "center",
    justifyContent: "center"
  }}>
      {kind === "logo_sting" ? <div style={{ transform: `scale(${0.86 + stingScale * 0.14})`, opacity: enter }}>
          {logoUrl ? <SafeImg
    src={logoUrl}
    role="decoration"
    label="endcard-logo"
    fallback={<div style={{
      color: palette.fg,
      fontFamily: titleFont,
      fontWeight: 900,
      fontSize: titleSize,
      letterSpacing: "-0.03em"
    }}>{titleText}</div>}
    style={{ width: Math.round(width * 0.34) }}
  /> : <div style={{
    color: palette.fg,
    fontFamily: titleFont,
    fontWeight: 900,
    fontSize: titleSize,
    letterSpacing: "-0.03em"
  }}>{titleText}</div>}
        </div> : <div style={{
    textAlign: "center",
    padding: `0 ${sidePad}px`,
    maxWidth: width,
    overflowWrap: "break-word"
  }}>
          {title ? <div style={{
    color: kind === "echo" ? palette.accent : palette.fg,
    fontFamily: titleFont,
    fontWeight: 800,
    fontSize: titleSize,
    lineHeight: Math.max(1.05, titleMetrics.lineHeight),
    letterSpacing: "-0.02em",
    opacity: enter,
    transform: `translateY(${interpolate2(enter, [0, 1], [20, 0])}px)`
  }}>{titleText}</div> : null}
          {lines.length ? <div style={{
    marginTop: Math.round(titleSize * 0.5),
    display: "flex",
    flexDirection: landscape ? "row" : "column",
    gap: Math.round(lineSize * (landscape ? 1.6 : 0.7)),
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "wrap"
  }}>{lines.map(renderLine)}</div> : null}
          <div style={{
    width: interpolate2(enter, [0, 1], [0, Math.round(width * 0.18)]),
    height: Math.max(3, Math.round(height * 5e-3)),
    background: palette.accent,
    borderRadius: 2,
    margin: `${Math.round(titleSize * 0.55)}px auto 0`
  }} />
        </div>}
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><EndCard {...p} /></div>;
};
