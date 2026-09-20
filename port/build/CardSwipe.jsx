/* CardSwipe — A is thrown off like a card, on ChatCut's timeline.
 *
 * A SEAM-COVERING COMPONENT OVER A HARD CUT, per Zac's ruling. ChatCut's
 * transition slot takes only its own thirteen presets with no custom code, so a
 * graphic spanning the cut is the only available shape. The cut underneath is
 * hard; this covers it.
 *
 * A rotates and translates away while B rises from beneath at slight scale —
 * the deck-of-cards read. A's opacity holds until halfway so the throw is seen
 * rather than faded through.
 *
 * NO VELOCITY CAP: a transition is a CUT, not a ramp zoom. The 11px/frame
 * ceiling bounds a move meant to be INVISIBLE — a push the viewer should feel
 * and not see. A transition is a deliberate sub-500ms event where the motion IS
 * the effect, the argument StepZoom makes for its single discontinuity. Capping
 * it would turn a throw into a dissolve and delete the component. The measured
 * peaks are in measured/transition_peaks_2026-09-20.md, so the exemption is
 * informed rather than assumed.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; a plain div root, never AbsoluteFill; editable values
 * read through an identifier literally named `props`; every declared property
 * read and used; and NO HARDCODED FALLBACKS — defaults live in the property
 * table alone.
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
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "cover", filter: correct };
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = clamp01((frame - start) / duration);
  const lerp = (t, a, b) => a + (b - a) * t;
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
  const e = ease(progress, 0.32, 0.72, 0, 1);
  const translateA = lerp(e, 0, sign * 120);
  const rotateA = lerp(e, 0, sign * -15);
  const scaleA = lerp(e, 1, 0.88);
  const opacityA = 1 - clamp01((progress - 0.5) / 0.5);
  const translateB = lerp(e, 60, 0);
  const scaleB = lerp(e, 0.92, 1);
  const opacityB = clamp01(progress / 0.3);
  return (
    <div style={rootStyle}>
      <div style={{ position: "absolute", inset: 0,
        transform: `translateY(${translateB}px) scale(${scaleB})`, opacity: opacityB }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
      {opacityA > 0.01 ? (
        <div style={{ position: "absolute", inset: 0,
          transform: `translateX(${translateA}%) rotate(${rotateA}deg) scale(${scaleA})`,
          opacity: opacityA }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
    </div>
  );
};
