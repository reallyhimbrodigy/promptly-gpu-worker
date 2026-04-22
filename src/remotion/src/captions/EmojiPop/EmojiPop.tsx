import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import { Lottie } from "@remotion/lottie";
import type { TikTokPage } from "../shared/types";
import type { EmojiPopProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { getEmojiForKeyword, type LottieEmojiData } from "./emojiMap";

/* ─── Word ─── */

const EmojiWord: React.FC<{
  text: string;
  isActive: boolean;
  isPast: boolean;
  isKeyword: boolean;
  activeColor: string;
  inactiveColor: string;
  fontSize: number;
  triggerFrame: number;
}> = ({
  text,
  isActive,
  isPast,
  isKeyword,
  activeColor,
  inactiveColor,
  fontSize,
  triggerFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const elapsed = frame - triggerFrame;
  const hasAppeared = elapsed >= 0;

  // Snappier spring — more overshoot, faster settle
  const revealSpring = hasAppeared
    ? spring({
        fps,
        frame: elapsed,
        config: { mass: 0.35, damping: 8.5, stiffness: 260 },
      })
    : 0;

  // Scale: pop from 0 with overshoot, then settle
  let targetScale: number;
  if (!hasAppeared) {
    targetScale = 0;
  } else if (isActive && isKeyword) {
    targetScale = 1.2; // big keyword punch
  } else if (isActive) {
    targetScale = 1.1;
  } else if (isPast && isKeyword) {
    targetScale = 1.04; // keywords stay slightly bigger after spoken
  } else if (isPast) {
    targetScale = 0.97; // past words shrink slightly — makes active pop more
  } else {
    targetScale = 1;
  }

  const scale = interpolate(revealSpring, [0, 1], [0, targetScale], {
    extrapolateRight: "clamp",
  });

  // Y punch on reveal — snappier
  const translateY = hasAppeared
    ? interpolate(revealSpring, [0, 0.4, 1], [14, -5, 0], {
        extrapolateRight: "clamp",
      })
    : 14;

  // Color logic
  let color: string;
  if (isActive && isKeyword) {
    color = activeColor;
  } else if (isPast && isKeyword) {
    color = activeColor; // keywords stay red
  } else {
    color = inactiveColor;
  }

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: CAPTION_FONTS.montserrat,
        fontWeight: 900,
        fontSize,
        textTransform: "none",
        letterSpacing: "0.04em",
        lineHeight: 1.2,
        color,
        textShadow: "0 4px 12px rgba(0,0,0,0.55)",
        transform: `scale(${scale}) translateY(${translateY}px)`,
        transformOrigin: "center bottom",
        whiteSpace: "pre",
        padding: "0 4px",
      }}
    >
      {text}
    </span>
  );
};

/* ─── Page ─── */

const EmojiPopPage: React.FC<{
  page: TikTokPage;
  pageStartFrame: number;
  pageDurationFrames: number;
  activeColor: string;
  inactiveColor: string;
  fontSize: number;
  emojiSize: number;
  maxWidth: number;
}> = ({
  page,
  pageStartFrame,
  pageDurationFrames,
  activeColor,
  inactiveColor,
  fontSize,
  emojiSize,
  maxWidth,
}) => {
  const localFrame = useCurrentFrame(); // 0-based within this Sequence
  const { fps } = useVideoConfig();
  const frame = localFrame + pageStartFrame; // absolute frame for timing

  // Page fade in/out
  const fadeFrames = 5;
  const entryOpacity = interpolate(
    localFrame,
    [0, fadeFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const exitOpacity = interpolate(
    localFrame,
    [pageDurationFrames - fadeFrames, pageDurationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const pageOpacity = Math.min(entryOpacity, exitOpacity);

  if (pageOpacity <= 0) return null;

  const currentTimeMs = (frame / fps) * 1000;

  // Find the FIRST keyword emoji for this page (one emoji per page)
  let pageEmoji: LottieEmojiData | null = null;
  const keywordSet = new Set<number>();

  for (const token of page.tokens) {
    const data = getEmojiForKeyword(token.text);
    if (data && !pageEmoji) {
      pageEmoji = data;
    }
    if (data) {
      keywordSet.add(page.tokens.indexOf(token));
    }
  }

  // Emoji animation — pops in with the page, stays for entire page
  let emojiNode: React.ReactNode = null;
  if (pageEmoji) {
    // Juicier spring — lower damping = more overshoot bounce
    const emojiSpring = spring({
      fps,
      frame: localFrame,
      config: { mass: 0.45, damping: 7.5, stiffness: 220 },
    });

    const emojiScale = interpolate(emojiSpring, [0, 1], [0, 1], {
      extrapolateRight: "clamp",
    });

    // Rotation wiggle — snappier
    const rotation = interpolate(
      emojiSpring,
      [0, 0.3, 0.6, 0.85, 1],
      [18, -10, 5, -2, 0],
      { extrapolateRight: "clamp" },
    );

    // Exit: scale down when page ends
    const exitScale = interpolate(
      localFrame,
      [pageDurationFrames - 5, pageDurationFrames],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );

    const finalScale = emojiScale * exitScale;

    emojiNode = (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          marginBottom: 16,
        }}
      >
        <div
          style={{
            width: emojiSize,
            height: emojiSize,
            transform: `scale(${finalScale}) rotate(${rotation}deg)`,
            transformOrigin: "center center",
            filter: "drop-shadow(0 4px 10px rgba(0,0,0,0.4))",
          }}
        >
          <Lottie
            animationData={pageEmoji.animationData}
            style={{ width: emojiSize, height: emojiSize }}
            playbackRate={1}
          />
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        display: "flex",
        justifyContent: "center",
        width: "100%",
        opacity: pageOpacity,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth,
        }}
      >
        {/* Emoji — centered above the text */}
        {emojiNode}

        {/* Words */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: "8px 18px",
          }}
        >
          {page.tokens.map((token, idx) => {
            const isActive =
              currentTimeMs >= token.fromMs && currentTimeMs < token.toMs;
            const isPast = currentTimeMs >= token.toMs;

            return (
              <EmojiWord
                key={idx}
                text={token.text}
                isActive={isActive}
                isPast={isPast}
                isKeyword={keywordSet.has(idx)}
                activeColor={activeColor}
                inactiveColor={inactiveColor}
                fontSize={fontSize}
                triggerFrame={msToFrames(token.fromMs, fps) - pageStartFrame}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};

/* ─── Main Component ─── */

export const EmojiPop: React.FC<EmojiPopProps> = ({
  pages,
  activeColor = "#FF0000",
  inactiveColor = "#FFFFFF",
  fontSize = 85,
  emojiSize = 110,
  position = "center",
  maxWidthPercent = 0.85,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * maxWidthPercent;

  const positionStyle = getCaptionPositionStyle(position);

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        ...positionStyle,
      }}
    >
      <div style={{ position: "relative", width: "100%", minHeight: 300 }}>
        {pages.map((page, pageIndex) => {
          const pageStartFrame = msToFrames(page.startMs, fps);
          const pageDurationFrames = msToFrames(page.durationMs, fps);

          return (
            <Sequence
              key={pageIndex}
              from={pageStartFrame}
              durationInFrames={pageDurationFrames}
              name={page.text}
              premountFor={10}
            >
              <EmojiPopPage
                page={page}
                pageStartFrame={pageStartFrame}
                pageDurationFrames={pageDurationFrames}
                activeColor={activeColor}
                inactiveColor={inactiveColor}
                fontSize={fontSize}
                emojiSize={emojiSize}
                maxWidth={maxWidth}
              />
            </Sequence>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
