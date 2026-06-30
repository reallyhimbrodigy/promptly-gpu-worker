import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface RaceBarItem {
  label: string;
  value: number;
  // Optional per-bar base color (overrides the neutral fill). Leader still
  // takes the accent on settle / while leading.
  color?: string;
}

export interface BarRaceProps extends MGTimingProps, MGPositionProps {
  // 2–4 bars read best.
  bars?: RaceBarItem[];
  // Scale ceiling. Defaults to the largest value in `bars`.
  maxValue?: number;
  // "compare": fixed order, bars grow once. "race": bars grow together and
  // reorder vertically as they overtake each other. Default "compare".
  mode?: "compare" | "race";
  valuePrefix?: string;
  valueSuffix?: string;
  // Fill for the leading bar (runners-up are white). Default "#FFB23E" gold.
  accentColor?: string;
  // Overall band width in px. Default 880.
  width?: number;
  textShadow?: string;
}
