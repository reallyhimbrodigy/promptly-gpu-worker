/* StepPush — the keynote step, on ChatCut's timeline.
 *
 * OUR CURVES ON TWO SOURCE LAYERS, per Zac's ruling. Both panels travel
 * together in the same direction: A exits, B arrives to take its place, with a
 * shadow on the trailing edge selling the two-slides-passing read.
 *
 * THE CURVE IS OURS, NOT THE ORIGINAL'S. The Remotion version used
 * Easing.bezier(0.65, 0, 0.35, 1) — a cubic ease-in-out, which peaks at 3x its
 * linear average. `Easing.inOut(Easing.cubic)` does NOT fix that; it peaks at
 * 3x too and merely moves the peak to the middle. The module's TRAPEZOID peaks
 * at 1/(1-b/2) instead, so the step departs and arrives with velocity zero at
 * both ends and no slam at either. That is what "confident departure, confident
 * arrival" was reaching for, done by construction rather than by a curve that
 * happens to look right.
 *
 * THE CEILING IS NOT APPLIED — a step moves a full frame width and is meant to
 * be SEEN. Measured in measured/transition_peaks_2026-09-20.md rather than
 * silently exceeded.
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
  const direction = props.direction;
  const separatorShadow = props.separatorShadow === true || props.separatorShadow === "true";
  const punch = props.punch === true || props.punch === "true";
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "cover", filter: correct };

  // @@VELOCITY_CAP@@

  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = clamp01((frame - start) / duration);
  // OUR curve. A step lands on the arriving slide, so PUNCH accelerates into it
  // and the default GLIDE decelerates into it — the same register the zooms use.
  const p = trapezoidEasing(1.0, punch ? SKEW_PUNCH : SKEW_GLIDE)(progress);

  const isHorizontal = direction === "left" || direction === "right";
  const sign = direction === "left" || direction === "up" ? -1 : 1;
  const travelA = sign * 100 * p;
  const travelB = sign * (-100 + 100 * p);
  const transformA = isHorizontal ? `translateX(${travelA}%)` : `translateY(${travelA}%)`;
  const transformB = isHorizontal ? `translateX(${travelB}%)` : `translateY(${travelB}%)`;
  const shadowVisible = separatorShadow && p > 0.02 && p < 0.98;
  // WRITTEN OUT PER DIRECTION rather than with computed keys. The Remotion
  // original built this object with `[cond ? "right" : ""]` expressions, which
  // can emit an EMPTY-STRING key — legal JavaScript, silently no style — and a
  // blob that draws nothing is indistinguishable from one that drew correctly.
  const shadowBox = { position: "absolute", pointerEvents: "none" };
  if (direction === "left") {
    shadowBox.right = 0; shadowBox.top = 0; shadowBox.width = 28; shadowBox.height = "100%";
    shadowBox.background = "linear-gradient(90deg, transparent, rgba(0,0,0,0.4))";
  } else if (direction === "right") {
    shadowBox.left = 0; shadowBox.top = 0; shadowBox.width = 28; shadowBox.height = "100%";
    shadowBox.background = "linear-gradient(-90deg, transparent, rgba(0,0,0,0.4))";
  } else if (direction === "up") {
    shadowBox.bottom = 0; shadowBox.left = 0; shadowBox.height = 28; shadowBox.width = "100%";
    shadowBox.background = "linear-gradient(0deg, transparent, rgba(0,0,0,0.4))";
  } else {
    shadowBox.top = 0; shadowBox.left = 0; shadowBox.height = 28; shadowBox.width = "100%";
    shadowBox.background = "linear-gradient(180deg, transparent, rgba(0,0,0,0.4))";
  }

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
      <div style={{ position: "absolute", inset: 0, transform: transformA, willChange: "transform" }}>
        <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        {shadowVisible ? <div style={shadowBox} /> : null}
      </div>
      <div style={{ position: "absolute", inset: 0, transform: transformB, willChange: "transform" }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
    </div>
  );
};
