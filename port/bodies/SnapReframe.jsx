/* SnapReframe — OUR spring, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. A fast, precise reframe: the tight composition arrives like a
 * camera operator snapping to a new frame, not like a slider being dragged.
 * ChatCut's zoom presets move at constant speed and cannot make this shape at
 * all — a spring is the whole component.
 *
 * THE SOLVER IS THE RUNTIME'S, NOT A SECOND COPY. `spring` is available in the
 * motion-graphic runtime (measured by frame, 2026-09-19), so this calls it
 * rather than carrying an implementation of one. That is the same rule the
 * velocity cap's build step exists to enforce, applied to the other direction:
 * where the runtime already owns the maths, we call it.
 *
 * THE CAP MEASURES HERE, IT DOES NOT RESHAPE. The cap's solver plans
 * TRAPEZOIDS; handing this curve to it would replace the spring with a
 * trapezoid and delete the component, which is why StepZoom declares no cap at
 * all. But "no ramp to cap" is FALSE here — a spring moves, and a 1.3x snap is
 * exactly the kind of move the 11px/frame law was written for. So the cap's
 * CURVE-AGNOSTIC half is used: cornerPx and peakDisplacementPx MEASURE the
 * spring's own sampled displacement, and lever 2 (grow the move) stretches the
 * spring in time until it fits. A spring stretched in time is the same curve at
 * lower velocity, so the register survives exactly; lever 1 is unavailable by
 * construction and lever 3 is never reached.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants, so the cap nests inside Component; the root is a plain
 * div, never AbsoluteFill; every editable value is read through an identifier
 * literally named `props`; and every declared property is read and used.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION. A layer that hardcodes
  // startFrom={0} plays the opening frame wherever it sits, so a reframe at 12s
  // would show second 0 — worse than no reframe.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom) || 0));
  // SIZE and POSITION are the same two dials on every ported zoom.
  const targetScale = Number(props.scale) || 1.3;
  const originX = props.originX === undefined ? 0.5 : Number(props.originX);
  const originY = props.originY === undefined ? 0.5 : Number(props.originY);
  const capped = props.capped === undefined ? true : props.capped !== false;
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // Our layer renders the source measurably brighter than the base item does: a
  // flat additive offset that belongs to the <Video> path, not to us. It MOVES
  // between runs (2.0363 then 1.7228 levels), so it arrives as a measured value
  // and is never baked in. SVG filters are inert in this runtime; the harness
  // sends `brightness(b) contrast(c)`, which composes to slope 1 and a pure
  // offset.
  const correct = props.correct || "";
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the reframe's span. The snap
  // lands early and holds; the release is the same spring played out.
  const span = Math.max(2, durationInFrames);
  const springConfig = { damping: 22, mass: 0.6, stiffness: 260 };
  const holdEnd = Math.max(2, Math.round(span * 0.6));
  // The authored snap is the spring's own natural length at this fps — ~9.6
  // frames to peak at 30fps, so 0.45s covers the settle without padding it.
  const authored = Math.max(2, Math.round(fps * 0.45));

  const springAt = (f, n) => spring({ frame: f, fps, config: springConfig, durationInFrames: n });
  const scalesFor = (n) => {
    const out = [];
    for (let f = 0; f <= n; f++) out.push(1 + (targetScale - 1) * springAt(f, n));
    return out;
  };

  // LEVER 2, and only lever 2. Grow the move until the measured peak fits, never
  // past the hold — a snap that ate its own hold would not be a snap.
  const corner = cornerPx(width, height, originX, originY);
  let enterFrames = authored;
  let peakPx = peakDisplacementPx(scalesFor(enterFrames), corner);
  if (capped) {
    while (peakPx > PEAK_DISPLACEMENT_CAP_PX && enterFrames < holdEnd) {
      enterFrames += 1;
      peakPx = peakDisplacementPx(scalesFor(enterFrames), corner);
    }
  }

  let progress = 0;
  if (frame >= 0 && frame < holdEnd) {
    progress = springAt(frame, enterFrames);
  } else if (frame < span) {
    // The release is the same spring, run backwards out of the hold.
    progress = 1 - springAt(frame - holdEnd, Math.max(2, span - holdEnd));
  }
  const scale = 1 + (targetScale - 1) * Math.min(Math.max(progress, 0), 1);

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
      <Video
        src={src}
        startFrom={srcFrom}
        muted
        volume={0}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          filter: correct || undefined,
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
    </div>
  );
};
