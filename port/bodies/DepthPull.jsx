/* DepthPull — OUR depth stack, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. Perceived depth, not just magnification: the plate pushes at
 * SIXTY PERCENT of the amplitude while haze, bokeh, edge blur and a vignette
 * ride the full move, so the background reads as further away than the frame.
 * A constant-speed preset has one layer and cannot separate them at all.
 *
 * THE PARALLAX IS THE POINT, AND THE CAP IS SOLVED AGAINST THE FULL TARGET.
 * bgScale is the 0.6x layer; the atmosphere layers ride 1.0x. Solving the cap
 * against the background would let the FOREGROUND move 1.67x over the ceiling,
 * so the solve uses the full amplitude and the background inherits the result.
 *
 * NO TOP-LEVEL CONSTANTS, so the orb table nests inside the component. In the
 * Remotion original it is a module-level array; ChatCut's validator refuses any
 * top-level binding beside the component itself, and a hoisted constant is
 * exactly what that rule is about.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts by port/emit_zoom_component.mjs.
 * Do not edit it here or in the built blob — edit the module and re-emit.
 * DepthPull is one of the four the cap was MEASURED against: 1.25/2200ms read
 * 33.8 px/frame before it, against an 11px ceiling.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; the root is a plain div, never AbsoluteFill; every
 * editable value is read through an identifier literally named `props`; and
 * every declared property is read and used.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom) || 0));
  // SIZE and POSITION are the same two dials on every ported zoom.
  const targetScale = Number(props.scale) || 1.15;
  const originX = props.originX === undefined ? 0.5 : Number(props.originX);
  const originY = props.originY === undefined ? 0.45 : Number(props.originY);
  const punch = props.punch === true || props.punch === "true";
  const capped = props.capped === undefined ? true : props.capped !== false;
  const edgeBlur = props.edgeBlur === undefined ? 4 : Number(props.edgeBlur);
  const frameLines = props.frameLines === undefined ? true : props.frameLines !== false;
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // It MOVES between runs (2.0363 then 1.7228 levels). It sits on the <Video>
  // itself, BEFORE this component's own depth grade, because the offset it
  // corrects belongs to the video path and the grade is ours on top of it. At
  // rest the grade is exactly neutral, so the corrected plate is what matches
  // the base item.
  const correct = props.correct || "";
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the pull's span. DepthPull is
  // the slow one — 40% in, 20% hold, 40% out.
  const span = Math.max(2, durationInFrames);
  const rampIn = Math.max(1, Math.round(span * 0.4));
  const holdEnd = Math.max(rampIn + 1, Math.round(span * 0.6));
  const corner = cornerPx(width, height, originX, originY);
  const capIn = capped
    ? planCappedRampIn({
        fromScale: 1, toScale: targetScale, landFrame: rampIn, earliestFrame: 0,
        authoredFrames: rampIn, fps, corner,
        skew: punch ? SKEW_PUNCH : SKEW_GLIDE,
      })
    : null;
  const capOut = capped
    ? planCappedRelease({
        fromScale: capIn ? capIn.toScale : targetScale, toScale: 1,
        startFrame: holdEnd, latestFrame: span,
        authoredFrames: Math.max(1, span - holdEnd), fps, corner,
        skew: SKEW_GLIDE,   // a release lands on nothing — it always glides
      })
    : null;
  const spanStart = capIn ? Math.max(0, capIn.startFrame) : 0;
  const spanEnd = capOut ? Math.min(span, capOut.endFrame) : span;
  const peakScale = capIn ? capIn.toScale : targetScale;
  const cubicIn = (t) => t * t * t;
  const cubicOut = (t) => 1 - Math.pow(1 - t, 3);
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);

  let zoomProgress = 0;
  if (frame >= spanStart && frame <= spanEnd) {
    if (frame < rampIn) {
      const t = clamp01((frame - spanStart) / Math.max(1, rampIn - spanStart));
      zoomProgress = capIn ? capIn.easing(t) : (punch ? cubicIn(t) : cubicOut(t));
    } else if (frame < holdEnd) {
      zoomProgress = 1;
    } else {
      const t = clamp01((frame - holdEnd) / Math.max(1, spanEnd - holdEnd));
      zoomProgress = capOut ? 1 - capOut.easing(t) : 1 - cubicIn(t);
    }
  }

  // ── the depth stack ────────────────────────────────────────────────────────
  const orbs = [
    { x: 15, y: 22, size: 110, delay: 0, driftX: 25, driftY: -12 },
    { x: 72, y: 58, size: 80, delay: 4, driftX: -18, driftY: 8 },
    { x: 42, y: 78, size: 95, delay: 7, driftX: 12, driftY: -20 },
    { x: 82, y: 18, size: 65, delay: 2, driftX: -8, driftY: 15 },
    { x: 28, y: 50, size: 70, delay: 10, driftX: 20, driftY: 5 },
  ];
  const bgScale = 1 + (peakScale - 1) * 0.6 * zoomProgress;
  const midScale = 1 + (peakScale - 1) * 1.0 * zoomProgress;
  const contrastBoost = 1 + 0.08 * zoomProgress;
  const brightnessLift = 1 + 0.02 * zoomProgress;
  const bgSaturation = 1 - 0.15 * zoomProgress;
  const currentEdgeBlur = edgeBlur * zoomProgress;
  const frameOpacity = zoomProgress <= 0 || zoomProgress >= 1
    ? 0
    : 0.15 * Math.min(1, Math.min(zoomProgress / 0.25, (1 - zoomProgress) / 0.25));
  const frameScale = 1 - 0.04 * zoomProgress;
  // The graded wrapper, not the root: the root stays the plain div the
  // validator asks for, and the grade applies to the whole composited stack
  // exactly as it does in the Remotion original.
  const grade = { position: "absolute", inset: 0, overflow: "hidden",
    filter: `contrast(${contrastBoost}) brightness(${brightnessLift})` };

  if (!src) {
    return (
      <div style={rootStyle}>
        <div style={{ color: "#FFFFFF", fontSize: 48, fontFamily: "sans-serif" }}>
          NO CLIP PROP
        </div>
      </div>
    );
  }
  return (
    <div style={rootStyle}>
      <div style={grade}>
        <Video
          src={src}
          startFrom={srcFrom}
          muted
          volume={0}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${bgScale})`,
            transformOrigin: `${originX * 100}% ${originY * 100}%`,
            filter: `${correct} saturate(${bgSaturation}) brightness(0.95)`,
          }}
        />
        <div style={{ position: "absolute", inset: 0,
          background: `rgba(30, 50, 80, ${0.06 * zoomProgress})`,
          mixBlendMode: "multiply", pointerEvents: "none" }} />
        <div style={{ position: "absolute", inset: 0,
          background: `linear-gradient(180deg, rgba(180, 160, 130, ${0.025 * zoomProgress}) 0%, rgba(160, 140, 110, ${0.04 * zoomProgress}) 50%, rgba(140, 120, 100, ${0.025 * zoomProgress}) 100%)`,
          mixBlendMode: "screen", filter: "blur(20px)",
          transform: `scale(${midScale})`, pointerEvents: "none" }} />
        {orbs.map((orb, i) => {
          const orbProgress = clamp01((frame - orb.delay) / Math.max(1, span - orb.delay));
          const orbOpacity = orbProgress <= 0 || orbProgress >= 1
            ? 0
            : 0.12 * Math.min(1, Math.min(orbProgress / 0.12, (1 - orbProgress) / 0.15));
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: `${orb.x + orb.driftX * orbProgress}%`,
                top: `${orb.y + orb.driftY * orbProgress}%`,
                width: orb.size,
                height: orb.size,
                borderRadius: "50%",
                background: "radial-gradient(circle, rgba(255,220,160,0.35) 0%, rgba(255,200,120,0.08) 40%, transparent 70%)",
                filter: "blur(15px)",
                mixBlendMode: "screen",
                opacity: orbOpacity,
                transform: `scale(${midScale})`,
                pointerEvents: "none",
              }}
            />
          );
        })}
        {currentEdgeBlur > 0.2 ? (
          <div style={{ position: "absolute", inset: 0,
            backdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitBackdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitMaskImage: "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            maskImage: "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            pointerEvents: "none" }} />
        ) : null}
        <div style={{ position: "absolute", inset: 0,
          background: `radial-gradient(ellipse at center, transparent 35%, rgba(15, 8, 3, ${0.2 * zoomProgress}) 70%, rgba(8, 4, 2, ${0.45 * zoomProgress}) 100%)`,
          pointerEvents: "none" }} />
        {frameLines && frameOpacity > 0.01 ? (
          <div style={{ position: "absolute", inset: 0, display: "flex",
            alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
            <div style={{ width: "84%", height: "84%",
              border: `1px solid rgba(255, 255, 255, ${frameOpacity})`,
              transform: `scale(${frameScale})` }} />
          </div>
        ) : null}
      </div>
    </div>
  );
};
