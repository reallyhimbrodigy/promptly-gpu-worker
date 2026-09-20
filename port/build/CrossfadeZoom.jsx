/* CrossfadeZoom — ported WHOLE, on ChatCut's timeline.
 *
 * A true cross dissolve with counter-zooms: A pushes in from 1.0 while B pulls
 * back to 1.0, and the dissolve carries between them.
 *
 * THE NO-BACKDROP-LEAK INVARIANT IS THE POINT, AND IT PORTS EXACTLY (Zac
 * 2026-08-02). These layers are STACKED ALPHA, not additive — B renders UNDER A
 * — so the black backdrop shows through by
 *     leak = (1 - opacityA) * (1 - opacityB)
 * The original ramps (A 1->0 over 0.1-0.7, B 0->1 over 0.3-0.9) left a window
 * where A was gone and B was not yet full: 17% black bleeding through
 * mid-transition, measured as a dip to min luma 20.0 — below either degraded arm
 * and near the blackdetect floor the INTEGRITY_TRIP class fires on.
 *
 * AND MATCHING THE TWO RAMPS DOES NOT FIX IT. Stated here so nobody "fixes" it
 * that way later: A = 1-t against B = t leaks t*(1-t), which PEAKS AT 25% at the
 * midpoint — worse than the bug. The base is therefore held FULLY OPAQUE and the
 * dissolve is carried by A alone, which makes the leak identically ZERO BY
 * CONSTRUCTION rather than by two curves agreeing. Composite is
 * opA*A + (1-opA)*B, a true cross dissolve.
 *
 * WHAT IS DELIBERATELY NOT PORTED: the SafeImg / cancelRender machinery that
 * survives one unloadable layer. It defends a failure that CANNOT HAPPEN HERE —
 * both sides are the SAME ASSET at two source offsets, so there is no state in
 * which one layer loads and the other does not — and neither cancelRender nor
 * SafeImg exists in this runtime. Porting it would be carrying a guard for an
 * impossible case and a dependency on two globals that are absent. Said out
 * loud because a missing guard nobody decided is the failure this port keeps
 * hunting.
 *
 * NO VELOCITY CAP: the counter-zooms are 1.0<->1.12 across the whole
 * transition — the gentlest move in the set — and a dissolve is a CUT, not a
 * ramp meant to be invisible. Measured in
 * measured/transition_peaks_2026-09-20.md.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; a plain div root, never AbsoluteFill; editable values
 * read through an identifier literally named `props`; every declared property
 * read and used; and NO HARDCODED FALLBACKS.
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
  const zoom = Number(props.zoom);
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };
  const plate = { width: "100%", height: "100%", objectFit: "contain", filter: correct };
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = clamp01((frame - start) / duration);
  const lerp = (t, a, b) => a + (b - a) * t;
  const e = Easing.bezier(0.25, 0.46, 0.45, 0.94)(progress);

  const scaleA = lerp(e, 1, zoom);
  const scaleB = lerp(e, zoom, 1);
  // THE BASE IS ALWAYS FULLY OPAQUE. The symmetric 0.1/0.9 window keeps the
  // brief hold at each end; A alone carries the dissolve.
  const opacityA = 1 - clamp01((progress - 0.1) / 0.8);

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
      <div style={{ position: "absolute", inset: 0, transform: `scale(${scaleB})`, opacity: 1 }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
      {opacityA > 0.01 ? (
        <div style={{ position: "absolute", inset: 0, transform: `scale(${scaleA})`, opacity: opacityA }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
    </div>
  );
};
