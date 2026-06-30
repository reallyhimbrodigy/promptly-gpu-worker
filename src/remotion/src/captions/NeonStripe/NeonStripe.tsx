import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { TikTokToken } from "../shared/types";
import type { NeonStripeProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

const STROKE = 1.3; // crisp neon rim on the core
const CONTOUR = 4.2; // dark outline width that seats the glyph on footage

// Deterministic per-frame hash (fract of a big sine) — gives stable "random"
// values without Math.random, so renders stay reproducible.
const fHash = (n: number): number => {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};

// A small deterministic seed from the word so keywords flicker out of phase.
const wordSeed = (text: string): number => {
  let seed = 0;
  for (let i = 0; i < text.length; i++) seed += text.charCodeAt(i) * (i + 1);
  return seed;
};

// The signature stutter pattern over 6 frames: a hard lit/off/lit/off flutter
// that settles — the classic "broken neon sign" buzz.
const FLUTTER = [0.15, 1, 0.22, 1, 0.55, 1];

// Authentic buzzing-neon flicker for keywords, deterministic. Mostly fully lit
// with a faint hum, punctuated by ONE deliberate stutter burst that recurs
// roughly every 22 frames, plus rare organic single-frame dips for life. `seed`
// jitters the burst timing per word so keywords don't flutter in unison.
// Returns a brightness multiplier (0.15 near-off → ~1 fully lit).
const neonFlicker = (elapsed: number, seed: number): number => {
  let level = 0.97 + 0.03 * Math.sin((elapsed + seed) * 0.8); // faint hum
  // Deliberate stutter burst — guaranteed to land within each keyword's window.
  const start = 8 + (seed % 5);
  if (elapsed >= start) {
    const phase = (elapsed - start) % 22;
    if (phase < FLUTTER.length) level *= FLUTTER[phase];
  }
  // Rare organic dip elsewhere so the hold isn't dead-steady between bursts.
  if (fHash(Math.floor(elapsed) + seed) < 0.05) level *= 0.4;
  return level;
};

// ---------------------------------------------------------------------------
// NeonStripeWord — a lit neon glyph built in layers, back to front:
//   1. ambient bloom   — a contained blurred neon copy (the soft glow)
//   2. dark contour     — a thick dark outline so it seats on busy footage
//   3. dimensional core — white-hot top → neon → deep base, a crisp neon rim
//   4. stripe texture   — thin drifting dark lines (the striped fill)
//   5. ignite sheen     — a one-shot white flash as the tube "strikes" on
// The word springs + rises in and powers on with a flicker, like real neon.
// ---------------------------------------------------------------------------

const NeonStripeWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  fontFamily: string;
  fontSize: number;
  isKw: boolean;
  neonColor: string;
  stripeColor: string;
  stripeWidth: number;
  scrollSpeed: number;
  allCaps: boolean;
  localFrame: number;
}> = ({
  token,
  pageStartMs,
  fontFamily,
  fontSize,
  isKw,
  neonColor,
  stripeColor,
  stripeWidth,
  scrollSpeed,
  allCaps,
  localFrame,
}) => {
  const { fps } = useVideoConfig();

  const entry = msToFrames(token.fromMs - pageStartMs, fps);
  const rawElapsed = localFrame - entry;
  const appeared = rawElapsed >= 0;
  // Normalize the frame-based flicker/scroll to a 30fps baseline so the tuned
  // neon buzz keeps the same wall-clock feel at any fps (e.g. 60fps delivery).
  const norm = 30 / fps;
  const elapsed = rawElapsed * norm;

  const s = appeared
    ? spring({
        fps,
        frame: rawElapsed,
        config: { damping: 16, mass: 0.5, stiffness: 200 },
      })
    : 0;
  const scale = interpolate(s, [0, 1], [0.86, 1], {
    extrapolateRight: "clamp",
  });
  const rise = interpolate(s, [0, 1], [12, 0], { extrapolateRight: "clamp" });
  const opacity = interpolate(s, [0, 0.32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Neon power-on: a stuttering flicker over the first ~8 frames, then a steady
  // breathe so the tube subtly pulses while it holds.
  const flicker = appeared
    ? interpolate(elapsed, [0, 1, 2, 3, 4, 6, 8], [0, 1, 0.4, 1, 0.65, 1, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;
  const breathe = 1 + 0.09 * Math.sin(elapsed * 0.13);
  const glow = Math.max(0.3, flicker) * breathe;

  // Keywords keep buzzing after the power-on: a continuous neon flicker, phase
  // offset per word. Crucially this dims the LIGHT, not toward black — on a
  // dropout the tube stays green but loses its glow and drops to a dull lit
  // state, like a real neon sign losing charge. Non-keywords hold steady.
  const lit = isKw ? neonFlicker(elapsed, wordSeed(token.text)) : 1;
  const kwBrightness = isKw ? 0.55 + 0.45 * lit : 1; // floor ~0.62 — dull green, never black
  const glowMul = isKw ? 0.12 + 0.88 * lit : 1; // glow nearly vanishes on dropouts

  // One-shot white "strike" flash as the tube ignites, then gone.
  const ignite = appeared
    ? interpolate(elapsed, [0, 2, 4, 11], [0, 0.9, 0.45, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const fontSizePx = isKw ? Math.round(fontSize * 1.16) : fontSize;
  // Contained ambient bloom (was a big smear — tightened so it doesn't wash the
  // footage). The tight inner glow lives on the core's own shadow.
  const haloBlur = (isKw ? 20 : 15) * glow;
  const coreGlow = (isKw ? 1.2 : 1) * glow * glowMul;
  const haloOpacity = 0.55 * glow * glowMul;

  // Fine horizontal texture lines scaled to the glyph; keywords get denser
  // lines. The dark line is a thin minority of the period so the fill stays
  // mostly bright neon with a subtle line texture, not chunky barcode bands.
  const period = Math.max(
    6,
    Math.round(fontSizePx * stripeWidth * (isKw ? 0.85 : 1)) * 2,
  );
  const darkBand = Math.max(1, Math.round(period * 0.3));
  // Drift the lines vertically — modulo the period keeps the loop seamless.
  const scrollY = appeared ? (localFrame * norm * scrollSpeed) % period : 0;

  const common: React.CSSProperties = {
    margin: 0,
    fontFamily,
    fontSize: fontSizePx,
    fontWeight: 800,
    textTransform: allCaps ? "uppercase" : "none",
    letterSpacing: "0.005em",
    lineHeight: 1.06,
    whiteSpace: "nowrap",
  };
  const overlay: React.CSSProperties = {
    ...common,
    position: "absolute",
    left: 0,
    top: 0,
    color: "transparent",
  };

  return (
    <span
      style={{
        position: "relative",
        display: "inline-block",
        transform: `translateY(${rise.toFixed(2)}px) scale(${scale.toFixed(3)})`,
        transformOrigin: "center bottom",
        opacity,
        filter: isKw ? `brightness(${kwBrightness.toFixed(3)})` : undefined,
      }}
    >
      {/* 1. Ambient bloom — a contained blurred neon copy behind everything. */}
      <span
        aria-hidden
        style={{
          ...common,
          position: "absolute",
          left: 0,
          top: 0,
          color: neonColor,
          filter: `blur(${haloBlur.toFixed(1)}px)`,
          opacity: haloOpacity,
        }}
      >
        {token.text}
      </span>

      {/* 2. Dark contour — a thick dark outline that seats the glyph on busy
          footage so the neon edge reads against any background. */}
      <span
        aria-hidden
        style={{
          ...overlay,
          WebkitTextStroke: `${CONTOUR}px ${stripeColor}`,
          opacity: 0.92,
        }}
      >
        {token.text}
      </span>

      {/* 3. Dimensional core — white-hot specular top → neon body → deep base,
          a crisp neon rim and a tight hot glow. Reads as a lit glass tube. */}
      <span
        style={{
          ...common,
          position: "relative",
          color: "transparent",
          backgroundImage: `linear-gradient(177deg, #FFFFFF 0%, ${neonColor} 15%, ${neonColor} 80%, ${stripeColor} 100%)`,
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          WebkitTextStroke: `${STROKE}px ${neonColor}`,
          textShadow: [
            `0 0 ${(2.5 * coreGlow).toFixed(1)}px ${neonColor}`,
            `0 0 ${(6 * coreGlow).toFixed(1)}px ${neonColor}`,
            `0 2px 5px rgba(0,0,0,0.82)`,
          ].join(", "),
        }}
      >
        {token.text}
      </span>

      {/* 4. Stripe texture — thin drifting dark lines over the fill. */}
      <span
        aria-hidden
        style={{
          ...overlay,
          opacity: 0.45,
          backgroundImage: `repeating-linear-gradient(0deg, ${stripeColor} 0px, ${stripeColor} ${darkBand}px, transparent ${darkBand}px, transparent ${period}px)`,
          backgroundPosition: `0px ${scrollY.toFixed(2)}px`,
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
        }}
      >
        {token.text}
      </span>

      {/* 5. Ignite sheen — a one-shot white flash as the tube strikes on. */}
      {ignite > 0.01 ? (
        <span
          aria-hidden
          style={{
            ...overlay,
            color: "#FFFFFF",
            opacity: ignite,
            textShadow: `0 0 ${(10 * coreGlow).toFixed(1)}px #FFFFFF`,
          }}
        >
          {token.text}
        </span>
      ) : null}
    </span>
  );
};

export const NeonStripe: React.FC<NeonStripeProps> = ({
  pages,
  neonColor = "#39FF14",
  stripeColor = "#04210A",
  stripeWidth = 0.05,
  stripeScrollSpeed = 0.25,
  fontFamily = CAPTION_FONTS.montserrat,
  fontSize = 104,
  position = "center",
  maxWordsPerLine = 3,
  keywords = [],
  allCaps = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.86;
  const positionStyle = getCaptionPositionStyle(position);
  const kwSet = useMemo(() => buildKeywordSet(keywords), [keywords]);

  // Render the active page by comparing the current frame to each page's
  // window — the component owns no <Sequence> (the pipeline bounds visibility).
  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;
        if (frame < startFrame || frame >= startFrame + durationFrames) {
          return null;
        }
        const localFrame = frame - startFrame;

        const lines: TikTokToken[][] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        return (
          <AbsoluteFill
            key={pageIndex}
            style={{ display: "flex", alignItems: "center", ...positionStyle }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
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
                    justifyContent: "center",
                    alignItems: "baseline",
                    columnGap: 22,
                  }}
                >
                  {lineTokens.map((token, tokenIdx) => (
                    <NeonStripeWord
                      key={tokenIdx}
                      token={token}
                      pageStartMs={page.startMs}
                      fontFamily={fontFamily}
                      fontSize={fontSize}
                      isKw={isKeyword(token.text, kwSet)}
                      neonColor={neonColor}
                      stripeColor={stripeColor}
                      stripeWidth={stripeWidth}
                      scrollSpeed={stripeScrollSpeed}
                      allCaps={allCaps}
                      localFrame={localFrame}
                    />
                  ))}
                </div>
              ))}
            </div>
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};
