// ── ported prelude: injected globals re-bound ──
const useVideoConfig2 = useVideoConfig;
const interpolate2 = interpolate;
const useContext = React.useContext;
const useState = React.useState;
const useRef = React.useRef;
const useEffect = React.useEffect;
const createContext = React.createContext;

// src/motion-graphics/AnnotationArrow/AnnotationArrow.tsx
// [ported] import removed — ChatCut injects these: react
// [ported] import removed — ChatCut injects these: remotion
// src/motion-graphics/shared/springs.ts
var SPRING_SNAPPY = {
  damping: 10,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false
};

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

// src/motion-graphics/shared/schedule.ts
var mgSchedule = (opts) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, settleBy * Math.max(1, window) / scaledEnd);
  return (f60) => f60 * scale * c;
};

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

// src/motion-graphics/AnnotationArrow/resolveEndpoints.ts
var clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
function resolveArrowEndpoint(pt, width, height) {
  const px = clamp(pt.x, 0, 1) * width;
  const py = clamp(pt.y, 0, 1) * height;
  return {
    x: clamp(px, SAFE_RECT.x, SAFE_RECT.x + SAFE_RECT.width),
    y: clamp(py, SAFE_RECT.y, SAFE_RECT.y + SAFE_RECT.height)
  };
}

// src/motion-graphics/AnnotationArrow/AnnotationArrow.tsx
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = a + 1831565813 >>> 0;
    let t = a;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function lerp(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}
function cubicPoint(p0, p1, p2, p3, t) {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const t2 = t * t;
  const a = mt2 * mt;
  const b = 3 * mt2 * t;
  const c = 3 * mt * t2;
  const d = t2 * t;
  return {
    x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    y: a * p0.y + b * p1.y + c * p2.y + d * p3.y
  };
}
function cubicLength(p0, p1, p2, p3, samples = 32) {
  let len = 0;
  let prev = p0;
  for (let i = 1; i <= samples; i++) {
    const t = i / samples;
    const cur = cubicPoint(p0, p1, p2, p3, t);
    const dx = cur.x - prev.x;
    const dy = cur.y - prev.y;
    len += Math.sqrt(dx * dx + dy * dy);
    prev = cur;
  }
  return len;
}
function buildBezier(start, end, pathType, seed) {
  const rand = mulberry32(seed);
  const j = () => rand() * 2 - 1;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lineLen = Math.max(1, Math.sqrt(dx * dx + dy * dy));
  const nx = -dy / lineLen;
  const ny = dx / lineLen;
  const at = (t) => lerp(start, end, t);
  let p1;
  let p2;
  if (pathType === "straight") {
    const j1 = j() * 8;
    const j2 = j() * 8;
    const a = at(0.33);
    const b = at(0.66);
    p1 = { x: a.x + nx * j1, y: a.y + ny * j1 };
    p2 = { x: b.x + nx * j2, y: b.y + ny * j2 };
  } else if (pathType === "curved-arc") {
    const amp = lineLen * 0.25;
    const j1 = j() * 14;
    const j2 = j() * 14;
    const a = at(0.33);
    const b = at(0.66);
    p1 = { x: a.x + nx * (amp + j1), y: a.y + ny * (amp + j1) };
    p2 = { x: b.x + nx * (amp + j2), y: b.y + ny * (amp + j2) };
  } else {
    const amp = lineLen * 0.5;
    const j1 = j() * 18;
    const j2 = j() * 18;
    const a = at(0.28);
    const b = at(0.72);
    p1 = { x: a.x - nx * (amp + j1), y: a.y - ny * (amp + j1) };
    p2 = { x: b.x + nx * (amp * 0.7 + j2), y: b.y + ny * (amp * 0.7 + j2) };
  }
  const d = `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} C ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}, ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
  const length = cubicLength(start, p1, p2, end, 32);
  return { p0: start, p1, p2, p3: end, d, length };
}
var AnnotationArrow = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  start,
  end,
  pathType,
  customPath,
  color = "#C8551F",
  strokeWidth = 8,
  seed = 1,
  arrowheadSize = 32
}) => {
  const { fps, width, height } = useVideoConfig2();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 22, defaultExitFrames: 10 }
  );
  const resolvedPathType = pathType ?? (customPath != null ? "custom" : "curved-arc");
  const K = mgSchedule({ fps, window: exitStartFrame, authoredEnd: 22 });
  const k = K(1);
  const customPathRef = useRef(null);
  const [customLength, setCustomLength] = useState(null);
  useEffect(() => {
    if (resolvedPathType === "custom" && customPathRef.current) {
      try {
        setCustomLength(customPathRef.current.getTotalLength());
      } catch {
        setCustomLength(0);
      }
    }
  }, [resolvedPathType, customPath]);
  const isCustom = resolvedPathType === "custom";
  const startPx = resolveArrowEndpoint(start, width, height);
  const endPx = resolveArrowEndpoint(end, width, height);
  const bezier = resolvedPathType === "custom" ? null : buildBezier(startPx, endPx, resolvedPathType, seed);
  const pathD = isCustom ? customPath ?? "" : bezier.d;
  const pathLength = isCustom ? customLength ?? 0 : bezier.length;
  let tangentX;
  let tangentY;
  if (isCustom) {
    tangentX = endPx.x - startPx.x;
    tangentY = endPx.y - startPx.y;
  } else {
    tangentX = bezier.p3.x - bezier.p2.x;
    tangentY = bezier.p3.y - bezier.p2.y;
  }
  const tMag = Math.max(1e-4, Math.sqrt(tangentX * tangentX + tangentY * tangentY));
  const tangentAngleDeg = Math.atan2(tangentY, tangentX) * 180 / Math.PI;
  const halfAngle = 28 * Math.PI / 180;
  const ux = tangentX / tMag;
  const uy = tangentY / tMag;
  const rot = (x, y, a) => ({
    x: x * Math.cos(a) - y * Math.sin(a),
    y: x * Math.sin(a) + y * Math.cos(a)
  });
  const armA = rot(-ux, -uy, halfAngle);
  const armB = rot(-ux, -uy, -halfAngle);
  const tipX = endPx.x;
  const tipY = endPx.y;
  const armAEnd = {
    x: tipX + armA.x * arrowheadSize,
    y: tipY + armA.y * arrowheadSize
  };
  const armBEnd = {
    x: tipX + armB.x * arrowheadSize,
    y: tipY + armB.y * arrowheadSize
  };
  const headD = `M ${armAEnd.x.toFixed(2)} ${armAEnd.y.toFixed(2)} L ${tipX.toFixed(2)} ${tipY.toFixed(2)} L ${armBEnd.x.toFixed(2)} ${armBEnd.y.toFixed(2)}`;
  const drawInRaw = interpolate2(localFrame, [0, K(18)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const drawInEased = 1 - Math.pow(1 - drawInRaw, 3);
  const drawOffset = pathLength * (1 - drawInEased);
  const eraseEased = 1 - Math.pow(1 - exitProgress, 3);
  const eraseOffset = pathLength * eraseEased;
  const isExiting = exitProgress > 0;
  const dashOffset = isExiting ? eraseOffset : drawOffset;
  const headSpring = spring({
    fps,
    frame: localFrame - K(16),
    config: SPRING_SNAPPY,
    durationInFrames: Math.max(2, Math.round(6 * k))
  });
  const headScale = interpolate2(headSpring, [0, 1], [0, 1]);
  const headFadeIn = interpolate2(localFrame, [K(16), K(22)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const headFadeOut = interpolate2(exitProgress, [0, 0.6], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const headOpacity = headFadeIn * headFadeOut;
  const wiggleT = localFrame / fps;
  const wiggleX = Math.sin(wiggleT * 4.2) * 1.5;
  const wiggleY = Math.cos(wiggleT * 3.18 + 1.3) * 1.5;
  if (!visible) return null;
  if (isCustom && customLength === null) return null;
  return <AbsoluteFill>
      <svg
    width={width}
    height={height}
    viewBox={`0 0 ${width} ${height}`}
    style={{
      position: "absolute",
      inset: 0,
      width: "100%",
      height: "100%",
      pointerEvents: "none"
    }}
  >
        <g transform={`translate(${wiggleX}, ${wiggleY})`}>
          <path
    ref={customPathRef}
    d={pathD}
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    strokeDasharray={pathLength}
    strokeDashoffset={dashOffset}
  />
          <path
    d={headD}
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    opacity={headOpacity}
    style={{
      transform: `translate(${tipX}px, ${tipY}px) rotate(${tangentAngleDeg}deg) scale(${headScale}) rotate(${-tangentAngleDeg}deg) translate(${-tipX}px, ${-tipY}px)`,
      transformOrigin: "0 0",
      transformBox: "view-box"
    }}
  />
        </g>
      </svg>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><AnnotationArrow {...p} /></div>;
};
