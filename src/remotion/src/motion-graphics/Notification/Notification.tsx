import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { APP_ICONS } from "./icons";
import type { NotificationItem, NotificationProps } from "./types";


const NOTIFICATION_SPRING = {
  mass: 0.6,
  damping: 14,
  stiffness: 220,
  overshootClamping: false,
};

const STAGGER_FRAMES = 30;
const NOTIFICATION_GAP = 10;

interface PlatformStyle {
  topOffset: number;
  sideInset: number;
  paddingY: number;
  paddingX: number;
  radius: number;
  background: string;
  blur: string;
  border: string | "none";
  shadow: string | "none";
  iconSize: number;
  iconRadius: number;
  fontFamily: string;
  appNameOpacity: number;
}

const STYLES: Record<"ios" | "android", PlatformStyle> = {
  ios: {
    topOffset: 24,
    sideInset: 24,
    paddingY: 22,
    paddingX: 24,
    radius: 26,
    background: "rgba(36, 36, 40, 0.78)",
    blur: "blur(42px) saturate(180%)",
    border: "1px solid rgba(255,255,255,0.09)",
    shadow: "0 6px 28px rgba(0,0,0,0.32), 0 1px 2px rgba(0,0,0,0.25)",
    iconSize: 84,
    iconRadius: 24,
    fontFamily: MG_FONTS.inter,
    appNameOpacity: 0.78,
  },
  android: {
    topOffset: 28,
    sideInset: 22,
    paddingY: 24,
    paddingX: 26,
    radius: 32,
    background: "rgba(35, 35, 38, 0.92)",
    blur: "blur(28px)",
    border: "none",
    shadow: "0 10px 28px rgba(0,0,0,0.42)",
    iconSize: 88,
    iconRadius: 26,
    fontFamily: MG_FONTS.roboto,
    appNameOpacity: 0.82,
  },
};

interface BannerProps {
  item: NotificationItem;
  style: PlatformStyle;
}

const NotificationBanner: React.FC<BannerProps> = ({ item, style }) => {
  const Icon = APP_ICONS[item.app];
  const timestamp = item.timestamp ?? "now";

  return (
    <div
      style={{
        borderRadius: style.radius,
        background: style.background,
        backdropFilter: style.blur,
        WebkitBackdropFilter: style.blur,
        border: style.border === "none" ? undefined : style.border,
        boxShadow: style.shadow === "none" ? undefined : style.shadow,
        paddingTop: style.paddingY,
        paddingBottom: style.paddingY,
        paddingLeft: style.paddingX,
        paddingRight: style.paddingX,
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        fontFamily: style.fontFamily,
      }}
    >
      <div
        style={{
          width: style.iconSize,
          height: style.iconSize,
          borderRadius: style.iconRadius,
          flexShrink: 0,
          overflow: "hidden",
          boxShadow: "inset 0 0 0 0.5px rgba(255,255,255,0.12)",
        }}
      >
        <Icon size={style.iconSize} />
      </div>

      <div
        style={{
          flex: 1,
          marginLeft: 18,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: `rgba(255,255,255,${style.appNameOpacity})`,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {item.appName}
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: "rgba(255,255,255,0.55)",
              marginLeft: 12,
              flexShrink: 0,
              letterSpacing: "0.01em",
            }}
          >
            {timestamp}
          </div>
        </div>

        <div
          style={{
            fontSize: 34,
            fontWeight: 700,
            color: "#FFFFFF",
            marginTop: 4,
            lineHeight: 1.18,
            letterSpacing: "-0.015em",
          }}
        >
          {item.title}
        </div>

        <div
          style={{
            fontSize: 28,
            fontWeight: 400,
            color: "rgba(255,255,255,0.88)",
            marginTop: 2,
            lineHeight: 1.3,
            letterSpacing: "-0.005em",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {item.body}
        </div>
      </div>
    </div>
  );
};

export const Notification: React.FC<NotificationProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  platform = "ios",
  notifications,
  // anchor / offsetX / offsetY are deliberately destructured-but-ignored.
  // The Notification is an iOS / Android notification banner that DROPS
  // DOWN from the top of the screen — placing it anywhere else (center,
  // bottom) makes the entry animation nonsensical. We honor `scale`
  // only because fine-tuning the size is safe; fine-tuning the position
  // breaks the visual metaphor. (Earlier renders shipped Notification at lower_third_safe
  // because Gemini interpreted "LARGE MGs allowed at upper OR lower
  // third" as a green light to place it at the bottom — the prompt has
  // since been tightened to call out Notification specifically, and
  // this component-level lock is the defensive backstop.)
  scale,
}) => {
  const platformTopOffset = STYLES[platform].topOffset;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor: "top", offsetY: platformTopOffset, scale },
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress, phase } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 14, defaultExitFrames: 10 },
  );

  if (!visible) return null;

  const items = Array.isArray(notifications)
    ? notifications.slice(0, 3)
    : [];
  if (items.length === 0) return null;

  const style = STYLES[platform];
  const isExiting = phase === "exiting" || phase === "after";

  const exitEased = Math.pow(exitProgress, 3);
  const exitTranslatePct = exitEased * -100;
  const exitFade = interpolate(exitProgress, [0.6, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const stackWidth = 1080 - style.sideInset * 2;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          width: stackWidth,
          display: "flex",
          flexDirection: "column",
          gap: NOTIFICATION_GAP,
        }}
      >
        {items.map((item, i) => {
          const itemFrame = localFrame - i * STAGGER_FRAMES;
          const dropSpring = spring({
            fps,
            frame: itemFrame,
            config: NOTIFICATION_SPRING,
            durationInFrames: 14,
          });
          const enterTranslatePct = interpolate(dropSpring, [0, 1], [-100, 0]);
          const enterOpacity = interpolate(itemFrame, [0, 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          const translateYPct = isExiting
            ? exitTranslatePct
            : enterTranslatePct;
          const opacity = isExiting ? exitFade : enterOpacity;

          return (
            <div
              key={i}
              style={{
                position: "relative",
                zIndex: items.length - i,
                transform: `translateY(${translateYPct}%)`,
                opacity,
              }}
            >
              <NotificationBanner item={item} style={style} />
            </div>
          );
        })}
      </div>
      </div>
    </AbsoluteFill>
  );
};
