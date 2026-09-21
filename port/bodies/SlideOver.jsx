/* SlideOver — B slides in over A, on ChatCut's timeline.
 *
 * A SEAM-COVERING COMPONENT OVER A HARD CUT, per Zac's ruling. ChatCut's
 * transition slot takes only its own thirteen presets and no custom code, so a
 * graphic spanning the cut is the only available shape. The cut underneath is
 * hard; this covers it.
 *
 * B travels in from the edge while A drifts the other way and settles back —
 * the parallax that makes one shot read as ON TOP OF the other rather than
 * beside it. The shadow under B's leading edge is what sells the depth.
 *
 * NO VELOCITY CAP: a transition is a CUT, not a ramp zoom. The 11px/frame
 * ceiling bounds a move that is meant to be INVISIBLE — a push the viewer
 * should feel and not see. A transition is a deliberate sub-500ms event where
 * the motion IS the effect, the same argument StepZoom makes for its single
 * discontinuity. Capping it would turn a whip into a dissolve and delete the
 * component. Stated here rather than omitted, because a missing cap nobody
 * decided is the failure the build step exists to prevent. The measured peaks
 * are recorded in measured/transition_peaks_2026-09-20.md so this is an
 * informed exemption and not an assumed one.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; the root is a plain div, never AbsoluteFill; every
 * editable value is read through an identifier literally named `props`; every
 * declared property is read and used; and NO HARDCODED FALLBACKS.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  // BOTH SIDES COME FROM ONE SOURCE. In this pipeline every clip is a seek into
  // the same file, so a transition is two offsets into one asset — which is
  // exactly the two-video-layer capability measured by frame on 2026-09-19.
  const srcFromA = Math.max(0, Math.round(Number(props.srcFromA)));
  const srcFromB = Math.max(0, Math.round(Number(props.srcFromB)));
  // THE TWO DIALS ZAC ASKED FOR. seamRoom is where the hard cut sits inside
  // this item, in frames from its start — so the item covers seamRoom before
  // the cut and the rest after. duration is how long the transition itself
  // runs, centred on that seam.
  const seamRoom = Math.max(1, Math.round(Number(props.seamRoom)));
  const duration = Math.max(2, Math.round(Number(props.duration)));
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written
  // here. It moved 2.0363 -> 1.7228 between two runs of the same arm. BOTH
  // plates wear it or the seam it hides becomes a level step of its own.
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "contain", filter: correct };
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const span = Math.max(2, durationInFrames);
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = clamp01((frame - start) / duration);
  const lerp = (t, a, b) => a + (b - a) * t;
  // Remotion's Easing.bezier is available in this runtime; a cubic-bezier
  // solver written here would be a second copy of one that already exists.
  const ease = (t, x1, y1, x2, y2) => Easing.bezier(x1, y1, x2, y2)(clamp01(t));

  if (!src) {
    return (
      <div style={rootStyle}>
        <div style={{ color: "#FFFFFF", fontSize: 48, fontFamily: "sans-serif" }}>
          NO CLIP PROP
        </div>
      </div>
    );
  }
  const sign = props.direction === "right" ? 1 : -1;
  const e = ease(progress, 0.25, 0.46, 0.45, 0.94);
  // A DRIFTS THE WAY B IS TRAVELLING, NOT AWAY FROM IT. This read `sign * -25`,
  // which sent A off in the direction B ARRIVES FROM — so the strip A vacated
  // was the one strip B had not reached yet, and the root (#000000) showed
  // through it. Measured off the shipped numbers: WORST 22.33% OF THE CANVAS
  // WIDTH was black, peaking around e=0.7, which is exactly what the still at
  // f240 shows. A transition carries BOTH SIDES of the cut; the uncovered
  // region shows the outgoing clip or the component is not a transition.
  const translateA = lerp(e, 0, sign * 25);
  // AND THE SCALE HAD THE SAME DEFECT VERTICALLY. Shrinking A to 0.92 about its
  // centre exposed a 4% band of root along the top and bottom edges for the
  // whole middle of the move — smaller than the horizontal gap and the same
  // bug. A now SETTLES from 1.09 to 1.0 instead of shrinking past full: the
  // depth cue survives (A eases back as B arrives) and A never covers less than
  // the canvas. Coverage is asserted over the whole ramp by
  // smoke_transition_covers_canvas.py rather than argued here.
  const scaleA = lerp(e, 1.09, 1.0);
  const translateB = lerp(e, -sign * 100, 0);
  const shadowOpacity = progress < 0.5
    ? lerp(progress / 0.5, 0, 0.5)
    : lerp((progress - 0.5) / 0.5, 0.5, 0.3);
  return (
    <div style={rootStyle}>
      <div style={{ position: "absolute", inset: 0,
        transform: `translateX(${translateA}%) scale(${scaleA})` }}>
        <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
      </div>
      <div style={{ position: "absolute", inset: 0,
        transform: `translateX(${translateB}%)`,
        boxShadow: `${sign * -20}px 0 60px rgba(0,0,0,${shadowOpacity})` }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
    </div>
  );
};
