/* LightLeakOverlay — the second TIGHT-CUT OVERLAY, on ChatCut's timeline.
 *
 * CARRIES NO CLIPS, like ShutterFlashOverlay. Two blurred radial glows drift
 * across a transparent root in `screen`, with a soft-light wash under them, so
 * whatever the timeline already shows plays through and the hard cut underneath
 * stays hard. No `clip`, no `srcFromA/B`, no `correct` — there is no <Video>
 * layer of ours for the rest calibration to apply to.
 *
 * Four palettes and four drift directions, both module-level tables in the
 * Remotion original and both nested here — ChatCut refuses any top-level
 * binding beside the component itself.
 *
 * THE GRAIN LAYER IS DELIBERATELY NOT PORTED, and this is the important part.
 * The original draws film grain with an SVG <feTurbulence> filter. SVG FILTERS
 * ARE INERT IN THIS RUNTIME — Builder-1 measured it at 128 levels, a hundred
 * times the magnitude that would matter, and the frame came back IDENTICAL to
 * no filter at all. So porting the grain would ship a layer that draws nothing,
 * and a layer that draws nothing is indistinguishable from one that works: the
 * component would look correct in review, pass every gate, and quietly lack the
 * texture someone tuned to 0.04 on 2026-06-15 (down from 0.08, because at 0.08
 * the noise was visible on dark baked-in cards).
 *
 * Dropped and named rather than carried dead. If grain is wanted here it needs
 * a CSS or bitmap implementation, which is a different component and a
 * decision, not a port.
 *
 * NO VELOCITY CAP: nothing moves that the cap can bound. The glows translate,
 * but they are BLURRED BY 28-40px and drawn in `screen` at partial opacity —
 * there is no edge whose per-frame displacement reads as judder, which is the
 * thing the 11px ceiling exists to bound. Exempt by nature, like DipToBlack and
 * ShutterFlashOverlay, and not in the peaks table.
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
  const seamRoom = Math.max(1, Math.round(Number(props.seamRoom)));
  const duration = Math.max(2, Math.round(Number(props.duration)));
  const palette = props.palette;
  const direction = props.direction;
  const intensity = Number(props.intensity);
  const rootStyle = { position: "absolute", inset: 0, overflow: "hidden",
    boxSizing: "border-box", pointerEvents: "none" };

  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = Math.min(Math.max((frame - start) / duration, 0), 1);

  const palettes = {
    warm: { primary: "#FF8A30", secondary: "#FFB870", highlight: "#FFE2B0" },
    gold: { primary: "#FFC93C", secondary: "#FFE070", highlight: "#FFF7C8" },
    cool: { primary: "#5BC8FF", secondary: "#A8DCFF", highlight: "#E0F2FF" },
    magenta: { primary: "#E64FA1", secondary: "#F593C5", highlight: "#FFD6EB" },
  };
  const paths = {
    "tr-bl": { l1: [50, -50, -50, 50], l2: [30, -60, -60, 30] },
    "left-right": { l1: [-60, 0, 60, 0], l2: [-40, -15, 70, 15] },
    "top-down": { l1: [0, -60, 0, 60], l2: [-15, -40, 15, 70] },
    "tl-br": { l1: [-50, -50, 50, 50], l2: [-30, -60, 60, 30] },
  };
  // An unknown palette or direction falls to the documented default rather than
  // to `undefined`, which would make every colour read as the string
  // "undefined" and paint nothing — the failure being silent, as usual.
  const pal = palettes[palette] || palettes.warm;
  const path = paths[direction] || paths["tl-br"];

  const l1X = interpolate(progress, [0, 1], [path.l1[0], path.l1[2]], clamp);
  const l1Y = interpolate(progress, [0, 1], [path.l1[1], path.l1[3]], clamp);
  const l1Opacity = interpolate(progress, [0, 0.5, 1], [0, 0.85 * intensity, 0], clamp);
  const l2X = interpolate(progress, [0, 1], [path.l2[0], path.l2[2]], clamp);
  const l2Y = interpolate(progress, [0, 1], [path.l2[1], path.l2[3]], clamp);
  const l2Opacity = interpolate(progress, [0.1, 0.55, 0.9], [0, 1.0 * intensity, 0], clamp);
  const washOpacity = interpolate(progress, [0.2, 0.5, 0.8], [0, 0.3 * intensity, 0], clamp);

  return (
    <div style={rootStyle}>
      {washOpacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, background: pal.secondary,
          mixBlendMode: "soft-light", opacity: washOpacity, pointerEvents: "none" }} />
      ) : null}
      {l1Opacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, mixBlendMode: "screen",
          opacity: l1Opacity, pointerEvents: "none" }}>
          <div style={{ position: "absolute", left: "-20%", top: "-20%",
            width: "140%", height: "140%",
            transform: `translate(${l1X}%, ${l1Y}%)`,
            background: `radial-gradient(circle at center, ${pal.primary} 0%, ${pal.primary}AA 30%, ${pal.primary}55 60%, transparent 100%)`,
            filter: "blur(40px)" }} />
        </div>
      ) : null}
      {l2Opacity > 0.001 ? (
        <div style={{ position: "absolute", inset: 0, mixBlendMode: "screen",
          opacity: l2Opacity, pointerEvents: "none" }}>
          <div style={{ position: "absolute", left: "20%", top: "20%",
            width: "60%", height: "60%",
            transform: `translate(${l2X}%, ${l2Y}%)`,
            background: `radial-gradient(circle at center, ${pal.highlight} 0%, ${pal.secondary}88 50%, transparent 100%)`,
            filter: "blur(28px)" }} />
        </div>
      ) : null}
    </div>
  );
};
