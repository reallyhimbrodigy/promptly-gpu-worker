/**
 * Coerce a text prop that TypeScript believes is required.
 *
 * WHY THIS EXISTS (RENDER_REMOTION:component_crash, job 22070e6d — PromptlyOverlay,
 * `.split` of undefined): every one of these props is typed `text: string` /
 * `title: string` / `caption: string`, so TypeScript says they cannot be
 * undefined. They arrive as JSON from Gemini via the Python pipeline, where
 * Vertex OMITS optional fields entirely — and TS types are erased at runtime, so
 * the renderer trusts a guarantee nothing enforces and calls `.split` on
 * undefined. The whole render dies for one missing string.
 *
 * Same lesson as SafeImg and the crossfade survivor: a missing asset DEGRADES,
 * it does not take the video with it. An empty string flows into each
 * component's existing empty-guard, which renders nothing for that layer and
 * leaves the rest of the frame intact.
 */
export const asText = (v: unknown): string =>
  typeof v === "string" ? v : v == null ? "" : String(v);
