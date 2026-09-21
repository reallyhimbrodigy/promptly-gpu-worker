/* DepthPull — OUR depth stack, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. Perceived depth, not just magnification: the plate pushes at
 * SIXTY PERCENT of the amplitude while haze, bokeh, edge blur and a vignette
 * ride the full move, so the background reads as further away than the frame.
 * A constant-speed preset has one layer and cannot separate them at all.
 *
 * THE PARALLAX IS THE POINT, AND THE CAP IS SOLVED AGAINST THE FULL TARGET.
 * bgScale is the 0.6x layer; the atmosphere layers ride 1.0x. Solving the cap
 * against the background would let the FOREGROUND move 1.67x over the ceiling,
 * so the solve uses the full amplitude and the background inherits the result.
 *
 * NO TOP-LEVEL CONSTANTS, so the orb table nests inside the component. In the
 * Remotion original it is a module-level array; ChatCut's validator refuses any
 * top-level binding beside the component itself, and a hoisted constant is
 * exactly what that rule is about.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts by port/emit_zoom_component.mjs.
 * Do not edit it here or in the built blob — edit the module and re-emit.
 * DepthPull is one of the four the cap was MEASURED against: 1.25/2200ms read
 * 33.8 px/frame before it, against an 11px ceiling.
 *
 * RE-AUTHORED FOR NORMAL COMPOSITING (Zac, 2026-09-21). ChatCut strips
 * mixBlendMode, so this component now declares NONE and says what it does.
 *
 * I OVERSTATED THE DEFECT BEFORE MEASURING IT, AND THE CORRECTION IS THE
 * USEFUL PART. I reported the stripped multiply as "a flat opaque overlay
 * rather than a darkening one". It is not: the layer ran at alpha 0.06, so
 * stripped it still DARKENS, by -0.0152 mean luma against an intended -0.0215
 * — about 70% of the depth — while lifting true blacks off zero. A tint at 6%
 * cannot cover anything, and I said it could before reading the alpha.
 *
 * WHAT CHANGED, EACH WITH ITS MEASUREMENT:
 *   the cool tint    DELETED as a layer, folded into the video's brightness()
 *                    filter, which is multiplicative and survives registration
 *                    — so it darkens by the intended amount and keeps the
 *                    black point that a normal composite would lift.
 *   the warm haze    alphas x2.5. Designed +0.0124 mean luma, stripped +0.0047.
 *   the orbs         0.35 -> 0.40. Designed +0.0205, stripped +0.0182 — nearly
 *                    at parity already.
 *
 * The criterion is matching MEAN LUMA on one real frame, stated rather than
 * implied, and it wants a picture before anyone believes it.
 * Measured 2026-09-21 by reading a registered asset back. Two layers below
 * declare a blend and neither gets it:
 *
 *   multiply (the vignette)  a layer that DARKENED what was under it becomes a
 *                            flat COVERING layer. Not a weaker vignette — a
 *                            different thing in front of the picture.
 *   screen (the glow)        an additive bloom becomes an opaque patch.
 *
 * The multiply one is the reason this is called out separately in
 * smoke_blend_mode_stripped.py: a stripped `screen` overstates a highlight,
 * while a stripped `multiply` replaces the image instead of shading it.
 *
 * NOT YET JUDGED. This component is STALE_BODY — its still photographs a body
 * re-authored since — and the frame it needs must be read with this in mind: if
 * it comes back heavier or flatter than the definition, the blend strip is the
 * first thing to suspect and not the registration.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; the root is a plain div, never AbsoluteFill; every
 * editable value is read through an identifier literally named `props`; and
 * every declared property is read and used.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom)));
  // SIZE and POSITION are the same two dials on every ported zoom.
  const targetScale = Number(props.scale);
  const originX = Number(props.originX);
  const originY = Number(props.originY);
  const punch = props.punch === true || props.punch === "true";
  const capped = !(props.capped === false || props.capped === "false");
  const edgeBlur = Number(props.edgeBlur);
  const frameLines = !(props.frameLines === false || props.frameLines === "false");
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // It MOVES between runs (2.0363 then 1.7228 levels). It sits on the <Video>
  // itself, BEFORE this component's own depth grade, because the offset it
  // corrects belongs to the video path and the grade is ours on top of it. At
  // rest the grade is exactly neutral, so the corrected plate is what matches
  // the base item.
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the pull's span. DepthPull is
  // the slow one — 40% in, 20% hold, 40% out.
  const span = Math.max(2, durationInFrames);
  const rampIn = Math.max(1, Math.round(span * 0.4));
  const holdEnd = Math.max(rampIn + 1, Math.round(span * 0.6));
  const corner = cornerPx(width, height, originX, originY);
  const capIn = capped
    ? planCappedRampIn({
        fromScale: 1, toScale: targetScale, landFrame: rampIn, earliestFrame: 0,
        authoredFrames: rampIn, fps, corner,
        skew: punch ? SKEW_PUNCH : SKEW_GLIDE,
      })
    : null;
  const capOut = capped
    ? planCappedRelease({
        fromScale: capIn ? capIn.toScale : targetScale, toScale: 1,
        startFrame: holdEnd, latestFrame: span,
        authoredFrames: Math.max(1, span - holdEnd), fps, corner,
        skew: SKEW_GLIDE,   // a release lands on nothing — it always glides
      })
    : null;
  const spanStart = capIn ? Math.max(0, capIn.startFrame) : 0;
  const spanEnd = capOut ? Math.min(span, capOut.endFrame) : span;
  const peakScale = capIn ? capIn.toScale : targetScale;
  const cubicIn = (t) => t * t * t;
  const cubicOut = (t) => 1 - Math.pow(1 - t, 3);
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);

  let zoomProgress = 0;
  if (frame >= spanStart && frame <= spanEnd) {
    if (frame < rampIn) {
      const t = clamp01((frame - spanStart) / Math.max(1, rampIn - spanStart));
      zoomProgress = capIn ? capIn.easing(t) : (punch ? cubicIn(t) : cubicOut(t));
    } else if (frame < holdEnd) {
      zoomProgress = 1;
    } else {
      const t = clamp01((frame - holdEnd) / Math.max(1, spanEnd - holdEnd));
      zoomProgress = capOut ? 1 - capOut.easing(t) : 1 - cubicIn(t);
    }
  }

  // ── the depth stack ────────────────────────────────────────────────────────
  const orbs = [
    { x: 15, y: 22, size: 110, delay: 0, driftX: 25, driftY: -12 },
    { x: 72, y: 58, size: 80, delay: 4, driftX: -18, driftY: 8 },
    { x: 42, y: 78, size: 95, delay: 7, driftX: 12, driftY: -20 },
    { x: 82, y: 18, size: 65, delay: 2, driftX: -8, driftY: 15 },
    { x: 28, y: 50, size: 70, delay: 10, driftX: 20, driftY: 5 },
  ];
  const bgScale = 1 + (peakScale - 1) * 0.6 * zoomProgress;
  const midScale = 1 + (peakScale - 1) * 1.0 * zoomProgress;
  const contrastBoost = 1 + 0.08 * zoomProgress;
  const brightnessLift = 1 + 0.02 * zoomProgress;
  const bgSaturation = 1 - 0.15 * zoomProgress;
  const currentEdgeBlur = edgeBlur * zoomProgress;
  const frameOpacity = zoomProgress <= 0 || zoomProgress >= 1
    ? 0
    : 0.15 * Math.min(1, Math.min(zoomProgress / 0.25, (1 - zoomProgress) / 0.25));
  const frameScale = 1 - 0.04 * zoomProgress;
  // The graded wrapper, not the root: the root stays the plain div the
  // validator asks for, and the grade applies to the whole composited stack
  // exactly as it does in the Remotion original.
  const grade = { position: "absolute", inset: 0, overflow: "hidden",
    filter: `contrast(${contrastBoost}) brightness(${brightnessLift})` };

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
      <div style={grade}>
        <Video
          src={src}
          startFrom={srcFrom}
          muted
          volume={0}
          style={{
            width: "100%",
            height: "100%",
  // CONTAIN, and the exception that kept this `cover` is GONE (2026-09-21).
  // Its own terms: both fits become the identity once canvas-follows-source
  // lands, because a source in a canvas of its own shape has no bars for
  // either to place — delete it then, do not re-argue it. That landed.
  // prestage derives the canvas per run, w/h/fps are keyword-only with no
  // default (a caller that omits them is a TypeError, not a silent portrait),
  // and kolkata-9 exported 1280x720 @ 28fps with probe_state MEASURED — read
  // off the artefact rather than asserted. Both reasons expire together and
  // both have.
            objectFit: "contain",
            transform: `scale(${bgScale})`,
            transformOrigin: `${originX * 100}% ${originY * 100}%`,
            // THE COOL TINT LIVES HERE NOW, NOT IN AN OVERLAY. It was a
            // rgba(30,50,80) layer at alpha 0.06 in `multiply`, and ChatCut
            // strips mixBlendMode — so it composited normally, which still
            // darkens but only to about 70% of the intended depth (-0.0152
            // against -0.0215 mean luma, measured) AND lifts true blacks off
            // zero instead of preserving them. brightness() is multiplicative
            // and survives registration, so it does exactly what the multiply
            // layer was for, with the black point intact.
            filter: `${correct} saturate(${bgSaturation}) brightness(${0.95 * (1 - 0.048 * zoomProgress)})`,
          }}
        />
        <div style={{ position: "absolute", inset: 0,
          // ALPHAS RAISED 2.5x BECAUSE THE BLEND IS GONE, NOT BECAUSE THE LOOK
          // CHANGED. In `screen` this lifted mean luma by +0.0124; composited
          // normally at the old alphas it lifts only +0.0047, so the haze was
          // rendering at a bit over a third of its intended strength. 2.5x
          // restores the measured lift. Matching mean luma on one frame is the
          // stated criterion, not a claim about every frame.
          background: `linear-gradient(180deg, rgba(180, 160, 130, ${0.0625 * zoomProgress}) 0%, rgba(160, 140, 110, ${0.10 * zoomProgress}) 50%, rgba(140, 120, 100, ${0.0625 * zoomProgress}) 100%)`,
          filter: "blur(20px)",
          transform: `scale(${midScale})`, pointerEvents: "none" }} />
        {orbs.map((orb, i) => {
          const orbProgress = clamp01((frame - orb.delay) / Math.max(1, span - orb.delay));
          const orbOpacity = orbProgress <= 0 || orbProgress >= 1
            ? 0
            : 0.12 * Math.min(1, Math.min(orbProgress / 0.12, (1 - orbProgress) / 0.15));
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: `${orb.x + orb.driftX * orbProgress}%`,
                top: `${orb.y + orb.driftY * orbProgress}%`,
                width: orb.size,
                height: orb.size,
                borderRadius: "50%",
                // 0.35 -> 0.40: nearest to parity of the three layers. In
                // `screen` an orb lifted mean luma +0.0205, normally +0.0182,
                // so it was already close and needs only a nudge.
                background: "radial-gradient(circle, rgba(255,220,160,0.40) 0%, rgba(255,200,120,0.09) 40%, transparent 70%)",
                filter: "blur(15px)",
                opacity: orbOpacity,
                transform: `scale(${midScale})`,
                pointerEvents: "none",
              }}
            />
          );
        })}
        {currentEdgeBlur > 0.2 ? (
          <div style={{ position: "absolute", inset: 0,
            backdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitBackdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitMaskImage: "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            maskImage: "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            pointerEvents: "none" }} />
        ) : null}
        <div style={{ position: "absolute", inset: 0,
          background: `radial-gradient(ellipse at center, transparent 35%, rgba(15, 8, 3, ${0.2 * zoomProgress}) 70%, rgba(8, 4, 2, ${0.45 * zoomProgress}) 100%)`,
          pointerEvents: "none" }} />
        {frameLines && frameOpacity > 0.01 ? (
          <div style={{ position: "absolute", inset: 0, display: "flex",
            alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
            <div style={{ width: "84%", height: "84%",
              border: `1px solid rgba(255, 255, 255, ${frameOpacity})`,
              transform: `scale(${frameScale})` }} />
          </div>
        ) : null}
      </div>
    </div>
  );
};
