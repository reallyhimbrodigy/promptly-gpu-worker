import type { CaptionStyleProps } from "../shared/types";

export interface TypewriterColorScheme {
  textColor: string;
  bgColor: string;
  cursorColor: string;
}

export type TypewriterSchemeName = "classic" | "terminal" | "amber" | "custom";

export const TYPEWRITER_SCHEMES: Record<
  Exclude<TypewriterSchemeName, "custom">,
  TypewriterColorScheme
> = {
  classic: {
    textColor: "#FFFFFF",
    bgColor: "#0a0a0a",
    cursorColor: "#FFFFFF",
  },
  terminal: {
    textColor: "#33FF33",
    bgColor: "rgba(0, 0, 0, 0.85)",
    cursorColor: "#33FF33",
  },
  amber: {
    textColor: "#FFB000",
    bgColor: "rgba(0, 0, 0, 0.85)",
    cursorColor: "#FFB000",
  },
};

export interface TypewriterRevealProps extends CaptionStyleProps {
  /** Color scheme. Default: "classic" */
  scheme?: TypewriterSchemeName;
  /** Custom colors (when scheme="custom") */
  customColors?: Partial<TypewriterColorScheme>;
  /** Show blinking cursor. Default: true */
  showCursor?: boolean;
  /** Cursor blink interval in ms. Default: 530 */
  cursorBlinkMs?: number;
  /** Show background box. Default: false */
  enableBox?: boolean;
  /** Force lowercase. Default: true */
  lowercase?: boolean;
  /** Letter spacing. Default: "0.03em" */
  letterSpacing?: string;
  /** Line height. Default: 1.4 */
  lineHeight?: number;
  /** Page fade-in duration in ms. Default: 150 */
  fadeInDurationMs?: number;
  /** Page fade-out duration in ms. Default: 150 */
  fadeOutDurationMs?: number;
  /** Box border radius. Default: 8 */
  boxBorderRadius?: number;
  /** Max width as fraction of frame. Default: 0.85 */
  maxWidthPercent?: number;
}
