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
  // §6 palette lock (pass #11, audited): "#E1306C" was invented Instagram
  // brand pink — chroma no palette selected, rendered whenever the spec
  // omits avatarColor (the live one does). Neutral disc by default.
  avatarColor = "rgba(255,255,255,0.22)",
  username,
  comment,
  timestamp,
  likes,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    // The 820 default pairs with the default "top" anchor only — it must not
    // survive an anchor-only override (the IMessageBubble precedent, pass #11).
    { anchor: "top", offsetY: anchor == null ? 820 : 0 },
    "InstagramComment",
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
              // User comments carry emoji AND non-Latin scripts; mgTextFont
              // routes the face by script + carries the emoji tail (font
              // census 2026-08-26 — generalizes the pass #11 hand-rolled
              // stack). Username routes on its own text.
              fontFamily: mgTextFont(comment, "inter"),
            }}
          >
            <span
              style={{
                fontFamily: mgTextFont(username, "inter"),
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
            {/* Doubled-dot fix (pass #11, audited): the separator + timestamp
                rendered unconditionally — a spec without timestamp (the live
                one) showed "Reply · · 1.6K likes". */}
            {timestamp ? (
              <>
                <span style={{ opacity: 0.7 }}>·</span>
                <span style={{ fontWeight: 400 }}>{timestamp}</span>
              </>
            ) : null}
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
