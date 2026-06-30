import React, { useMemo } from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { EditorialQuoteProps } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const clamp = (x: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(hi, x));

const SIDE_INSET = 92;
const TEXT_MAX_WIDTH = 1080 - 2 * SIDE_INSET; // 896
const CHAR_RATIO = 0.47; // italic serif advance estimate

export const EditorialQuote: React.FC<EditorialQuoteProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  text,
  author,
  role,
  accentColor = "#FFD60A",
  textColor = "#FFFFFF",
  authorColor = "rgba(255,255,255,0.7)",
  fontKey = "playfairDisplay",
  fontSize = 108,
  maxWordsPerLine = 3,
  italic = true,
  lineStagger = 8,
  showQuoteMark = true,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 40, defaultExitFrames: 26 },
  );

  const words = useMemo(
    () => text.trim().split(/\s+/).filter(Boolean),
    [text],
  );

  if (!visible) return null;
  if (words.length === 0) return null;

  // Chunk into lines.
  const m = Math.max(1, maxWordsPerLine);
  const lines: string[] = [];
  for (let i = 0; i < words.length; i += m) {
    lines.push(words.slice(i, i + m).join(" "));
  }

  // Deterministic font-fit on the longest line (no DOM measurement).
  let maxChars = 0;
  for (const l of lines) maxChars = Math.max(maxChars, l.length);
  const widthFit = TEXT_MAX_WIDTH / (Math.max(1, maxChars) * CHAR_RATIO);
  const finalFontSize = clamp(Math.min(fontSize, widthFit), 56, 150);

  // Left accent bar draws down first.
  const barScaleY = interpolate(localFrame, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  // Opening quote mark pops in with the bar.
  const quoteOpacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const quoteScale = interpolate(localFrame, [0, 16], [0.55, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  const authorStart = 10 + lines.length * lineStagger + 8;
  const authorOpacity = interpolate(
    localFrame,
    [authorStart, authorStart + 14],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const authorX = interpolate(
    localFrame,
    [authorStart, authorStart + 18],
    [-18, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeOutCubic },
  );

  // Exit: choreographed wipe-out — author fades, lines wipe away left -> right
  // (staggered top to bottom), the bar retracts up, the quote mark lifts off.
  const authorExitV = clamp(exitProgress / 0.32, 0, 1);
  const quoteExit = easeOutCubic(clamp((exitProgress - 0.04) / 0.42, 0, 1));
  const barExit = easeOutCubic(clamp((exitProgress - 0.14) / 0.5, 0, 1));

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "stretch",
            gap: 38,
          }}
        >
          {/* Left accent bar */}
          <div
            style={{
              width: 9,
              flexShrink: 0,
              borderRadius: 5,
              backgroundColor: accentColor,
              boxShadow: `0 0 20px ${accentColor}66`,
              transform: `scaleY(${(barScaleY * (1 - barExit)).toFixed(3)})`,
              transformOrigin: "top center",
            }}
          />

          {/* Quote + attribution */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
            }}
          >
            {showQuoteMark ? (
              <div
                style={{
                  fontFamily: MG_FONTS[fontKey],
                  fontSize: finalFontSize * 1.5,
                  lineHeight: 0.66,
                  fontStyle: italic ? "italic" : "normal",
                  color: accentColor,
                  marginBottom: -finalFontSize * 0.34,
                  opacity: quoteOpacity * (1 - quoteExit),
                  transform: `translateY(${(-finalFontSize * 0.3 * quoteExit).toFixed(2)}px) scale(${(quoteScale * (1 - 0.35 * quoteExit)).toFixed(3)})`,
                  transformOrigin: "left top",
                  textShadow: "0 2px 16px rgba(0,0,0,0.4)",
                }}
              >
                {"“"}
              </div>
            ) : null}

            {lines.map((line, li) => {
              const start = 10 + li * lineStagger;
              // Left-to-right wipe (clip-path reveal) + a small slide-in.
              const prog = interpolate(localFrame, [start, start + 24], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: easeOutCubic,
              });
              const slideX = interpolate(
                localFrame,
                [start, start + 22],
                [-32, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: easeOutCubic,
                },
              );
              const op = interpolate(localFrame, [start, start + 14], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              // Exit wipe: left inset grows left -> right, staggered per line.
              const lineExit = easeOutCubic(
                clamp((exitProgress - (0.06 + li * 0.1)) / 0.5, 0, 1),
              );
              const leftClip =
                lineExit > 0 ? `${(lineExit * 100).toFixed(2)}%` : "-0.06em";
              const reveal = `inset(-0.2em ${(100 - prog * 100).toFixed(2)}% -0.28em ${leftClip})`;
              const tx = slideX + lineExit * 30;
              return (
                <div
                  key={li}
                  style={{
                    fontFamily: MG_FONTS[fontKey],
                    fontSize: finalFontSize,
                    fontStyle: italic ? "italic" : "normal",
                    fontWeight: 500,
                    color: textColor,
                    lineHeight: 1.16,
                    letterSpacing: "-0.01em",
                    whiteSpace: "nowrap",
                    opacity: op,
                    transform: `translateX(${tx.toFixed(2)}px)`,
                    clipPath: reveal,
                    WebkitClipPath: reveal,
                    textShadow: "0 2px 16px rgba(0,0,0,0.5)",
                  }}
                >
                  {line}
                </div>
              );
            })}

            {author ? (
              <div
                style={{
                  marginTop: 28,
                  display: "flex",
                  flexDirection: "column",
                  opacity: authorOpacity * (1 - authorExitV),
                  transform: `translateX(${(authorX + authorExitV * 24).toFixed(2)}px)`,
                }}
              >
                <div
                  style={{
                    fontFamily: MG_FONTS.inter,
                    fontSize: Math.round(finalFontSize * 0.3),
                    fontWeight: 700,
                    color: textColor,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                  }}
                >
                  {author}
                </div>
                {role ? (
                  <div
                    style={{
                      fontFamily: MG_FONTS.inter,
                      fontSize: Math.round(finalFontSize * 0.22),
                      fontWeight: 500,
                      color: authorColor,
                      letterSpacing: "0.04em",
                      marginTop: 5,
                    }}
                  >
                    {role}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
