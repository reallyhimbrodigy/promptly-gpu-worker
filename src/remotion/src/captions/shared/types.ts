import type { TikTokToken, TikTokPage } from "@remotion/captions";

export type { TikTokToken, TikTokPage };

export interface CaptionStyleProps {
  pages: TikTokPage[];
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: number | string;
  primaryColor?: string;
  secondaryColor?: string;
  position?: "top" | "center" | "bottom";
  strokeColor?: string;
  strokeWidth?: number;
}
