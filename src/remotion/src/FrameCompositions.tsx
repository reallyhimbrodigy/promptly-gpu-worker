import React from "react";
import { AbsoluteFill, Freeze } from "remotion";
import { Video } from "@remotion/media";

// ── THE FOUR GENERATION-FREE COMPOSITIONS ───────────────────────────────────
//
// No image model, no Vertex call, no quota, no asset pipeline, no new
// dependency. Two are built on a frame of the USER'S OWN video; two are pure
// type. Every visual property arrives in a SPEC built by frame_compositions.py
// from the job's design system — a component that picks its own colour is a
// second design system competing with the real one (brand_components.py).
//
// FRAME-1-IS-FINAL. There is NO entrance animation anywhere in this file: no
// opacity ramp, no slide, no scale. The first frame is the final frame (the
// crisp-entrance law, 2026-07-13). An earlier draft of these components used a
// rise-and-fade and was wrong; the spec now carries `entrance: "none"` so the
// intent is explicit rather than inferred from the absence of code.
//
// §4 COMPOSITION: tilt 5-8 degrees, hard edge, real drop shadow — a physical
// object on a surface. Elements OVERLAP and OCCLUDE. "A stack of centred,
// non-overlapping boxes reads as a slide."

export interface FrameCompSpec {
  kind: string;
  bg: string; fg: string; accent: string;
  cap_px: number;
  tilt_deg: number;
  legibility: { shadow_offset_px: number; shadow_blur_px: number; shadow_opacity: number };
  at_seconds: number;
  duration_s: number;
  entrance: string;
  claim?: string; caption?: string; still_width_pct?: number;
  label?: string; shell_radius_px?: number; still_width_px?: number;
  value?: string; value_width_pct?: number; outline?: boolean;
  emoji?: string; words?: string[]; emoji_px?: number;
}

/** §2.4, from the spec's numbers — never a hardcoded shadow. */
const legible = (s: FrameCompSpec): React.CSSProperties => ({
  textShadow: `0 ${s.legibility.shadow_offset_px}px ${s.legibility.shadow_blur_px}px `
    + `rgba(0,0,0,${s.legibility.shadow_opacity})`,
});

/** ONE FROZEN FRAME OF THE USER'S OWN VIDEO, treated as a physical print. */
const SourceStill: React.FC<{
  sourceUrl: string; atSeconds: number; fps: number;
  tiltDeg?: number; style?: React.CSSProperties; label?: string;
}> = ({ sourceUrl, atSeconds, fps, tiltDeg = 0, style, label }) => {
  const frame = Math.max(0, Math.round((atSeconds || 0) * (fps || 30)));
  return (
    <div
      aria-label={label}
      style={{
        transform: `rotate(${tiltDeg}deg)`,
        boxShadow: "0 26px 60px rgba(16,16,20,0.34), 0 2px 6px rgba(16,16,20,0.22)",
        overflow: "hidden", background: "#000",
        ...style,
      }}
    >
      <Freeze frame={frame}>
        <Video src={sourceUrl} startFrom={frame} muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </Freeze>
    </div>
  );
};

/** EVIDENCE CARD — "here is the thing I just said, on screen." */
export const EvidenceCard: React.FC<{ spec: FrameCompSpec; sourceUrl: string; fps: number }> =
  ({ spec, sourceUrl, fps }) => (
    <AbsoluteFill style={{ background: spec.bg }}>
      {/* PLANE 1 — background type, cropped by the frame edge on purpose */}
      <div style={{
        position: "absolute", top: "12%", left: "-4%", right: "-4%",
        fontSize: spec.cap_px * 1.2, fontWeight: 800, lineHeight: 0.92,
        color: spec.fg, opacity: 0.14, letterSpacing: "-0.03em",
        textTransform: "uppercase",
      }}>{spec.claim}</div>
      {/* PLANE 2 — the user's own frame */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <SourceStill sourceUrl={sourceUrl} atSeconds={spec.at_seconds} fps={fps}
          tiltDeg={spec.tilt_deg} label="EvidenceCard.still"
          style={{ width: `${spec.still_width_pct ?? 58}%`, aspectRatio: "9 / 16" }} />
      </AbsoluteFill>
      {/* PLANE 3 — foreground type OVERLAPPING the still */}
      <div style={{
        position: "absolute", bottom: "16%", left: "6%", right: "10%",
        fontSize: spec.cap_px * 0.56, fontWeight: 800, color: spec.fg,
        lineHeight: 1.02, letterSpacing: "-0.02em", ...legible(spec),
      }}>
        <span style={{ boxShadow: `inset 0 -0.34em 0 ${spec.accent}55` }}>
          {spec.caption || spec.claim}
        </span>
      </div>
    </AbsoluteFill>
  );

/** DEVICE MOCKUP — the user's own frame inside a DRAWN shell (never an asset). */
export const DeviceMockup: React.FC<{ spec: FrameCompSpec; sourceUrl: string; fps: number }> =
  ({ spec, sourceUrl, fps }) => (
    <AbsoluteFill style={{ background: spec.bg }}>
      {spec.label ? (
        <div style={{
          position: "absolute", top: "9%", left: "6%",
          fontSize: spec.cap_px, fontWeight: 800, color: spec.accent,
          opacity: 0.16, letterSpacing: "-0.03em", textTransform: "uppercase",
        }}>{spec.label}</div>
      ) : null}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{
          padding: 14, borderRadius: spec.shell_radius_px ?? 46, background: "#0B0B0F",
          transform: `rotate(${spec.tilt_deg}deg)`,
          boxShadow: "0 34px 70px rgba(16,16,20,0.38), 0 2px 8px rgba(16,16,20,0.3)",
        }}>
          <SourceStill sourceUrl={sourceUrl} atSeconds={spec.at_seconds} fps={fps}
            label="DeviceMockup.still"
            style={{ width: spec.still_width_px ?? 430, aspectRatio: "9 / 16",
                     borderRadius: (spec.shell_radius_px ?? 46) - 12, boxShadow: "none" }} />
        </div>
      </AbsoluteFill>
      {spec.label ? (
        <div style={{
          position: "absolute", bottom: "14%", left: "8%",
          fontSize: spec.cap_px * 0.5, fontWeight: 800, color: spec.fg,
          letterSpacing: "-0.02em", ...legible(spec),
        }}>{spec.label}</div>
      ) : null}
    </AbsoluteFill>
  );

/** NUMBER CARD — REF-2's "$2,000,000": flat field, huge type, ZERO assets.
 *  Full-bleed, cropping off BOTH frame edges — that crop is what makes it read
 *  as designed rather than centred (§4). */
export const NumberCard: React.FC<{ spec: FrameCompSpec }> = ({ spec }) => (
  <AbsoluteFill style={{ background: spec.bg, justifyContent: "center" }}>
    <div style={{
      width: `${spec.value_width_pct ?? 118}%`, marginLeft: "-9%",
      textAlign: "center", fontWeight: 900,
      fontSize: spec.cap_px * 2.4, lineHeight: 0.86, color: spec.fg,
      letterSpacing: "-0.05em",
      WebkitTextStroke: spec.outline ? `3px ${spec.accent}` : undefined,
      ...legible(spec),
    }}>{spec.value}</div>
    {spec.label ? (
      <div style={{
        marginTop: spec.cap_px * 0.22, textAlign: "center",
        fontSize: spec.cap_px * 0.42, fontWeight: 700, color: spec.accent,
        letterSpacing: "0.06em", textTransform: "uppercase", ...legible(spec),
      }}>{spec.label}</div>
    ) : null}
  </AbsoluteFill>
);

/** EMOJI-AS-TYPE — REF-2's TOP SECRET folder: an emoji, a tilt, a shadow and
 *  two words. Noto Color Emoji is ALREADY in the image (the caption stack uses
 *  it), so this adds no font, no asset and no dependency. */
export const EmojiCard: React.FC<{ spec: FrameCompSpec }> = ({ spec }) => (
  <AbsoluteFill style={{ background: spec.bg, alignItems: "center",
                         justifyContent: "center" }}>
    <div style={{
      fontSize: spec.emoji_px ?? spec.cap_px * 3.2,
      transform: `rotate(${spec.tilt_deg}deg)`,
      filter: `drop-shadow(0 ${spec.legibility.shadow_offset_px * 6}px `
        + `${spec.legibility.shadow_blur_px * 5}px rgba(0,0,0,0.45))`,
      lineHeight: 1,
    }}>{spec.emoji}</div>
    {(spec.words || []).length ? (
      <div style={{
        marginTop: spec.cap_px * 0.3, display: "flex", gap: spec.cap_px * 0.22,
      }}>
        {(spec.words || []).map((w, i) => (
          <span key={i} style={{
            fontSize: spec.cap_px * 0.62, fontWeight: 900,
            color: i === 0 ? spec.fg : spec.accent,
            letterSpacing: "0.02em", textTransform: "uppercase", ...legible(spec),
          }}>{w}</span>
        ))}
      </div>
    ) : null}
  </AbsoluteFill>
);

// ── THE ADAPTERS — MG_MAP dispatches THESE, never the bare components ────────
// The NamePlate/EndCard precedent: registering a bare component renders a card
// with no content, because the spec's keys live in a different shape. The
// adapter IS the wiring (gate: brand-mg-wiring.test.mjs).
const withSpec = (Comp: React.FC<any>, needsSource: boolean): React.FC<any> =>
  (props: any) => {
    const spec: FrameCompSpec | undefined = props?.spec || props?.props?.spec;
    if (!spec || !spec.kind) return null;      // no spec, no pixels — never a blank card
    if (needsSource && !props?.sourceUrl) return null;
    return <Comp spec={spec} sourceUrl={props?.sourceUrl} fps={props?.fps ?? 30} />;
  };

export const EvidenceCardMG = withSpec(EvidenceCard, true);
export const DeviceMockupMG = withSpec(DeviceMockup, true);
export const NumberCardMG = withSpec(NumberCard, false);
export const EmojiCardMG = withSpec(EmojiCard, false);
