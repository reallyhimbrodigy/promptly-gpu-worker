import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokPage } from "../shared/types";
import type { CleanCutProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const CleanCutPage: React.FC<{
  page: TikTokPage;
  textColor: string;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  allCaps: boolean;
  textShadow: string;
  maxWidth: number;
  localFrame: number;
  positionStyle: React.CSSProperties;
}> = ({
  page,
  textColor,
  fontFamily,
  fontSize,
  fontWeight,
  allCaps,
  textShadow,
  maxWidth,
  localFrame,
  positionStyle,
}) => {
  const { fps } = useVideoConfig();
  const localMs = (localFrame / fps) * 1000;

  // Pick the single active token — the last one that has started.
  let activeIdx = 0;
  for (let i = 0; i < page.tokens.length; i++) {
    if (localMs >= page.tokens[i].fromMs - page.startMs) activeIdx = i;
  }
  const token = page.tokens[activeIdx];
  if (!token) return null;

  const since = localMs - (token.fromMs - page.startMs);
  // Crisp, quick entrance — a small rise + settle, no flair.
  const opacity = interpolate(since, [0, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(since, [0, 140], [1.04, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const y = interpolate(since, [0, 140], [7, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  // Gentle fade at the very end of the page.
  const fadeOut = interpolate(
    localMs,
    [page.durationMs - 150, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{ display: "flex", alignItems: "center", ...positionStyle }}
    >
      <span
        style={{
          fontFamily,
          fontSize,
          fontWeight,
          color: textColor,
          textTransform: allCaps ? "uppercase" : "none",
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          textAlign: "center",
          maxWidth,
          overflowWrap: "break-word",
          textShadow,
          transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(3)})`,
          transformOrigin: "center",
          opacity: opacity * fadeOut,
        }}
      >
        {token.text}
      </span>
    </AbsoluteFill>
  );
};

export const CleanCut: React.FC<CleanCutProps> = ({
  pages,
  textColor = "#FFFFFF",
  fontFamily = CAPTION_FONTS.inter,
  fontSize = 100,
  fontWeight = 800,
  position = "center",
  allCaps = false,
  textShadow = "0 4px 22px rgba(0,0,0,0.6), 0 2px 6px rgba(0,0,0,0.55), 0 0 1px rgba(0,0,0,0.5)",
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const positionStyle = getCaptionPositionStyle(position);

  // Render the active page by comparing the current frame to each page's
  // window — the component owns no <Sequence> (the pipeline bounds visibility).
  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;
        if (frame < startFrame || frame >= startFrame + durationFrames) {
          return null;
        }

        return (
          <CleanCutPage
            key={pageIndex}
            page={page}
            textColor={textColor}
            fontFamily={fontFamily}
            fontSize={fontSize}
            fontWeight={fontWeight}
            allCaps={allCaps}
            textShadow={textShadow}
            maxWidth={maxWidth}
            localFrame={frame - startFrame}
            positionStyle={positionStyle}
          />
        );
      })}
    </AbsoluteFill>
  );
};
