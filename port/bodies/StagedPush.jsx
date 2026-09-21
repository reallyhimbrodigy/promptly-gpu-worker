/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
/* StagedPush — OUR multi-stage push, on ChatCut's timeline.
 *
 * A push that lands on TWO OR MORE words in a row: each stage's peak is nailed
 * to its own word, the scale carries forward between them, and the release only
 * happens after the last one. ChatCut has no preset of this shape at all — their
 * six are single moves at constant speed — so this component has no counterpart
 * to be compared against, only a before and after.
 *
 * THE STAGES ARE A TEXT PROPERTY, AND THAT IS NOT A SHORTCUT. ChatCut's property
 * types are text, number, color, boolean, select, font, image and video: there is
 * no array. A multi-stage component either encodes its stages in one of those or
 * cannot be edited by a user at all, so `stages` is "seconds:scale" pairs
 * relative to the item's own start, and a malformed pair is DROPPED and named in
 * the frame rather than silently treated as zero.
 *
 * THE CAP IS NOT WRITTEN HERE. The section below the marker is EMITTED from
 * src/remotion/src/zoom/shared/velocity-cap.ts. Edit the module and re-emit.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and no
 * top-level constants; the root is a plain div; editable values are read through
 * an identifier literally named `props`.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  const srcFrom = Math.max(0, Math.round(Number(props.srcFrom)));
  const originX = Number(props.originX);
  const originY = Number(props.originY);
  const capped = props.capped === true || props.capped === "true";   // the DEFAULT is true in the property table, not here
  const cutTerminated = props.cutTerminated === true || props.cutTerminated === "true";
  const pushF = Math.max(1, Math.round(((Number(props.pushMs)) / 1000) * fps));
  const holdF = Math.max(0, Math.round(((Number(props.holdMs)) / 1000) * fps));
  const releaseF = Math.max(1, Math.round(((Number(props.releaseMs)) / 1000) * fps));
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

  // ── the stages ─────────────────────────────────────────────────────────────
  // "0.30:1.15, 0.95:1.30" — seconds into the item, and the scale its peak reaches.
  // A pair that does not parse is dropped and counted, never read as 0:0, because a
  // stage silently at scale zero would black the frame and look like a render bug.
  const raw = String(props.stages);
  const st = [];
  let dropped = 0;
  for (const part of raw.split(",")) {
    const bits = part.split(":");
    const at = Number(bits[0]);
    const sc = Number(bits[1]);
    if (bits.length !== 2 || !isFinite(at) || !isFinite(sc) || at < 0 || sc <= 0) {
      if (part.trim() !== "") dropped += 1;
      continue;
    }
    st.push({ peak: Math.floor(at * fps), scale: sc });
  }
  st.sort((a, b) => a.peak - b.peak);

  let scale = 1;
  if (st.length >= 2) {
    const corner = cornerPx(width, height, originX, originY);
    // Solved CUMULATIVELY: stage i travels from whatever stage i-1 actually
    // reached after its own cap, and each push may only grow BACKWARDS into the
    // hold before it, because every peak is nailed to its own word.
    const staged = [];
    let cum = 1;
    for (let i = 0; i < st.length; i++) {
      const c = capped
        ? planCappedRampIn({
            fromScale: cum, toScale: st[i].scale, landFrame: st[i].peak,
            earliestFrame: i === 0 ? 0 : st[i - 1].peak,
            authoredFrames: pushF, fps, corner,
          })
        : null;
      staged.push({ start: c ? c.startFrame : st[i].peak - pushF,
                    scale: c ? c.toScale : st[i].scale,
                    easing: c ? c.easing : null });
      cum = staged[i].scale;
    }
    const last = st[st.length - 1];
    const lastScale = staged[staged.length - 1].scale;
    const releaseStartF = last.peak + holdF;
    const capRelease = capped
      ? planCappedRelease({
          fromScale: lastScale, toScale: 1, startFrame: releaseStartF,
          latestFrame: durationInFrames, authoredFrames: releaseF, fps, corner,
        })
      : null;
    const releaseEndF = capRelease ? capRelease.endFrame : releaseStartF + releaseF;
    const beginF = staged[0].start;
    const spanEndF = cutTerminated ? releaseStartF : releaseEndF;
    const clamp01 = (t) => Math.min(Math.max(t, 0), 1);
    const cubicOut = (t) => 1 - Math.pow(1 - t, 3);
    const cubicInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

    if (frame >= beginF && frame <= spanEndF) {
      let s = 1;
      let prevScale = 1;
      let resolved = false;
      for (let i = 0; i < st.length; i++) {
        if (frame < staged[i].start) { s = prevScale; resolved = true; break; }
        if (frame <= st[i].peak) {
          const t = clamp01((frame - staged[i].start) / Math.max(1, st[i].peak - staged[i].start));
          const e = staged[i].easing ? staged[i].easing(t) : cubicOut(t);
          s = prevScale + (staged[i].scale - prevScale) * e;
          resolved = true; break;
        }
        prevScale = staged[i].scale;
      }
      if (!resolved) {
        if (frame <= releaseStartF || cutTerminated) {
          s = lastScale;
        } else {
          const t = clamp01((frame - releaseStartF) / Math.max(1, releaseEndF - releaseStartF));
          const e = capRelease ? capRelease.easing(t) : cubicInOut(t);
          s = lastScale + (1 - lastScale) * e;
        }
      }
      scale = s;
    }
  }

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
      {st.length < 2 || dropped > 0 ? (
        <div style={{ position: "absolute", left: 24, bottom: 24, color: "#FFD166",
                      fontSize: 34, fontFamily: "sans-serif" }}>
          {st.length < 2
            ? "STAGES: need at least 2, got " + st.length
            : "STAGES: dropped " + dropped + " malformed pair(s)"}
        </div>
      ) : null}
    </div>
  );
};
