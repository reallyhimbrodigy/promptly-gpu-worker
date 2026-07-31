// ---------------------------------------------------------------------------
// Caption width-fit GUARANTEE (F4 launch blocker) — SINGLE SHARED LAYER.
// ---------------------------------------------------------------------------
//
// Every caption style and free-form text overlay lays its page out through
// fitPage(). The contract: rendered text NEVER crosses the horizontal safe
// margins — no dropped captions, no hidden text, no position jumps. The
// block stays where the style puts it; it wraps more or renders smaller.
//
// Fit ladder (identity-preserving, in order):
//   a. RE-WRAP at the style's own base size, on word boundaries, up to
//      maxLines (fit beats the style's words-per-line preference).
//   b. SCALE: still overflowing -> largest uniform fontSize scale in
//      [MIN_FIT_SCALE, 1] whose greedy wrap fits within maxLines.
//   c. CHARWRAP (pathological single word wider than the safe width even
//      at floor scale): character-level split of that word. Lines may
//      exceed maxLines at floor scale before we ever cross a margin.
//
// Measurement is canvas.measureText against the loaded @remotion/google-fonts
// families (Remotion's loadFont() delays rendering until fonts are ready, so
// measurements at render time see the real font). letterSpacing is added
// manually (canvas ignores CSS letter-spacing; Chromium's ctx.letterSpacing
// is used when present, and the manual path covers the rest).
//
// SAFE_TEXT_WIDTH derives from the safe-zone single source of truth
// (TIKTOK_SAFE_SIDE); a style with a stricter own box (e.g. centered styles
// inset 200px both sides) passes that box in and the min() wins.

import type { CSSProperties } from "react";
import { CANVAS_WIDTH, TIKTOK_SAFE_SIDE } from "../../shared/safeZone";

export const H_TEXT_MARGIN = TIKTOK_SAFE_SIDE; // 80 — one source of truth
export const SAFE_TEXT_WIDTH = CANVAS_WIDTH - 2 * H_TEXT_MARGIN; // 920
export const MIN_FIT_SCALE = 0.6;

export interface FitFont {
  fontFamily: string;
  fontWeight: number | string;
  /** em units, e.g. 0.02 for "0.02em". Applied per character, trailing included
   *  (matches CSS letter-spacing on an inline-block span). */
  letterSpacingEm?: number;
  uppercase?: boolean;
  /** Models textTransform:lowercase (Prime) — caps input measured as caps
   *  over-measures the lowercase glyphs actually rendered. */
  lowercase?: boolean;
}

export interface FitRequest {
  words: string[]; // raw token texts, in order
  baseFontSize: number;
  font: FitFont;
  /** px gap between words on a line (flex gap). Does not scale with font. */
  wordGap: number;
  /** Style's preferred words per line (count-based look). 0/undefined = flow. */
  preferredWordsPerLine?: number;
  /** Hard-ish line budget for steps a+b; step c may exceed it at floor scale. */
  maxLines: number;
  /** The style's own available box width; min()'d with SAFE_TEXT_WIDTH. */
  availableWidth: number;
}

export interface FitEntry {
  /** Index into the original tokens array — timing/keyword identity. */
  tokenIndex: number;
  /** Display text: the whole word, or a charwrap fragment of it. */
  text: string;
}

export interface FitResult {
  lines: FitEntry[][];
  fontSize: number;
  scale: number;
  action: "none" | "wrap" | "scale" | "charwrap";
  safeWidth: number;
  /** Widest line at the final size — re-measured, for the invariant. */
  measuredWidth: number;
}

// ── measurement ─────────────────────────────────────────────────────────────

let _ctx: CanvasRenderingContext2D | null | undefined;
const _measureCache = new Map<string, number>();

function getCtx(): CanvasRenderingContext2D | null {
  if (_ctx !== undefined) return _ctx;
  try {
    const canvas = document.createElement("canvas");
    _ctx = canvas.getContext("2d");
  } catch {
    _ctx = null; // non-DOM context (unit tests) — callers inject a measurer
  }
  return _ctx;
}

export type WordMeasurer = (word: string, fontSize: number, font: FitFont) => number;

export const canvasMeasurer: WordMeasurer = (word, fontSize, font) => {
  const text = font.uppercase
    ? word.toUpperCase()
    : font.lowercase
      ? word.toLowerCase()
      : word;
  const spacingPx = (font.letterSpacingEm ?? 0) * fontSize;
  const key = `${font.fontFamily}|${font.fontWeight}|${fontSize}|${spacingPx}|${text}`;
  const hit = _measureCache.get(key);
  if (hit !== undefined) return hit;
  const ctx = getCtx();
  if (!ctx) return text.length * fontSize * 0.62 + spacingPx * text.length; // crude non-DOM fallback
  ctx.font = `${font.fontWeight} ${fontSize}px ${font.fontFamily}`;
  // Chromium supports ctx.letterSpacing; when present it handles spacing
  // (including the trailing space CSS adds). Otherwise add it manually.
  const anyCtx = ctx as CanvasRenderingContext2D & { letterSpacing?: string };
  let width: number;
  if ("letterSpacing" in anyCtx) {
    anyCtx.letterSpacing = `${spacingPx}px`;
    width = ctx.measureText(text).width;
  } else {
    width = ctx.measureText(text).width + spacingPx * text.length;
  }
  _measureCache.set(key, width);
  return width;
};

// ── ladder internals ────────────────────────────────────────────────────────

function lineWidth(
  entries: FitEntry[],
  fontSize: number,
  font: FitFont,
  wordGap: number,
  measure: WordMeasurer,
): number {
  let w = 0;
  for (let i = 0; i < entries.length; i++) {
    if (i > 0) w += wordGap;
    w += measure(entries[i].text, fontSize, font);
  }
  return w;
}

/** Greedy word-boundary wrap at a given size. Never splits words. */
function greedyWrap(
  words: string[],
  fontSize: number,
  font: FitFont,
  wordGap: number,
  safeWidth: number,
  measure: WordMeasurer,
): FitEntry[][] {
  const lines: FitEntry[][] = [];
  let line: FitEntry[] = [];
  let w = 0;
  words.forEach((word, tokenIndex) => {
    const ww = measure(word, fontSize, font);
    const extra = line.length > 0 ? wordGap + ww : ww;
    if (line.length > 0 && w + extra > safeWidth) {
      lines.push(line);
      line = [{ tokenIndex, text: word }];
      w = ww;
    } else {
      line.push({ tokenIndex, text: word });
      w += extra;
    }
  });
  if (line.length > 0) lines.push(line);
  return lines;
}

// Grapheme-cluster split of a string. `for...of` over a string iterates code
// POINTS, which still severs a Devanagari/Tamil/Thai syllable (a base letter
// plus its combining vowel signs / virama conjuncts is ONE user-perceived
// character spread across several code points) and ZWJ emoji sequences — the
// fragments render as visibly broken glyphs. Intl.Segmenter groups by grapheme
// cluster so every fragment is a whole character. It is present in the Chromium
// that renders these compositions; the code-point fallback only runs if it
// somehow is not (still strictly better than the old code-unit behavior).
const _graphemeSeg =
  typeof Intl !== "undefined" && (Intl as any).Segmenter
    ? new (Intl as any).Segmenter(undefined, { granularity: "grapheme" })
    : null;
function toGraphemes(word: string): string[] {
  if (_graphemeSeg) {
    return Array.from(_graphemeSeg.segment(word), (s: any) => s.segment);
  }
  return Array.from(word);
}

/** Grapheme-level split of one word so every fragment fits safeWidth. */
function charwrapWord(
  word: string,
  tokenIndex: number,
  fontSize: number,
  font: FitFont,
  safeWidth: number,
  measure: WordMeasurer,
): FitEntry[] {
  const frags: FitEntry[] = [];
  let frag = "";
  for (const ch of toGraphemes(word)) {
    const next = frag + ch;
    if (frag.length > 0 && measure(next, fontSize, font) > safeWidth) {
      frags.push({ tokenIndex, text: frag });
      frag = ch;
    } else {
      frag = next;
    }
  }
  if (frag.length > 0) frags.push({ tokenIndex, text: frag });
  return frags;
}

function fitsWithin(
  lines: FitEntry[][],
  fontSize: number,
  font: FitFont,
  wordGap: number,
  safeWidth: number,
  measure: WordMeasurer,
): boolean {
  return lines.every(
    (l) => lineWidth(l, fontSize, font, wordGap, measure) <= safeWidth,
  );
}

function widestLine(
  lines: FitEntry[][],
  fontSize: number,
  font: FitFont,
  wordGap: number,
  measure: WordMeasurer,
): number {
  let max = 0;
  for (const l of lines) {
    const w = lineWidth(l, fontSize, font, wordGap, measure);
    if (w > max) max = w;
  }
  return max;
}

// ── the guarantee ───────────────────────────────────────────────────────────

const _loggedPages = new Set<string>();

// ── uniform page scale for CSS-wrapping styles ──────────────────────────────
//
// Styles whose lines already wrap via CSS (flexWrap / pre-wrap / break-word)
// can only overflow when a SINGLE rendered word is wider than the box — e.g.
// keyword multipliers (×1.25–×1.8) or display sizes (Quintessence 160px).
// fitScale() measures every word at ITS OWN rendered size/font and returns
// the largest uniform scale ≤ 1 that brings the widest word inside the safe
// width. Below MIN_FIT_SCALE it clamps to the floor and reports floored=true
// — the style then applies its character-break CSS fallback so the guarantee
// holds even for pathological unbroken strings.

export interface ScaleFitPart {
  text: string;
  fontSize: number;
  font: FitFont;
}

export interface ScaleFitItem {
  /** One unbreakable run (a nowrap line, or a single word). Width = Σ parts. */
  parts: ScaleFitPart[];
  /** Fixed px riding on the run (gaps/margins/paddings) that do NOT scale. */
  extraPx?: number;
}

export interface ScaleFitResult {
  scale: number;
  floored: boolean;
}

export function fitScale(
  items: ScaleFitItem[],
  availableWidth: number,
  styleName: string,
  measure: WordMeasurer = canvasMeasurer,
): ScaleFitResult {
  const safeWidth = Math.min(availableWidth, SAFE_TEXT_WIDTH);
  let scale = 1;
  let widestText = "";
  for (const item of items) {
    let textPx = 0;
    for (const p of item.parts) textPx += measure(p.text, p.fontSize, p.font);
    const extraPx = item.extraPx ?? 0;
    if (textPx + extraPx > safeWidth) {
      // Fixed extras don't scale with the font: solve s·textPx + extraPx ≤ safe.
      const s = textPx > 0 ? Math.max(0, (safeWidth - extraPx) / textPx) : 0;
      if (s < scale) {
        scale = s;
        widestText = item.parts.map((p) => p.text).join(" ");
      }
    }
  }
  const floored = scale < MIN_FIT_SCALE;
  if (floored) scale = MIN_FIT_SCALE;
  if (scale < 1) {
    const logKey = `${styleName}|${widestText}|fitScale|${scale.toFixed(2)}|${floored}`;
    if (!_loggedPages.has(logKey)) {
      _loggedPages.add(logKey);
      console.log(
        `[caption-fit] style=${styleName} page="${widestText}" action=${
          floored ? "charwrap" : `scale(${scale.toFixed(2)})`
        }`,
      );
    }
  }
  return { scale, floored };
}

/** Char-break CSS fallback for floored fits — the absolute last resort that
 *  makes the guarantee hold for pathological unbroken strings. Spread into a
 *  word span's style; pairs with the container's own maxWidth. */
export const CHARWRAP_FALLBACK_STYLE: CSSProperties = {
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
};

export function fitPage(
  req: FitRequest,
  styleName: string,
  measure: WordMeasurer = canvasMeasurer,
): FitResult {
  const { words, baseFontSize, font, wordGap, maxLines } = req;
  const safeWidth = Math.min(req.availableWidth, SAFE_TEXT_WIDTH);
  const pageText = words.join(" ");

  const finish = (
    lines: FitEntry[][],
    fontSize: number,
    action: FitResult["action"],
  ): FitResult => {
    let measuredWidth = widestLine(lines, fontSize, font, wordGap, measure);
    let scale = fontSize / baseFontSize;
    // INVARIANT: measured ≤ safe. A violation throws under strict mode
    // (battery / dev); in prod it clamps the scale and logs — never overflow.
    if (measuredWidth > safeWidth + 0.5) {
      const strict =
        typeof globalThis !== "undefined" &&
        (globalThis as { REMOTION_FIT_STRICT?: boolean }).REMOTION_FIT_STRICT;
      const msg =
        `[caption-fit] INVARIANT VIOLATION style=${styleName} ` +
        `page="${pageText}" measured=${measuredWidth.toFixed(1)} safe=${safeWidth}`;
      if (strict) throw new Error(msg);
      console.error(msg);
      const clamp = safeWidth / measuredWidth;
      fontSize = fontSize * clamp;
      scale = fontSize / baseFontSize;
      measuredWidth = widestLine(lines, fontSize, font, wordGap, measure);
    }
    if (action !== "none") {
      const logKey = `${styleName}|${pageText}|${action}|${scale.toFixed(2)}`;
      if (!_loggedPages.has(logKey)) {
        _loggedPages.add(logKey);
        const detail = action === "scale" ? `scale(${scale.toFixed(2)})` : action;
        console.log(
          `[caption-fit] style=${styleName} page="${pageText}" action=${detail}`,
        );
      }
    }
    return { lines, fontSize, scale, action, safeWidth, measuredWidth };
  };

  // Preferred layout: the style's count-based look, unchanged when it fits.
  const perLine =
    req.preferredWordsPerLine && req.preferredWordsPerLine > 0
      ? req.preferredWordsPerLine
      : words.length;
  const preferred: FitEntry[][] = [];
  for (let i = 0; i < words.length; i += perLine) {
    preferred.push(
      words.slice(i, i + perLine).map((text, j) => ({ tokenIndex: i + j, text })),
    );
  }
  if (
    preferred.length <= maxLines &&
    fitsWithin(preferred, baseFontSize, font, wordGap, safeWidth, measure)
  ) {
    return finish(preferred, baseFontSize, "none");
  }

  // (a) RE-WRAP at base size, word boundaries, within the line budget.
  const rewrapped = greedyWrap(words, baseFontSize, font, wordGap, safeWidth, measure);
  if (
    rewrapped.length <= maxLines &&
    fitsWithin(rewrapped, baseFontSize, font, wordGap, safeWidth, measure)
  ) {
    return finish(rewrapped, baseFontSize, "wrap");
  }

  // (b) SCALE: binary-search the largest scale in [floor, 1] that wraps
  // within the line budget with every line inside the safe width.
  let lo = MIN_FIT_SCALE;
  let hi = 1.0;
  let best: { lines: FitEntry[][]; scale: number } | null = null;
  for (let iter = 0; iter < 10; iter++) {
    const mid = (lo + hi) / 2;
    const size = baseFontSize * mid;
    const attempt = greedyWrap(words, size, font, wordGap, safeWidth, measure);
    const ok =
      attempt.length <= maxLines &&
      fitsWithin(attempt, size, font, wordGap, safeWidth, measure);
    if (ok) {
      best = { lines: attempt, scale: mid };
      lo = mid;
    } else {
      hi = mid;
    }
  }
  if (best) {
    return finish(best.lines, baseFontSize * best.scale, "scale");
  }

  // (c) FLOOR + CHARWRAP: at floor scale, split any word that alone exceeds
  // the safe width, then wrap freely (line budget yields before the margin).
  const floorSize = baseFontSize * MIN_FIT_SCALE;
  const pieces: FitEntry[] = [];
  words.forEach((word, tokenIndex) => {
    if (measure(word, floorSize, font) > safeWidth) {
      pieces.push(...charwrapWord(word, tokenIndex, floorSize, font, safeWidth, measure));
    } else {
      pieces.push({ tokenIndex, text: word });
    }
  });
  const lines: FitEntry[][] = [];
  let line: FitEntry[] = [];
  let w = 0;
  for (const piece of pieces) {
    const ww = measure(piece.text, floorSize, font);
    const extra = line.length > 0 ? wordGap + ww : ww;
    if (line.length > 0 && w + extra > safeWidth) {
      lines.push(line);
      line = [piece];
      w = ww;
    } else {
      line.push(piece);
      w += extra;
    }
  }
  if (line.length > 0) lines.push(line);
  const didSplit = pieces.length > words.length;
  return finish(lines, floorSize, didSplit ? "charwrap" : "scale");
}
