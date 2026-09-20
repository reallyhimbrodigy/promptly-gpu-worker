/* ZoomThrough — a whip THROUGH A into B, on ChatCut's timeline.
 *
 * OUR CURVES ON TWO SOURCE LAYERS, per Zac's ruling — so the ramps are the
 * module's TRAPEZOID, not the Remotion original's cubic-bezier. That is the
 * whole point of the ruling: a cubic peaks at 3x its linear average and puts
 * that peak on the first frame, which is the front-loading defect the cap was
 * written to remove. A trapezoid at blend b peaks at 1/(1-b/2) instead, and the
 * PUNCH/GLIDE skew moves where that peak sits without raising it. A whip should
 * accelerate INTO the cut and decelerate out of it, which is exactly what the
 * two registers express.
 *
 * THE CEILING IS EXCEEDED ON PURPOSE, AND MEASURED OFFLINE. A whip-zoom drives
 * A to 3x in under half a second — far past 11px/frame, deliberately: the smear
 * IS the transition. The cap's ceiling bounds a move meant to be INVISIBLE, and
 * this one is meant to be seen. So the module is carried for its CURVE and the
 * ceiling is not applied. The peak is measured OUTSIDE the component, in
 * measured/transition_peaks_2026-09-20.md, because a number computed in here
 * would be read by nothing — a measured value no consumer reads is the most
 * expensive kind of dead code. An exemption nobody measured is what the build
 * step exists to prevent; this one is measured, just not here.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts by port/emit_zoom_component.mjs.
 * Edit the module and re-emit; never edit here or in the built blob.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants, so the cap nests inside Component; a plain div root,
 * never AbsoluteFill; editable values read through an identifier literally
 * named `props`; every declared property read and used; and NO HARDCODED
 * FALLBACKS — defaults live in the property table alone.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  const srcFromA = Math.max(0, Math.round(Number(props.srcFromA)));
  const srcFromB = Math.max(0, Math.round(Number(props.srcFromB)));
  const seamRoom = Math.max(1, Math.round(Number(props.seamRoom)));
  const duration = Math.max(2, Math.round(Number(props.duration)));
  const through = Number(props.through);
  const punch = props.punch === true || props.punch === "true";
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "contain", filter: correct };

  // @@VELOCITY_CAP@@

  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = clamp01((frame - start) / duration);
  const lerp = (t, a, b) => a + (b - a) * t;

  // OUR curve: the trapezoid, skewed by the register. A accelerates into the
  // cut (PUNCH) or eases out of it (GLIDE); B always settles, so it glides.
  const outEase = trapezoidEasing(1.0, punch ? SKEW_PUNCH : SKEW_GLIDE);
  const inEase = trapezoidEasing(1.0, SKEW_GLIDE);

  const scaleA = lerp(outEase(clamp01(progress / 0.6)), 1, through);
  const opacityA = 1 - clamp01((progress - 0.2) / 0.35);
  const scaleB = lerp(inEase(clamp01((progress - 0.3) / 0.7)), 0.6, 1);
  const opacityB = clamp01((progress - 0.3) / 0.3);

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
      <div style={{ position: "absolute", inset: 0,
        transform: `scale(${scaleB})`, opacity: opacityB }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
      {opacityA > 0.01 ? (
        <div style={{ position: "absolute", inset: 0,
          transform: `scale(${scaleA})`, opacity: opacityA }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
    </div>
  );
};
