// Pure script-detection + routing decisions (React/Remotion-free so the
// gate — mg-text-font.test.mjs — imports the shipped module directly).
// The face-name resolution lives in text-font.ts.

export type MGScript =
  | "latin"
  | "devanagari"
  | "bengali"
  | "telugu"
  | "arabic"
  | "cyrillic"
  | "cjk";

const RANGES: [MGScript, RegExp][] = [
  ["devanagari", /[ऀ-ॿ]/],
  ["bengali", /[ঀ-৿]/],
  ["telugu", /[ఀ-౿]/],
  ["arabic", /[؀-ۿݐ-ݿ]/],
  ["cyrillic", /[Ѐ-ӿ]/],
  ["cjk", /[一-鿿぀-ヿ가-힯]/],
];

export function detectScript(text: string): MGScript {
  for (const [script, re] of RANGES) {
    if (re.test(text)) return script;
  }
  return "latin";
}

// Faces that genuinely cover Cyrillic (loaded with cyrillic subsets in
// fonts.ts). Display faces (Anton/serifs/CaveatBrush) have none — Cyrillic
// display text routes to Oswald, the closest condensed voice.
const CYRILLIC_CAPABLE = new Set<string>(["inter", "oswald", "roboto"]);

const SCRIPT_FACE_KEY: Partial<Record<MGScript, string>> = {
  devanagari: "notoSansDevanagari",
  bengali: "notoSansBengali",
  telugu: "notoSansTelugu",
  arabic: "notoSansArabic",
};

/** Which census face KEY should render this text. CJK keeps the preferred
 *  face (no loaded CJK face by coordinator ruling — flagged, falls back). */
export function routeFaceKey(text: string, preferredKey: string): string {
  const script = detectScript(text);
  if (script === "cyrillic" && !CYRILLIC_CAPABLE.has(preferredKey)) {
    return "oswald";
  }
  return SCRIPT_FACE_KEY[script] ?? preferredKey;
}

/** Non-Latin scripts need more vertical room (matras/hooks) and no
 *  uppercase transform; autofits need a safe advance estimate. The numbers
 *  are the render-proven conservative estimates from passes #7b/#9. */
export function mgTextMetrics(text: string): {
  script: MGScript;
  lineHeight: number;
  uppercaseSafe: boolean;
  advanceEm: number;
} {
  const script = detectScript(text);
  const nonLatin = script !== "latin";
  return {
    script,
    lineHeight: nonLatin ? 1.3 : 1.0,
    uppercaseSafe: !nonLatin,
    advanceEm: script === "latin" ? 0.62 : 0.42,
  };
}
