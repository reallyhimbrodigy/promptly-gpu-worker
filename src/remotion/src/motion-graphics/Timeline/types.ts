import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface TimelineStep {
  // Optional index chip text (e.g. "01"). Falls back to the 1-based position.
  index?: string;
  // Card title (the step name).
  label: string;
  // Optional supporting line under the title.
  description?: string;
}

export interface TimelineProps extends MGTimingProps, MGPositionProps {
  // Ordered steps, top → bottom. 2–5 read best.
  steps?: TimelineStep[];
  // Single accent (rail fill + active node tint + card accent). Default "#FF8A1E".
  accentColor?: string;
  // Neutral rail behind the accent fill. Default "rgba(255,255,255,0.16)".
  trackColor?: string;
  // Node chip diameter in px. Default 84.
  nodeSize?: number;
  // Overall block width in px (rail + card). Default 880.
  width?: number;
  // Vertical distance between node centres in px. Default 210.
  rowGap?: number;
  // Title color. Default "#FFFFFF".
  labelColor?: string;
  // Index numeral color when a node is reached. Default "#FFFFFF".
  indexColor?: string;
  textShadow?: string;
}
