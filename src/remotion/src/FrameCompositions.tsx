import React from "react";
import {
  AbsoluteFill,
  Freeze,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import { Video } from "@remotion/media";
import { cappedEntranceProgress } from "./motion-graphics/shared/entrance-cap";
import { dur } from "./motion-graphics/shared/motion";
import { MotionBlurWrap } from "./motion-graphics/shared/motion-blur";

// ── THE GENERATION-FREE COMPOSITIONS ────────────────────────────────────────
//
// No image model, no Vertex call, no quota, no asset pipeline, no new
// dependency. Two are built on a frame of the USER'S OWN video (EvidenceCard,
// DeviceMockup); one is pure type (EmojiCard). Every visual property arrives in
// a SPEC built by frame_compositions.py from the job's design system — a
// component that picks its own colour is a second design system competing with
// the real one (brand_components.py).
//
// ENTRANCES (correcting the 2026-08-20 ruling). FRAME-1-IS-FINAL is a CAPTION
// law — established over four passes by the owner's eye on the caption text
// layer. It was wrongly carried onto these CARDS, which shipped `entrance:
// "none"` and popped on with zero motion — amateur regardless of composition.
// REF-2's cards animate in. So these compositions now animate their arrival:
//   • eased + velocity-capped — cappedEntranceProgress, the same peak-per-frame
//     travel cap (MAX_ENTRANCE_STEP = 1/6) every MG entrance obeys, so a card
//     never steps; the shared trapezoid GLIDES (decelerates into rest).
//   • motion-blurred — the moving group is wrapped in MotionBlurWrap; when the
//     render's motionBlur flag is on it renders through CameraMotionBlur at the
//     film 180° shutter, which is where 30fps smoothness actually comes from.
//   • frame-1-is-final AT REST — at p=1 the entrance is identity (translateY 0,
//     scale 1, rotate 0), so the resting composition is byte-identical to the
//     static §4 design. `entrance: "none"` still renders the static path exactly.
//
// §4 COMPOSITION (unchanged): tilt 5-8 degrees, hard edge, real drop shadow — a
// physical object on a surface. Elements OVERLAP and OCCLUDE. "A stack of
// centred, non-overlapping boxes reads as a slide."

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

// ── ENTRANCE ────────────────────────────────────────────────────────────────
// One card-entrance vocabulary, driven from the component-LOCAL frame (these
// mount inside a Sequence via MG_MAP, so useCurrentFrame() is 0 at arrival).

interface Entrance { active: boolean; opacity: number; translateY: number; scale: number; rotate: number; }

/** A small over-tilt that settles OUT — the object relaxing onto the surface.
 *  Opposite sign to the resting tilt so it starts a touch more upright. */
const settleRot = (tiltDeg: number, mag: number): number => (tiltDeg < 0 ? mag : -mag);

/**
 * The card's arrival transform for the current frame. `entrance: "none"` (or an
 * absent value) returns inactive → the static §4 composition, unchanged. Any
 * other value animates: rise + settle-scale + a small tilt settle, all off the
 * shared velocity-capped trapezoid so no frame exceeds the peak-travel cap.
 */
const useCardEntrance = (
  spec: FrameCompSpec,
  opts: { rise: number; scaleFrom: number; rotMag: number },
): Entrance => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const kind = spec.entrance || "none";
  if (kind === "none") return { active: false, opacity: 1, translateY: 0, scale: 1, rotate: 0 };
  const p = cappedEntranceProgress({ localFrame: frame, fps, authoredFrames: dur("BASE", fps) });
  return {
    active: true,
    opacity: interpolate(p, [0, 0.55], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    translateY: interpolate(p, [0, 1], [opts.rise, 0]),
    scale: interpolate(p, [0, 1], [opts.scaleFrom, 1]),
    rotate: interpolate(p, [0, 1], [settleRot(spec.tilt_deg, opts.rotMag), 0]),
  };
};

/** Group style for the moving layer. Empty (no transform, no compositing
 *  layer) when inactive, so the static path is byte-for-byte the §4 design. */
const groupStyle = (e: Entrance, origin: string): React.CSSProperties =>
  e.active
    ? {
        transform: `translateY(${e.translateY}px) scale(${e.scale}) rotate(${e.rotate}deg)`,
        opacity: e.opacity,
        transformOrigin: origin,
      }
    : {};

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
  ({ spec, sourceUrl, fps }) => {
    const e = useCardEntrance(spec, { rise: 52, scaleFrom: 0.972, rotMag: 2.2 });
    return (
      <AbsoluteFill style={{ background: spec.bg }}>
        <MotionBlurWrap>
          <AbsoluteFill style={groupStyle(e, "50% 56%")}>
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
        </MotionBlurWrap>
      </AbsoluteFill>
    );
  };

/** DEVICE MOCKUP — the user's own frame inside a DRAWN shell (never an asset). */
export const DeviceMockup: React.FC<{ spec: FrameCompSpec; sourceUrl: string; fps: number }> =
  ({ spec, sourceUrl, fps }) => {
    const e = useCardEntrance(spec, { rise: 56, scaleFrom: 0.968, rotMag: 2.5 });
    return (
      <AbsoluteFill style={{ background: spec.bg }}>
        <MotionBlurWrap>
          <AbsoluteFill style={groupStyle(e, "50% 52%")}>
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
        </MotionBlurWrap>
      </AbsoluteFill>
    );
  };

/** EMOJI-AS-TYPE — REF-2's TOP SECRET folder: an emoji, a tilt, a shadow and
 *  two words. Noto Color Emoji is ALREADY in the image (the caption stack uses
 *  it), so this adds no font, no asset and no dependency. The emoji POPS in
 *  (bigger scale delta than the print cards) and its words settle with it. */
export const EmojiCard: React.FC<{ spec: FrameCompSpec }> = ({ spec }) => {
  const e = useCardEntrance(spec, { rise: 24, scaleFrom: 0.8, rotMag: 3 });
  return (
    <AbsoluteFill style={{ background: spec.bg, alignItems: "center",
                           justifyContent: "center" }}>
      <MotionBlurWrap>
        <div style={{ ...groupStyle(e, "50% 50%"), display: "flex",
                      flexDirection: "column", alignItems: "center" }}>
          {/* §4 pass (2026-08-25, craft lane): two planes, not a stack. The
              emoji is the OBJECT; the words are FOREGROUND TYPE that OVERLAPS
              and occludes its lower third — REF-2's grammar (type over object,
              heavy shadow separation). Was: a small centred caption UNDER the
              emoji at 0.62×cap — centred non-overlapping boxes, the named §4
              defect. Words stack as a slab (line 2 in the accent, slightly
              larger, tucked up under line 1), opposing tilts via the individual
              `rotate` property (REMOTION_CONVENTIONS forward law). Occlusion is
              of the GRAPHIC only — user words are never covered. */}
          <div style={{
            fontSize: spec.emoji_px ?? spec.cap_px * 3.2,
            rotate: `${spec.tilt_deg}deg`,
            filter: `drop-shadow(0 ${spec.legibility.shadow_offset_px * 6}px `
              + `${spec.legibility.shadow_blur_px * 5}px rgba(0,0,0,0.45))`,
            lineHeight: 1,
          }}>{spec.emoji}</div>
          {(spec.words || []).length ? (
            <div style={{
              marginTop: -(spec.emoji_px ?? spec.cap_px * 3.2) * 0.28,
              display: "flex", flexDirection: "column", alignItems: "center",
              position: "relative", zIndex: 2,
            }}>
              {(spec.words || []).map((w, i) => (
                <span key={i} style={{
                  // Render-caught (2026-08-25): no fontFamily = browser SERIF —
                  // the words rendered Times-like since birth. Inter 900 is the
                  // catalogue's claim voice.
                  // Corpus law 1 (pass #7b): the widest word spans ~92% of the
                  // 1080 frame (REF-2's number clips the edge; ours sat at
                  // ~50% width). Deterministic fit, no DOM measurement. Law 2:
                  // the HIT word (line 2) carries the emphasis — palette lock
                  // (§6) forbids inventing a redder accent, so emphasis comes
                  // from SCALE at full palette chroma.
                  fontFamily: "Inter, sans-serif",
                  // The HIT word is width-FILL driven, not cap-relative
                  // (render-caught: Math.min made cap_px the ceiling, so the
                  // fill term never bound and "CAR" sat at ~43% width). The
                  // support word keeps cap_px. Advance ratio 0.80 is
                  // render-measured for Inter 900 uppercase + 0.01em tracking
                  // (~0.775em/char) — the old 0.62 estimate would let text
                  // run to ~99% and crop, and text may never crop.
                  fontSize: i === 0
                    ? Math.min(
                        spec.cap_px,
                        (1080 * 0.92) / (Math.max(3, w.length) * 0.8)
                      )
                    : (1080 * 0.92) / (Math.max(3, w.length) * 0.8),
                  fontWeight: 900,
                  color: i === 0 ? spec.fg : spec.accent,
                  letterSpacing: "0.01em", textTransform: "uppercase",
                  lineHeight: 0.92,
                  rotate: `${(i % 2 === 0 ? -1 : 1) * 2.2}deg`,
                  marginTop: i > 0 ? -spec.cap_px * 0.08 : 0,
                  // Type-over-OBJECT needs more separation than type-over-bg:
                  // the spec's legibility numbers are calibrated for the card
                  // ground, so the overlapping slab doubles them (§2.4 scaled,
                  // the StatCard contrast-floor precedent).
                  textShadow: `0 ${spec.legibility.shadow_offset_px * 2}px ${spec.legibility.shadow_blur_px * 2}px `
                    + `rgba(0,0,0,${Math.min(0.65, spec.legibility.shadow_opacity * 1.8)})`,
                }}>{w}</span>
              ))}
            </div>
          ) : null}
        </div>
      </MotionBlurWrap>
    </AbsoluteFill>
  );
};

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
export const EmojiCardMG = withSpec(EmojiCard, false);
