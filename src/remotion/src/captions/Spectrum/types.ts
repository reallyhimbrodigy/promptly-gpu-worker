import type { CaptionStyleProps } from "../shared/types";

export interface SpectrumProps extends CaptionStyleProps {
  // Iridescent ramp the phrase flows through. Should loop (last ≈ first) for a
  // seamless drift. If empty, a designed default ramp is used.
  colors?: string[];
  // Fraction of the ramp advanced per word (hue spacing across the phrase). Default 0.13.
  hueStep?: number;
  // Ramp drift speed per frame at 30fps (fps-normalized live color-cycle). Default 0.006.
  flowSpeed?: number;
  // Words to spotlight: these cycle the ramp much faster + sit slightly larger.
  keywords?: string[];
  // How many times faster keywords cycle vs normal words. Default 4.
  keywordSpeed?: number;
  fontFamily?: string; // Default Poppins.
  fontSize?: number; // Default 104.
  position?: "top" | "center" | "bottom";
  maxWordsPerLine?: number; // Default 3.
  allCaps?: boolean; // Default true.
}
