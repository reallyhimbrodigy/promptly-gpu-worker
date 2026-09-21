/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
/* SmoothPush — OUR curve, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. ChatCut's six zoom presets take a start frame and a duration,
 * move at CONSTANT SPEED, and expose no timing or curve parameter at all. Ours
 * ramps in over the first 35% of the span, holds to 60%, and releases — and the
 * ramp LANDS on the word, because peak-on-word is a product law. PUNCH
 * accelerates INTO the word; the default GLIDE decelerates into it. Only the
 * ramp-in ease changes between the two registers; the scale completes on the
 * word either way.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts by port/emit_zoom_component.mjs.
 * Do not edit it in this file or in the built blob — edit the module and re-emit.
 *
 * CONTRACT (from ChatCut's validator, not its docs): exactly one top-level
 * component and NO top-level constants, so the cap nests inside Component; the
 * root is a plain div, never AbsoluteFill; and every editable value is read
 * through an identifier literally named `props`.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION. A layer that hardcodes
  // startFrom={0} plays the opening frame wherever it sits, so a zoom at 12s
  // would show second 0 — worse than no zoom.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom)));
  const targetScale = Number(props.scale);
  const originX = Number(props.originX);
  const originY = Number(props.originY);
  const punch = props.punch === true || props.punch === "true";
  const capped = props.capped === true || props.capped === "true";   // the DEFAULT is true in the property table, not here
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // Our layer renders the source measurably brighter than the base item does: a flat
  // additive offset, independent of level, saturation and channel, and identical
  // across every variant of this component, so it belongs to the <Video> path and
  // not to us. Left uncorrected it puts a uniform brightness STEP at this item's in
  // and out boundaries. The value MOVES between runs (2.04 then 1.72 levels), which
  // is why it arrives as a measured value and is not baked in. SVG filters are inert
  // here; `brightness(b) contrast(c)` composes to slope 1 and a pure offset.
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the zoom's span, so there is no
  // event list to walk and no previous event to grow backwards into. rampIn and
  // holdEnd are the authored 35%/60% of that span.
  const span = Math.max(2, durationInFrames);
  const rampIn = Math.max(1, Math.round(span * 0.35));
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
  // The uncapped registers, kept so `capped: false` is the module's own cubic
  // and not a different edit: PUNCH eases IN, GLIDE eases OUT.
  const cubicIn = (t) => t * t * t;
  const cubicOut = (t) => 1 - Math.pow(1 - t, 3);
  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);

  let progress = 0;
  if (frame >= spanStart && frame <= spanEnd) {
    if (frame < rampIn) {
      const t = clamp01((frame - spanStart) / Math.max(1, rampIn - spanStart));
      progress = capIn ? capIn.easing(t) : (punch ? cubicIn(t) : cubicOut(t));
    } else if (frame < holdEnd) {
      progress = 1;
    } else {
      const t = clamp01((frame - holdEnd) / Math.max(1, spanEnd - holdEnd));
      progress = capOut ? 1 - capOut.easing(t) : 1 - cubicIn(t);
    }
  } else if (frame > spanEnd) {
    progress = 0;
  }
  const scale = 1 + (peakScale - 1) * progress;

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
  // CONTAIN, and the exception that kept this `cover` is GONE (2026-09-21).
  // It said: both fits become the identity once canvas-follows-source lands,
  // because a source in a canvas of its own shape has no bars for either to
  // place — delete it then, do not re-argue it. That landed. prestage now
  // derives the canvas per run and w/h/fps are keyword-only with no default,
  // so a caller that omits them is a TypeError rather than a silent portrait;
  // kolkata-9 exported 1280x720 @ 28fps with probe_state MEASURED, read off
  // the artefact rather than asserted. Both of the exception's two reasons
  // expire together and both have: there is no letterbox edge for a contained
  // zoom to drag, and the velocity cap is unaffected (see below).
          objectFit: "contain",
          filter: correct,
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
    </div>
  );
};
