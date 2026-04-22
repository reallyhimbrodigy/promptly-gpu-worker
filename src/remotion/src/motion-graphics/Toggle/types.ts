import type { MGTimingProps } from "../shared/types";

export interface ToggleProps extends MGTimingProps {
  // Label rendered left of the switch.
  text: string;
  // Milliseconds from component start when the toggle flips ON.
  // Default 400ms.
  activateAtMs?: number;
  // Label font size. Default 72.
  fontSize?: number;
  // Multiplier on the switch dimensions. Default 1.5.
  toggleScale?: number;
  // Off-state track color. Default "#D1D5DB".
  offColor?: string;
  // On-state track color. Default iMessage blue "#3B82F6".
  onColor?: string;
  // Label text color. Default "#FFFFFF".
  labelColor?: string;
  // Knob (thumb) color. Default "#FFFFFF".
  knobColor?: string;
  // CSS top position. Default "12%".
  top?: string;
  // CSS left position. Default "50%".
  left?: string;
}
