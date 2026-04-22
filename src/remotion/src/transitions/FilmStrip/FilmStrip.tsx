import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  OffthreadVideo,
  useVideoConfig,
} from "remotion";
import type { FilmStripProps } from "../types";

export const FILM_STRIP_PEAK_PROGRESS = 0.5;

const FRAME_PADDING = 24;
const TILE_RADIUS = 22;
const TILE_WIDTH_PCT = 0.77;
const TILE_TOP_PCT = 0.13;
const TILE_GAP_PCT = 0.1;
const GRID_CELL = 90;
const GRID_LINE_COLOR = "rgba(255,255,255,0.6)";
const GRID_LINE_WIDTH = 1.5;

const EASE_OUT_QUINT = Easing.bezier(0.22, 1, 0.36, 1);
const EASE_IN_QUINT = Easing.bezier(0.64, 0, 0.78, 0);
const SMOOTH_SCROLL = Easing.bezier(0.45, 0, 0.55, 1);

/**
 * FilmStrip — device-frame film-reel transition.
 *
 *   0 → 0.3  resize-in:  clip A morphs from full viewport into the tile
 *                        position (rounded square, 77% wide, 13% down).
 *                        Device frame (grid, bezel, vignette) fades in
 *                        as clip A shrinks and reveals it.
 *   0.3 → 0.7 scroll:    strip translates upward by exactly one tile
 *                        pitch (tileH + gap). Clip A exits off the top,
 *                        clip B arrives at the tile rest position.
 *                        Mechanical scroll, no crossfade, 2% settle on
 *                        arrival.
 *   0.7 → 1   resize-out: clip B morphs from the tile back to full
 *                        viewport. Frame fades out.
 *
 * Layers (back → front): frame background, radial-masked grid, optional
 * caption, ghost squares, clip B, clip A, bookmark, bezel highlight,
 * corner vignette.
 */
export const FilmStrip: React.FC<FilmStripProps> = ({
  clipA,
  clipB,
  progress,
  style,
  frameBackground = "#0b0a0a",
  caption,
  showBookmark = false,
  showGrid = true,
  advanceFrames = 1,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const { width, height } = useVideoConfig();

  // Tile geometry
  const tileW = Math.round(width * TILE_WIDTH_PCT);
  const tileH = tileW; // 1:1
  const tileX = Math.round((width - tileW) / 2);
  const tileY = Math.round(height * TILE_TOP_PCT);
  // Tight configured gap for dense strip look
  const gap = Math.round(tileH * TILE_GAP_PCT);
  const pitch = tileH + gap;
  // Clip A needs `tileY + tileH` of upward travel to fully leave the
  // viewport. One pitch of scroll provides only `pitch`. The difference
  // is an extra push applied only to clip A so it clears even when the
  // strip's own scroll distance is small.
  const aExtraClear = Math.max(0, tileY + tileH - pitch);

  const P1_END = 0.3;
  const P3_START = 0.7;

  const p1Raw = interpolate(progress, [0, P1_END], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const p1 = EASE_OUT_QUINT(p1Raw);

  const p3Raw = interpolate(progress, [P3_START, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const p3 = EASE_IN_QUINT(p3Raw);

  const aBase = progress < P1_END ? p1 : 1;
  const aLeft = interpolate(aBase, [0, 1], [0, tileX]);
  const aTop = interpolate(aBase, [0, 1], [0, tileY]);
  const aWidth = interpolate(aBase, [0, 1], [width, tileW]);
  const aHeight = interpolate(aBase, [0, 1], [height, tileH]);
  const aRadius = interpolate(aBase, [0, 1], [0, TILE_RADIUS]);

  const bBase = progress > P3_START ? 1 - p3 : 1;
  const bLeft = interpolate(bBase, [0, 1], [0, tileX]);
  const bTop = interpolate(bBase, [0, 1], [0, tileY]);
  const bWidth = interpolate(bBase, [0, 1], [width, tileW]);
  const bHeight = interpolate(bBase, [0, 1], [height, tileH]);
  const bRadius = interpolate(bBase, [0, 1], [0, TILE_RADIUS]);

  // Micro motion blur during the resize. Peaks earlier on A (it's
  // decelerating into the tile) and later on B (accelerating out).
  const blurA = interpolate(p1Raw, [0, 0.4, 1], [0, 2.2, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blurB = interpolate(p3Raw, [0, 0.6, 1], [0, 2.2, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const p2Raw = interpolate(progress, [P1_END, P3_START], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const p2 = SMOOTH_SCROLL(p2Raw);
  const stripOffsetY = -p2 * advanceFrames * pitch;

  // Frame fades in with clip A's arrival, out with clip B's departure
  const frameOpacity = interpolate(
    progress,
    [0, P1_END * 0.9, P3_START + (1 - P3_START) * 0.1, 1],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const shadowOpacity = frameOpacity;

  // Clip A transform: 0 during phase 1, rides the strip offset during
  // phase 2, plus an extra upward push proportional to scroll progress so
  // it fully clears the viewport (the visible gap between scrolling tiles
  // is small, so the strip's own scroll isn't enough to push A off-screen).
  const aTransform =
    progress < P1_END
      ? "translate3d(0, 0, 0)"
      : `translate3d(0, ${stripOffsetY - aExtraClear * p2}px, 0)`;

  const bTransform =
    progress < P3_START
      ? `translate3d(0, ${advanceFrames * pitch + stripOffsetY}px, 0)`
      : "translate3d(0, 0, 0)";

  const aFilter = blurA > 0.1 ? `blur(${blurA.toFixed(2)}px)` : undefined;
  const bFilter = blurB > 0.1 ? `blur(${blurB.toFixed(2)}px)` : undefined;

  const captionY = tileY + tileH + Math.round(tileH * 0.05);

  const ghostOffsets = [
    -3,
    -2,
    -1,
    advanceFrames + 1,
    advanceFrames + 2,
    advanceFrames + 3,
  ];

  const ghostBaseTransform = (pitchesFromA: number) =>
    `translate3d(0, ${pitchesFromA * pitch + stripOffsetY}px, 0)`;

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background: frameBackground,
        ...style,
      }}
    >
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {showGrid && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              opacity: frameOpacity,
              backgroundImage: `
                linear-gradient(to right, ${GRID_LINE_COLOR} ${GRID_LINE_WIDTH}px, transparent ${GRID_LINE_WIDTH}px),
                linear-gradient(to bottom, ${GRID_LINE_COLOR} ${GRID_LINE_WIDTH}px, transparent ${GRID_LINE_WIDTH}px)`,
              backgroundSize: `${GRID_CELL}px ${GRID_CELL}px`,
              WebkitMaskImage:
                "radial-gradient(ellipse at center, #000 0%, rgba(0,0,0,0.88) 15%, rgba(0,0,0,0.42) 40%, transparent 68%)",
              maskImage:
                "radial-gradient(ellipse at center, #000 0%, rgba(0,0,0,0.88) 15%, rgba(0,0,0,0.42) 40%, transparent 68%)",
            }}
          />
        )}

        {caption && (
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: captionY,
              textAlign: "center",
              color: "#b5b5b5",
              fontFamily:
                "-apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif",
              fontSize: 30,
              fontWeight: 500,
              letterSpacing: 0.2,
              opacity: frameOpacity * 0.9,
              pointerEvents: "none",
            }}
          >
            {caption}
          </div>
        )}

        {ghostOffsets.map((n) => (
          <GhostTile
            key={`g-${n}`}
            tileX={tileX}
            tileY={tileY}
            tileW={tileW}
            tileH={tileH}
            transform={ghostBaseTransform(n)}
            opacity={frameOpacity}
          />
        ))}

        <TileContainer
          src={clipB}
          startFrom={startFromB}
          playbackRate={playbackRateB}
          left={bLeft}
          top={bTop}
          width={bWidth}
          height={bHeight}
          radius={bRadius}
          transform={bTransform}
          shadowOpacity={shadowOpacity}
          filter={bFilter}
        />

        <TileContainer
          src={clipA}
          startFrom={startFromA}
          playbackRate={playbackRateA}
          left={aLeft}
          top={aTop}
          width={aWidth}
          height={aHeight}
          radius={aRadius}
          transform={aTransform}
          shadowOpacity={shadowOpacity}
          filter={aFilter}
        />

        {showBookmark && (
          <div
            style={{
              position: "absolute",
              top: FRAME_PADDING,
              right: FRAME_PADDING,
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "#1a1a1a",
              boxShadow: [
                "inset 0 1px 0 rgba(255,255,255,0.06)",
                "inset 0 -1px 0 rgba(0,0,0,0.5)",
                "0 2px 6px rgba(0,0,0,0.4)",
              ].join(", "),
              opacity: frameOpacity,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              pointerEvents: "none",
            }}
          >
            <svg
              width="22"
              height="26"
              viewBox="0 0 22 26"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M5 3.5 C5 2.12 6.12 1 7.5 1 L14.5 1 C15.88 1 17 2.12 17 3.5 L17 24.5 L11 20 L5 24.5 Z"
                stroke="#bfbfbf"
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )}

        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "38%",
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.025) 38%, transparent 100%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            boxShadow: [
              "inset 0 1px 0 rgba(255,255,255,0.09)",
              "inset 0 -1px 0 rgba(0,0,0,0.4)",
            ].join(", "),
            pointerEvents: "none",
          }}
        />

        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0,0,0,0.22) 82%, rgba(0,0,0,0.42) 100%)",
            pointerEvents: "none",
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

interface GhostTileProps {
  tileX: number;
  tileY: number;
  tileW: number;
  tileH: number;
  transform: string;
  opacity: number;
}

// Empty rounded square defined purely by luminance — no border, no fill.
// Outer halo matches the live tiles; inset glow bleeds inward from the
// edges so the shape reads clearly against the dark grid without a crisp
// outline.
const GhostTile: React.FC<GhostTileProps> = ({
  tileX,
  tileY,
  tileW,
  tileH,
  transform,
  opacity,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        left: tileX,
        top: tileY,
        width: tileW,
        height: tileH,
        transform,
        willChange: "transform",
        opacity,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: TILE_RADIUS,
          boxShadow: [
            `0 0 30px rgba(255,255,255,${0.32 * opacity})`,
            `0 0 80px rgba(255,255,255,${0.14 * opacity})`,
            `inset 0 0 36px rgba(255,255,255,${0.26 * opacity})`,
            `inset 0 0 6px rgba(255,255,255,${0.1 * opacity})`,
          ].join(", "),
        }}
      />
    </div>
  );
};

interface TileContainerProps {
  src: string;
  left: number;
  top: number;
  width: number;
  height: number;
  radius: number;
  transform: string;
  shadowOpacity: number;
  opacity?: number;
  filter?: string;
  startFrom?: number;
  playbackRate?: number;
}

const TileContainer: React.FC<TileContainerProps> = ({
  src,
  left,
  top,
  width,
  height,
  radius,
  transform,
  shadowOpacity,
  opacity = 1,
  filter,
  startFrom,
  playbackRate,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        left,
        top,
        width,
        height,
        transform,
        willChange: "transform, filter",
        opacity,
        filter,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          boxShadow: [
            `0 0 28px rgba(255,255,255,${0.32 * shadowOpacity})`,
            `0 0 72px rgba(255,255,255,${0.14 * shadowOpacity})`,
            `0 16px 42px rgba(0,0,0,${0.58 * shadowOpacity})`,
            `0 4px 12px rgba(0,0,0,${0.42 * shadowOpacity})`,
          ].join(", "),
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          overflow: "hidden",
          background: "#000",
          boxShadow: [
            // 0.85α not 0.95α — higher felt like a harsh outline
            "inset 0 0 0 1.25px rgba(255,255,255,0.85)",
            "inset 0 0 16px rgba(255,255,255,0.14)",
          ].join(", "),
        }}
      >
        <OffthreadVideo
          src={src}
          startFrom={startFrom}
          playbackRate={playbackRate}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    </div>
  );
};
