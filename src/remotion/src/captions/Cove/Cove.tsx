import React, { useMemo } from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { CoveProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { CAPTION_PADDING } from "../shared/captionPosition";

export const Cove: React.FC<CoveProps> = ({
  pages,
  fontSize = 76,
  position = "bottom",
  boxedWords = [],
  boxPaddingX = 14,
  boxPaddingY = 8,
  maxWordsPerLine = 4,
  lineGap = 14,
  wordGap = 14,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const currentTimeMs = (frame / fps) * 1000;

  const boxedSet = useMemo(
    () => new Set(boxedWords.map((w) => w.toLowerCase())),
    [boxedWords],
  );

  const maxWidth = width * 0.85;

  let positionStyles: React.CSSProperties;
  switch (position) {
    case "top":
      positionStyles = {
        position: "absolute",
        left: CAPTION_PADDING.sides,
        top: CAPTION_PADDING.top,
      };
      break;
    case "center":
      positionStyles = {
        position: "absolute",
        left: CAPTION_PADDING.sides,
        top: "50%",
        transform: "translateY(-50%)",
      };
      break;
    case "bottom":
    default:
      positionStyles = {
        position: "absolute",
        left: CAPTION_PADDING.sidesSafe,
        right: CAPTION_PADDING.sidesSafe,
        bottom: CAPTION_PADDING.bottomSafe,
        display: "flex",
        justifyContent: "center",
      };
      break;
  }

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        const endFrame = startFrame + durationFrames;
        // 1 frame (~17ms at 60fps) — captions snap on/off with the spoken
        // word; single-frame is enough to avoid a hard pop.
        const fadeFrames = 1;
        const fadeIn = interpolate(
          frame,
          [startFrame, startFrame + fadeFrames],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        const fadeOut = interpolate(
          frame,
          [endFrame - fadeFrames, endFrame],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        const pageOpacity = fadeIn * fadeOut;

        const lines: typeof page.tokens[] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <AbsoluteFill style={{ opacity: pageOpacity }}>
              <div style={{ ...positionStyles, maxWidth }}>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: lineGap,
                    position: "relative",
                  }}
                >
                  {lines.map((lineTokens, lineIdx) => {
                    return (
                      <div
                        key={lineIdx}
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          alignItems: "baseline",
                          columnGap: wordGap,
                          rowGap: lineGap,
                          position: "relative",
                          zIndex: lineIdx + 1,
                        }}
                      >
                        {lineTokens.map((token, tokenIdx) => {
                          const isSpecial = boxedSet.has(
                            token.text.toLowerCase(),
                          );
                          const isSpoken =
                            currentTimeMs >= token.fromMs;

                          const color = !isSpoken
                            ? "transparent"
                            : isSpecial
                              ? "#F0E8DD"
                              : "#FFFFFF";

                          return (
                            <span
                              key={tokenIdx}
                              style={{
                                fontFamily: isSpecial
                                  ? CAPTION_FONTS.playfairDisplay
                                  : CAPTION_FONTS.montserrat,
                                fontSize: isSpecial
                                  ? fontSize * 1.8
                                  : fontSize,
                                fontWeight: isSpecial ? 400 : 700,
                                fontStyle: isSpecial
                                  ? "italic"
                                  : "normal",
                                letterSpacing: isSpecial
                                  ? "-0.02em"
                                  : "normal",
                                color,
                                lineHeight: isSpecial ? 0.8 : 1,
                                whiteSpace: "nowrap",
                                display: "inline-block",
                                position: "relative",
                                padding: isSpecial
                                  ? `${boxPaddingY}px ${boxPaddingX}px`
                                  : undefined,
                                textShadow: !isSpoken
                                  ? "none"
                                  : isSpecial
                                    ? "0 0 12px rgba(255,255,255,0.7), 0 0 28px rgba(255,245,230,0.4), 0 0 50px rgba(255,240,220,0.2), 0 -20px 30px rgba(0,0,0,0.45), 0 -12px 20px rgba(0,0,0,0.35), 0 -6px 10px rgba(0,0,0,0.25), 0 0 6px rgba(0,0,0,0.15)"
                                    : "0 2px 6px rgba(0,0,0,0.55), 0 0 2px rgba(0,0,0,0.85)",
                                // Universal stroke for guaranteed readability over any background.
                                WebkitTextStroke: isSpoken ? "0.75px rgba(0,0,0,0.65)" : undefined,
                              }}
                            >
                              {/* Word-shaped blurred shadow biased above */}
                              {!isSpecial && isSpoken && (
                                <span
                                  aria-hidden="true"
                                  style={{
                                    position: "absolute",
                                    top: isSpecial ? "-30px" : "-20px",
                                    left: 0,
                                    right: 0,
                                    fontFamily: isSpecial ? CAPTION_FONTS.playfairDisplay : CAPTION_FONTS.montserrat,
                                    fontSize: isSpecial ? fontSize * 1.8 : fontSize,
                                    fontWeight: isSpecial ? 400 : 700,
                                    fontStyle: isSpecial ? "italic" : "normal",
                                    letterSpacing: isSpecial ? "-0.02em" : "normal",
                                    lineHeight: isSpecial ? 0.8 : 1,
                                    color: "rgba(0,0,0,0.6)",
                                    filter: "blur(18px)",
                                    clipPath: "none",
                                    pointerEvents: "none",
                                    zIndex: -1,
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {token.text}
                                </span>
                              )}
                              {isSpecial && isSpoken && (
                                <span
                                  style={{
                                    position: "absolute",
                                    inset: "-18px -22px",
                                    borderRadius: "50%",
                                    background:
                                      "radial-gradient(ellipse at center, rgba(255,245,230,0.12) 0%, rgba(255,245,230,0) 70%)",
                                    pointerEvents: "none",
                                    zIndex: -1,
                                  }}
                                />
                              )}
                              {token.text}
                            </span>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
