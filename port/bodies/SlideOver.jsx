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
  const plate = { width: "100%", height: "100%", objectFit: "cover", filter: correct };
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
  const translateA = lerp(e, 0, sign * -25);
  const scaleA = lerp(e, 1, 0.92);
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
