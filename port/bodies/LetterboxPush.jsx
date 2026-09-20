/* LetterboxPush — OUR push inside OUR bars, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. The frame narrows to a cinematic ratio while the inner image
 * pushes in, and the untouched footage stays visible behind the bars so the
 * narrowing reads as a framing choice rather than a crop. ChatCut's presets
 * move at constant speed and have no second layer at all, so this shape is
 * unavailable to them.
 *
 * TWO SOURCE LAYERS, ONE ASSET. The base plate and the pushed plate are the
 * same clip at the same source offset — the capability measured by frame on
 * 2026-09-19 (two <Video> layers, one graphic). The bars ride the SAME progress
 * as the push, so they cannot drift out of step with it.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts by port/emit_zoom_component.mjs.
 * Do not edit it in this file or in the built blob — edit the module and
 * re-emit. LetterboxPush is one of the four the cap was MEASURED against:
 * 1.25/1400ms read 50.3 px/frame before it, against an 11px ceiling.
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
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION — and BOTH layers take it,
  // or the plate behind the bars would play a different moment than the push.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom)));
  // SIZE and POSITION are the same two dials on every ported zoom.
  const targetScale = Number(props.scale);
  const originX = Number(props.originX);
  const originY = Number(props.originY);
  const punch = props.punch === true || props.punch === "true";
  const capped = !(props.capped === false || props.capped === "false");
  const maxBarHeight = Number(props.maxBarHeight);
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // It MOVES between runs (2.0363 then 1.7228 levels). SVG filters are inert in
  // this runtime; the harness sends `brightness(b) contrast(c)`, slope 1 and a
  // pure offset. BOTH layers wear it, or the bars would sit at a different level
  // than the push they frame.
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the push's span, so there is no
  // event list to walk and no predecessor to grow backwards into. rampIn and
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

  let barProgress = 0;
  if (frame >= spanStart && frame <= spanEnd) {
    if (frame < rampIn) {
      const t = clamp01((frame - spanStart) / Math.max(1, rampIn - spanStart));
      barProgress = capIn ? capIn.easing(t) : (punch ? cubicIn(t) : cubicOut(t));
    } else if (frame < holdEnd) {
      barProgress = 1;
    } else {
      const t = clamp01((frame - holdEnd) / Math.max(1, spanEnd - holdEnd));
      barProgress = capOut ? 1 - capOut.easing(t) : 1 - cubicIn(t);
    }
  }
  const scale = 1 + (peakScale - 1) * barProgress;
  const barHeight = maxBarHeight * height * barProgress;
  // FIT EXCEPTION, AND IT IS TEMPORARY (Zac, 2026-09-20). The nine transitions
  // are `contain` so their plate matches the letterboxed base track. THE ZOOMS
  // STAY `cover` FOR TWO REASONS, both of which expire together: a contained
  // zoom drags the letterbox EDGE through frame, and the velocity-cap
  // calibration was measured against a COVERING plate.
  // WHEN CANVAS-FOLLOWS-SOURCE LANDS, BOTH FITS ARE THE IDENTITY — a 1920x1080
  // source in a 1920x1080 canvas has no bars for either to place — and this
  // exception ENDS. Delete it then; do not re-argue it.
  const plate = { width: "100%", height: "100%", objectFit: "cover",
    filter: correct };

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
      <Video src={src} startFrom={srcFrom} muted volume={0} style={plate} />
      <div style={{ position: "absolute", inset: 0,
        backgroundColor: `rgba(0,0,0,${0.35 * barProgress})`, pointerEvents: "none" }} />
      <div style={{ position: "absolute", top: barHeight, left: 0, right: 0,
        bottom: barHeight, overflow: "hidden" }}>
        <Video
          src={src}
          startFrom={srcFrom}
          muted
          volume={0}
          style={{
            width: "100%",
            height: `${height}px`,
            objectFit: "cover",
            position: "absolute",
            top: -barHeight,
            left: 0,
            filter: correct,
            transform: `scale(${scale})`,
            transformOrigin: `${originX * 100}% ${originY * 100}%`,
          }}
        />
      </div>
    </div>
  );
};
