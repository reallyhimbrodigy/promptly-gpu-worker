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
import { MAX_ENTRANCE_MS } from "../shared/fadeTiming";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";

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
  fitFloored?: boolean;
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
  fitFloored,
}) => {
  const { fps } = useVideoConfig();

  const entry = msToFrames(token.fromMs - pageStartMs, fps) + globalIndex;
  // WS2 universal fast cap: the slam settles within MAX_ENTRANCE_MS (was an
  // unbounded SLAM_SPRING ≈ 330ms — a quick slam now, still present).
  const s = spring({ fps, frame: localFrame - entry, config: SLAM_SPRING,
                     durationInFrames: Math.max(1, msToFrames(MAX_ENTRANCE_MS, fps)) });
  // Slam in: from slightly oversized + lifted, settling to rest.
  const scale = interpolate(s, [0, 1], [1.18, 1], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(s, [0, 1], [18, 0], { extrapolateRight: "clamp" });
  // WS2 fast-but-present (Zac 2026-07-12, overriding the identity-exemption):
  // opacity fades fast and DECOUPLED from the slam spring so the word lands ON
  // the beat; the slam scale/lift (TwoTone's character) stays on the spring.
  const opacity = interpolate(localFrame - entry, [0, Math.max(2, Math.round(fps * 0.06))], [0, 1], {
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
        ...(fitFloored ? CHARWRAP_FALLBACK_STYLE : {}),
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
  fitFloored?: boolean;
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
  fitFloored,
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
        fitFloored={fitFloored}
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

        // F4 width-fit guarantee: rows flex-wrap between words, so the
        // overflow unit is a single word (900-weight caps at 110px). Scale
        // the page uniformly to bring the widest word inside the margins;
        // the 0.1em side paddings are folded in as fixed px (conservative).
        const fit = fitScale(
          page.tokens.map((t) => ({
            parts: [
              {
                text: t.text,
                fontSize,
                font: {
                  fontFamily,
                  fontWeight: 900,
                  letterSpacingEm: -0.02,
                  uppercase: allCaps,
                },
              },
            ],
            extraPx: 0.2 * fontSize,
          })),
          maxWidth,
          "TwoTone",
        );
        const fittedFontSize = fontSize * fit.scale;

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
                fontSize={fittedFontSize}
                allCaps={allCaps}
                textShadow={topShadow}
                localFrame={localFrame}
                fitFloored={fit.floored}
              />
              {line2.length > 0 ? (
                <TwoToneLine
                  tokens={line2}
                  startIndex={line1.length}
                  pageStartMs={page.startMs}
                  color={accentColor}
                  fontFamily={fontFamily}
                  fontSize={fittedFontSize}
                  allCaps={allCaps}
                  textShadow={accentShadow}
                  localFrame={localFrame}
                  fitFloored={fit.floored}
                />
              ) : null}
            </div>
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};
