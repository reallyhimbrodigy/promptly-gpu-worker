import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface LowerThirdProps extends MGTimingProps, MGPositionProps {
  // Speaker name. Broadcast budget: ≤ 26 characters (incl. spaces).
  // Longer text won't wrap — it will extend past the safe zone as a signal
  // to shorten the text in the edit, per broadcast/editorial convention.
  name: string;
  // Role / affiliation. Broadcast budget: ≤ 40 characters (incl. spaces).
  // Same no-wrap rule as `name`.
  title: string;
  // Drives the accent bar on the card's leading edge.
  accentColor?: string;
  // Optional circular avatar rendered to the left of the card.
  avatarSrc?: string;
  // "dark" (default) → ink-black gradient card with white/grey text.
  // "light" → cream/bone gradient card with warm ink-black text.
  theme?: "dark" | "light";
}
