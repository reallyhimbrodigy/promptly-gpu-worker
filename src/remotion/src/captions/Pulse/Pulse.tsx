import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { PulseProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

/* ─── Single line renderer ─── */

const PulseLine: React.FC<{
  tokens: { text: string }[];
  keywordSet: Set<string>;
  textColor: string;
  keywordColor: string;
  fontSize: number;
  opacity: number;
  dimmed: boolean;
}> = ({ tokens, keywordSet, textColor, keywordColor, fontSize, opacity, dimmed }) => {
  const dimColor = "#BBBBBB";

  return (
    <div
      style={{
        opacity,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "4px 12px",
        lineHeight: 1.1,
      }}
    >
      {tokens.map((token, idx) => {
        const isKw = isKeyword(token.text, keywordSet);
        const color = dimmed ? dimColor : isKw ? keywordColor : textColor;
        return (
          <span
            key={idx}
            style={{
              fontFamily: CAPTION_FONTS.dmSans,
              fontWeight: 700,
              fontSize: isKw ? fontSize * 1.25 : fontSize,
              color,
              textTransform: "none",
              letterSpacing: "-0.02em",
              textShadow: [
                // Diffused background shadow (all directions)
                "0 0 12px rgba(0,0,0,0.7)",
                "0 0 30px rgba(0,0,0,0.4)",
                "0 0 50px rgba(0,0,0,0.2)",
                // Existing drop shadow
                "1px 2px 5px rgba(0,0,0,0.4)",
                // Keyword glow (only for active keywords)
                ...(isKw && !dimmed
                  ? [
                      `0 0 10px ${keywordColor}80`,
                      `0 0 20px ${keywordColor}40`,
                      `0 0 40px ${keywordColor}25`,
                    ]
                  : []),
              ].join(", "),
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

/* ─── Main component ─── */

export const Pulse: React.FC<PulseProps> = ({
  pages,
  fontSize = 80,
  position = "bottom",
  keywords = [],
  textColor = "#FFFFFF",
  keywordColor = "#00BFFF",
  fadeDurationFrames = 3,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position);

  // Find latest page that has started = active line
  let activeIdx = -1;
  for (let i = pages.length - 1; i >= 0; i--) {
    if (frame >= msToFrames(pages[i].startMs, fps)) {
      activeIdx = i;
      break;
    }
  }

  if (activeIdx < 0) return null;

  // Group pages into pairs — no text ever repeats across screens
  const pairIdx = Math.floor(activeIdx / 2);
  const isFirstInPair = activeIdx % 2 === 0;
  const slot1PageIdx = pairIdx * 2;
  const slot2PageIdx = pairIdx * 2 + 1;
  const hasSlot2 = !isFirstInPair && slot2PageIdx < pages.length;

  const activeStart = msToFrames(pages[activeIdx].startMs, fps);

  const slot1Start = msToFrames(pages[slot1PageIdx].startMs, fps);
  let slot1Opacity = interpolate(
    frame,
    [slot1Start, slot1Start + fadeDurationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  let slot2Opacity = 0;
  if (hasSlot2) {
    slot2Opacity = interpolate(
      frame,
      [activeStart, activeStart + fadeDurationFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }

  const lastVisibleIdx = hasSlot2 ? slot2PageIdx : slot1PageIdx;
  if (lastVisibleIdx === pages.length - 1) {
    const activeEnd = msToFrames(
      pages[lastVisibleIdx].startMs + pages[lastVisibleIdx].durationMs,
      fps,
    );
    const fadeOut = interpolate(
      frame,
      [activeEnd - fadeDurationFrames, activeEnd],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
    if (hasSlot2) {
      slot2Opacity *= fadeOut;
    } else {
      slot1Opacity *= fadeOut;
    }
  }

  const t = frame / fps;
  const floatY = Math.sin(t * 1.2) * 14 + Math.sin(t * 1.8) * 7;

  return (
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
          width: "100%",
          maxWidth,
          gap: Math.round(fontSize * 0.25),
          transform: `translateY(${floatY.toFixed(2)}px)`,
          willChange: "transform",
        }}
      >
        <PulseLine
          tokens={pages[slot1PageIdx].tokens}
          keywordSet={keywordSet}
          textColor={textColor}
          keywordColor={keywordColor}
          fontSize={fontSize}
          opacity={slot1Opacity}
          dimmed={hasSlot2}
        />
        {hasSlot2 && (
          <PulseLine
            tokens={pages[slot2PageIdx].tokens}
            keywordSet={keywordSet}
            textColor={textColor}
            keywordColor={keywordColor}
            fontSize={fontSize}
            opacity={slot2Opacity}
            dimmed={false}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
