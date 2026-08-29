import React from "react";
import { AbsoluteFill, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { useSmoothGraphics } from "../shared/smooth-graphics-flag";
import { cappedEntranceProgress } from "../shared/entrance-cap";
import { MG_FONTS } from "../shared/fonts";
import { mgTextFont } from "../shared/text-font";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { HeartIcon } from "./icons";
import { Avatar, composeBubbleTransform, formatCount } from "./shared";
import type { TikTokCommentProps } from "./types";


const TEXT_SHADOW = "0 2px 8px rgba(0,0,0,0.7)";

export const TikTokComment: React.FC<TikTokCommentProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  anchor,
  offsetX,
  offsetY,
  scale,
  width = 620,
  avatarSrc,
  initials,
  // §6: brand-red was invented chroma (the InstagramComment precedent) —
  // neutral disc unless the spec sends a palette color.
  avatarColor = "rgba(255,255,255,0.22)",
  username,
  comment,
  likes,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    // The 820 default pairs with the default "top" anchor only — it must not
    // survive an anchor-only override (the audited IMessageBubble class; this
    // was the third sibling carrying it).
    { anchor: "top", offsetY: anchor == null ? 820 : 0 },
    "TikTokComment",
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 },
  );

  if (!visible) return null;

  // ENTRANCE VELOCITY CAP (Zac 2026-08-01). SPRING_SNAPPY over 12 frames dumps
  // ~60% of the travel into ONE delivered frame (measured peak_step 0.61 => ~1.6
  // effective positions) — the worst stepper in the MG set despite being one of
  // the LONGEST entrances. OFF => today's exact spring.
  const smoothEntrance = useSmoothGraphics();
  const springProgress = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 12,
  });
  const enterProgress = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 12 })
    : springProgress;
  const { transform, opacity } = composeBubbleTransform(
    enterProgress,
    exitProgress,
  );

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
          flexDirection: "row",
          alignItems: "flex-start",
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <Avatar
          size={44}
          src={avatarSrc}
          initials={initials}
          fallbackColor={avatarColor}
          fallbackText={username}
        />

        <div
          style={{
            marginLeft: 12,
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
          }}
        >
          <div
            style={{
              // User text routes by script + emoji tail (font census
              // 2026-08-26); the like count keeps the root Inter (chrome).
              fontFamily: mgTextFont(username, "inter"),
              fontSize: 22,
              fontWeight: 500,
              color: "#A8A8A8",
              textShadow: TEXT_SHADOW,
              lineHeight: 1.2,
              letterSpacing: "-0.005em",
            }}
          >
            {username}
          </div>

          <div
            style={{
              fontFamily: mgTextFont(comment, "inter"),
              fontSize: 24,
              fontWeight: 400,
              color: "#FFFFFF",
              textShadow: TEXT_SHADOW,
              marginTop: 4,
              lineHeight: 1.3,
              wordBreak: "break-word",
            }}
          >
            {comment}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            marginLeft: 16,
            flexShrink: 0,
            filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.55))",
          }}
        >
          <HeartIcon size={28} color="#FFFFFF" />
          <div
            style={{
              fontSize: 18,
              fontWeight: 500,
              color: "#A8A8A8",
              marginTop: 6,
              textShadow: TEXT_SHADOW,
              lineHeight: 1,
            }}
          >
            {formatCount(likes)}
          </div>
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
