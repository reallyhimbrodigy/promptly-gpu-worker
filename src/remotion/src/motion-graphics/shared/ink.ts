// Partner-tracking ink (coupled-defaults audit, 2026-08-26): a text-color
// default authored for a surface-color default must not survive a
// surface-only override (white-on-light / dark-on-dark). Components derive
// unspecified ink from the ACTUAL surface via inkFor; explicit overrides
// always pass through. React-free (gate-importable).

/** WCAG relative luminance of a #rgb/#rrggbb/rgb()/rgba() color; 0 for
 *  anything unparseable (treat unknown surfaces as dark — light ink). */
export function relativeLuminance(color: string): number {
  let r = 0, g = 0, b = 0;
  const hex = color.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  const fn = color.match(/^rgba?\(([^)]+)\)$/i);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    r = parseInt(h.slice(0, 2), 16);
    g = parseInt(h.slice(2, 4), 16);
    b = parseInt(h.slice(4, 6), 16);
  } else if (fn) {
    const parts = fn[1].split(",").map((p) => parseFloat(p));
    [r, g, b] = [parts[0] || 0, parts[1] || 0, parts[2] || 0];
  } else {
    return 0;
  }
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** Ink that reads on the given surface: dark ink on light surfaces, light
 *  ink on dark ones. */
export function inkFor(
  surface: string,
  dark = "#15151E",
  light = "#FFFFFF",
): string {
  return relativeLuminance(surface) > 0.5 ? dark : light;
}

/** True when the surface is light (for muted/secondary ink pairs). */
export function isLightSurface(surface: string): boolean {
  return relativeLuminance(surface) > 0.5;
}
