/**
 * Per-word font-size auto-fit. Returns a fontSize that guarantees `text`
 * renders within `maxWidth` for the given font specification.
 *
 * Why this exists: NegativeFlash and Prism scale keyword tokens by 1.6x.
 * For long keywords like "ELECTROCUTED" (12 chars), 80px × 1.6 = 128px
 * font lands at ~1100px rendered width — wider than the 918px line
 * (1080 × 0.85 maxWidth). The browser doesn't shrink to fit; it just
 * crops at the canvas edge. Result: the user sees "LECTROCUTE" with
 * both sides chopped.
 *
 * Solution: before rendering, measure the natural width at the requested
 * fontSize using Canvas's measureText(). If it exceeds the budget, scale
 * fontSize down so the rendered text fits with a small margin. No
 * truncation, no ellipsis, no flex-wrap (whiteSpace: nowrap on each word
 * means wrap can't help). Just sized-to-fit.
 *
 * Headless Chromium has document.createElement('canvas') and the 2d
 * context, so this works inside Remotion renders. Falls back to a
 * conservative character-width estimate for environments without document
 * (SSR, unit tests).
 */

const FALLBACK_CHAR_WIDTH_RATIO = 0.6;
// Leave a tiny margin for sub-pixel rendering / kerning differences
// between the canvas measurement and the actual rendered span.
const FIT_MARGIN = 0.97;

export interface FitFont {
  fontFamily: string;
  fontWeight: number | string;
  fontStyle?: string;
}

export function measureTextWidth(
  text: string,
  fontSize: number,
  font: FitFont,
): number {
  if (typeof document === "undefined") {
    return text.length * fontSize * FALLBACK_CHAR_WIDTH_RATIO;
  }
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return text.length * fontSize * FALLBACK_CHAR_WIDTH_RATIO;
  }
  const style = font.fontStyle ? `${font.fontStyle} ` : "";
  ctx.font = `${style}${font.fontWeight} ${fontSize}px ${font.fontFamily}`;
  return ctx.measureText(text).width;
}

/**
 * Return a fontSize ≤ requestedFontSize that will render `text` within
 * `maxWidth` (with the small FIT_MARGIN safety factor). Never enlarges.
 */
export function fitFontSize(
  text: string,
  requestedFontSize: number,
  maxWidth: number,
  font: FitFont,
): number {
  if (!text || requestedFontSize <= 0 || maxWidth <= 0) return requestedFontSize;
  const naturalWidth = measureTextWidth(text, requestedFontSize, font);
  const budget = maxWidth * FIT_MARGIN;
  if (naturalWidth <= budget) return requestedFontSize;
  return requestedFontSize * (budget / naturalWidth);
}
