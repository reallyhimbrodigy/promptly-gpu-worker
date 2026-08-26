import React, { useMemo } from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { PullQuoteFontKey, PullQuoteProps } from "./types";
import { asText } from "../../shared/asText";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
const clamp = (x: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(hi, x));

const SIDE_INSET = 90;
const TOP_SAFE = 220;
const TEXT_MAX_WIDTH = 1080 - 2 * SIDE_INSET; // 900
const TEXT_MAX_HEIGHT = 1920 - 2 * TOP_SAFE; // 1480
const MIN_FONT = 64;
const MAX_FONT = 320;

const DEFAULT_TEXT_SHADOW =
  "0 2px 8px rgba(0,0,0,0.6), 0 8px 30px rgba(0,0,0,0.45), 0 0 2px rgba(0,0,0,0.5)";

const CHAR_RATIO: Record<PullQuoteFontKey, number> = {
  anton: 0.52,
  oswald: 0.55,
  inter: 0.56,
  roboto: 0.56,
  dmSerifDisplay: 0.5,
  playfairDisplay: 0.5,
};

// Unicode-aware (font census 2026-08-26): the old [^a-zA-Z0-9] strip deleted
// every non-Latin keyword to "" — silent content deletion (a Hindi keyword
// could never match its word). Strip punctuation/whitespace only.
const normalize = (w: string): string =>
  w.replace(/[^\p{L}\p{N}]/gu, "").toLocaleLowerCase();

export const PullQuote: React.FC<PullQuoteProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  text,
  keywords = [],
  textColor = "#FFFFFF",
  keywordColor,
  accentColor,
  fontKey = "anton",
  fontSize = 150,
  maxWordsPerLine = 3,
  highlightStyle = "color",
  keywordScale = 1.18,
  barColor,
  highlightTextColor = "#0A0A0A",
  align = "center",
  uppercase = true,
  wordStagger = 6,
  wordReveal = 16,
  blurIn = true,
  showQuoteMark = false,
  quoteMarkColor,
  textShadow = DEFAULT_TEXT_SHADOW,
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
    { defaultEnterFrames: 40, defaultExitFrames: 30 },
  );

  const resolvedKeywordColor = keywordColor ?? accentColor ?? "#FFD60A";
  const resolvedBarColor = barColor ?? resolvedKeywordColor;
  const resolvedQuoteColor = quoteMarkColor ?? resolvedKeywordColor;

  const keywordSet = useMemo(
    () => new Set(keywords.map(normalize)),
    [keywords],
  );

  const words = useMemo(
    () => asText(text).trim().split(/\s+/).filter(Boolean),
    [text],
  );

  if (!visible) return null;
  if (words.length === 0) return null;

  // Fail-open (render-caught 2026-08-25): an unrecognized highlightStyle
  // silently rendered keywords PLAIN — no colour, no bar, indistinguishable
  // from body words at a glance. The handler's contract is color|bar|scale;
  // anything else now degrades to "color" (some highlight, never none).
  const effStyle = highlightStyle === "bar" || highlightStyle === "scale"
    ? highlightStyle : "color";

  const isKw = (w: string): boolean => keywordSet.has(normalize(w));
  const kwCount = words.filter(isKw).length;
  const suppressSize = words.length > 0 && kwCount / words.length > 0.6;
  const effKeywordScale = suppressSize ? 1 : keywordScale;

  // Chunk into lines.
  const lines: string[][] = [];
  if (maxWordsPerLine == null) {
    lines.push(words);
  } else {
    const m = Math.max(1, maxWordsPerLine);
    for (let i = 0; i < words.length; i += m) lines.push(words.slice(i, i + m));
  }

  // User/model text routes by script + emoji tail (font census 2026-08-26);
  // computed once for the whole quote so every word carries one face.
  const quoteText = words.join(" ");
  const quoteFont = mgTextFont(quoteText, fontKey);
  const quoteMetrics = mgTextMetrics(quoteText);

  // Deterministic font-fit (no DOM measurement). CHAR_RATIO stays the latin
  // advance; non-Latin uses the census-conservative estimate.
  const ratio =
    quoteMetrics.script === "latin" ? CHAR_RATIO[fontKey] : quoteMetrics.advanceEm;
  let maxWeight = 0;
  for (const line of lines) {
    let w = 0;
    for (const word of line) w += word.length * (isKw(word) ? effKeywordScale : 1);
    w += (line.length - 1) * 0.3;
    maxWeight = Math.max(maxWeight, w);
  }
  const widthFit = (TEXT_MAX_WIDTH * 0.96) / (Math.max(1, maxWeight) * ratio);
  const heightFit = TEXT_MAX_HEIGHT / (lines.length * 1.04);
  const finalFontSize = clamp(
    Math.min(fontSize, widthFit, heightFit),
    MIN_FONT,
    MAX_FONT,
  );

  // Cap total entrance time for long lines.
  const N = words.length;
  const effStagger = Math.min(
    wordStagger,
    (74 - wordReveal) / Math.max(1, N - 1),
  );

  // Corpus law 1 (pass #7b): the payoff LINE (the last line — the isolated
  // hit: "$100K on its own beat", "big oversized 0 as its own visual beat")
  // lands at up to 2.8x support scale, fit to ~98% frame width. The panel
  // measured ours at 1.2-1.4x — the isolation move never landed.
  const lastIdx = lines.length - 1;
  const lastWeight = lines[lastIdx].reduce((acc, w2) => acc + w2.length * (isKw(w2) ? effKeywordScale : 1), 0)
    + (lines[lastIdx].length - 1) * 0.3;
  const payoffScale = lines.length > 1
    ? Math.max(1, Math.min(2.8, (TEXT_MAX_WIDTH * 0.98) / (Math.max(1, lastWeight) * ratio * finalFontSize)))
    : 1;

  const RISE = finalFontSize * 0.3;
  const BLUR0 = 12;

  // Exit (whole block): an even blur-dissolve spread across the exit window.
  const exitY = -22 * exitProgress;
  const exitScale = 1 - 0.06 * exitProgress;
  const exitBlur = 16 * exitProgress;
  const exitOpacity = interpolate(exitProgress, [0, 0.94], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Decorative opening quote mark, popping in just before the words.
  const quoteOpacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const quoteScale = interpolate(localFrame, [0, 18], [0.5, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack,
  });
  const quoteRise = interpolate(localFrame, [0, 16], [RISE * 0.5, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  const flexAlign =
    align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center";

  let gi = -1; // running global word index

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            maxWidth: TEXT_MAX_WIDTH,
            display: "flex",
            flexDirection: "column",
            alignItems: flexAlign,
            // §4 interlock: adjacent display lines tuck slightly (was +0.06em
            // of air) so ascenders/descenders interleave like a composed title
            // card. lineHeight 0.95 keeps every glyph fully legible.
            gap: -finalFontSize * 0.025,
            transform: `translateY(${exitY}px) scale(${exitScale})`,
            transformOrigin: "center",
            opacity: exitOpacity,
            filter: exitBlur > 0.05 ? `blur(${exitBlur}px)` : undefined,
          }}
        >
          {showQuoteMark ? (
            <div
              style={{
                position: "absolute",
                top: -finalFontSize * 0.62,
                left: -finalFontSize * 0.08,
                fontFamily: MG_FONTS.dmSerifDisplay,
                fontSize: finalFontSize * 1.5,
                lineHeight: 0.8,
                color: resolvedQuoteColor,
                opacity: quoteOpacity * 0.92,
                transform: `translateY(${quoteRise}px) scale(${quoteScale})`,
                transformOrigin: "left top",
                textShadow,
                zIndex: 0,
              }}
            >
              {"“"}
            </div>
          ) : null}
          {lines.map((line, li) => (
            <div
              key={li}
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "baseline",
                justifyContent: flexAlign,
                gap: finalFontSize * 0.26,
                whiteSpace: "nowrap",
                // §4 (2026-08-25): a perfectly-centred stack of straight lines
                // reads as a slide. Alternating ±1.2° per line — restraint is
                // the treatment at display sizes; the interlock below does the
                // rest. Individual rotate property (REMOTION_CONVENTIONS).
                rotate: `${((li % 2 === 0 ? -1 : 1) * 1.2).toFixed(1)}deg`,
              }}
            >
              {line.map((word, wi) => {
                gi++;
                const kw = isKw(word);
                const start = effStagger * gi;
                const opacity = interpolate(
                  localFrame,
                  [start, start + 10],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                );
                const riseY = interpolate(
                  localFrame,
                  [start, start + wordReveal],
                  [RISE, 0],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: easeOutCubic,
                  },
                );
                const blur = blurIn
                  ? interpolate(localFrame, [start, start + 12], [BLUR0, 0], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                    })
                  : 0;
                const scaleIn = interpolate(
                  localFrame,
                  [start, start + 12],
                  [0.9, 1],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: easeOutCubic,
                  },
                );
                const pop = kw
                  ? interpolate(localFrame, [start, start + 16], [0.7, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: easeOutBack,
                    })
                  : 1;
                const stamp = kw
                  ? interpolate(
                      localFrame,
                      [start + 14, start + 18, start + 24],
                      [1, 1.06, 1],
                      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                    )
                  : 1;
                const wordScale = kw ? pop * stamp : scaleIn;

                const lineScale = li === lastIdx ? payoffScale : 1;
                const restingSize = (kw
                  ? finalFontSize * effKeywordScale
                  : finalFontSize) * lineScale;
                const useColor = kw && effStyle === "color";
                const useBar = kw && effStyle === "bar";
                const color = useBar
                  ? highlightTextColor
                  : useColor
                    ? resolvedKeywordColor
                    : textColor;
                const wordShadow =
                  useColor
                    ? `${textShadow}, 0 0 18px ${resolvedKeywordColor}66, 0 0 40px ${resolvedKeywordColor}33`
                    : textShadow;

                let fontWeight = 400;
                if (fontKey === "inter" || fontKey === "roboto") {
                  fontWeight = kw ? 900 : 700;
                } else if (
                  fontKey === "dmSerifDisplay" ||
                  fontKey === "playfairDisplay"
                ) {
                  fontWeight = kw ? 700 : 400;
                }

                const barScaleX = useBar
                  ? interpolate(localFrame, [start + 2, start + 12], [0, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: easeOutCubic,
                    })
                  : 0;
                const barTextOpacity = useBar
                  ? interpolate(localFrame, [start + 6, start + 14], [0, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                    })
                  : 1;

                return (
                  <span
                    key={wi}
                    style={{
                      position: "relative",
                      display: "inline-block",
                      fontFamily: quoteFont,
                      fontSize: restingSize,
                      fontWeight,
                      color,
                      textTransform:
                        uppercase && quoteMetrics.uppercaseSafe
                          ? "uppercase"
                          : "none",
                      letterSpacing: "-0.01em",
                      lineHeight:
                        quoteMetrics.script === "latin"
                          ? 0.95
                          : quoteMetrics.lineHeight,
                      opacity,
                      transform: `translateY(${riseY}px) scale(${wordScale})`,
                      transformOrigin: "center",
                      filter: blur > 0.05 ? `blur(${blur}px)` : undefined,
                      textShadow: useBar ? "none" : wordShadow,
                      willChange: "transform, opacity",
                    }}
                  >
                    {useBar ? (
                      <span
                        style={{
                          position: "absolute",
                          left: -finalFontSize * 0.08,
                          right: -finalFontSize * 0.08,
                          top: "0.06em",
                          bottom: "0.1em",
                          backgroundColor: resolvedBarColor,
                          transform: `scaleX(${barScaleX})`,
                          transformOrigin: "left center",
                          zIndex: 0,
                          borderRadius: 4,
                          // §4: the bar is a physical label slapped over the
                          // word — its own small tilt + a hard offset shadow
                          // (an axis-aligned glow reads as a UI hover).
                          rotate: `${((li % 2 === 0 ? 1 : -1) * 2.2).toFixed(1)}deg`,
                          boxShadow: "0 6px 16px rgba(0,0,0,0.4)",
                        }}
                      />
                    ) : null}
                    <span
                      style={{
                        position: "relative",
                        zIndex: 1,
                        opacity: barTextOpacity,
                      }}
                    >
                      {word}
                    </span>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
