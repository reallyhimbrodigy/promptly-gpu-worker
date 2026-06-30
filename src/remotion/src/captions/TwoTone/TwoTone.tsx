import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { SpringConfig } from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { TwoToneProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

const SLAM_SPRING: SpringConfig = {
  mass: 0.5,
  damping: 12,
  stiffness: 220,
  overshootClamping: false,
};

// Tight contour + a solid downward extrude (the 3D "sticker block" depth) +
// a soft ambient drop. extrudeColor sits behind the contour so the glyph reads
// like a chunky block lifted off the footage.
function buildDepth(
  strokeWidth: number,
  strokeColor: string,
  extrudeColor: string,
): string {
  const s = Math.ceil(strokeWidth / 2);
  const contour = [
    `${-s}px ${-s}px 0 ${strokeColor}`,
    `${s}px ${-s}px 0 ${strokeColor}`,
    `${-s}px ${s}px 0 ${strokeColor}`,
    `${s}px ${s}px 0 ${strokeColor}`,
    `0 ${-s}px 0 ${strokeColor}`,
    `0 ${s}px 0 ${strokeColor}`,
    `${-s}px 0 0 ${strokeColor}`,
    `${s}px 0 0 ${strokeColor}`,
  ];
  const extrude: string[] = [];
  for (let i = 1; i <= 6; i++) {
    extrude.push(`${Math.round(i * 0.6)}px ${i * 2}px 0 ${extrudeColor}`);
  }
  const ambient = "0 16px 26px rgba(0,0,0,0.5)";
  return [...contour, ...extrude, ambient].join(", ");
}

const TwoToneWord: React.FC<{
  token: TikTokToken;
  globalIndex: number;
  pageStartMs: number;
  color: string;
  fontFamily: string;
  fontSize: number;
  allCaps: boolean;
  textShadow: string;
  localFrame: number;
}> = ({
  token,
  globalIndex,
  pageStartMs,
  color,
  fontFamily,
  fontSize,
  allCaps,
  textShadow,
  localFrame,
}) => {
  const { fps } = useVideoConfig();

  const entry = msToFrames(token.fromMs - pageStartMs, fps) + globalIndex;
  const s = spring({ fps, frame: localFrame - entry, config: SLAM_SPRING });
  // Slam in: from slightly oversized + lifted, settling to rest.
  const scale = interpolate(s, [0, 1], [1.18, 1], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(s, [0, 1], [18, 0], { extrapolateRight: "clamp" });
  const opacity = interpolate(s, [0, 0.25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily,
        fontSize,
        fontWeight: 900,
        color,
        textTransform: allCaps ? "uppercase" : "none",
        letterSpacing: "-0.02em",
        lineHeight: 0.9,
        textShadow,
        transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(3)})`,
        transformOrigin: "center bottom",
        opacity,
        whiteSpace: "nowrap",
        padding: "0 0.1em",
      }}
    >
      {token.text}
    </span>
  );
};

const TwoToneLine: React.FC<{
  tokens: TikTokToken[];
  startIndex: number;
  pageStartMs: number;
  color: string;
  fontFamily: string;
  fontSize: number;
  allCaps: boolean;
  textShadow: string;
  localFrame: number;
}> = ({
  tokens,
  startIndex,
  pageStartMs,
  color,
  fontFamily,
  fontSize,
  allCaps,
  textShadow,
  localFrame,
}) => (
  <div
    style={{
      display: "flex",
      flexWrap: "wrap",
      justifyContent: "center",
      alignItems: "flex-end",
      columnGap: "0.16em",
    }}
  >
    {tokens.map((token, i) => (
      <TwoToneWord
        key={i}
        token={token}
        globalIndex={startIndex + i}
        pageStartMs={pageStartMs}
        color={color}
        fontFamily={fontFamily}
        fontSize={fontSize}
        allCaps={allCaps}
        textShadow={textShadow}
        localFrame={localFrame}
      />
    ))}
  </div>
);

export const TwoTone: React.FC<TwoToneProps> = ({
  pages,
  topColor = "#FFFFFF",
  accentColor = "#FFC53D",
  fontFamily = CAPTION_FONTS.montserrat,
  fontSize = 110,
  position = "center",
  strokeWidth = 6,
  strokeColor = "#101014",
  allCaps = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.88;
  const positionStyle = getCaptionPositionStyle(position);

  // Both lines extrude into a dark base for the chunky 3D "sticker" depth —
  // top line into cool-dark, accent line into warm-dark to match its hue.
  const topShadow = useMemo(
    () => buildDepth(strokeWidth, strokeColor, "rgba(8,10,16,0.92)"),
    [strokeWidth, strokeColor],
  );
  const accentShadow = useMemo(
    () => buildDepth(strokeWidth, strokeColor, "rgba(92,42,0,0.94)"),
    [strokeWidth, strokeColor],
  );

  // Render the active page by comparing the current frame to each page's
  // window — the component owns no <Sequence> (the pipeline bounds visibility).
  return (
    <AbsoluteFill>
      {pages.map((page: TikTokPage, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;
        if (frame < startFrame || frame >= startFrame + durationFrames) {
          return null;
        }
        const localFrame = frame - startFrame;

        // Split the page into two stacked lines (top / accent bottom).
        const n = page.tokens.length;
        const splitAt = Math.ceil(n / 2);
        const line1 = page.tokens.slice(0, splitAt);
        const line2 = page.tokens.slice(splitAt);

        return (
          <AbsoluteFill
            key={pageIndex}
            style={{ display: "flex", alignItems: "center", ...positionStyle }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                rowGap: "0.02em",
                maxWidth,
                width: "100%",
              }}
            >
              <TwoToneLine
                tokens={line1}
                startIndex={0}
                pageStartMs={page.startMs}
                color={topColor}
                fontFamily={fontFamily}
                fontSize={fontSize}
                allCaps={allCaps}
                textShadow={topShadow}
                localFrame={localFrame}
              />
              {line2.length > 0 ? (
                <TwoToneLine
                  tokens={line2}
                  startIndex={line1.length}
                  pageStartMs={page.startMs}
                  color={accentColor}
                  fontFamily={fontFamily}
                  fontSize={fontSize}
                  allCaps={allCaps}
                  textShadow={accentShadow}
                  localFrame={localFrame}
                />
              ) : null}
            </div>
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};
