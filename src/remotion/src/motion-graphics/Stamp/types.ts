import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type StampStyle = "seal" | "stamp" | "ribbon";
export type StampMark = "none" | "star" | "check" | "stars";
export type StampFontKey = "oswald" | "anton" | "inter";

export interface StampProps extends MGTimingProps, MGPositionProps {
  text: string; // main word, e.g. "VERIFIED" — required
  style?: StampStyle; // Default "seal".
  subtextTop?: string; // small-caps line above main (seal).
  subtextBottom?: string; // small-caps line below main.
  mark?: StampMark; // inline-SVG mark. Default "star" (seal) / "none" (stamp).
  color?: string; // single ink: ring/border + text. Default "#C8321F".
  textColor?: string; // override text color. Default = color.
  markColor?: string; // override mark color. Default = color.
  rotation?: number; // rest tilt in degrees. Default -9.
  entryScale?: number; // oversized entry scale. Default 1.28.
  fontKey?: StampFontKey; // Default per style.
  fontSize?: number; // main text px. Default per style.
  size?: number; // seal diameter / stamp min-width base px. Default per style.
  doubleRing?: boolean; // seal double ring / stamp double border. Default true.
  distress?: boolean; // deterministic ink grain. Default true (stamp) / false (seal).
  shockRing?: boolean; // expanding impact ring. Default true.
  impactFlash?: boolean; // one-frame contact flash. Default true.
  textShadow?: string;
}
