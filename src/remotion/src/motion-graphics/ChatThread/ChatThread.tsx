import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { ChatMessage, ChatThreadProps } from "./types";


const ENTRANCE_FRAMES = 5;
const DEFAULT_TYPING_MS_INCOMING = 900;
const DEFAULT_HOLD_MS = 450;

const CARD_ENTER_FRAMES = 14;
const CARD_EXIT_FRAMES = 12;
const CARD_ENTER_OFFSET = 12; // message schedule waits this many frames

const DOT_CYCLE_FRAMES = 42;
const DOT_STAGGER_FRAMES = 6;

function dotPulse(frame: number, dotIndex: number): { opacity: number; scale: number } {
  const phase =
    ((frame - dotIndex * DOT_STAGGER_FRAMES) * Math.PI * 2) /
    DOT_CYCLE_FRAMES;
  const wave = (Math.sin(phase) + 1) / 2;
  return { opacity: 0.3 + wave * 0.7, scale: 0.85 + wave * 0.15 };
}

interface ScheduleEntry {
  typingStart: number;
  typingEnd: number;
  bubbleAppear: number;
  bubbleSettled: number;
}

function buildSchedule(
  messages: ChatMessage[],
  fps: number,
  startOffset = 0,
): ScheduleEntry[] {
  let cursor = startOffset;
  return messages.map((m) => {
    const defaultTyping =
      m.sender === "them" ? DEFAULT_TYPING_MS_INCOMING : 0;
    const typingFrames = msToFrames(m.typingMs ?? defaultTyping, fps);
    const holdFrames = msToFrames(m.holdMs ?? DEFAULT_HOLD_MS, fps);
    const typingStart = cursor;
    const typingEnd = typingStart + typingFrames;
    const bubbleAppear = typingEnd;
    const bubbleSettled = bubbleAppear + ENTRANCE_FRAMES;
    cursor = bubbleSettled + holdFrames;
    return { typingStart, typingEnd, bubbleAppear, bubbleSettled };
  });
}


const SignalBars: React.FC = () => (
  <svg width={34} height={22} viewBox="0 0 34 22" fill="#FFFFFF">
    <rect x="0" y="14" width="5" height="8" rx="1.2" />
    <rect x="8" y="10" width="5" height="12" rx="1.2" />
    <rect x="16" y="5" width="5" height="17" rx="1.2" />
    <rect x="24" y="0" width="5" height="22" rx="1.2" />
  </svg>
);

const WifiIcon: React.FC = () => (
  <svg width={30} height={22} viewBox="0 0 30 22" fill="#FFFFFF">
    <path d="M15 3.5C21 3.5 26 5.6 29 8.4L26.7 11C24.3 8.7 20 7 15 7S5.7 8.7 3.3 11L1 8.4C4 5.6 9 3.5 15 3.5Z" />
    <path d="M15 10.2c3.6 0 6.7 1.3 8.6 3.2L21.3 16C19.8 14.7 17.7 13.7 15 13.7S10.2 14.7 8.7 16L6.4 13.4C8.3 11.5 11.4 10.2 15 10.2Z" />
    <circle cx="15" cy="18.3" r="2.5" />
  </svg>
);

const BatteryIcon: React.FC<{ level?: number }> = ({ level = 1 }) => {
  const fillWidth = 38 * Math.max(0, Math.min(1, level));
  return (
    <svg width={52} height={22} viewBox="0 0 52 22" fill="none">
      <rect
        x="1"
        y="1"
        width="42"
        height="20"
        rx="5"
        stroke="#FFFFFF"
        strokeOpacity="0.5"
        strokeWidth="1.5"
        fill="none"
      />
      <rect
        x="44"
        y="7"
        width="3"
        height="8"
        rx="1"
        fill="#FFFFFF"
        fillOpacity="0.5"
      />
      <rect
        x="3"
        y="3"
        width={fillWidth}
        height="16"
        rx="3"
        fill="#FFFFFF"
      />
    </svg>
  );
};

interface StatusBarProps {
  time: string;
}

const StatusBar: React.FC<StatusBarProps> = ({ time }) => (
  <div
    style={{
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingLeft: 56,
      paddingRight: 56,
      paddingTop: 24,
      paddingBottom: 14,
      height: 88,
      boxSizing: "border-box",
    }}
  >
    <div
      style={{
        fontFamily: MG_FONTS.inter,
        fontSize: 34,
        fontWeight: 600,
        color: "#FFFFFF",
        letterSpacing: "-0.01em",
        lineHeight: 1,
      }}
    >
      {time}
    </div>
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
      }}
    >
      <SignalBars />
      <WifiIcon />
      <BatteryIcon level={1} />
    </div>
  </div>
);


const BackChevron: React.FC = () => (
  <svg width={22} height={38} viewBox="0 0 22 38" fill="none">
    <path
      d="M20 2L3 19L20 36"
      stroke="#0A84FF"
      strokeWidth="4.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const FaceTimeIcon: React.FC = () => (
  <svg width={44} height={28} viewBox="0 0 44 28" fill="#0A84FF">
    <rect x="0" y="4" width="28" height="20" rx="5" />
    <path d="M30 10L44 4V24L30 18Z" />
  </svg>
);

interface iMessageHeaderProps {
  name: string;
  subtitle: string;
  avatarSrc?: string;
  initials?: string;
  avatarColor: string;
}

const MessageHeader: React.FC<iMessageHeaderProps> = ({
  name,
  subtitle,
  avatarSrc,
  initials,
  avatarColor,
}) => {
  const fallbackLetter = (initials ?? name).slice(0, 2).toUpperCase();
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "stretch",
        paddingBottom: 14,
        borderBottom: "1px solid rgba(255,255,255,0.1)",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingLeft: 32,
          paddingRight: 40,
          paddingTop: 12,
          paddingBottom: 8,
        }}
      >
        <BackChevron />
        <FaceTimeIcon />
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 4,
        }}
      >
        <div
          style={{
            width: 110,
            height: 110,
            borderRadius: "50%",
            overflow: "hidden",
            backgroundColor: avatarColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#FFFFFF",
            fontFamily: MG_FONTS.inter,
            fontSize: 48,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            marginBottom: 10,
          }}
        >
          {avatarSrc ? (
            <Img
              src={avatarSrc}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
          ) : (
            fallbackLetter
          )}
        </div>
        <div
          style={{
            fontFamily: MG_FONTS.inter,
            fontSize: 28,
            fontWeight: 600,
            color: "#FFFFFF",
            letterSpacing: "-0.01em",
            lineHeight: 1.1,
          }}
        >
          {name}
        </div>
        <div
          style={{
            fontFamily: MG_FONTS.inter,
            fontSize: 22,
            fontWeight: 400,
            color: "rgba(255,255,255,0.55)",
            letterSpacing: "0.01em",
            marginTop: 2,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span>{subtitle}</span>
          <svg
            width={12}
            height={16}
            viewBox="0 0 12 16"
            fill="rgba(255,255,255,0.4)"
            style={{ marginTop: 1 }}
          >
            <path d="M2 2L10 8L2 14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>
  );
};


const HomeIndicator: React.FC = () => (
  <div
    style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: 44,
      paddingBottom: 14,
    }}
  >
    <div
      style={{
        width: 280,
        height: 8,
        borderRadius: 4,
        backgroundColor: "#FFFFFF",
      }}
    />
  </div>
);


interface BubbleProps {
  text: string;
  sender: "me" | "them";
  bgColor: string;
  textColor: string;
  entranceProgress: number;
}

const MessageBubble: React.FC<BubbleProps> = ({
  text,
  sender,
  bgColor,
  textColor,
  entranceProgress,
}) => {
  const scale = 0.85 + entranceProgress * 0.15;
  const opacity = entranceProgress;
  return (
    <div
      style={{
        display: "flex",
        justifyContent: sender === "me" ? "flex-end" : "flex-start",
        width: "100%",
        padding: "6px 22px",
      }}
    >
      <div
        style={{
          maxWidth: "75%",
          backgroundColor: bgColor,
          color: textColor,
          padding: "16px 22px",
          borderRadius: 30,
          fontFamily: MG_FONTS.inter,
          fontSize: 34,
          fontWeight: 400,
          lineHeight: 1.28,
          letterSpacing: "-0.005em",
          transform: `scale(${scale})`,
          transformOrigin:
            sender === "me" ? "bottom right" : "bottom left",
          opacity,
          wordBreak: "break-word",
        }}
      >
        {text}
      </div>
    </div>
  );
};

interface TypingBubbleProps {
  sender: "me" | "them";
  bgColor: string;
  localFrame: number;
  entranceProgress: number;
}

const TypingBubble: React.FC<TypingBubbleProps> = ({
  sender,
  bgColor,
  localFrame,
  entranceProgress,
}) => {
  const scale = 0.85 + entranceProgress * 0.15;
  const opacity = entranceProgress;
  return (
    <div
      style={{
        display: "flex",
        justifyContent: sender === "me" ? "flex-end" : "flex-start",
        width: "100%",
        padding: "6px 22px",
      }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          padding: "20px 26px",
          backgroundColor: bgColor,
          borderRadius: 30,
          transform: `scale(${scale})`,
          transformOrigin:
            sender === "me" ? "bottom right" : "bottom left",
          opacity,
        }}
      >
        {[0, 1, 2].map((i) => {
          const { opacity: dotOpacity, scale: dotScale } = dotPulse(
            localFrame,
            i,
          );
          return (
            <div
              key={i}
              style={{
                width: 16,
                height: 16,
                borderRadius: 8,
                backgroundColor: "#8E8E93",
                opacity: dotOpacity,
                transform: `scale(${dotScale})`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
};


export const ChatThread: React.FC<ChatThreadProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  header,
  messages,
  width = 820,
  minHeight = 1320,
  borderRadius = 56,
  statusBarTime = "9:41",
  showStatusBar = true,
  showHomeIndicator = true,
  backgroundColor = "#000000",
  incomingColor = "#26252A",
  incomingTextColor = "#FFFFFF",
  outgoingColor = "#0A84FF",
  outgoingTextColor = "#FFFFFF",
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    {
      defaultEnterFrames: CARD_ENTER_FRAMES,
      defaultExitFrames: CARD_EXIT_FRAMES,
    },
  );

  const { containerStyle, wrapperStyle } = resolveMGPosition({
    anchor,
    offsetX,
    offsetY,
    scale,
  });

  if (!visible) return null;

  const enterProgress = interpolate(
    localFrame,
    [0, CARD_ENTER_FRAMES],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    },
  );
  const enterScale = interpolate(enterProgress, [0, 1], [0.88, 1]);
  const enterOpacity = interpolate(
    localFrame,
    [0, CARD_ENTER_FRAMES * 0.75],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const enterTranslateY = interpolate(enterProgress, [0, 1], [24, 0]);

  const exitEased = Easing.in(Easing.cubic)(exitProgress);
  const exitScale = interpolate(exitEased, [0, 1], [1, 0.94]);
  const exitOpacityEased = 1 - exitEased;
  const exitTranslateY = exitEased * 14;

  const isExiting = exitProgress > 0;
  const cardScale = isExiting ? exitScale : enterScale;
  const cardOpacity = isExiting ? exitOpacityEased : enterOpacity;
  const cardTranslateY = isExiting ? exitTranslateY : enterTranslateY;

  const schedule = buildSchedule(messages, fps, CARD_ENTER_OFFSET);

  const messageStates = messages.map((m, i) => {
    const s = schedule[i];
    const entranceProgress = interpolate(
      localFrame,
      [s.bubbleAppear, s.bubbleSettled],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
    const hasArrived = localFrame >= s.bubbleAppear;
    return { message: m, hasArrived, entranceProgress };
  });

  let activeTypingIndex: number | null = null;
  for (let i = 0; i < messages.length; i++) {
    const s = schedule[i];
    const typingFrames = s.typingEnd - s.typingStart;
    if (
      typingFrames > 0 &&
      localFrame >= s.typingStart &&
      localFrame < s.typingEnd
    ) {
      activeTypingIndex = i;
      break;
    }
  }

  const typingEntrance =
    activeTypingIndex !== null
      ? interpolate(
          localFrame,
          [
            schedule[activeTypingIndex].typingStart,
            schedule[activeTypingIndex].typingStart + 4,
          ],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      : 0;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            width,
            minHeight,
            backgroundColor,
            borderRadius,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            opacity: cardOpacity,
            transform: `translateY(${cardTranslateY}px) scale(${cardScale})`,
            transformOrigin: "center center",
            boxShadow:
              "0 28px 80px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4)",
          }}
        >
          {showStatusBar ? <StatusBar time={statusBarTime} /> : null}

          {header ? (
            <MessageHeader
              name={header.name}
              subtitle={header.subtitle ?? "iMessage"}
              avatarSrc={header.avatarSrc}
              initials={header.initials}
              avatarColor={header.avatarColor ?? "#636366"}
            />
          ) : null}

          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
              overflow: "hidden",
              paddingTop: 16,
              paddingBottom: 16,
            }}
          >
            {messageStates.map((state, i) =>
              state.hasArrived ? (
                <MessageBubble
                  key={`msg-${i}`}
                  text={state.message.text}
                  sender={state.message.sender}
                  bgColor={
                    state.message.sender === "me"
                      ? outgoingColor
                      : incomingColor
                  }
                  textColor={
                    state.message.sender === "me"
                      ? outgoingTextColor
                      : incomingTextColor
                  }
                  entranceProgress={state.entranceProgress}
                />
              ) : null,
            )}

            {activeTypingIndex !== null ? (
              <TypingBubble
                sender={messages[activeTypingIndex].sender}
                bgColor={
                  messages[activeTypingIndex].sender === "me"
                    ? outgoingColor
                    : incomingColor
                }
                localFrame={localFrame}
                entranceProgress={typingEntrance}
              />
            ) : null}
          </div>

          {showHomeIndicator ? <HomeIndicator /> : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
