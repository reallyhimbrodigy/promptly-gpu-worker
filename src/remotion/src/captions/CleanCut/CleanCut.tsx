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
import { boundedFade } from "../shared/fadeTiming";
import { getCaptionPositionStyle, CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale } from "../shared/fit";

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
  const { fps, width } = useVideoConfig();
  const localMs = (localFrame / fps) * 1000;

  // Pick the single active token — the last one that has started.
  let activeIdx = 0;
  for (let i = 0; i < page.tokens.length; i++) {
    if (localMs >= page.tokens[i].fromMs - page.startMs) activeIdx = i;
  }
  const token = page.tokens[activeIdx];
  if (!token) return null;

  // F4 width-fit guarantee: one word at a time; scale it to the real box
  // (the 200px-inset safe rect) before the existing break-word fallback —
  // a scaled whole word beats a mid-word CSS break. fitScale floors at 0.6;
  // below that, overflowWrap:break-word (already on the span) takes over.
  const fit = fitScale(
    [
      {
        parts: [
          {
            text: token.text,
            fontSize,
            font: { fontFamily, fontWeight, letterSpacingEm: -0.02, uppercase: allCaps },
          },
        ],
      },
    ],
    Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
    "CleanCut",
  );

  const since = localMs - (token.fromMs - page.startMs);
  // Crisp, quick entrance — a small rise + settle, no flair. WS2 fade-bound:
  // 55ms base (was 80), capped at 25% of this word's on-screen window (until the
  // next word, or page end) so fast speech doesn't leave the word still fading
  // in when it's already spoken (shared/fadeTiming).
  const nextTok = page.tokens[activeIdx + 1];
  const wordWindowMs = (nextTok ? nextTok.fromMs : page.startMs + page.durationMs) - token.fromMs;
  const fadeInMs = boundedFade(55, wordWindowMs);
  const opacity = interpolate(since, [0, fadeInMs], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // WS2 universal fast cap: the scale+lift motion is capped like the fade (was a
  // fixed 140ms that bypassed the bound — the caption still read slow).
  const _mms = boundedFade(140, wordWindowMs);
  const scale = interpolate(since, [0, _mms], [1.04, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const y = interpolate(since, [0, _mms], [7, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  // Gentle fade at the very end of the page — bounded to 25% of the page window
  // so a short final page doesn't spend half its life fading out (shared/fadeTiming).
  const pageFadeOutMs = boundedFade(150, page.durationMs);
  const fadeOut = interpolate(
    localMs,
    [page.durationMs - pageFadeOutMs, page.durationMs],
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
          fontSize: fontSize * fit.scale,
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
