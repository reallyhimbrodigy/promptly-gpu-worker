import React from "react";
import { Img } from "remotion";


interface AvatarProps {
  size: number;
  src?: string;
  initials?: string;
  fallbackColor: string;
  fontFamily: string;
  fallbackText?: string;
}

export const Avatar: React.FC<AvatarProps> = ({
  size,
  src,
  initials,
  fallbackColor,
  fontFamily,
  fallbackText,
}) => {
  if (src) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size / 2,
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
      </div>
    );
  }

  const letters = (initials ?? fallbackText ?? "?").slice(0, 2).toUpperCase();

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: fallbackColor,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#FFFFFF",
        fontFamily,
        fontSize: Math.round(size * 0.42),
        fontWeight: 700,
        letterSpacing: "-0.01em",
        lineHeight: 1,
      }}
    >
      {letters}
    </div>
  );
};

export function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1)}K`;
  if (n < 100_000) return `${(n / 1000).toFixed(1)}K`;
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`;
  if (n < 10_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  return `${Math.round(n / 1_000_000)}M`;
}

export function composeBubbleTransform(
  enterProgress: number,
  exitProgress: number,
): { transform: string; opacity: number } {
  const enterScale = 0.9 + 0.1 * enterProgress;
  const enterTranslate = 20 * (1 - enterProgress);
  const enterOpacity = enterProgress;

  const exitScaleMult = 1 - 0.05 * exitProgress;
  const exitOpacity = 1 - exitProgress;

  const scale = enterScale * exitScaleMult;
  const opacity = enterOpacity * exitOpacity;

  return {
    transform: `translateY(${enterTranslate}px) scale(${scale})`,
    opacity,
  };
}
