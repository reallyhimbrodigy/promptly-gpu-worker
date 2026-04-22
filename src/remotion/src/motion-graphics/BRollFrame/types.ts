import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type BRollFrameAspectRatio = "16:9" | "4:5" | "1:1" | "9:16";
export type BRollFrameVariant = "clean" | "white-border" | "polaroid";
export type BRollFrameMediaType = "image" | "video";

export interface BRollFrameProps extends MGTimingProps, MGPositionProps {
  // Either a single staticFile() URL, or an array of 1-3 URLs.
  // When 2 or 3 are provided, they render stacked on top of one another
  // with scrapbook-style rotation offsets per photo (same frame chrome
  // for every photo — only the rotation/z-order differs).
  src: string | string[];
  // Default "image". Applies to all sources when `src` is an array.
  mediaType?: BRollFrameMediaType;
  // Default "16:9". Drives the frame's height derivation from width.
  aspectRatio?: BRollFrameAspectRatio;
  // Default 540 (px at 1080-wide composition = 50% of frame width).
  width?: number;
  // Default "clean". Governs border / shadow / caption treatment.
  variant?: BRollFrameVariant;
  // Optional caption shown below each photo. Pass a string to apply the
  // same caption to every photo in the stack, or an array matched by index
  // (captions[0] → back photo, etc.) to give each a different label.
  caption?: string | string[];
}
