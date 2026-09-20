/* StepZoom — OUR step, on ChatCut's timeline.
 *
 * Instant jump cuts between zoom levels. No easing, no animation: the scale is
 * held for the span and cut back at the end, like cutting between a wide and a
 * tight shot of the same camera.
 *
 * NO VELOCITY CAP: there is no ramp to cap. The cap bounds per-frame
 * displacement across a MOVE; a step has exactly one discontinuity and that
 * discontinuity IS the effect. Capping it would turn the cut into a ramp and
 * delete the component. Stated here rather than omitted, because a missing cap
 * that nobody decided is the failure this build step exists to prevent.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and no
 * top-level constants; the root is a plain div; editable values are read
 * through an identifier literally named `props`.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom) || 0));
  const targetScale = Number(props.scale) || 1.3;
  const originX = props.originX === undefined ? 0.5 : Number(props.originX);
  const originY = props.originY === undefined ? 0.5 : Number(props.originY);
  // The step can start late inside the item, so a single placement can hold the
  // wide shot and then cut tight on the word rather than opening on the cut.
  const stepAt = Math.max(0, Math.round(Number(props.stepAtFrame) || 0));
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  const span = Math.max(1, durationInFrames);
  const scale = frame >= stepAt && frame < span ? targetScale : 1;

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
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
    </div>
  );
};
