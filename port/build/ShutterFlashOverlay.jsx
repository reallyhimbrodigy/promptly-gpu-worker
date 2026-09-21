/* ShutterFlashOverlay — a TIGHT-CUT OVERLAY, on ChatCut's timeline.
 *
 * NOT A TRANSITION, AND THAT IS THE WHOLE DIFFERENCE. The nine transitions each
 * carry both sides of the cut and draw them. An overlay carries NO CLIPS: it
 * renders decoration on a transparent root over whatever the timeline already
 * shows, and the cut underneath stays a hard cut. So it takes no `clip`, no
 * `srcFromA/B`, and it has no calibration — there is no <Video> layer of ours
 * for the rest offset to apply to.
 *
 * That also makes it the CHEAPEST way to hide a cut: the flash does the masking
 * without either side being warped, scaled or re-rendered.
 *
 *   0 -> 0.42   white wash ramps in, the beam appears
 *   0.42 - 0.58 peak: wash plus a bright dot at centre
 *   0.58 -> 1   wash and beam fade out
 *
 * THE 0.82 IS MEASURED AND MUST NOT BE ROUNDED UP. It was 0.95 until
 * 2026-06-15, where on real talking-head footage the speaker became a
 * near-invisible silhouette through the wash — which reads as a glitch or a
 * blown exposure rather than an intentional camera-flash punch. 0.82 keeps the
 * speaker PERCEPTIBLE THROUGH the flash. The whole plateau is flattened to 0.82
 * so that 0.82 is the true maximum: the shoulders used to sit at 0.85, so
 * changing only the centre value would have INVERTED the curve.
 *
 * NO VELOCITY CAP: nothing moves. Every value here is an opacity, and an
 * opacity ramp has no per-frame pixel displacement to bound. Exempt by nature
 * rather than by margin, the same way DipToBlack is.
 *
 * THE BEAM AND DOT DECLARE NO BLEND MODE, DELIBERATELY. They asked for
 * `screen`; ChatCut strips mixBlendMode at registration — measured 2026-09-21
 * by reading a registered asset back — so the declaration never survived and
 * was dead code that looked live. Removed rather than annotated: the source
 * now says what runs, and registered_diff can hold the two byte-identical.
 *
 * THE 0.82 IS UNAFFECTED AND THAT IS NOT LUCK. The wash is the term the
 * perceptibility measurement is about, and the wash was always a normal
 * composite — no blend mode to lose. What changes is the beam and the dot:
 * additive highlights become opaque ones. Over a wash already at 0.82 of a
 * white flash they land in nearly the same place, which is why the frame still
 * reads correctly.
 *
 * AND THE VERDICT ALREADY COVERS THE STRIPPED FORM. The still this component
 * was passed on was rendered FROM THE REGISTERED CODE, so it photographed the
 * normal-blend composite. Every frame in this repo is evidence about the
 * runtime, never about the source — which is exactly the confusion that made me
 * solve LightLeakOverlay's peak against a blend that does not happen.
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
  // THE TWO DIALS, as on every transition: seamRoom is where the hard cut sits
  // inside this item, duration is how long the flash runs, centred on it.
  const seamRoom = Math.max(1, Math.round(Number(props.seamRoom)));
  const duration = Math.max(2, Math.round(Number(props.duration)));
  const flashColor = props.flashColor;
  const peak = Number(props.peak);
  // THE ROOT IS TRANSPARENT. An overlay that painted its own background would
  // cover the cut it exists to decorate, and the frame underneath would be gone
  // rather than flashed.
  const rootStyle = { position: "absolute", inset: 0, overflow: "hidden",
    boxSizing: "border-box", pointerEvents: "none" };

  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = Math.min(Math.max((frame - start) / duration, 0), 1);

  // The plateau is FLAT at `peak` across 0.42-0.58 so peak is the true maximum.
  const washOpacity = interpolate(progress, [0.0, 0.42, 0.5, 0.58, 1.0],
    [0.0, peak, peak, peak, 0.0], clamp);
  const beamOpacity = interpolate(progress, [0.15, 0.42, 0.58, 0.85], [0, 1, 1, 0], clamp);
  const dotOpacity = interpolate(progress, [0.36, 0.5, 0.64], [0, 1, 0], clamp);

  return (
    <div style={rootStyle}>
      {washOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, background: flashColor,
          opacity: washOpacity, pointerEvents: "none" }} />
      ) : null}
      {beamOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
          opacity: beamOpacity }}>
          <div style={{
            position: "absolute", left: 0, right: 0, top: "50%", height: 4,
            transform: "translateY(-50%)",
            background: `linear-gradient(90deg, transparent 0%, ${flashColor}33 10%, ${flashColor} 50%, ${flashColor}33 90%, transparent 100%)`,
            boxShadow: `0 0 24px 4px ${flashColor}66`,
            filter: "blur(1px)",
          }} />
        </div>
      ) : null}
      {dotOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
          opacity: dotOpacity }}>
          <div style={{
            position: "absolute", left: "50%", top: "50%", width: 28, height: 28,
            transform: "translate(-50%, -50%)", borderRadius: "50%",
            background: flashColor,
            boxShadow: `0 0 40px 10px ${flashColor}, 0 0 100px 30px ${flashColor}aa, 0 0 220px 60px ${flashColor}55`,
          }} />
        </div>
      ) : null}
    </div>
  );
};
