import React from "react";
import { AbsoluteFill, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { HeartIcon } from "./icons";
import { Avatar, composeBubbleTransform, formatCount } from "./shared";
import type { InstagramCommentProps } from "./types";


const TEXT_SHADOW = "0 2px 8px rgba(0,0,0,0.4)";

export const InstagramComment: React.FC<InstagramCommentProps> = ({
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
  avatarColor = "#E1306C",
  username,
  comment,
  timestamp,
  likes,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "top", offsetY: 820 },
    "InstagramComment",
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 12, defaultExitFrames: 8 },
  );

  if (!visible) return null;

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

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          width,
          transform,
          opacity,
          transformOrigin: "center center",
          background:
            "linear-gradient(to right, rgba(0,0,0,0.6), rgba(0,0,0,0.3))",
          borderRadius: 12,
          padding: 18,
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
          fontFamily={MG_FONTS.inter}
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
              fontSize: 22,
              lineHeight: 1.3,
              color: "#FFFFFF",
              textShadow: TEXT_SHADOW,
              wordBreak: "break-word",
            }}
          >
            <span
              style={{
                fontWeight: 600,
                marginRight: 6,
              }}
            >
              {username}
            </span>
            <span style={{ fontWeight: 400 }}>{comment}</span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
              gap: 12,
              marginTop: 8,
              fontSize: 20,
              color: "#A8A8A8",
              textShadow: TEXT_SHADOW,
            }}
          >
            <span style={{ fontWeight: 600 }}>Reply</span>
            <span style={{ opacity: 0.7 }}>·</span>
            <span style={{ fontWeight: 400 }}>{timestamp}</span>
            {likes && likes > 0 ? (
              <>
                <span style={{ opacity: 0.7 }}>·</span>
                <span style={{ fontWeight: 400 }}>
                  {formatCount(likes)} likes
                </span>
              </>
            ) : null}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginLeft: 12,
            marginTop: 10,
            flexShrink: 0,
            filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.35))",
          }}
        >
          <HeartIcon size={22} color="#FFFFFF" />
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
