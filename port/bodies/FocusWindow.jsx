/* FocusWindow — OUR window, on ChatCut's timeline.
 *
 * WHAT THIS BUYS. Two framings of one moment at once: the plate behind pushes
 * into a detail while an inset window holds the original composition, so the
 * viewer sees the detail WITHOUT losing where it sits. A single-layer preset
 * cannot state that relationship at all.
 *
 * TWO SOURCE LAYERS, ONE ASSET, ONE OFFSET. Both plates are the same clip at
 * the same srcFrom — the capability measured by frame on 2026-09-19. If the two
 * layers took different offsets the window would show a different moment than
 * the frame around it, which is the one thing this component must never do.
 *
 * THE SOLVER IS THE RUNTIME'S. The entrance is a spring and `spring` exists in
 * the motion-graphic runtime, so this calls it instead of carrying a copy.
 *
 * THE CAP MEASURES HERE, IT DOES NOT RESHAPE — same reasoning as SnapReframe.
 * The cap's solver plans trapezoids and would replace the spring; its
 * curve-agnostic half (cornerPx, peakDisplacementPx) measures the spring's own
 * displacement instead, and lever 2 stretches the spring in time until it fits.
 * The cap is solved against the BACKGROUND plate, which is the layer that
 * actually moves — the window scales in the opposite direction and by less.
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
  // THE SOURCE OFFSET IS AN INPUT, NOT AN ASSUMPTION — and BOTH plates take it.
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom)));
  // SIZE and POSITION are the same two dials on every ported zoom. Here `scale`
  // is the BACKGROUND magnification — the thing that moves.
  const targetScale = Number(props.scale);
  const originX = Number(props.originX);
  const originY = Number(props.originY);
  const capped = !(props.capped === false || props.capped === "false");
  const windowScale = Number(props.windowScale);
  const borderWidth = Number(props.borderWidth);
  const borderColor = props.borderColor;
  // THE REST CALIBRATION, SUPPLIED BY THE HARNESS — never a number written here.
  // It MOVES between runs (2.0363 then 1.7228 levels). BOTH plates wear it: the
  // window sits directly on top of the background, so a correction on one and
  // not the other would put a visible level seam at the window's own edge.
  const correct = props.correct;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", backgroundColor: "#000000" };

  // @@VELOCITY_CAP@@

  // ── the curve ──────────────────────────────────────────────────────────────
  // A ChatCut item IS the event: its own span is the window's span. The window
  // springs open, holds, and eases shut over the last 0.4s.
  const span = Math.max(2, durationInFrames);
  const springConfig = { damping: 19.5, mass: 0.7, stiffness: 180 };
  const exitFrames = Math.max(1, Math.round(fps * 0.4));
  const exitStart = Math.max(1, span - exitFrames);
  // The authored entrance is 0.5s — the natural peak is ~11.9 frames at 30fps,
  // held inside that envelope.
  const authored = Math.max(2, Math.round(fps * 0.5));

  const springAt = (f, n) => spring({ frame: f, fps, config: springConfig, durationInFrames: n });
  // The BACKGROUND plate is what the cap is solved against: it carries the whole
  // magnification, so it is the layer with the displacement.
  const scalesFor = (n) => {
    const out = [];
    for (let f = 0; f <= n; f++) out.push(1 + (targetScale - 1) * springAt(f, n));
    return out;
  };

  // LEVER 2, and only lever 2 — grow the entrance until the measured peak fits,
  // never past the point where the exit begins.
  const corner = cornerPx(width, height, originX, originY);
  let enterFrames = authored;
  let peakPx = peakDisplacementPx(scalesFor(enterFrames), corner);
  if (capped) {
    while (peakPx > PEAK_DISPLACEMENT_CAP_PX && enterFrames < exitStart) {
      enterFrames += 1;
      peakPx = peakDisplacementPx(scalesFor(enterFrames), corner);
    }
  }

  const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
  const cubicIn = (t) => t * t * t;
  const enter = springAt(frame, enterFrames);
  const exit = frame >= exitStart ? cubicIn(clamp01((frame - exitStart) / exitFrames)) : 0;
  const progress = clamp01(enter * (1 - exit));

  const currentWindowScale = 1 + (windowScale - 1) * progress;
  const currentBgScale = 1 + (targetScale - 1) * progress;
  const currentBorder = borderWidth * progress;

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
  // FIT EXCEPTION, AND IT IS TEMPORARY (Zac, 2026-09-20). The nine transitions
  // are `contain` so their plate matches the letterboxed base track. THE ZOOMS
  // STAY `cover` FOR TWO REASONS, both of which expire together: a contained
  // zoom drags the letterbox EDGE through frame, and the velocity-cap
  // calibration was measured against a COVERING plate.
  // WHEN CANVAS-FOLLOWS-SOURCE LANDS, BOTH FITS ARE THE IDENTITY — a 1920x1080
  // source in a 1920x1080 canvas has no bars for either to place — and this
  // exception ENDS. Delete it then; do not re-argue it.
          objectFit: "cover",
          filter: correct,
          transform: `scale(${currentBgScale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
      <div style={{ position: "absolute", inset: 0,
        backgroundColor: `rgba(0,0,0,${0.3 * progress})`, pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, display: "flex",
        alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
        <div style={{
          width: `${currentWindowScale * 100}%`,
          height: `${currentWindowScale * 100}%`,
          overflow: "hidden",
          border: `${currentBorder}px solid ${borderColor}`,
          boxShadow: progress > 0.1
            ? `0 ${8 * progress}px ${30 * progress}px rgba(0,0,0,${0.5 * progress})`
            : "none",
          position: "relative",
        }}>
          <Video
            src={src}
            startFrom={srcFrom}
            muted
            volume={0}
            style={{
              width: `${(1 / currentWindowScale) * 100}%`,
              height: `${(1 / currentWindowScale) * 100}%`,
              objectFit: "cover",
              position: "absolute",
              top: "50%",
              left: "50%",
              filter: correct,
              transform: "translate(-50%, -50%)",
            }}
          />
        </div>
      </div>
    </div>
  );
};
