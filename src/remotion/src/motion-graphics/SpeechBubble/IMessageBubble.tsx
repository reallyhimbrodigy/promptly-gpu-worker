import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { composeBubbleTransform } from "./shared";
import type { IMessageBubbleProps } from "./types";


const OUTGOING_GRADIENT = "linear-gradient(180deg, #1E9BF0 0%, #0479D9 100%)";
const OUTGOING_FALLBACK = "#0A84FF"; // used for the tail solid fill
const INCOMING_COLOR = "#2C2C2E";

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
    { anchor: "top", offsetY: 820 },
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 },
  );

  if (!visible) return null;

  const isOutgoing = messageType === "outgoing";
  const bubbleFill = isOutgoing ? OUTGOING_GRADIENT : INCOMING_COLOR;
  const tailColor = isOutgoing ? OUTGOING_FALLBACK : INCOMING_COLOR;

  const enterProgress = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 12,
  });
  const { transform, opacity } = composeBubbleTransform(
    enterProgress,
    exitProgress,
  );

  const showTypingIndicator =
    typewriter && localFrame < TYPING_PHASE_FRAMES;

  let displayedText = text;
  if (typewriter) {
    const typeFrame = localFrame - TYPING_PHASE_FRAMES;
    const chars = Math.max(
      0,
      Math.floor(
        interpolate(typeFrame, [0, TYPE_REVEAL_FRAMES], [0, text.length], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      ),
    );
    displayedText = text.slice(0, chars);
  }

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
}> = ({ isOutgoing, bubbleFill, tailColor, text }) => {
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
          borderRadius: 26,
          paddingLeft: 18,
          paddingRight: 18,
          paddingTop: 14,
          paddingBottom: 14,
          color: "#FFFFFF",
          fontSize: 30,
          fontWeight: 400,
          lineHeight: 1.3,
          letterSpacing: "-0.005em",
          wordBreak: "break-word",
          boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
          minHeight: 30 * 1.3,
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
