import React, { useMemo } from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import type { CoveProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";

export const Cove: React.FC<CoveProps> = ({
  pages,
  fontSize = 76,
  position = "bottom",
  anchor,
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

  // SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): a per-page anchor pins the
  // block top at `topPx` (centred, safe-rect inset) — same box geometry as the
  // "bottom" case but top-anchored to the speaker head. Absent → the switch below
  // runs exactly as before (byte-identical fixed-slot behavior).
  const anchored = !!anchor;
  let positionStyles: React.CSSProperties;
  if (anchor) {
    positionStyles = {
      position: "absolute",
      left: CAPTION_PADDING.sidesSafe,
      right: CAPTION_PADDING.sidesSafe,
      top: anchor.topPx,
      display: "flex",
      justifyContent: "center",
    };
  } else
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

        const lines: typeof page.tokens[] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        // F4 width-fit guarantee: rows flex-wrap between words, so the
        // overflow unit is one word — the ×1.8 Playfair boxed words are the
        // risk. Uniform page scale; below the floor, char-break fallback.
        // The box the style actually occupies depends on position: bottom
        // is inset 200px both sides; top/center are left-anchored at 80.
        const fitBox =
          position === "bottom" || anchored
            ? width - 2 * CAPTION_PADDING.sidesSafe
            : Math.min(maxWidth, width - 2 * CAPTION_PADDING.sides);
        const fit = fitScale(
          page.tokens.map((t) => {
            const boxed = boxedSet.has(t.text.toLowerCase());
            return {
              parts: [
                {
                  text: t.text,
                  fontSize: boxed ? fontSize * 1.8 : fontSize,
                  font: boxed
                    ? {
                        fontFamily: CAPTION_FONTS.playfairDisplay,
                        fontWeight: 400,
                        letterSpacingEm: -0.02,
                      }
                    : { fontFamily: CAPTION_FONTS.montserrat, fontWeight: 700 },
                },
              ],
              extraPx: boxed ? 2 * boxPaddingX : 0,
            };
          }),
          fitBox,
          "Cove",
        );

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <AbsoluteFill>
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

                          // WS2 fast-but-present (Zac 2026-07-12, overriding the
                          // identity-exemption): the word fades in fast (~60ms)
                          // instead of a hard cut, so it reads as landing ON the
                          // beat rather than popping. Present, not slow.
                          // CRISP ENTRANCE (Zac 2026-07-13): full opacity the instant
                          // the word is spoken — no 60ms ramp (the ghost). Cove's
                          // serif/glow character lives in its ongoing look, not a fade.
                          const wordOpacity = isSpoken ? 1 : 0;

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
                                fontSize:
                                  (isSpecial ? fontSize * 1.8 : fontSize) *
                                  fit.scale,
                                fontWeight: isSpecial ? 400 : 700,
                                fontStyle: isSpecial
                                  ? "italic"
                                  : "normal",
                                letterSpacing: isSpecial
                                  ? "-0.02em"
                                  : "normal",
                                color,
                                opacity: wordOpacity,
                                lineHeight: isSpecial ? 0.8 : 1,
                                whiteSpace: "nowrap",
                                display: "inline-block",
                                position: "relative",
                                ...(fit.floored
                                  ? CHARWRAP_FALLBACK_STYLE
                                  : {}),
                                padding: isSpecial
                                  ? `${boxPaddingY}px ${boxPaddingX}px`
                                  : undefined,
                                textShadow: !isSpoken
                                  ? "none"
                                  : isSpecial
                                    ? "0 0 12px rgba(255,255,255,0.7), 0 0 28px rgba(255,245,230,0.4), 0 0 50px rgba(255,240,220,0.2), 0 -20px 30px rgba(0,0,0,0.45), 0 -12px 20px rgba(0,0,0,0.35), 0 -6px 10px rgba(0,0,0,0.25), 0 0 6px rgba(0,0,0,0.15)"
                                    : "none",
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
                                    fontSize: (isSpecial ? fontSize * 1.8 : fontSize) * fit.scale,
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
