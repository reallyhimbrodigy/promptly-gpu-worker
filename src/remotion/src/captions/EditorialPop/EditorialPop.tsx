import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { EditorialPopProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

/* ─── Constants ─── */

const SHADOW = [
  "0 0 12px rgba(0,0,0,0.7)",
  "0 0 30px rgba(0,0,0,0.4)",
  "0 0 50px rgba(0,0,0,0.2)",
  "1px 2px 5px rgba(0,0,0,0.4)",
].join(", ");

/* ─── Single line renderer ─── */

const EditorialPopLine: React.FC<{
  tokens: { text: string }[];
  keywordSet: Set<string>;
  fontSize: number;
  keywordScale: number;
  textColor: string;
}> = ({ tokens, keywordSet, fontSize, keywordScale, textColor }) => {

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "nowrap",
        alignItems: "baseline",
        justifyContent: "center",
        gap: "0px 14px",
      }}
    >
      {tokens.map((token, idx) => {
        const isKw = isKeyword(token.text, keywordSet);
        return (
          <span
            key={idx}
            style={{
              fontFamily: CAPTION_FONTS.playfairDisplay,
              fontWeight: isKw ? 700 : 400,
              fontStyle: isKw ? "italic" : "normal",
              fontSize: isKw ? fontSize * keywordScale : fontSize,
              color: textColor,
              letterSpacing: "-0.02em",
              textShadow: SHADOW,
              whiteSpace: "nowrap",
            }}
          >
            {token.text}
          </span>
        );
      })}
    </div>
  );
};

/* ─── Page with 2-line stagger ─── */

const EditorialPopPage: React.FC<{
  lines: { text: string }[][];
  lineDelayMs: number;
  keywordSet: Set<string>;
  fontSize: number;
  keywordScale: number;
  textColor: string;
  maxWidth: number;
}> = ({ lines, lineDelayMs, keywordSet, fontSize, keywordScale, textColor, maxWidth }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < 0) return null;

  const line2Visible = lines.length > 1 && frame >= msToFrames(lineDelayMs, fps);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: "100%",
        maxWidth,
        gap: Math.round(fontSize * 0.05),
      }}
    >
      <EditorialPopLine
        tokens={lines[0]}
        keywordSet={keywordSet}
        fontSize={fontSize}
        keywordScale={keywordScale}
        textColor={textColor}
      />
      {line2Visible && (
        <EditorialPopLine
          tokens={lines[1]}
          keywordSet={keywordSet}
          fontSize={fontSize}
          keywordScale={keywordScale}
          textColor={textColor}
        />
      )}
    </div>
  );
};

/* ─── Main component ─── */

export const EditorialPop: React.FC<EditorialPopProps> = ({
  pages,
  fontSize = 62,
  position = "bottom",
  keywords = [],
  keywordScale = 1.35,
  textColor = "#FFFFFF",
  maxWordsPerLine = 3,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position);

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        // Split tokens into lines
        const lines: { text: string }[][] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        // Line 2 delay: use the first token's timing from line 2, relative to page start
        const line2DelayMs = lines.length > 1
          ? (page.tokens[maxWordsPerLine]?.fromMs ?? page.startMs) - page.startMs
          : 0;

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
              <EditorialPopPage
                lines={lines}
                lineDelayMs={line2DelayMs}
                keywordSet={keywordSet}
                fontSize={fontSize}
                keywordScale={keywordScale}
                textColor={textColor}
                maxWidth={maxWidth}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
