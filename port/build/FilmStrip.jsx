/* FilmStrip — the device-frame film reel, on ChatCut's timeline.
 *
 * A SEAM-COVERING COMPONENT OVER A HARD CUT, and the most elaborate in the set.
 * Both clips become rounded square tiles on a vertical strip inside a device
 * frame; the strip scrolls up by exactly one tile pitch, carrying A off the top
 * and B into the rest position; then B grows back to full frame.
 *
 *   0 -> 0.3   A morphs from full viewport into the tile, and the frame (grid,
 *              bezel, vignette) fades IN as A shrinks and reveals it
 *   0.3 -> 0.7 the strip translates by exactly tileH + gap. MECHANICAL, no
 *              crossfade — the scroll is the transition
 *   0.7 -> 1   B morphs from the tile back to full viewport, frame fades out
 *
 * THE SCROLL IS ONE PITCH AND THAT IS WHY IT READS AS A STRIP. Every ghost tile
 * takes the same stripOffsetY as the live ones, so the whole reel moves as one
 * object. Give the ghosts their own offset and it stops being a strip and
 * becomes two clips and some decoration moving separately.
 *
 * NINE MODULE CONSTANTS, THREE EASINGS AND TWO SUB-COMPONENTS ALL HAD TO NEST.
 * ChatCut refuses any top-level binding beside the component itself, and this
 * file had more of them than every other port combined. GhostTile and
 * TileContainer are arrow functions inside the body, which is the same shape
 * Builder-1's own probe uses for its Freeze shim.
 *
 * NO VELOCITY CAP: a transition is a CUT, not a ramp zoom, and here the move is
 * a full-viewport-to-tile morph plus a mechanical scroll — both are the effect.
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
  const { width, height, durationInFrames } = useVideoConfig();
  const props = (item && item.props) || {};
  const src = props.clip;
  const srcFromA = Math.max(0, Math.round(Number(props.srcFromA)));
  const srcFromB = Math.max(0, Math.round(Number(props.srcFromB)));
  const seamRoom = Math.max(1, Math.round(Number(props.seamRoom)));
  const duration = Math.max(2, Math.round(Number(props.duration)));
  const frameBackground = props.frameBackground;
  const caption = props.caption;
  const showBookmark = props.showBookmark === true || props.showBookmark === "true";
  const showGrid = props.showGrid === true || props.showGrid === "true";
  const advanceFrames = Math.max(1, Math.round(Number(props.advanceFrames)));
  const correct = props.correct;

  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
  const start = Math.max(0, seamRoom - Math.round(duration / 2));
  const progress = Math.min(Math.max((frame - start) / duration, 0), 1);

  // ── the nested constants ───────────────────────────────────────────────────
  const framePadding = 24;
  const tileRadius = 22;
  const gridCell = 90;
  const gridLineColor = "rgba(255,255,255,0.6)";
  const gridLineWidth = 1.5;
  const easeOutQuint = Easing.bezier(0.22, 1, 0.36, 1);
  const easeInQuint = Easing.bezier(0.64, 0, 0.78, 0);
  const smoothScroll = Easing.bezier(0.45, 0, 0.55, 1);

  const tileW = Math.round(width * 0.77);
  const tileH = tileW;
  const tileX = Math.round((width - tileW) / 2);
  const tileY = Math.round(height * 0.13);
  const gap = Math.round(tileH * 0.1);
  const pitch = tileH + gap;

  const p1End = 0.3;
  const p3Start = 0.7;
  const p1Raw = interpolate(progress, [0, p1End], [0, 1], clamp);
  const p1 = easeOutQuint(p1Raw);
  const p3Raw = interpolate(progress, [p3Start, 1], [0, 1], clamp);
  const p3 = easeInQuint(p3Raw);

  const aBase = progress < p1End ? p1 : 1;
  const aLeft = interpolate(aBase, [0, 1], [0, tileX]);
  const aTop = interpolate(aBase, [0, 1], [0, tileY]);
  const aWidth = interpolate(aBase, [0, 1], [width, tileW]);
  const aHeight = interpolate(aBase, [0, 1], [height, tileH]);
  const aRadius = interpolate(aBase, [0, 1], [0, tileRadius]);

  const bBase = progress > p3Start ? 1 - p3 : 1;
  const bLeft = interpolate(bBase, [0, 1], [0, tileX]);
  const bTop = interpolate(bBase, [0, 1], [0, tileY]);
  const bWidth = interpolate(bBase, [0, 1], [width, tileW]);
  const bHeight = interpolate(bBase, [0, 1], [height, tileH]);
  const bRadius = interpolate(bBase, [0, 1], [0, tileRadius]);

  const blurA = interpolate(p1Raw, [0, 0.4, 1], [0, 2.2, 0], clamp);
  const blurB = interpolate(p3Raw, [0, 0.6, 1], [0, 2.2, 0], clamp);

  const p2Raw = interpolate(progress, [p1End, p3Start], [0, 1], clamp);
  const p2 = smoothScroll(p2Raw);
  const stripOffsetY = -p2 * advanceFrames * pitch;

  const frameOpacity = interpolate(progress, [0, p1End, p3Start, 1], [0, 1, 1, 0], clamp);
  const shadowOpacity = frameOpacity;
  const aTransform = `translate3d(0, ${stripOffsetY}px, 0)`;
  const bTransform = `translate3d(0, ${advanceFrames * pitch + stripOffsetY}px, 0)`;
  const aFilter = blurA > 0.1 ? `blur(${blurA.toFixed(2)}px)` : undefined;
  const bFilter = blurB > 0.1 ? `blur(${blurB.toFixed(2)}px)` : undefined;
  const captionY = tileY + tileH + Math.round(tileH * 0.05);
  const ghostOffsets = [-3, -2, -1, advanceFrames + 1, advanceFrames + 2, advanceFrames + 3];

  // An empty rounded square defined purely by LUMINANCE — no border, no fill.
  // A crisp outline reads as a UI element; the halo reads as a frame on a reel.
  const GhostTile = ({ n }) => (
    <div style={{ position: "absolute", left: tileX, top: tileY, width: tileW, height: tileH,
      transform: `translate3d(0, ${n * pitch + stripOffsetY}px, 0)`,
      willChange: "transform", opacity: frameOpacity, pointerEvents: "none" }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: tileRadius,
        boxShadow: `0 0 30px rgba(255,255,255,${0.32 * frameOpacity}), 0 0 80px rgba(255,255,255,${0.14 * frameOpacity}), inset 0 0 36px rgba(255,255,255,${0.26 * frameOpacity}), inset 0 0 6px rgba(255,255,255,${0.1 * frameOpacity})` }} />
    </div>
  );

  const TileContainer = ({ from, left, top, w, h, radius, transform, filter }) => (
    <div style={{ position: "absolute", left, top, width: w, height: h, transform,
      willChange: "transform, filter", filter }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: radius,
        boxShadow: `0 0 28px rgba(255,255,255,${0.32 * shadowOpacity}), 0 0 72px rgba(255,255,255,${0.14 * shadowOpacity}), 0 16px 42px rgba(0,0,0,${0.58 * shadowOpacity}), 0 4px 12px rgba(0,0,0,${0.42 * shadowOpacity})`,
        pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: radius, overflow: "hidden",
        background: "#000",
        // 0.85 alpha and not 0.95 — higher read as a harsh outline on real footage.
        boxShadow: "inset 0 0 0 1.25px rgba(255,255,255,0.85), inset 0 0 16px rgba(255,255,255,0.14)" }}>
        <Video src={src} startFrom={from} muted volume={0}
          style={{ width: "100%", height: "100%", objectFit: "cover", filter: correct }} />
      </div>
    </div>
  );

  const rootStyle = { position: "absolute", inset: 0, overflow: "hidden",
    boxSizing: "border-box", background: frameBackground };

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
      {showGrid ? (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", opacity: frameOpacity,
          backgroundImage: `linear-gradient(to right, ${gridLineColor} ${gridLineWidth}px, transparent ${gridLineWidth}px), linear-gradient(to bottom, ${gridLineColor} ${gridLineWidth}px, transparent ${gridLineWidth}px)`,
          backgroundSize: `${gridCell}px ${gridCell}px`,
          WebkitMaskImage: "radial-gradient(ellipse at center, #000 0%, rgba(0,0,0,0.88) 15%, rgba(0,0,0,0.42) 40%, transparent 68%)",
          maskImage: "radial-gradient(ellipse at center, #000 0%, rgba(0,0,0,0.88) 15%, rgba(0,0,0,0.42) 40%, transparent 68%)" }} />
      ) : null}
      {caption ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: captionY, textAlign: "center",
          color: "#b5b5b5", fontSize: 30, fontWeight: 500, letterSpacing: 0.2,
          opacity: frameOpacity * 0.9, pointerEvents: "none" }}>
          {caption}
        </div>
      ) : null}
      {ghostOffsets.map((n) => <GhostTile key={`g-${n}`} n={n} />)}
      <TileContainer from={srcFromB} left={bLeft} top={bTop} w={bWidth} h={bHeight}
        radius={bRadius} transform={bTransform} filter={bFilter} />
      <TileContainer from={srcFromA} left={aLeft} top={aTop} w={aWidth} h={aHeight}
        radius={aRadius} transform={aTransform} filter={aFilter} />
      {showBookmark ? (
        <div style={{ position: "absolute", top: framePadding, right: framePadding,
          width: 56, height: 56, borderRadius: 14, background: "#1a1a1a",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06), inset 0 -1px 0 rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.4)",
          opacity: frameOpacity, display: "flex", alignItems: "center",
          justifyContent: "center", pointerEvents: "none" }}>
          <div style={{ width: 22, height: 26, borderRadius: 3,
            border: "1.5px solid #bfbfbf", borderBottomColor: "transparent" }} />
        </div>
      ) : null}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "38%",
        background: "linear-gradient(180deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.025) 38%, transparent 100%)",
        pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.09), inset 0 -1px 0 rgba(0,0,0,0.4)",
        pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0,
        background: "radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0,0,0,0.22) 82%, rgba(0,0,0,0.42) 100%)",
        pointerEvents: "none" }} />
    </div>
  );
};
