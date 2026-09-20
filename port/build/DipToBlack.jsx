/* DipToBlack — ported EXACT, on ChatCut's timeline.
 *
 * A quick blink of black between two cuts. The dip is what hides the cut;
 * everything else is invisible. Zac's ruling was "exact", so the two bezier
 * curves and the 0.5 peak are the Remotion original's, unchanged:
 *   0 -> 0.5  A fades to black on a cosine-out — the screen LOOKS like A right
 *             up until the last beat, then snaps dark
 *   0.5       full black
 *   0.5 -> 1  B opens off black on the mirror curve
 * Designed for ~350ms. Faster reads as a flicker; slower eats a beat.
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
 * declared property is read and used; and NO HARDCODED FALLBACKS — defaults
 * live in the property table alone.
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
  const peak = 0.5;
  const aOpacity = 1 - ease((progress - 0) / peak, 0.55, 0, 0.85, 0.2);
  const bOpacity = ease((progress - peak) / (1 - peak), 0.15, 0.8, 0.45, 1);
  return (
    <div style={rootStyle}>
      {aOpacity > 0.01 ? (
        <div style={{ position: "absolute", inset: 0, opacity: aOpacity, willChange: "opacity" }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
      {bOpacity > 0.01 ? (
        <div style={{ position: "absolute", inset: 0, opacity: bOpacity, willChange: "opacity" }}>
          <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
        </div>
      ) : null}
    </div>
  );
};
