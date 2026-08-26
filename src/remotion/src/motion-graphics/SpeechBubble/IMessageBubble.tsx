import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { useSmoothGraphics } from "../shared/smooth-graphics-flag";
import { cappedEntranceProgress } from "../shared/entrance-cap";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { composeBubbleTransform } from "./shared";
import { mgSchedule } from "../shared/schedule";
import { asText } from "../../shared/asText";
import type { IMessageBubbleProps } from "./types";


const OUTGOING_GRADIENT = "linear-gradient(180deg, #1E9BF0 0%, #0479D9 100%)";
// The tail abuts the bubble's BOTTOM edge, so it must match the gradient's
// end stop — the old #0A84FF painted a visibly brighter seam where the tail
// met the bubble (pass #11, audited).
const OUTGOING_FALLBACK = "#0479D9";
const INCOMING_COLOR = "#2C2C2E";

// 60fps-authored; scaled by mgSchedule at render time (pass #11 — the raw
// constants meant the typewriter could not complete inside short live windows).
const TYPING_PHASE_FRAMES = 30;
const TYPE_REVEAL_FRAMES = 60;

export const IMessageBubble: React.FC<IMessageBubbleProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  anchor,
  offsetX,
  offsetY,
  scale,
  width = 620,
  messageType,
  text,
  status,
  typewriter = false,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    // The 820 default was AUTHORED for the default "top" anchor (bubble in
    // the lower half). It must not survive an anchor-only override — the live
    // "center" placement rendered 615px below center with the status line in
    // the TikTok nav zone (pass #11, audited).
    { anchor: "top", offsetY: anchor == null ? 820 : 0 },
    "IMessageBubble",
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 },
  );

  if (!visible) return null;

  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: typewriter ? TYPING_PHASE_FRAMES + TYPE_REVEAL_FRAMES : 22,
  });
  const k = K(1);

  const isOutgoing = messageType === "outgoing";
  const bubbleFill = isOutgoing ? OUTGOING_GRADIENT : INCOMING_COLOR;
  const tailColor = isOutgoing ? OUTGOING_FALLBACK : INCOMING_COLOR;

  // ENTRANCE VELOCITY CAP (Zac 2026-08-01). SPRING_SNAPPY over 12 frames dumps
  // ~60% of the travel into ONE delivered frame (measured peak_step 0.61 => ~1.6
  // effective positions) — the worst stepper in the MG set despite being one of
  // the LONGEST entrances. OFF => today's exact spring.
  const smoothEntrance = useSmoothGraphics();
  // 12 was authored at 60fps (200ms) — raw, it ran 2x slower at production
  // 30fps (pass #11, audited).
  const enterF = Math.max(3, Math.round((12 / 60) * fps));
  const springProgress = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: enterF,
  });
  const enterProgress = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: enterF })
    : springProgress;
  const { transform, opacity } = composeBubbleTransform(
    enterProgress,
    exitProgress,
  );

  const showTypingIndicator =
    typewriter && localFrame < K(TYPING_PHASE_FRAMES);

  let displayedText = text;
  if (typewriter) {
    const typeFrame = localFrame - K(TYPING_PHASE_FRAMES);
    const chars = Math.max(
      0,
      Math.floor(
        interpolate(typeFrame, [0, K(TYPE_REVEAL_FRAMES)], [0, text.length], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      ),
    );
    displayedText = text.slice(0, chars);
  }

  // Takeover for the dramatic short message (pass #11, audited: the live solo
  // "LOST" occupied ~10% of the axis). Short texts scale up toward the bubble
  // box; running text keeps the mimic's 30px. Paddings/radius are em-relative
  // so the bubble keeps its proportions at any size.
  const msgChars = Math.max(1, [...asText(text)].length);
  const msgFontSize =
    msgChars <= 20
      ? Math.min(64, Math.max(30, Math.round(480 / (msgChars * 0.62))))
      : 30;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          width,
          transform,
          opacity,
          transformOrigin: "center center",
          fontFamily: MG_FONTS.inter,
          display: "flex",
          justifyContent: isOutgoing ? "flex-end" : "flex-start",
          flexDirection: "column",
          alignItems: isOutgoing ? "flex-end" : "flex-start",
          WebkitFontSmoothing: "antialiased",
        }}
      >
        {showTypingIndicator ? (
          <TypingIndicatorBubble
            isOutgoing={isOutgoing}
            bubbleFill={bubbleFill}
            tailColor={tailColor}
            frame={localFrame}
          />
        ) : (
          <MessageBubble
            isOutgoing={isOutgoing}
            bubbleFill={bubbleFill}
            tailColor={tailColor}
            text={displayedText}
            fontSize={msgFontSize}
          />
        )}

        {isOutgoing && status && !showTypingIndicator ? (
          <div
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: "#8E8E93",
              marginTop: 6,
              marginRight: 4,
              letterSpacing: "-0.01em",
            }}
          >
            {status}
          </div>
        ) : null}
      </div>
      </div>
    </AbsoluteFill>
  );
};


const MessageBubble: React.FC<{
  isOutgoing: boolean;
  bubbleFill: string;
  tailColor: string;
  text: string;
  fontSize?: number;
}> = ({ isOutgoing, bubbleFill, tailColor, text, fontSize = 30 }) => {
  return (
    <div
      style={{
        position: "relative",
        maxWidth: 480,
      }}
    >
      <div
        style={{
          background: bubbleFill,
          borderRadius: "0.87em",
          paddingLeft: "0.6em",
          paddingRight: "0.6em",
          paddingTop: "0.47em",
          paddingBottom: "0.47em",
          color: "#FFFFFF",
          fontSize,
          fontWeight: 400,
          lineHeight: 1.3,
          letterSpacing: "-0.005em",
          wordBreak: "break-word",
          boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
          minHeight: "1.3em",
        }}
      >
        {text}
      </div>
      <Tail isOutgoing={isOutgoing} color={tailColor} />
    </div>
  );
};


const TypingIndicatorBubble: React.FC<{
  isOutgoing: boolean;
  bubbleFill: string;
  tailColor: string;
  frame: number;
}> = ({ isOutgoing, bubbleFill, tailColor, frame }) => {
  const dotPhase = (offset: number) =>
    Math.sin((frame + offset) * 0.35) * 4;

  return (
    <div
      style={{
        position: "relative",
      }}
    >
      <div
        style={{
          background: bubbleFill,
          borderRadius: 22,
          paddingLeft: 20,
          paddingRight: 20,
          paddingTop: 16,
          paddingBottom: 16,
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          gap: 8,
          boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
        }}
      >
        {[0, 4, 8].map((offset) => (
          <div
            key={offset}
            style={{
              width: 10,
              height: 10,
              borderRadius: 5,
              backgroundColor: "rgba(255,255,255,0.7)",
              transform: `translateY(${dotPhase(offset)}px)`,
            }}
          />
        ))}
      </div>
      <Tail isOutgoing={isOutgoing} color={tailColor} />
    </div>
  );
};


const Tail: React.FC<{ isOutgoing: boolean; color: string }> = ({
  isOutgoing,
  color,
}) => {
  const tailPath = "M0 0 C6 8 12 14 18 16 C12 18 6 20 0 22 Z";

  return (
    <svg
      width={18}
      height={22}
      viewBox="0 0 18 22"
      style={{
        position: "absolute",
        bottom: 0,
        [isOutgoing ? "right" : "left"]: -6,
        transform: isOutgoing ? "scaleX(1)" : "scaleX(-1)",
      }}
    >
      <path d={tailPath} fill={color} />
    </svg>
  );
};
