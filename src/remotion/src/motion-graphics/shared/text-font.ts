import { MG_FONTS } from "./fonts";
import { routeFaceKey } from "./text-script";

export { detectScript, mgTextMetrics } from "./text-script";
export type { MGScript } from "./text-script";

// mgTextFont — the coverage law generalized (catalogue font census,
// 2026-08-26: 52/52 user/model text sites were latin-only against traffic
// that is ~18% non-Latin + 7.5% emoji).
//
// Every USER/MODEL text site styles through this: detect the script by
// Unicode RANGE (the standing rule — never a language tag), route to a
// censused face that covers it, and always carry 'Noto Color Emoji' so
// emoji render by declaration, not fontconfig accident. Chrome literals
// (fixed English UI strings, digits) may keep bare MG_FONTS faces.
//
// CJK (1.0% of traffic) deliberately has NO loaded face (coordinator
// ruling: a Chinese face ~doubles the payload for 1%): CJK text keeps the
// preferred face and falls back — flagged for a separate ruling.

const EMOJI_TAIL = "'Noto Color Emoji', sans-serif";

/** Face + stack for a USER/MODEL text node. `preferred` is the design's
 *  latin face; non-Latin scripts route to a covering face. */
export function mgTextFont(
  text: string,
  preferred: keyof typeof MG_FONTS = "inter",
): string {
  const key = routeFaceKey(text, preferred) as keyof typeof MG_FONTS;
  const base = MG_FONTS[key] ?? MG_FONTS[preferred];
  return `${base}, ${EMOJI_TAIL}`;
}
