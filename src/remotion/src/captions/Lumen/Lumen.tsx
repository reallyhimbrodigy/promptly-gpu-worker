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
import { MAX_ENTRANCE_MS } from "../shared/fadeTiming";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle, CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";
import { buildKeywordSet, isKeyword } from "../shared/keywords";
import {
  LEGIBILITY_ANCHOR_LAYERS,
  KEYWORD_CONTRAST_LAYERS,
  keywordContrastShadow,
} from "../shared/legibility";

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
  bandLuma?: number;
  fitFloored?: boolean;
}> = ({
  token,
  pageStartMs,
  fontSize,
  isKw,
  hasShine,
  textColor,
  keywordColor,
  sweepDuration,
  bandLuma,
  fitFloored,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const activateFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const elapsed = frame - activateFrame;
  const hasAppeared = elapsed >= 0;

  // WS2 universal fast cap: the scale spring settles within MAX_ENTRANCE_MS (was
  // an unbounded damping:200 spring ≈ 1s — the slowest caption entrance).
  const entranceSpring = hasAppeared
    ? spring({ fps, frame: elapsed, config: { damping: 200 },
               durationInFrames: Math.max(1, msToFrames(MAX_ENTRANCE_MS, fps)) })
    : 0;

  // Scale: 0.95 -> 1
  const scale = interpolate(entranceSpring, [0, 1], [0.95, 1], {
    extrapolateRight: "clamp",
  });

  // WS2 fast-but-present (Zac 2026-07-12, overriding the identity-exemption):
  // opacity resolves quickly so the word lands ON the beat — was the slow
  // overdamped spring, which faded in well after the word was spoken. The soft
  // 0.95→1 scale stays (Lumen's character); only the fade is made fast.
  const fastOpacity = hasAppeared
    ? interpolate(elapsed, [0, Math.max(2, Math.round(fps * 0.06))], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

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
    // F4 last resort: below the fit floor, char-break instead of overflow.
    ...(fitFloored ? CHARWRAP_FALLBACK_STYLE : {}),
  };

  // Sweep clip: angled white strip that moves left→right
  const w = 15;
  const skew = 20;
  const p = sweepPosition;
  const showSweep = hasShine && hasAppeared && p > -w - skew && p < 100 + w + skew;
  const polyClip = `polygon(${p - w}% ${-skew}%, ${p + w}% ${-skew - 10}%, ${p + w + skew}% ${100 + 10}%, ${p - w + skew}% ${100 + skew}%)`;

  // Diffused shadow for legibility — the shared floor anchor (tight
  // near-glyph layers) first, then Lumen's own wide diffusion. Still no
  // outlines — the anchor is the shadow equivalent of a soft 1px edge.
  const diffusedShadow = [
    ...LEGIBILITY_ANCHOR_LAYERS,
    "0 0 12px rgba(0,0,0,0.7)",
    "0 0 30px rgba(0,0,0,0.4)",
    "0 0 50px rgba(0,0,0,0.2)",
    "1px 2px 5px rgba(0,0,0,0.4)",
  ];

  // B3 (directive #11): Lumen's amber carries a PERMANENT dark stroke floor —
  // D3 measured the bare amber at 1.22–1.32:1 against warm surfaces — plus the
  // shared auto step-up when the measured band luma converges with the amber.
  const kwContrast = [
    ...KEYWORD_CONTRAST_LAYERS,
    ...keywordContrastShadow(keywordColor, bandLuma),
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
        opacity: fastOpacity,
        transform: `scale(${scale})`,
        transformOrigin: "center bottom",
        textShadow: hasAppeared
          ? isKw
            ? [...kwContrast, ...diffusedShadow, ...kwGlow].join(", ")
            : diffusedShadow.join(", ")
          : "none",
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
  bandLuma = undefined,
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

        // F4 width-fit guarantee: rows flex-wrap between words; the risk is
        // a single word at its multiplier (shine x1.6 / keyword x1.3). The
        // real box is the 200px-inset safe rect (680), not maxWidth.
        const fit = fitScale(
          page.tokens.map((t) => {
            const kw = isKeyword(t.text, keywordSet);
            const shine = isKeyword(t.text, shineSet);
            return {
              parts: [
                {
                  text: t.text,
                  fontSize: shine ? fontSize * 1.6 : kw ? fontSize * 1.3 : fontSize,
                  font: kw
                    ? {
                        fontFamily: CAPTION_FONTS.playfairDisplay,
                        fontWeight: 400,
                        letterSpacingEm: -0.02,
                      }
                    : {
                        fontFamily: CAPTION_FONTS.montserrat,
                        fontWeight: 600,
                        letterSpacingEm: 0.01,
                      },
                },
              ],
            };
          }),
          Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
          "Lumen",
        );

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
                        fontSize={fontSize * fit.scale}
                        isKw={isKeyword(token.text, keywordSet)}
                        hasShine={isKeyword(token.text, shineSet)}
                        textColor={textColor}
                        keywordColor={keywordColor}
                        sweepDuration={sweepDuration}
                        bandLuma={bandLuma}
                        fitFloored={fit.floored}
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
