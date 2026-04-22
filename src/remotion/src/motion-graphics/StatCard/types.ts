import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface StatCardProps extends MGTimingProps, MGPositionProps {
  // Target number to count up to (the hero value).
  value: number;
  // Start value for the count-up. Default 0.
  fromValue?: number;
  // Optional prefix rendered before the number (e.g. "$").
  prefix?: string;
  // Optional suffix rendered after the number (e.g. "%", "K", "M", "+").
  suffix?: string;
  // If set, display with N decimal places. Otherwise renders as an integer
  // with thousands separators via toLocaleString().
  decimals?: number;
  // Short descriptive label below the number (e.g. "IN 90 DAYS").
  label: string;
  // Number color. Default "#FFFFFF" — max readability on any video.
  numberColor?: string;
  // Label color. Default "#FFFFFF" — size differential carries the hierarchy.
  labelColor?: string;
  // Thin accent line drawn between number and label (ties the component to
  // the rest of the kit). Default "#C8551F" (rust).
  accentColor?: string;
  // Override the text drop shadow used on the number and label. Pass "" to
  // disable shadows entirely (e.g. for solid-color backgrounds).
  textShadow?: string;
}
