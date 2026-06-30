import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface TimelineRoadmapStep {
  // Optional index chip text (e.g. "01"). Falls back to the 1-based position.
  index?: string;
  // Primary label beside the node.
  label: string;
  // Optional secondary line under the label.
  sublabel?: string;
}

export interface TimelineRoadmapProps extends MGTimingProps, MGPositionProps {
  // Ordered nodes, top → bottom. 4–6 read best.
  steps?: TimelineRoadmapStep[];
  // Single accent (spine fill + active node tint). Default "#4F9DF7".
  accentColor?: string;
  // Neutral spine behind the accent fill. Default "rgba(255,255,255,0.18)".
  trackColor?: string;
  // Node chip diameter in px. Default 72.
  nodeSize?: number;
  // Overall band width in px (room for labels both sides). Default 820.
  width?: number;
  // Vertical distance between node centres. Default 210.
  rowHeight?: number;
  // Which side the first label sits on; subsequent alternate. Default "right".
  firstSide?: "right" | "left";
  labelColor?: string;
  sublabelColor?: string;
  indexColor?: string;
  textShadow?: string;
}
