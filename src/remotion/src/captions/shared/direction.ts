// MULTILINGUAL A2.2 — caption text direction (RTL support).
//
// The contact sheet proved the shaping is perfect (A1 Noto fonts + HarfBuzz):
// Arabic joins, lam-alef ligates, Hebrew niqqud attaches — zero tofu. The ONE
// remaining defect was WORD ORDER: every caption lays its words out as separate
// inline-block spans in a flex row, and each span is an atomic bidi box, so the
// row flows in the container's `direction` — which defaulted to ltr. Arabic and
// Hebrew captions therefore read left-to-right (first word leftmost) instead of
// right-to-left.
//
// The fix is structural, not per-component: set `direction` on the single
// wrapper that every caption renders inside (CaptionSegmentRenderer in
// production, FitSpecimen in the battery). `direction` is inherited, and a
// `flex-direction: row` container lays its items along the main axis per its
// own (inherited) direction — so under rtl the first word lands rightmost, in
// every one of the 9 caption components at once. Physical `left`/`translateX`
// centering is unaffected; ltr captions get `direction: "ltr"` (a no-op), so
// every existing Latin render stays byte-identical.

// Strong-RTL scripts (Unicode script property). Hebrew + Arabic cover ~all UGC
// RTL; the rest are included for correctness so a Syriac/Thaana/N'Ko/Adlam
// caption is not silently laid out backwards.
const RTL_LETTER =
  /[\p{sc=Hebrew}\p{sc=Arabic}\p{sc=Syriac}\p{sc=Thaana}\p{sc=Nko}\p{sc=Samaritan}\p{sc=Mandaic}\p{sc=Adlam}]/u;
const ANY_LETTER = /\p{L}/u;

/**
 * Direction of a caption string by the Unicode paragraph-direction heuristic
 * (UBA rule P2/P3, the same rule as HTML `dir="auto"`): the direction is set
 * by the FIRST strong-directional LETTER. Digits, punctuation, whitespace and
 * emoji are skipped (they are direction-neutral), so "🔥 مرحبا" is rtl and
 * "Let's go🔥" is ltr. Single-language captions — the overwhelming common case
 * — are classified by their script; a mixed caption follows its opening word,
 * which is what a reader expects.
 */
export const captionDirection = (text: string): "ltr" | "rtl" => {
  for (const ch of text) {
    if (RTL_LETTER.test(ch)) return "rtl";
    if (ANY_LETTER.test(ch)) return "ltr";
  }
  return "ltr";
};

/** Direction across a set of token texts (the words actually rendered). */
export const pagesDirection = (
  pages: { tokens?: { text?: string }[] }[],
): "ltr" | "rtl" => {
  for (const page of pages) {
    for (const tok of page.tokens ?? []) {
      if (tok.text) {
        const d = captionDirection(tok.text);
        // First token that carries a strong letter decides the caption.
        if (ANY_LETTER.test(tok.text)) return d;
      }
    }
  }
  return "ltr";
};
