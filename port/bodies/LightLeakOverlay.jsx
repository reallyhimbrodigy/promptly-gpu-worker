/* LightLeakOverlay — the second TIGHT-CUT OVERLAY, on ChatCut's timeline.
 *
 * CARRIES NO CLIPS, like ShutterFlashOverlay. Two blurred radial glows drift
 * across a transparent root, with a wash under them, so
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
 * CHATCUT STRIPS mixBlendMode AT REGISTRATION, AND THAT CHANGES THIS COMPONENT
 * MORE THAN ANY NUMBER IN IT. Read back from the registered asset 2026-09-21:
 * all three `mixBlendMode` declarations gone, while these comments still said
 * "screen". It is a FIFTH auto-rewrite beside the props-fallback strip, the
 * nested ({item}) injection, <img> -> <Img> and the trailing newline, and the
 * only one that silently changes what the component LOOKS LIKE. The layers
 * composite NORMALLY: flat colour over the picture, far heavier than a screen.
 * The source keeps mixBlendMode so it renders correctly anywhere else; what
 * ships here is measured against the stripped form, because that is what runs.
 *
 * NO VELOCITY CAP: nothing moves that the cap can bound. The glows translate,
 * but they are BLURRED BY 28-40px and drawn at partial opacity —
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
  // THE PICTURE MUST STAY PERCEPTIBLE THROUGH THE LEAK, AND 0.71 IS MEASURED.
  // Ruled by Zac 2026-09-21: the borrowed 0.82 had to become a number.
  //
  // THE TEST IS THE ONE SHUTTERFLASH GOT IN JUNE, run on THIS composite —
  // retained detail, the RMS of high-pass luma of the composite over the same
  // quantity for the clean frame, on a real frame of zac_blueshirt. Brightness
  // is the effect and divides out; texture is the picture and is what is
  // counted. A ratio against the same frame, so the source's own detail cancels
  // and there is no absolute threshold fitted to one draw.
  //
  // THE BAR IS SHUTTERFLASH AT ITS ACCEPTED 0.82 = 0.1831 retained. The same
  // instrument scores ShutterFlash at 0.95 — the value judged a blown exposure
  // — at 0.0625, so the bar sits between a shipped value and a rejected one.
  //
  //     l2 peak 1.00  retained 0.0719   <- WHAT SHIPPED. Worse than the 0.95
  //                                        that was rejected in June.
  //     l2 peak 0.82  retained 0.1402   <- MY BORROW. Still below the bar:
  //                                        borrowing it was not conservative,
  //                                        it was simply wrong in the same
  //                                        direction, which is exactly why a
  //                                        threshold from another code path is
  //                                        a guess wearing a measurement's
  //                                        clothes.
  //     l2 peak 0.71  retained 0.1858   <- lands above the bar. Solved 0.712.
  //
  // l1 and the wash alone retain 0.4730, so the defect really is l2 and not the
  // stack — which is what makes changing this one number the whole fix.
  //
  // THE 0.71 ABOVE WAS MEASURED ON THE DESIGNED BLEND AND IS NOT THE BINDING
  // CONSTRAINT. Against the REGISTERED (stripped) composite the whole stack is
  // heavier and l2 stops being the term that matters: even at l2 = 0, l1 at
  // 0.85 plus the wash retain only 0.1088 against a 0.1822 bar. The dial that
  // fixes it is `intensity`, which scales all three, and its registered default
  // is now 0.65 (ceiling 0.670, measured). The rendered still is what settled
  // which model is real: it showed the picture all but gone, which the normal
  // model predicts (0.033) and the screen model does not (0.069).
  //
  // MEASURED AT the WORST pixel:
  // full gradient alpha with both blooms coincident. The blur, the radial
  // falloff and the real overlap all make a rendered frame kinder than that
  // bound, so this is conservative by construction. Ladder in
  // measured/PERCEPTIBILITY_2026-09-21.json; gated by
  // smoke_perceptibility_peaks.py so it cannot drift back up.
  const l2Opacity = interpolate(progress, [0.1, 0.55, 0.9], [0, 0.71 * intensity, 0], clamp);
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
