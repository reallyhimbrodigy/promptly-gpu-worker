import type { CaptionStyleProps } from "../shared/types";

export interface EmojiEntry {
  /** The emoji character */
  emoji: string;
  /** Which word index triggers this emoji */
  wordIndex: number;
}

export interface EmojiPopProps extends CaptionStyleProps {
  /** Color for the active/current word. Default: "#FF0000" */
  activeColor?: string;
  /** Color for inactive words. Default: "#FFFFFF" */
  inactiveColor?: string;
  /** Emoji size in pixels. Default: 110 */
  emojiSize?: number;
  /** Max width as fraction of frame width. Default: 0.85 */
  maxWidthPercent?: number;
}
