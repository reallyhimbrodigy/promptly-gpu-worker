import type { MGTimingProps } from "../shared/types";

export interface StickyNote {
  text: string;
  color: string; // note background (e.g. "#FFEF8C" yellow)
  rotation: number; // resting rotation in degrees
}

export interface StickyNotesProps extends MGTimingProps {
  // Up to 3 notes. Positioned left / center / right with a fixed layout
  // matching the Clarity caption's design.
  notes: StickyNote[];
  // Note square side length in px. Default 300.
  noteSize?: number;
  // Handwritten text size on each note. Default 50.
  noteFontSize?: number;
  // Font family for the handwriting. Default Caveat Brush.
  noteFontFamily?: string;
  // Render the white gradient "fog" behind the notes. Default true.
  showFog?: boolean;
  // Vertical offset from the top of the frame for the notes group.
  // Default "5%".
  topOffset?: string;
}
