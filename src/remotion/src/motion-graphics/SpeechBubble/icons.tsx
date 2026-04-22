import React from "react";


interface SizedIconProps {
  size: number;
  color?: string;
}

export const VerifiedIcon: React.FC<SizedIconProps> = ({
  size,
  color = "#1D9BF0",
}) => {
  const points: string[] = [];
  const cx = 12;
  const cy = 12;
  const outerR = 11;
  const innerR = 8.8;
  const count = 12;
  for (let i = 0; i < count * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (i / (count * 2)) * Math.PI * 2 - Math.PI / 2;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    points.push(`${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`);
  }
  const starPath = points.join(" ") + " Z";

  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <path d={starPath} fill={color} />
      <path
        d="M7.5 12.3 L10.6 15.3 L16.5 9"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export const ReplyIcon: React.FC<SizedIconProps> = ({
  size,
  color = "#536471",
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path
      d="M4 5 C4 3.9 4.9 3 6 3 L18 3 C19.1 3 20 3.9 20 5 L20 15 C20 16.1 19.1 17 18 17 L13.5 17 L9 21 L9 17 L6 17 C4.9 17 4 16.1 4 15 Z"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);

export const RepostIcon: React.FC<SizedIconProps> = ({
  size,
  color = "#536471",
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path
      d="M4 8 L4 6 C4 4.9 4.9 4 6 4 L17 4 L14 1 M17 4 L14 7"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M20 16 L20 18 C20 19.1 19.1 20 18 20 L7 20 L10 23 M7 20 L10 17"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

interface HeartProps extends SizedIconProps {
  filled?: boolean;
}
export const HeartIcon: React.FC<HeartProps> = ({
  size,
  color = "#536471",
  filled = false,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path
      d="M12 21 C12 21 3 15 3 8.5 C3 5.5 5.2 3.5 7.8 3.5 C9.6 3.5 11.1 4.5 12 6 C12.9 4.5 14.4 3.5 16.2 3.5 C18.8 3.5 21 5.5 21 8.5 C21 15 12 21 12 21 Z"
      fill={filled ? color : "none"}
      stroke={color}
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);

export const ViewsIcon: React.FC<SizedIconProps> = ({
  size,
  color = "#536471",
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path
      d="M5 20 L5 14 M11 20 L11 9 M17 20 L17 4"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
    />
  </svg>
);

