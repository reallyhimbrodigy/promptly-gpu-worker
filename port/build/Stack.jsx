/* Stack — the iOS task-switcher, on ChatCut's timeline.
 *
 * A SEAM-COVERING COMPONENT OVER A HARD CUT, per Zac's ruling. ChatCut's
 * transition slot takes only its own thirteen presets with no custom code, so a
 * graphic spanning the cut is the only shape available; the cut underneath
 * stays hard.
 *
 * Three phases, and the phases are the component:
 *   0 -> 0.3   A shrinks into a card and the switcher wallpaper comes up
 *   0.3 -> 0.7 the whole ROW scrolls left by one slot — A, B and the ghost
 *              cards all move by the SAME amount, which is what makes it read
 *              as one coherent scroll rather than two clips passing
 *   0.7 -> 1   B zooms out of the stack to full screen and the wallpaper goes
 *
 * THE ROW MOVES TOGETHER OR IT IS NOT A STACK. A travels 0 -> +stackShift with
 * everything else and only then carries on past the edge; the ghosts take the
 * same stackShift; B arrives from -stackShift. One number drives all three.
 *
 * THE SOLVER IS THE RUNTIME'S. `interpolate` and `Easing` are available here
 * (measured by frame, 2026-09-19), so the piecewise ramps call them rather than
 * carrying a hand-rolled multi-stop interpolator — the same rule that has
 * SnapReframe calling `spring`.
 *
 * FOUR TOP-LEVEL CONSTANTS HAD TO NEST. CARD_RADIUS, CARD_SCALE, GHOST_CARDS
 * and STACK_SHIFT are module-level in the Remotion original and ChatCut refuses
 * any top-level binding beside the component itself.
 *
 * NO VELOCITY CAP: a transition is a CUT, not a ramp zoom. The ceiling bounds a
 * move meant to be INVISIBLE, and a task-switcher scroll is meant to be seen.
 * Measured in measured/transition_peaks_2026-09-20.md rather than silently
 * exceeded.
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
  const cardScale = Number(props.cardScale);
  const cardRadius = Number(props.cardRadius);
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#0a0a0f" };
  const plate = { width: "100%", height: "100%", objectFit: "cover", filter: correct };

  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = Math.min(Math.max((frame - start) / duration, 0), 1);

  // The ghosts sit to the LEFT of B — in a switcher the apps ahead of your
  // next-app are further along the row — and the whole row shifts by stackShift.
  const ghosts = [
    { offsetX: -115, scale: 0.72 },
    { offsetX: -180, scale: 0.68 },
  ];
  const stackShift = 55;
  const ease = Easing.bezier(0.32, 0.72, 0, 1);

  const enterSwitcher = interpolate(progress, [0, 0.3], [0, 1], { easing: ease, ...clamp });
  const exitSwitcher = interpolate(progress, [0.7, 1], [0, 1], { easing: Easing.out(Easing.cubic), ...clamp });
  const slideProgress = interpolate(progress, [0.3, 0.7], [0, 1],
    { easing: Easing.bezier(0.25, 0.46, 0.45, 0.94), ...clamp });
  const bgOpacity = interpolate(progress, [0, 0.25, 0.75, 1], [0, 1, 1, 0], clamp);

  const scaleA = interpolate(enterSwitcher, [0, 1], [1, cardScale], clamp);
  const radiusA = interpolate(enterSwitcher, [0, 1], [0, cardRadius], clamp);
  const slideXA = interpolate(slideProgress, [0, 0.7, 1], [0, stackShift, 110], clamp);
  const opacityA = interpolate(slideProgress, [0.6, 1], [1, 0], clamp);

  const slideXB = interpolate(slideProgress, [0, 1], [-stackShift, 0], clamp);
  const finalScaleB = interpolate(exitSwitcher, [0, 1], [cardScale, 1], clamp);
  const scaleBTotal = progress < 0.7 ? cardScale : finalScaleB;
  const radiusB = interpolate(exitSwitcher, [0, 1], [cardRadius, 0], clamp);
  const opacityB = interpolate(progress, [0.15, 0.35], [0, 1], clamp);
  const ghostOpacity = interpolate(progress, [0.1, 0.3, 0.7, 0.9], [0, 1, 1, 0], clamp);

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
        background: "radial-gradient(ellipse at 50% 30%, #1a1a30 0%, #0a0a0f 70%)",
        opacity: bgOpacity }} />
      {ghosts.map((ghost, i) => (
        <div key={i} style={{ position: "absolute", inset: 0, display: "flex",
          alignItems: "center", justifyContent: "center", opacity: ghostOpacity,
          transform: `translateX(${ghost.offsetX + slideProgress * stackShift}%) scale(${ghost.scale})`,
          pointerEvents: "none" }}>
          <div style={{ width: "92%", height: "85%", borderRadius: cardRadius,
            background: "#ffffff", boxShadow: "0 20px 60px rgba(0,0,0,0.45)" }} />
        </div>
      ))}
      <div style={{ position: "absolute", inset: 0,
        transform: `translateX(${slideXB}%) scale(${scaleBTotal})`,
        borderRadius: radiusB, overflow: "hidden", opacity: opacityB,
        boxShadow: progress > 0.15 && progress < 0.95 ? "0 20px 60px rgba(0,0,0,0.5)" : "none" }}>
        <Video src={src} startFrom={srcFromB} muted volume={0} style={plate} />
      </div>
      {opacityA > 0.01 ? (
        <div style={{ position: "absolute", inset: 0,
          transform: `translateX(${slideXA}%) scale(${scaleA})`,
          borderRadius: radiusA, overflow: "hidden", opacity: opacityA,
          boxShadow: `0 20px 60px rgba(0,0,0,${0.5 * (1 - slideProgress)})` }}>
          <Video src={src} startFrom={srcFromA} muted volume={0} style={plate} />
        </div>
      ) : null}
      <div style={{ position: "absolute", bottom: 18, left: "50%",
        transform: "translateX(-50%)", width: 140, height: 5, borderRadius: 3,
        backgroundColor: `rgba(255,255,255,${0.7 * bgOpacity})`, pointerEvents: "none" }} />
    </div>
  );
};
