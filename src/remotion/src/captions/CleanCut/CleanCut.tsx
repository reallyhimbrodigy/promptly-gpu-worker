import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokPage } from "../shared/types";
import type { CleanCutProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { boundedFade } from "../shared/fadeTiming";
import { getCaptionPositionStyle, CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale } from "../shared/fit";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const CleanCutPage: React.FC<{
  page: TikTokPage;
  textColor: string;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  allCaps: boolean;
  textShadow: string;
  maxWidth: number;
  localFrame: number;
  positionStyle: React.CSSProperties;
}> = ({
  page,
  textColor,
  fontFamily,
  fontSize,
  fontWeight,
  allCaps,
  textShadow,
  maxWidth,
  localFrame,
  positionStyle,
}) => {
  const { fps, width } = useVideoConfig();
  const localMs = (localFrame / fps) * 1000;

  // CAPTION LATENESS (Zac 2026-07-14): activate on the FRAME the token starts,
  // not on a continuous-ms threshold. The old `localMs >= fromMs - startMs`
  // compared a stepped-16.67ms clock against a sub-frame ms value, so any
  // threshold just above N frames needed frame N+1 — CleanCut revealed ~47% of
  // words a full frame late (the "captions feel late" complaint). Round the
  // activation to a frame (like Lumen/Prime/TwoTone) so it lands on the
  // IDENTICAL frame the SFX/zoom/MG fire. Paired with the frame-aligned
  // page.startMs (handler) this is exact: 0-frame delta across all styles.
  const actFrame = (tok: (typeof page.tokens)[number]) =>
    msToFrames(tok.fromMs - page.startMs, fps);
  // Pick the single active token — the last one that has started.
  let activeIdx = 0;
  for (let i = 0; i < page.tokens.length; i++) {
    if (localFrame >= actFrame(page.tokens[i])) activeIdx = i;
  }
  const token = page.tokens[activeIdx];
  if (!token) return null;

  // F4 width-fit guarantee: one word at a time; scale it to the real box
  // (the 200px-inset safe rect) before the existing break-word fallback —
  // a scaled whole word beats a mid-word CSS break. fitScale floors at 0.6;
  // below that, overflowWrap:break-word (already on the span) takes over.
  const fit = fitScale(
    [
      {
        parts: [
          {
            text: token.text,
            fontSize,
            font: { fontFamily, fontWeight, letterSpacingEm: -0.02, uppercase: allCaps },
          },
        ],
      },
    ],
    Math.min(maxWidth, width - 2 * CAPTION_PADDING.sidesSafe),
    "CleanCut",
  );

  const since = localFrame - actFrame(token);
  // Crisp, quick entrance — a small rise + settle, no flair. WS2 fade-bound:
  // 55ms base (was 80), capped at 25% of this word's on-screen window (until the
  // next word, or page end) so fast speech doesn't leave the word still fading
  // in when it's already spoken (shared/fadeTiming).
  const nextTok = page.tokens[activeIdx + 1];
  const wordWindowMs = (nextTok ? nextTok.fromMs : page.startMs + page.durationMs) - token.fromMs;
  // CRISP ENTRANCE (Zac 2026-07-13): full opacity from frame 1 — no 0→1 ramp (the
  // ghost). CleanCut's subtle scale+lift stays as the whisper on a fully-VISIBLE word.
  const opacity = since >= 0 ? 1 : 0;
  // FRAME-1-IS-FINAL ENTRANCE (Zac 2026-07-13, 4th pass): the word arrives at FINAL
  // position + FULL scale — no rise-and-settle. The scale 1.04→1 grow and 7px lift were
  // entrance MOTION; CleanCut is the plain no-style style, so it just IS there, crisp.
  const scale = 1;
  const y = 0;

  // Gentle fade at the very end of the page — bounded to 25% of the page window
  // so a short final page doesn't spend half its life fading out (shared/fadeTiming).
  const pageFadeOutMs = boundedFade(150, page.durationMs);
  const fadeOut = interpolate(
    localMs,
    [page.durationMs - pageFadeOutMs, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{ display: "flex", alignItems: "center", ...positionStyle }}
    >
      <span
        style={{
          fontFamily,
          fontSize: fontSize * fit.scale,
          fontWeight,
          color: textColor,
          textTransform: allCaps ? "uppercase" : "none",
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          textAlign: "center",
          maxWidth,
          overflowWrap: "break-word",
          textShadow,
          transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(3)})`,
          transformOrigin: "center",
          opacity: opacity * fadeOut,
        }}
      >
        {token.text}
      </span>
    </AbsoluteFill>
  );
};

export const CleanCut: React.FC<CleanCutProps> = ({
  pages,
  textColor = "#FFFFFF",
  fontFamily = CAPTION_FONTS.inter,
  fontSize = 100,
  fontWeight = 800,
  position = "center",
  allCaps = false,
  textShadow = "0 4px 22px rgba(0,0,0,0.6), 0 2px 6px rgba(0,0,0,0.55), 0 0 1px rgba(0,0,0,0.5)",
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const positionStyle = getCaptionPositionStyle(position);

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

        return (
          <CleanCutPage
            key={pageIndex}
            page={page}
            textColor={textColor}
            fontFamily={fontFamily}
            fontSize={fontSize}
            fontWeight={fontWeight}
            allCaps={allCaps}
            textShadow={textShadow}
            maxWidth={maxWidth}
            localFrame={frame - startFrame}
            positionStyle={positionStyle}
          />
        );
      })}
    </AbsoluteFill>
  );
};
