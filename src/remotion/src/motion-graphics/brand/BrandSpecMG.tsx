/**
 * THE SIXTH LINK — brand spec dicts become PIXELS.
 *
 * Components D (name-plate) and F (end-card) are produced by
 * `brand_components.py` as SPEC DICTS, not as component props: the producer is
 * pure and deterministic, it certs offline for $0, and every value in it comes
 * from `edit_plan["_design_system"]`. Those dicts have never matched the props
 * `NamePlate` / `EndCard` declare, and `MG_MAP` had no key for either name — so
 * asking for a name-plate moved a liveness counter and produced nothing. This
 * module is the mapping that closes it, and it lives HERE rather than in
 * handler.py for one reason: the component's prop shape is the renderer's
 * business, and a Python file that knows it is a fourth schema mirror waiting to
 * drift (this repo already lost `motionTokens` to a mirror it forgot about).
 *
 * THE CONTRACT WITH THE HANDLER, exactly:
 *
 *   motion_graphics_out.append({
 *       "type": "NamePlate",          # or "EndCard"
 *       "fromFrame": <output frames>, # OUTPUT clock, not source
 *       "durationInFrames": <frames>,
 *       "props": <the spec dict from edit_plan["_brand_specs"]>,
 *   })
 *
 * `props` is the SPEC, verbatim. `MotionGraphicRenderer` then supplies
 * `startMs=0` + `durationMs` from the Sequence window and spreads the spec over
 * it, so `start_s` / `hold_s` are the HANDLER's job (they become fromFrame and
 * durationInFrames) and never reach this file. That split is deliberate: the
 * component window is a `<Sequence>`, and a component that also tried to place
 * itself in time would be doing the same math twice on two different clocks.
 *
 * EVERY STYLE FIELD IS SPENT. `style` is the design system's resolved output —
 * dropping one silently is how a plate renders in an invented colour or a
 * hundred-screen-tall type size. The two maps below are the whole mapping, and
 * `brand-mg-wiring.test.mjs` DERIVES the expected key set straight out of
 * brand_components.py and fails if either side gains or loses a field. There is
 * no hand-typed list of style keys anywhere in the gate.
 */
import React from "react";
import { NamePlate } from "../NamePlate";
import { EndCard } from "../EndCard";
import type { EndCardKind, EndCardLine } from "../EndCard";
import type { MGTimingProps } from "../shared/types";

// ── The style mapping, machine-readable ─────────────────────────────────────
// brand_components.build_name_plate -> NamePlateProps. Keys are the `style`
// fields the producer emits; values are the component props they land on.
export const NAME_PLATE_STYLE_MAP = {
  name_px: "namePx",
  role_px: "rolePx",
  color: "nameColor",
  accent: "accentColor",
  backdrop: "backdropColor",
} as const;

// brand_components.build_end_card -> EndCardProps. The card INVERTS (the
// producer's own note): the accent becomes the FIELD, `color` is the text the
// palette already proved contrasts against it, and `rule` is the underline.
export const END_CARD_STYLE_MAP = {
  background: "palette.bg",
  headline_px: "titlePx",
  subline_px: "linePx",
  color: "palette.fg",
  rule: "palette.accent",
} as const;

// ── Spec shapes, as they arrive over JSON ───────────────────────────────────
// Every field is nullable because Python emits `None` for "not supplied" and
// Vertex omits optional fields outright — the exact pair of habits `asText`
// exists for. Typing them as required here would be a guarantee nothing
// enforces.
type Num = number | null | undefined;
type Str = string | null | undefined;

export interface NamePlateSpec extends Partial<MGTimingProps> {
  kind?: Str;
  name?: Str;
  role?: Str;
  style?: {
    name_px?: Num; role_px?: Num;
    color?: Str; accent?: Str; backdrop?: Str;
  } | null;
  /** Producer emits `{x_fraction, y_fraction}`; the handler's MG normalization
   *  and the band composer may instead have written an MGAnchor string here. */
  anchor?: { x_fraction?: Num; y_fraction?: Num } | string | null;
  safe?: { doctrine?: Str; x?: number[] | null; y?: number[] | null } | null;
  source?: Str;
}

export interface EndCardSpec extends Partial<MGTimingProps> {
  kind?: Str;
  headline?: Str;
  subline?: Str;
  style?: {
    background?: Str; headline_px?: Num; subline_px?: Num;
    color?: Str; rule?: Str;
  } | null;
  safe?: { doctrine?: Str; x?: number[] | null; y?: number[] | null } | null;
  source?: Str;
  /** Optional overrides the handler may add later. `cardKind` picks the close's
   *  register (cta / logo_sting / social / echo); `logoUrl` turns it into a
   *  sting. Neither is invented here — absent means the default close. */
  cardKind?: Str;
  logoUrl?: Str;
}

// ── Helpers ─────────────────────────────────────────────────────────────────
const px = (v: Num): number | undefined =>
  typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.round(v) : undefined;

const str = (v: Str): string | undefined => {
  if (typeof v !== "string") return undefined;
  const t = v.trim();
  return t.length ? t : undefined;
};

/** `safe.x` is `[left, right]` in the design system's own canvas px. Only the
 *  left inset is a margin; the component clamps it against the frame it is
 *  actually rendering, so a design system built for another canvas degrades to
 *  a sane inset instead of pushing text off-screen. */
const safeInsetPx = (safe: NamePlateSpec["safe"]): number | undefined => {
  const x = safe && Array.isArray(safe.x) ? safe.x : null;
  const v = x && typeof x[0] === "number" && Number.isFinite(x[0]) ? x[0] : null;
  return v === null || v < 0 ? undefined : Math.round(v);
};

/** Three anchor vocabularies reach this prop and all three are legitimate:
 *  the producer's `{y_fraction}`, the MGAnchor string the handler merges into
 *  every MG's props, and the band the composer may have relocated it to. Any of
 *  them must resolve; an unknown value keeps the reference plate's home rather
 *  than guessing. */
const resolveThird = (
  anchor: NamePlateSpec["anchor"],
): "lower_third_safe" | "upper_third_safe" => {
  if (typeof anchor === "string") {
    if (anchor === "upper_third_safe") return "upper_third_safe";
    if (anchor === "lower_third_safe") return "lower_third_safe";
    // MGAnchor vocabulary (types.ts): top* sits in the upper third.
    if (anchor === "top" || anchor === "top-left" || anchor === "top-right") {
      return "upper_third_safe";
    }
    return "lower_third_safe";
  }
  const yf = anchor && typeof anchor.y_fraction === "number" ? anchor.y_fraction : null;
  if (yf !== null && Number.isFinite(yf)) {
    return yf < 0.5 ? "upper_third_safe" : "lower_third_safe";
  }
  return "lower_third_safe";
};

// ── The adapters — what MG_MAP dispatches ───────────────────────────────────

/**
 * NO NAME -> NO PLATE. The producer already refuses to build a spec without a
 * name; this is the second half of the same rule, because the spec can also
 * reach us from a `render_only` replay of a stored plan. A coloured rule with
 * no text is worse than nothing.
 */
export const NamePlateMG: React.FC<NamePlateSpec> = (spec) => {
  const name = str(spec.name);
  if (!name) return null;
  const style = spec.style || {};
  return (
    <NamePlate
      startMs={spec.startMs ?? 0}
      durationMs={spec.durationMs ?? 0}
      enterFrames={spec.enterFrames}
      exitFrames={spec.exitFrames}
      name={name}
      role={str(spec.role)}
      namePx={px(style.name_px)}
      rolePx={px(style.role_px)}
      nameColor={str(style.color)}
      accentColor={str(style.accent)}
      backdropColor={str(style.backdrop)}
      sideMarginPx={safeInsetPx(spec.safe)}
      anchor={resolveThird(spec.anchor)}
    />
  );
};

/**
 * NO HEADLINE -> NO CARD, for the same reason: the close is the last thing on
 * screen and the only moment the edit is allowed to be still. A still frame in
 * a brand colour with nothing written on it is a defect, not a close.
 *
 * `kind` defaults to "cta" — the producer's spec carries `kind: "end_card"`
 * (WHICH component it is), not an EndCardKind (which REGISTER the close plays
 * in). "cta" renders headline + subline + rule, which is exactly the shape the
 * producer emits; the other registers need copy the producer does not build.
 */
export const EndCardMG: React.FC<EndCardSpec> = (spec) => {
  const headline = str(spec.headline);
  if (!headline) return null;
  const style = spec.style || {};
  // FAIL CLOSED ON A PARTIAL PALETTE. The card is the one moment a brand colour
  // owns the whole frame, so a defaulted colour here is an INVENTED BRAND filling
  // 100% of the pixels — strictly worse than closing without a card, which is
  // what a missing design system already produces. Same rule as the producer's
  // "NO DESIGN SYSTEM -> NO COMPONENT".
  const field = str(style.background);
  const ink = str(style.color);
  const rule = str(style.rule);
  if (!field || !ink || !rule) return null;
  const subline = str(spec.subline);
  // Never invents an icon (EndCardLine's own rule) — text only.
  const lines: EndCardLine[] = subline ? [{ text: subline }] : [];
  const kind = (["cta", "logo_sting", "social", "echo"] as const).includes(
    (spec.cardKind || "") as EndCardKind,
  )
    ? (spec.cardKind as EndCardKind)
    : "cta";
  return (
    <EndCard
      startMs={spec.startMs ?? 0}
      durationMs={spec.durationMs ?? 0}
      enterFrames={spec.enterFrames}
      exitFrames={spec.exitFrames}
      kind={kind}
      title={headline}
      lines={lines}
      titlePx={px(style.headline_px)}
      linePx={px(style.subline_px)}
      sideMarginPx={safeInsetPx(spec.safe)}
      logoUrl={str(spec.logoUrl)}
      // THE LOCKED PALETTE, inverted per the producer: the accent is the field.
      palette={{ bg: field, fg: ink, accent: rule }}
    />
  );
};
