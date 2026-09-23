// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const createContext = React.createContext;

// src/motion-graphics/DropCard/DropCard.tsx
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

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/DropCard/DropCard.tsx
var easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
var clamp01 = (t) => Math.max(0, Math.min(1, t));
var hexToRgb = (h) => {
  const n = parseInt(h.replace("#", ""), 16);
  return [n >> 16 & 255, n >> 8 & 255, n & 255];
};
var lerpColor = (a, b, t) => {
  const A = hexToRgb(a);
  const B = hexToRgb(b);
  const c = A.map((v, i) => Math.round(v + (B[i] - v) * clamp01(t)));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
};
var TOP_MARGIN = 90;
var SIDE_MARGIN = 54;
var RAIL_GAP = 56;
var RING_STROKE = 9;
var START_ROT = [-22, 18, -15, 12, -10];
var DropCard = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  titleLead,
  subtitle,
  steps = [],
  points = [],
  cardColor = "#FFFFFF",
  titleColor,
  subtitleColor,
  labelColor,
  accentColor = "#F5A11E",
  railColor,
  spokenColor,
  mutedColor,
  cardHeightPct = 0.44
}) => {
  const { fps, width, height } = useVideoConfig2();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 24, defaultExitFrames: 16 }
  );
  if (!visible) return null;
  const rows = steps.slice(0, START_ROT.length);
  const n = rows.length;
  const rail = railColor ?? accentColor;
  const lightCard = isLightSurface(cardColor);
  const effTitleColor = titleColor ?? inkFor(cardColor);
  const effSpokenColor = spokenColor ?? inkFor(cardColor);
  const effSubtitleColor = subtitleColor ?? (lightCard ? "#5A5A5A" : "#B0B0B8");
  const effLabelColor = labelColor ?? (lightCard ? "#2A2A30" : "#D6D6DC");
  const effMutedColor = mutedColor ?? (lightCard ? "#C2C2CA" : "#55555E");
  const totalFrames = Math.max(
    1,
    Math.round((durationMs ?? 4e3) / 1e3 * fps)
  );
  const CIRCLE_START = Math.round(0.25 * fps);
  const CIRCLE_STAGGER = Math.max(1, Math.round(0.1 * fps));
  const SETTLE = Math.round(0.33 * fps);
  const WORD_STEP = Math.max(1, Math.round(0.067 * fps));
  const WORD_FADE = Math.max(1, Math.round(0.083 * fps));
  const FIRST_SCROLL = Math.min(
    Math.round(0.92 * fps),
    Math.round(0.3 * totalFrames)
  );
  const STEP = Math.min(
    Math.round(1.63 * fps),
    Math.max(
      Math.round(0.5 * fps),
      Math.round(
        (0.85 * totalFrames - FIRST_SCROLL) / Math.max(1, points.length)
      )
    )
  );
  const cardW = width - SIDE_MARGIN * 2;
  const ITEM_W = n > 0 ? Math.min(250, Math.floor((cardW - 80 - RAIL_GAP * (n - 1)) / n)) : 250;
  const CIRCLE_SIZE = Math.min(190, Math.round(ITEM_W * 0.76));
  const slideHeight = Math.round(cardHeightPct * height);
  const OFFSCREEN = TOP_MARGIN + slideHeight + 80;
  const cardSpring = spring({
    fps,
    frame: localFrame,
    config: { damping: 13, mass: 0.8, stiffness: 130 }
  });
  const cardEnterY = interpolate2(cardSpring, [0, 1], [-OFFSCREEN, 0]);
  const cardExitY = exitProgress * -OFFSCREEN;
  const cardY = cardEnterY + cardExitY;
  const titleOpacity = interpolate2(localFrame, [4, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const subtitleOpacity = interpolate2(localFrame, [8, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const railEnd = CIRCLE_START + Math.max(0, n - 1) * CIRCLE_STAGGER + Math.round(0.13 * fps);
  const railScale = interpolate2(localFrame, [CIRCLE_START, railEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic
  });
  const railOpacity = interpolate2(
    localFrame,
    [CIRCLE_START, CIRCLE_START + 5],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  let stepSum = 0;
  for (let k = 0; k < points.length; k++) {
    stepSum += spring({
      fps,
      frame: localFrame - (FIRST_SCROLL + k * STEP),
      config: { damping: 19, stiffness: 100 }
    });
  }
  const columnY = -slideHeight * stepSum;
  const titleText = titleLead ? `${titleLead} ${title}` : title;
  const titleMetrics = mgTextMetrics(titleText);
  const introSlide = <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      width: "100%",
      padding: "0 50px",
      boxSizing: "border-box"
    }}
  >
      <div
    style={{
      fontFamily: mgTextFont(titleText, "anton"),
      // Interior takeover (pass #7c): 68px on a ~850px card read as a
      // caption, not a claim. The title is the card's voice.
      fontSize: 104,
      fontWeight: 400,
      letterSpacing: "-0.005em",
      textTransform: titleMetrics.uppercaseSafe ? "uppercase" : "none",
      textAlign: "center",
      lineHeight: Math.max(1.02, titleMetrics.lineHeight),
      opacity: titleOpacity
    }}
  >
        {titleLead ? <span style={{ color: accentColor }}>{titleLead} </span> : null}
        <span style={{ color: effTitleColor }}>{title}</span>
      </div>

      {subtitle ? <div
    style={{
      fontFamily: mgTextFont(subtitle, "inter"),
      fontSize: 40,
      fontWeight: 400,
      color: effSubtitleColor,
      textAlign: "center",
      lineHeight: 1.3,
      marginTop: 18,
      opacity: subtitleOpacity
    }}
  >
          {subtitle}
        </div> : null}

      <div
    style={{
      position: "relative",
      display: "flex",
      flexDirection: "row",
      justifyContent: "center",
      gap: RAIL_GAP,
      marginTop: 56
    }}
  >
        {n > 1 ? <div
    style={{
      position: "absolute",
      top: CIRCLE_SIZE / 2,
      left: ITEM_W / 2,
      right: ITEM_W / 2,
      height: 0,
      borderTop: `3px dashed ${rail}`,
      opacity: railOpacity,
      transform: `scaleX(${railScale.toFixed(3)})`,
      transformOrigin: "left center",
    }}
  /> : null}

        {rows.map((step, j) => {
    const startF = CIRCLE_START + j * CIRCLE_STAGGER;
    const cs = spring({
      fps,
      frame: localFrame - startF,
      config: { damping: 11, mass: 0.8, stiffness: 120 }
    });
    const sc = cs;
    const rot = interpolate2(
      cs,
      [0, 1],
      [START_ROT[j % START_ROT.length], 0]
    );
    const circleOp = interpolate2(localFrame, [startF, startF + 4], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const labelOp = interpolate2(
      localFrame,
      [startF + 6, startF + 16],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const labelY = interpolate2(
      localFrame,
      [startF + 6, startF + 18],
      [10, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: easeOutCubic
      }
    );
    return <div
      key={j}
      style={{
        position: "relative",

        width: ITEM_W,
        display: "flex",
        flexDirection: "column",
        alignItems: "center"
      }}
    >
              <div
      style={{
        width: CIRCLE_SIZE,
        height: CIRCLE_SIZE,
        borderRadius: "50%",
        border: `${RING_STROKE}px solid ${accentColor}`,
        backgroundColor: cardColor,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: circleOp,
        transform: `scale(${sc.toFixed(3)}) rotate(${rot.toFixed(2)}deg)`,
        transformOrigin: "center"
      }}
    >
                <span
      style={{
        fontFamily: MG_FONTS.inter,
        fontSize: Math.round(CIRCLE_SIZE * 0.5),
        fontWeight: 800,
        color: accentColor,
        lineHeight: 1
      }}
    >
                  {j + 1}
                </span>
              </div>

              {step.label ? (
      // Step labels are model text (font census 2026-08-26).
      <div
        style={{
          fontFamily: mgTextFont(step.label, "inter"),
          fontSize: 30,
          fontWeight: 700,
          color: effLabelColor,
          textTransform: mgTextMetrics(step.label).uppercaseSafe ? "uppercase" : "none",
          letterSpacing: "0.06em",
          textAlign: "center",
          marginTop: 24,
          opacity: labelOp,
          transform: `translateY(${labelY.toFixed(2)}px)`
        }}
      >
                  {step.label}
                </div>
    ) : null}
            </div>;
  })}
      </div>
    </div>;
  const captionSlides = points.map((pt, k) => {
    const captionStart = FIRST_SCROLL + k * STEP + SETTLE;
    const captionText = asText(pt.caption);
    const words = captionText.split(" ");
    const ptTitleMetrics = mgTextMetrics(pt.title);
    return <div
      key={`pt-${k}`}
      style={{
        width: "100%",
        padding: "0 64px",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start"
      }}
    >
        <div
      style={{
        fontFamily: mgTextFont(pt.title, "anton"),
        // The payoff slide is the beat's HIT — it carries the accent and
        // the scale (pass #7c; was 56px floating in a ~850px void).
        fontSize: 96,
        fontWeight: 400,
        color: accentColor,
        textTransform: ptTitleMetrics.uppercaseSafe ? "uppercase" : "none",
        letterSpacing: "-0.01em",
        lineHeight: Math.max(1, ptTitleMetrics.lineHeight)
      }}
    >
          {pt.title}
        </div>

        <div
      style={{
        marginTop: 36,
        fontFamily: mgTextFont(captionText, "inter"),
        fontSize: 58,
        fontWeight: 600,
        lineHeight: 1.28,
        textAlign: "left"
      }}
    >
          {words.map((w, j) => {
      const activation = captionStart + j * WORD_STEP;
      const t = (localFrame - activation) / WORD_FADE;
      return <span key={j} style={{ color: lerpColor(effMutedColor, effSpokenColor, t) }}>
                {w}
                {j < words.length - 1 ? " " : ""}
              </span>;
    })}
        </div>
      </div>;
  });
  const slides = [introSlide, ...captionSlides];
  return <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
    style={{
      position: "absolute",
      top: TOP_MARGIN,
      left: SIDE_MARGIN,
      width: width - SIDE_MARGIN * 2,
      height: slideHeight,
      backgroundColor: cardColor,
      borderRadius: 44,
      boxShadow: "0 32px 64px rgba(0,0,0,0.30), 0 10px 22px rgba(0,0,0,0.16)",
      overflow: "hidden",
      transform: `translateY(${cardY.toFixed(2)}px)`,
      willChange: "transform"
    }}
  >
        {
    /* The scrolling content column — slides stacked vertically. */
  }
        <div
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      width: "100%",
      transform: `translateY(${columnY.toFixed(2)}px)`
    }}
  >
          {slides.map((node, i) => {
    const dist = Math.abs(i * slideHeight + columnY);
    const scale = interpolate2(dist, [0, slideHeight], [1, 0.84], {
      extrapolateRight: "clamp"
    });
    const opacity = interpolate2(dist, [0, slideHeight * 0.7], [1, 0], {
      extrapolateRight: "clamp"
    });
    return <div
      key={i}
      style={{
        height: slideHeight,
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        boxSizing: "border-box",
        transform: `scale(${scale.toFixed(3)})`,
        opacity,
        transformOrigin: "center"
      }}
    >
                {node}
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
  return <div style={rootStyle}><DropCard {...p} /></div>;
};
