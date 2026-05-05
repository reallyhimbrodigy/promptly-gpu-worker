import React from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { PrimeProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { CAPTION_PADDING } from "../shared/captionPosition";
import { leadInElapsed } from "../shared/leadIn";

// ---------------------------------------------------------------------------
// PrimeWord — single word with staggered entrance
// ---------------------------------------------------------------------------

const PrimeWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  wordIndex: number;
  isLine2: boolean;
  isSpecial: boolean;
  line1Color: string;
  line2Color: string;
  line1FontSize: number;
  line2FontSize: number;
  line1FontWeight: number | string;
  line2FontWeight: number | string;
  fontFamily: string;
  specialFontFamily: string;
  specialColor: string;
  letterSpacing: string;
  textShadow: string;
}> = ({
  token,
  pageStartMs,
  wordIndex,
  isLine2,
  isSpecial,
  line1Color,
  line2Color,
  line1FontSize,
  line2FontSize,
  line1FontWeight,
  line2FontWeight,
  fontFamily,
  specialFontFamily,
  specialColor,
  letterSpacing,
  textShadow,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring entrance per word — lead-in matches the spring's 0.25s duration
  // so the slide-up settles AT the spoken moment, not 0.25s after.
  const activateFrame = Math.round(((token.fromMs - pageStartMs) / 1000) * fps);
  const springFrames = Math.round(fps * 0.25);
  const wordSpring = spring({
    frame: leadInElapsed(frame, activateFrame, springFrames),
    fps,
    config: { damping: 200 },
    durationInFrames: springFrames,
  });

  const slideY = interpolate(wordSpring, [0, 1], [20, 0]);
  const wordOpacity = interpolate(wordSpring, [0, 1], [0, 1]);

  const color = isSpecial ? specialColor : line1Color;
  const fontSize = isSpecial ? line2FontSize : (isLine2 ? line2FontSize : line1FontSize);
  const fontWeightVal = isLine2 ? line2FontWeight : line1FontWeight;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: isSpecial ? specialFontFamily : fontFamily,
        fontSize,
        fontWeight: isSpecial ? 600 : fontWeightVal,
        fontStyle: isSpecial ? "italic" : "normal",
        color,
        letterSpacing,
        lineHeight: 1.1,
        textShadow,
        // Universal stroke for guaranteed readability over any background.
        WebkitTextStroke: "0.75px rgba(0,0,0,0.6)",
        textTransform: "lowercase",
        whiteSpace: "nowrap",
        transform: `translateY(${slideY}px)`,
        opacity: wordOpacity,
        marginRight: 12,
      }}
    >
      {token.text}
    </span>
  );
};

// ---------------------------------------------------------------------------
// PrimePage — splits tokens into lines, renders word by word
// ---------------------------------------------------------------------------

const PrimePage: React.FC<{
  page: TikTokPage;
  maxWordsPerLine: number;
  lineGap: number;
  specialWords: string[];
  line1Color: string;
  line2Color: string;
  line1FontSize: number;
  line2FontSize: number;
  line1FontWeight: number | string;
  line2FontWeight: number | string;
  fontFamily: string;
  specialFontFamily: string;
  specialColor: string;
  letterSpacing: string;
  textShadow: string;
}> = ({
  page,
  maxWordsPerLine,
  lineGap,
  specialWords,
  ...wordProps
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isSpecial = (text: string) =>
    specialWords.some((w) => w.toLowerCase() === text.toLowerCase());

  // Split tokens into lines — special words get their own line
  const lines: { tokens: TikTokToken[]; hasSpecial: boolean }[] = [];
  let buffer: TikTokToken[] = [];

  for (const token of page.tokens) {
    if (isSpecial(token.text)) {
      if (buffer.length > 0) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
      lines.push({ tokens: [token], hasSpecial: true });
    } else {
      buffer.push(token);
      if (buffer.length >= maxWordsPerLine) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
    }
  }
  if (buffer.length > 0) {
    lines.push({ tokens: buffer, hasSpecial: false });
  }

  // Hard cut on/off — no fade. Captions snap to the spoken word.
  let globalWordIdx = 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      {(() => {
        let normalLineCount = 0;
        return lines.map((line, lineIdx) => {
        const isLine2 = !line.hasSpecial && normalLineCount++ >= 1;
        return (
          <div
            key={lineIdx}
            style={{
              display: "flex",
              alignItems: "baseline",
              marginTop: lineIdx > 0 ? lineGap : 0,
              ...(line.hasSpecial ? { justifyContent: "center" } : {}),
            }}
          >
            {line.tokens.map((token, idx) => {
              const wi = globalWordIdx++;
              return (
                <PrimeWord
                  key={idx}
                  token={token}
                  pageStartMs={page.startMs}
                  wordIndex={wi}
                  isLine2={isLine2}
                  isSpecial={line.hasSpecial}
                  {...wordProps}
                  line2FontSize={line.hasSpecial ? wordProps.line2FontSize * 2 : wordProps.line2FontSize}
                  line1FontSize={line.hasSpecial ? wordProps.line1FontSize * 2 : wordProps.line1FontSize}
                />
              );
            })}
          </div>
        );
      });
      })()}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Prime — main exported component
// ---------------------------------------------------------------------------

export const Prime: React.FC<PrimeProps> = ({
  pages,
  fontFamily = CAPTION_FONTS.inter,
  position = "bottom",
  line1Color = "#FFFFFF",
  line2Color = "#3BA5FF",
  line1FontSize = 52,
  line2FontSize = 66,
  line1FontWeight = 600,
  line2FontWeight = 800,
  maxWordsPerLine = 3,
  letterSpacing = "0.01em",
  lineGap = -30,
  textShadow = "0 2px 8px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.4)",
  specialWords = [],
  specialFontFamily = CAPTION_FONTS.playfairDisplay,
  specialColor = "#5ED4E8",
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
            premountFor={10}
          >
            <div
              style={{
                position: "absolute",
                left: "50%",
                maxWidth,
                ...(position === "top"
                  ? { top: CAPTION_PADDING.top, transform: "translateX(-50%)" }
                  : position === "center"
                    ? { top: "50%", transform: "translate(-50%, -50%)" }
                    : { bottom: CAPTION_PADDING.bottomSafe, transform: "translateX(-50%)" }
                ),
              }}
            >
              <PrimePage
                page={page}
                maxWordsPerLine={maxWordsPerLine}
                lineGap={lineGap}
                specialWords={specialWords}
                line1Color={line1Color}
                line2Color={line2Color}
                line1FontSize={line1FontSize}
                line2FontSize={line2FontSize}
                line1FontWeight={line1FontWeight}
                line2FontWeight={line2FontWeight}
                fontFamily={fontFamily}
                specialFontFamily={specialFontFamily}
                specialColor={specialColor}
                letterSpacing={letterSpacing}
                textShadow={textShadow}
              />
            </div>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
