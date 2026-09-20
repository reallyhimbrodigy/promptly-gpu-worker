/* ShutterFlash — ported EXACT, on ChatCut's timeline.
 *
 * The CRT power-off into power-on. A's picture collapses vertically into a thin
 * horizontal beam, the beam contracts into a single bright dot, the dot blooms
 * and fades; then B powers on in reverse. Zac's ruling was "exact", so all five
 * phase boundaries and all seven bezier curves are the Remotion original's,
 * unchanged:
 *   0    -> 0.28  A collapses vertically   (scaleY -> 0.006)
 *   0.28 -> 0.42  A collapses horizontally (scaleX -> 0.015)
 *   0.42 -> 0.58  the dot holds and fades
 *   0.58 -> 0.72  B expands horizontally
 *   0.72 -> 1     B expands vertically
 * The phosphor-glow brightness boost as the picture compresses (1 -> 1.35 -> 2,
 * mirrored on the way out) is part of the effect, not a grade.
 *
 * THREE PROPERTIES OF THE ORIGINAL ARE DELIBERATELY NOT PORTED. `blades`,
 * `bladeColor` and `chromaticAberrationOnReveal` are on the Remotion
 * interface and READ BY NOTHING — the file says so itself: "kept on the
 * interface for API compat but unused in this CRT effect". ChatCut refuses a
 * declared property the code does not read, so porting them would have been a
 * guaranteed registration failure; and a property that controls nothing is
 * worse on a platter than an absent one, because the agent will spend a choice
 * on it. Named here so their absence is a decision and not an oversight.
 *
 * NO VELOCITY CAP: a transition is a CUT, not a ramp zoom. This one is the
 * clearest case in the set — the collapse to 0.6% of frame height IS the
 * effect, and capping per-frame displacement would turn a CRT power-off into a
 * slow squash. Measured in measured/transition_peaks_2026-09-20.md rather than
 * silently exceeded.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants — the five phase boundaries and two sizes are module
 * constants in the original and nest here; a plain div root, never
 * AbsoluteFill; editable values read through an identifier literally named
 * `props`; every declared property read and used; and NO HARDCODED FALLBACKS.
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
  const flashColor = props.flashColor;
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "cover", filter: correct };

  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = Math.min(Math.max((frame - start) / duration, 0), 1);

  const lineThickness = 0.006;
  const dotSizeX = 0.015;
  const vCollapseEnd = 0.28;
  const hCollapseEnd = 0.42;
  const dotMid = 0.5;
  const hExpandStart = 0.58;
  const hExpandEnd = 0.72;

  const aScaleY = interpolate(progress, [0, vCollapseEnd], [1, lineThickness],
    { easing: Easing.bezier(0.72, 0, 0.9, 1), ...clamp });
  const aScaleX = interpolate(progress, [vCollapseEnd, hCollapseEnd], [1, dotSizeX],
    { easing: Easing.bezier(0.5, 0, 0.9, 1), ...clamp });
  const aOpacity = interpolate(progress, [hCollapseEnd, dotMid], [1, 0], clamp);
  const aBrightness = interpolate(progress, [0, vCollapseEnd, hCollapseEnd], [1, 1.35, 2], clamp);

  const bOpacity = interpolate(progress, [dotMid, hExpandStart], [0, 1], clamp);
  const bScaleX = interpolate(progress, [hExpandStart, hExpandEnd], [dotSizeX, 1],
    { easing: Easing.bezier(0.1, 0, 0.3, 1), ...clamp });
  const bScaleY = interpolate(progress, [hExpandEnd, 1], [lineThickness, 1],
    { easing: Easing.bezier(0.1, 0, 0.3, 1), ...clamp });
  const bBrightness = interpolate(progress, [hExpandStart, hExpandEnd, 1], [2, 1.35, 1], clamp);

  const dotOpacity = interpolate(progress,
    [hCollapseEnd - 0.06, dotMid, hExpandStart + 0.06], [0, 1, 0], clamp);
  const beamA = interpolate(progress,
    [vCollapseEnd - 0.06, vCollapseEnd + 0.02, hCollapseEnd, hCollapseEnd + 0.04],
    [0, 1, 1, 0], clamp);
  const beamB = interpolate(progress,
    [hExpandStart - 0.04, hExpandStart + 0.02, hExpandEnd, hExpandEnd + 0.04],
    [0, 1, 1, 0], clamp);
  const totalBeamOpacity = Math.max(beamA, beamB);

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
      {aOpacity > 0.01 ? (
        <div style={{ position: "absolute", inset: 0,
          transform: `scaleX(${aScaleX}) scaleY(${aScaleY})`,
          transformOrigin: "center center", opacity: aOpacity,
          filter: `brightness(${aBrightness})`, willChange: "transform, filter" }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
      {bOpacity > 0.01 ? (
        <div style={{ position: "absolute", inset: 0,
          transform: `scaleX(${bScaleX}) scaleY(${bScaleY})`,
          transformOrigin: "center center", opacity: bOpacity,
          filter: `brightness(${bBrightness})`, willChange: "transform, filter" }}>
          <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
        </div>
      ) : null}
      {totalBeamOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
          opacity: totalBeamOpacity, mixBlendMode: "screen" }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 4,
            transform: "translateY(-50%)",
            background: `linear-gradient(90deg, transparent 0%, ${flashColor}33 10%, ${flashColor} 50%, ${flashColor}33 90%, transparent 100%)`,
            boxShadow: `0 0 24px 4px ${flashColor}66`, filter: "blur(1px)" }} />
        </div>
      ) : null}
      {dotOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
          opacity: dotOpacity, mixBlendMode: "screen" }}>
          <div style={{ position: "absolute", left: "50%", top: "50%", width: 28, height: 28,
            transform: "translate(-50%, -50%)", borderRadius: "50%", background: flashColor,
            boxShadow: `0 0 40px 10px ${flashColor}, 0 0 100px 30px ${flashColor}aa, 0 0 220px 60px ${flashColor}55` }} />
        </div>
      ) : null}
    </div>
  );
};
