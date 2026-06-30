import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
  interpolateColors,
} from "remotion";
import type { TikTokToken } from "../shared/types";
import type { SpectrumProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

// A tight iridescent ramp (loops back to the first stop) so the phrase reads as
// one flowing holographic gradient, not a row of unrelated colors.
const DEFAULT_RAMP = [
  "#3FE0FF",
  "#5B8CFF",
  "#A86BFF",
  "#FF6BD0",
  "#FF8A5B",
  "#3FE0FF",
];

// Sample the ramp at a wrapped position t (0..1).
const sampleRamp = (ramp: string[], t: number): string => {
  const wrapped = ((t % 1) + 1) % 1;
  const idx = wrapped * (ramp.length - 1);
  const range = ramp.map((_, i) => i);
  return interpolateColors(idx, range, ramp);
};

const SpectrumWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  rampPos: number; // this word's base position along the ramp
  ramp: string[];
  flowSpeed: number;
  isKw: boolean;
  keywordSpeed: number;
  fontFamily: string;
  fontSize: number;
  allCaps: boolean;
  localFrame: number;
}> = ({
  token,
  pageStartMs,
  rampPos,
  ramp,
  flowSpeed,
  isKw,
  keywordSpeed,
  fontFamily,
  fontSize,
  allCaps,
  localFrame,
}) => {
  const { fps } = useVideoConfig();

  const entry = msToFrames(token.fromMs - pageStartMs, fps);
  const elapsed = localFrame - entry;
  const appeared = elapsed >= 0;
  const s = appeared
    ? spring({
        fps,
        frame: elapsed,
        config: { damping: 14, mass: 0.5, stiffness: 200 },
      })
    : 0;
  const kwScale = isKw ? 1.08 : 1; // special words sit a touch larger
  const scale = interpolate(s, [0, 1], [0.72, kwScale], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(s, [0, 1], [14, 0], { extrapolateRight: "clamp" });
  const opacity = interpolate(s, [0, 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // The ramp drifts over time → the live color-cycle. Normal words share one
  // global drift so the line reads as a single flowing gradient; keywords drift
  // much faster (keywordSpeed×) so the spotlight word visibly races through the
  // spectrum while the rest cycles gently. Each word also samples a slice
  // slightly further along for a dimensional top→bottom sheen.
  const speed = isKw ? flowSpeed * keywordSpeed : flowSpeed;
  // Normalize the frame-based color drift to a 30fps baseline so the cycle keeps
  // the same wall-clock speed at any fps (e.g. 60fps delivery).
  const drift = localFrame * (30 / fps) * speed;
  const hue = sampleRamp(ramp, rampPos + drift);
  const hueLo = sampleRamp(ramp, rampPos + drift + 0.12);

  // Keywords get a hotter halo so the fast-cycling word pops.
  const glow = isKw
    ? `0 3px 7px rgba(0,0,0,0.72), 0 0 32px ${hue}B0, 0 0 64px ${hue}66`
    : `0 3px 7px rgba(0,0,0,0.72), 0 0 26px ${hue}88, 0 0 52px ${hue}44`;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily,
        fontSize,
        fontWeight: 900,
        textTransform: allCaps ? "uppercase" : "none",
        letterSpacing: "-0.02em",
        lineHeight: 1.02,
        whiteSpace: "nowrap",
        // Glossy iridescent fill: white-hot top → this word's hue → a deeper
        // neighbouring hue, so the glyph looks lit foil rather than flat color.
        color: "transparent",
        backgroundImage: `linear-gradient(165deg, #FFFFFF 0%, ${hue} 38%, ${hue} 66%, ${hueLo} 100%)`,
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        WebkitTextStroke: "1px rgba(0,0,0,0.22)",
        transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(3)})`,
        transformOrigin: "center bottom",
        opacity,
        // Dark legibility drop + a soft glow tinted to the word's own hue.
        textShadow: glow,
      }}
    >
      {token.text}
    </span>
  );
};

export const Spectrum: React.FC<SpectrumProps> = ({
  pages,
  colors = [],
  hueStep = 0.13,
  flowSpeed = 0.006,
  keywords = [],
  keywordSpeed = 4,
  fontFamily = CAPTION_FONTS.poppins,
  fontSize = 104,
  position = "center",
  maxWordsPerLine = 3,
  allCaps = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.86;
  const positionStyle = getCaptionPositionStyle(position);
  const ramp = colors.length >= 2 ? colors : DEFAULT_RAMP;
  const kwSet = useMemo(() => buildKeywordSet(keywords), [keywords]);

  // Cumulative token count before each page so the gradient keeps flowing
  // across pages instead of resetting.
  let runningBase = 0;
  const pageBases = pages.map((p) => {
    const base = runningBase;
    runningBase += p.tokens.length;
    return base;
  });

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
        const localFrame = frame - startFrame;

        const base = pageBases[pageIndex];
        const lines: TikTokToken[][] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

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
                gap: 4,
                maxWidth,
                width: "100%",
              }}
            >
              {lines.map((lineTokens, lineIdx) => {
                const lineStart = lineIdx * maxWordsPerLine;
                return (
                  <div
                    key={lineIdx}
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      justifyContent: "center",
                      alignItems: "baseline",
                      columnGap: 20,
                    }}
                  >
                    {lineTokens.map((token, tokenIdx) => (
                      <SpectrumWord
                        key={tokenIdx}
                        token={token}
                        pageStartMs={page.startMs}
                        rampPos={(base + lineStart + tokenIdx) * hueStep}
                        ramp={ramp}
                        flowSpeed={flowSpeed}
                        isKw={isKeyword(token.text, kwSet)}
                        keywordSpeed={keywordSpeed}
                        fontFamily={fontFamily}
                        fontSize={fontSize}
                        allCaps={allCaps}
                        localFrame={localFrame}
                      />
                    ))}
                  </div>
                );
              })}
            </div>
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};
