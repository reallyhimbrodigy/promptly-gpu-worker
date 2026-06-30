import React from "react";
import type { IconName } from "./types";

export interface IconProps {
  size: number;
  strokeWidth?: number;
}

// Shared stroke svg wrapper. Color comes from the parent via `currentColor`.
const Svg: React.FC<{
  size: number;
  strokeWidth: number;
  children: React.ReactNode;
}> = ({ size, strokeWidth, children }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {children}
  </svg>
);

const Check: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M4.5 12.5l5 5 10-11" />
  </Svg>
);

const Bolt: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M13 2L4.5 13.5H10l-1 8.5L19.5 10H13.5L13 2z" />
  </Svg>
);

const Star: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 3.2l2.6 5.27 5.81.84-4.2 4.1.99 5.79L12 16.9l-5.2 2.73.99-5.79-4.2-4.1 5.81-.84z" />
  </Svg>
);

const Dollar: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 2.5v19" />
    <path d="M16.5 6.2c-1-1.2-2.6-1.9-4.3-1.9h-.7a3.3 3.3 0 0 0 0 6.6h1.8a3.3 3.3 0 0 1 0 6.6h-1c-1.7 0-3.3-.7-4.3-1.9" />
  </Svg>
);

const ArrowUp: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 20V5" />
    <path d="M6 11l6-6 6 6" />
  </Svg>
);

const Fire: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 3c1 2.6.2 4.4-1 5.6C9.5 10.1 9 11.2 9 12.6a3 3 0 0 0 6 0c0-1-.3-1.8-.4-1.9.9.7 1.4 1.9 1.4 3.3a5 5 0 1 1-10 0C6 9.6 9 6.6 12 3z" />
  </Svg>
);

const Heart: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 20.5C5.5 15 3 11.3 3 8.2A4.4 4.4 0 0 1 12 6.4 4.4 4.4 0 0 1 21 8.2c0 3.1-2.5 6.8-9 12.3z" />
  </Svg>
);

const Clock: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.4 2" />
  </Svg>
);

const Lock: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <rect x="5" y="10.5" width="14" height="10" rx="2" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </Svg>
);

const Trophy: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M8 4h8v4.5a4 4 0 0 1-8 0V4z" />
    <path d="M8 5H5.2a2.2 2.2 0 0 0 2.6 4" />
    <path d="M16 5h2.8a2.2 2.2 0 0 1-2.6 4" />
    <path d="M12 12.5V16M9.5 20h5M10 20a2 2 0 0 1 4 0" />
  </Svg>
);

const Target: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="4.5" />
    <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
  </Svg>
);

const ChartUp: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M3 17l5.5-5.5 4 4L21 7" />
    <path d="M15 7h6v6" />
  </Svg>
);

const Sparkle: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M12 3l1.9 6.1L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9z" />
    <path d="M19 3.5l.6 1.9 1.9.6-1.9.6L19 8.5l-.6-1.9L16.5 6l1.9-.6z" />
  </Svg>
);

const X: React.FC<IconProps> = ({ size, strokeWidth = 2 }) => (
  <Svg size={size} strokeWidth={strokeWidth}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Svg>
);

export const ICONS: Record<IconName, React.FC<IconProps>> = {
  check: Check,
  bolt: Bolt,
  star: Star,
  dollar: Dollar,
  "arrow-up": ArrowUp,
  fire: Fire,
  heart: Heart,
  clock: Clock,
  lock: Lock,
  trophy: Trophy,
  target: Target,
  "chart-up": ChartUp,
  sparkle: Sparkle,
  x: X,
};
