import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface QuoteCardProps extends MGTimingProps, MGPositionProps {
  quote: string;
  // e.g. "Steve Jobs, 2005" — rendered beneath the quote, prefixed with em-dash.
  attribution: string;
  // "dark" (default) → ink-black gradient card with warm cream type.
  // "light" → cream/bone gradient card with warm ink type.
  theme?: "dark" | "light";
  // Optional solid card color override (disables the theme gradient).
  cardColor?: string;
  // Quote text color. Defaults to the theme's title color.
  quoteColor?: string;
  // Attribution color. Defaults to the theme's attribution color.
  attributionColor?: string;
  // Color of the oversized decorative quote mark. Default warm cream
  // ("#F2E9D6") on dark, warm rust ("#C8551F") on light.
  accentColor?: string;
  // Defaults to Playfair Display.
  quoteFont?: string;
  // Default 64. Callers can shrink for longer quotes.
  quoteFontSize?: number;
  // Card width in pixels. Default 918 (~85% of 1080 frame).
  width?: number;
}
