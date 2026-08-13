import type { MGTimingProps } from "../shared/types";

// [§3.1 component F] The end-card / brand system.
//
// REF-1 closes with CTA card (URL, phone, email) -> logo sting -> social-handle
// cards. REF-2 closes with a stylised echo outro. Both END DELIBERATELY; neither
// just stops. An edit that stops is an edit that ran out, and the reference set
// says the close is part of the craft.
//
// PALETTE LOCK [§4.2]: the palette is passed IN, generated per video from the
// footage and the brand — it is never a constant in this file. That is the
// no-templating line: the end-card RENDERER is a tool; two videos produce two
// different end cards because their palettes and their content differ. A
// hardcoded palette here would make it canned creative.
export type EndCardKind = "cta" | "logo_sting" | "social" | "echo";

export interface EndCardLine {
  // e.g. "legalsoft.com" / "@promptly" / "hello@x.com"
  text: string;
  // Optional leading glyph name the renderer maps to an icon (globe, phone,
  // mail, at). Absent = text only; never invents an icon.
  icon?: "globe" | "phone" | "mail" | "at";
}

export interface EndCardProps extends MGTimingProps {
  kind: EndCardKind;
  // The headline for cta/echo; the wordmark text for logo_sting.
  title?: string;
  // Contact/handle lines. Ignored by logo_sting.
  lines?: EndCardLine[];
  // THE LOCKED PALETTE — 2-3 colours held for the whole edit (REF-1:
  // orange/blue/white). Passed from the plan, never defaulted per-card, so a
  // sequence of cards cannot drift colour mid-outro.
  palette: { bg: string; fg: string; accent: string };
  // Logo asset URL for the sting. Absent -> wordmark from `title`, which is the
  // honest fallback rather than a placeholder mark.
  logoUrl?: string;
}
