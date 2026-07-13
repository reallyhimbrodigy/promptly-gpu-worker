import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { PulseProps } from "./types";
import { msToFrames } from "../shared/timing";
import { boundedFade } from "../shared/fadeTiming";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle, CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";
import { buildKeywordSet, isKeyword } from "../shared/keywords";
import { LEGIBILITY_ANCHOR_LAYERS } from "../shared/legibility";

/* ─── Single line renderer ─── */

const PulseLine: React.FC<{
  tokens: { text: string }[];
  keywordSet: Set<string>;
  textColor: string;
  keywordColor: string;
  fontSize: number;
  opacity: number;
  dimmed: boolean;
  fitFloored?: boolean;
}> = ({ tokens, keywordSet, textColor, keywordColor, fontSize, opacity, dimmed, fitFloored }) => {
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
                // Shared legibility floor — tight near-glyph anchor.
                ...LEGIBILITY_ANCHOR_LAYERS,
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
              // F4 last resort: below the fit floor, char-break.
              ...(fitFloored ? CHARWRAP_FALLBACK_STYLE : {}),
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
  keywordColor = "#FF6B4A", // directive #12: recolored off the blue family (was #00BFFF); Prime owns blue
  fadeDurationFrames = 5,
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

  // CRISP ENTRANCE (Zac 2026-07-13): each paired slot appears at FULL opacity the
  // instant it starts — no 0→1 ramp (the ghost). Pulse's rhythm lives in the paired
  // stack + the top-line dim, not a fade-up; the fade-OUT below stays.
  const slot1Start = msToFrames(pages[slot1PageIdx].startMs, fps);
  let slot1Opacity = frame >= slot1Start ? 1 : 0;

  let slot2Opacity = 0;
  if (hasSlot2) {
    slot2Opacity = frame >= activeStart ? 1 : 0;
  }

  const lastVisibleIdx = hasSlot2 ? slot2PageIdx : slot1PageIdx;
  if (lastVisibleIdx === pages.length - 1) {
    const activeEnd = msToFrames(
      pages[lastVisibleIdx].startMs + pages[lastVisibleIdx].durationMs,
      fps,
    );
    const lastFadeF = boundedFade(fadeDurationFrames, msToFrames(pages[lastVisibleIdx].durationMs, fps));
    const fadeOut = interpolate(
      frame,
      [activeEnd - lastFadeF, activeEnd],
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

  // F4 width-fit guarantee: both visible pages share one uniform scale so
  // the pair reads as one block; rows flex-wrap, so the overflow unit is a
  // single word (keywords at x1.25). Real box = the 200px-inset safe rect.
  // Both pages of the pair inform the scale from the FIRST frame — gating
  // on slot-2 activation made the visible line pop smaller mid-display the
  // moment a wide second page arrived (final-wave review finding).
  const fitTokens = slot2PageIdx < pages.length
    ? [...pages[slot1PageIdx].tokens, ...pages[slot2PageIdx].tokens]
    : pages[slot1PageIdx].tokens;
  const fit = fitScale(
    fitTokens.map((tok) => ({
      parts: [
        {
          text: tok.text,
          fontSize: isKeyword(tok.text, keywordSet) ? fontSize * 1.25 : fontSize,
          font: {
            fontFamily: CAPTION_FONTS.dmSans,
            fontWeight: 700,
            letterSpacingEm: -0.02,
          },
        },
      ],
    })),
    Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
    "Pulse",
  );
  const fittedFontSize = fontSize * fit.scale;

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
          fontSize={fittedFontSize}
          opacity={slot1Opacity}
          dimmed={hasSlot2}
          fitFloored={fit.floored}
        />
        {hasSlot2 && (
          <PulseLine
            tokens={pages[slot2PageIdx].tokens}
            keywordSet={keywordSet}
            textColor={textColor}
            keywordColor={keywordColor}
            fontSize={fittedFontSize}
            opacity={slot2Opacity}
            dimmed={false}
            fitFloored={fit.floored}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
