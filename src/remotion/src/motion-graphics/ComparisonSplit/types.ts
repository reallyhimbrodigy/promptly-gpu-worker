import type { MGTimingProps } from "../shared/types";

// Content for one half of the comparison. `desaturate` applies a subtle
// saturate+brightness filter to de-emphasize a side (typically the "before").
export type ComparisonContent =
  | { type: "image"; src: string; desaturate?: boolean }
  | { type: "video"; src: string; desaturate?: boolean }
  | { type: "color"; color: string; desaturate?: boolean }
  | { type: "text"; text: string; desaturate?: boolean }
  // Animated count-up stat — the 80% use case for creator/business content
  // ("$2,000/mo" → "$20,000/mo"). Each side runs its own count-up.
  | {
      type: "stat";
      value: number;
      fromValue?: number;
      prefix?: string;
      suffix?: string;
      decimals?: number;
      // Small caps label under the number (e.g. "PER MONTH").
      label: string;
      desaturate?: boolean;
    };

export interface ComparisonSplitProps extends MGTimingProps {
  // "vertical" (default) = left vs right, divider runs top-to-bottom.
  // "horizontal" = top vs bottom, divider runs left-to-right.
  orientation?: "vertical" | "horizontal";
  // Tuple: first entry is the leading side (left for vertical, top for
  // horizontal), second entry is the trailing side.
  sides: [ComparisonContent, ComparisonContent];
  // Editorial header labels for each side (e.g. ["BEFORE", "AFTER"]).
  labels: [string, string];
  // Accent color for the divider and header labels. Default "#C8551F" (rust).
  accentColor?: string;
  // Backdrop theme for text / stat / color sides. "dark" (default) = ink
  // gradient; "light" = cream gradient.
  theme?: "dark" | "light";
  // Divider color override. Defaults to accentColor.
  dividerColor?: string;
  // Hero number size for `type: "stat"` sides. Affix ($, %) renders at
  // ~60% of this. Default 148. Shrink for long values that overflow.
  statFontSize?: number;
}
