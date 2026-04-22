import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import type { IlluminateProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

const SHADOW = [
  "0 0 10px rgba(0,0,0,0.7)",
  "0 0 30px rgba(0,0,0,0.4)",
  "1px 2px 4px rgba(0,0,0,0.5)",
].join(", ");

/**
 * Illuminate — a diagonal light sweep reveals each word from dark to lit.
 * Words start dim, a bright gradient mask sweeps across left-to-right,
 * lighting up the text. Keywords keep a warm lingering glow after the
 * sweep passes. Cinematic spotlight feel.
 */

const IlluminateWord: React.FC<{
  text: string;
  fromMs: number;
  pageStartMs: number;
  isKw: boolean;
  fontSize: number;
  textColor: string;
  glowColor: string;
}> = ({ text, fromMs, pageStartMs, isKw, fontSize, textColor, glowColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const wordStart = msToFrames(fromMs - pageStartMs, fps);
  const localFrame = frame - wordStart;

  // Sweep progress: the light beam crosses this word
  const sweep = interpolate(localFrame, [0, 7], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Before sweep: dim. After sweep: fully lit.
  const brightness = interpolate(sweep, [0, 0.4, 1], [0.2, 0.6, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Gradient mask position — sweeps from left to right across the word
  const maskPos = interpolate(sweep, [0, 1], [-50, 150], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Keyword glow: fades in after sweep completes
  const glowOpacity = isKw
    ? interpolate(localFrame, [5, 10], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const kwGlow = glowOpacity > 0
    ? `0 0 20px ${glowColor}${Math.round(glowOpacity * 60).toString(16).padStart(2, "0")}, 0 0 40px ${glowColor}${Math.round(glowOpacity * 30).toString(16).padStart(2, "0")}`
    : "";

  return (
    <span
      style={{
        fontFamily: CAPTION_FONTS.playfairDisplay,
        fontWeight: isKw ? 700 : 400,
        fontStyle: isKw ? "italic" : "normal",
        fontSize: isKw ? fontSize * 1.2 : fontSize,
        color: textColor,
        letterSpacing: "-0.01em",
        textShadow: `${SHADOW}${kwGlow ? `, ${kwGlow}` : ""}`,
        opacity: brightness,
        WebkitMaskImage: `linear-gradient(110deg, black ${maskPos - 30}%, rgba(0,0,0,0.3) ${maskPos}%, black ${maskPos + 30}%)`,
        maskImage: `linear-gradient(110deg, black ${maskPos - 30}%, rgba(0,0,0,0.3) ${maskPos}%, black ${maskPos + 30}%)`,
        display: "inline-block",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
};

const IlluminatePage: React.FC<{
  tokens: { text: string; fromMs: number }[];
  pageStartMs: number;
  keywordSet: Set<string>;
  fontSize: number;
  textColor: string;
  glowColor: string;
  maxWordsPerLine: number;
  maxWidth: number;
}> = ({ tokens, pageStartMs, keywordSet, fontSize, textColor, glowColor, maxWordsPerLine, maxWidth }) => {
  // Split into lines
  const lines: { text: string; fromMs: number }[][] = [];
  for (let i = 0; i < tokens.length; i += maxWordsPerLine) {
    lines.push(tokens.slice(i, i + maxWordsPerLine));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, maxWidth }}>
      {lines.map((line, li) => (
        <div key={li} style={{ display: "flex", gap: 16, justifyContent: "center" }}>
          {line.map((token, wi) => (
            <IlluminateWord
              key={wi}
              text={token.text}
              fromMs={token.fromMs}
              pageStartMs={pageStartMs}
              isKw={isKeyword(token.text, keywordSet)}
              fontSize={fontSize}
              textColor={textColor}
              glowColor={glowColor}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

export const Illuminate: React.FC<IlluminateProps> = ({
  pages,
  fontSize = 58,
  position = "bottom",
  keywords = [],
  textColor = "#FFFFFF",
  glowColor = "#D4A853",
  maxWordsPerLine = 3,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position);

  return (
    <AbsoluteFill>
      {pages.map((page, pi) => {
        const startFrame = msToFrames(page.startMs, fps);
        const dur = msToFrames(page.durationMs, fps);
        if (dur <= 0) return null;
        return (
          <Sequence key={pi} from={startFrame} durationInFrames={dur}>
            <AbsoluteFill style={{ display: "flex", alignItems: "center", ...positionStyle }}>
              <IlluminatePage tokens={page.tokens} pageStartMs={page.startMs} keywordSet={keywordSet} fontSize={fontSize} textColor={textColor} glowColor={glowColor} maxWordsPerLine={maxWordsPerLine} maxWidth={maxWidth} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
