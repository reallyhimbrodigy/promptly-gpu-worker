/**
 * 8-direction text-shadow outline. Replaces `WebkitTextStroke` for any caption
 * style that combines a stroke with `transform: scale()` on the text element.
 *
 * Why this exists: Chromium rasterizes the WebkitTextStroke as a single
 * geometric outline along the letter contour. Under fractional `transform:
 * scale(s)` (mid-spring entrance), sub-pixel coverage at acute apex joins
 * (W, A, V, M apexes) doesn't sum to 1.0, leaving visible notch artifacts —
 * the "little triangles" above letterforms. text-shadow at 8 directions is
 * multi-sampled (8 overlapping copies of the glyph offset by `width`px),
 * so even if one copy has sub-pixel gaps, the other 7 cover for it. Net
 * appearance is sub-pixel-equivalent to a 1px stroke at fontSize 80+ but
 * survives any transform without apex artifacts.
 *
 * The diagonal offset is `width * √½ ≈ width * 0.7071` so the outline
 * radius is uniform in all 8 directions (cardinals + 45° diagonals).
 *
 * Returns a comma-joined `text-shadow` value string. Compose with other
 * shadows by concatenating: `${otherShadows}, ${textOutline(1, "...")}`.
 */
export function textOutline(width: number, color: string): string {
  const diag = (width * 0.7071).toFixed(3);
  return [
    `${width}px 0 0 ${color}`,
    `-${width}px 0 0 ${color}`,
    `0 ${width}px 0 ${color}`,
    `0 -${width}px 0 ${color}`,
    `${diag}px ${diag}px 0 ${color}`,
    `-${diag}px -${diag}px 0 ${color}`,
    `${diag}px -${diag}px 0 ${color}`,
    `-${diag}px ${diag}px 0 ${color}`,
  ].join(", ");
}
