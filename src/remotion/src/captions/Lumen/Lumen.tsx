import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { TikTokToken } from "../shared/types";
import type { LumenProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

/* ─── Word Component ─── */

const LumenWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  fontSize: number;
  isKw: boolean;
  hasShine: boolean;
  textColor: string;
  keywordColor: string;
  sweepDuration: number;
}> = ({
  token,
  pageStartMs,
  fontSize,
  isKw,
  hasShine,
  textColor,
  keywordColor,
  sweepDuration,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const activateFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const elapsed = frame - activateFrame;
  const hasAppeared = elapsed >= 0;

  const entranceSpring = hasAppeared
    ? spring({ fps, frame: elapsed, config: { damping: 200 } })
    : 0;

  // Scale: 0.95 -> 1
  const scale = interpolate(entranceSpring, [0, 1], [0.95, 1], {
    extrapolateRight: "clamp",
  });

  // Lens flare sweep position — only for shine words
  const sweepPosition = hasShine && hasAppeared
    ? interpolate(elapsed, [0, sweepDuration], [-100, 200], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : -100;

  const wordFontSize = hasShine ? fontSize * 1.6 : isKw ? fontSize * 1.3 : fontSize;
  const color = isKw ? keywordColor : textColor;

  const fontProps: React.CSSProperties = {
    fontFamily: isKw
      ? CAPTION_FONTS.playfairDisplay
      : CAPTION_FONTS.montserrat,
    fontWeight: isKw ? 400 : 600,
    fontStyle: isKw ? "italic" : "normal",
    fontSize: wordFontSize,
    lineHeight: 1.1,
    whiteSpace: "nowrap" as const,
    letterSpacing: isKw ? "-0.02em" : "0.01em",
  };

  // Sweep clip: angled white strip that moves left→right
  const w = 15;
  const skew = 20;
  const p = sweepPosition;
  const showSweep = hasShine && hasAppeared && p > -w - skew && p < 100 + w + skew;
  const polyClip = `polygon(${p - w}% ${-skew}%, ${p + w}% ${-skew - 10}%, ${p + w + skew}% ${100 + 10}%, ${p - w + skew}% ${100 + skew}%)`;

  // Diffused shadow for legibility — no outlines needed
  const diffusedShadow = [
    "0 0 12px rgba(0,0,0,0.7)",
    "0 0 30px rgba(0,0,0,0.4)",
    "0 0 50px rgba(0,0,0,0.2)",
    "1px 2px 5px rgba(0,0,0,0.4)",
  ];

  const kwGlow = [
    "0 0 20px rgba(212,162,76,0.5)",
    "0 0 40px rgba(212,162,76,0.3)",
  ];

  return (
    <span
      style={{
        display: "inline-block",
        position: "relative",
        ...fontProps,
        color: hasAppeared ? color : "transparent",
        opacity: entranceSpring,
        transform: `scale(${scale})`,
        transformOrigin: "center bottom",
        textShadow: hasAppeared
          ? isKw
            ? [...diffusedShadow, ...kwGlow].join(", ")
            : diffusedShadow.join(", ")
          : "none",
        // Universal stroke for guaranteed readability over any background.
        WebkitTextStroke: hasAppeared ? "0.75px rgba(0,0,0,0.6)" : undefined,
      }}
    >
      {token.text}
      {/* Shine sweep */}
      {showSweep && (
        <span
          aria-hidden="true"
          style={{
            ...fontProps,
            position: "absolute",
            top: 0,
            left: 0,
            color: "#FFFFFF",
            textShadow: "0 0 10px rgba(255,255,255,0.8)",
            clipPath: polyClip,
            pointerEvents: "none",
          }}
        >
          {token.text}
        </span>
      )}
    </span>
  );
};

/* ─── Main Component ─── */

export const Lumen: React.FC<LumenProps> = ({
  pages,
  fontSize = 70,
  position = "bottom",
  keywords = [],
  shineWords = [],
  maxWordsPerLine = 4,
  lineGap = 0,
  wordGap = 14,
  textColor = "#FFFFFF",
  keywordColor = "#D4A24C",
  sweepDuration = 15,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const shineSet = useMemo(() => buildKeywordSet(shineWords), [shineWords]);
  const positionStyle = getCaptionPositionStyle(position);

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        const lines: TikTokToken[][] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
            premountFor={10}
          >
            <AbsoluteFill
              style={{
                display: "flex",
                alignItems: "center",
                ...positionStyle,
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: lineGap,
                  maxWidth,
                  width: "100%",
                }}
              >
                {lines.map((lineTokens, lineIdx) => (
                  <div
                    key={lineIdx}
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "baseline",
                      justifyContent: "center",
                      columnGap: wordGap,
                      rowGap: lineGap,
                    }}
                  >
                    {lineTokens.map((token, tokenIdx) => (
                      <LumenWord
                        key={tokenIdx}
                        token={token}
                        pageStartMs={page.startMs}
                        fontSize={fontSize}
                        isKw={isKeyword(token.text, keywordSet)}
                        hasShine={isKeyword(token.text, shineSet)}
                        textColor={textColor}
                        keywordColor={keywordColor}
                        sweepDuration={sweepDuration}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
