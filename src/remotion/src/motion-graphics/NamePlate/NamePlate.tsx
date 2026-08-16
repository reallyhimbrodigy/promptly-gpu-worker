import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import { asText } from "../../shared/asText";
import type { NamePlateProps } from "./types";

const clamp01 = (t: number): number => Math.max(0, Math.min(1, t));
const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

// The rule draws left-to-right, then the text rises behind it. Frame-1-is-final
// applies to CAPTIONS, not to a title plate — a plate is an authored graphic and
// the reference set animates them.
const RULE_FRAMES = 8;
const EXIT_FRAMES = 6;
const TEXT_STAGGER = 3;

export const NamePlate: React.FC<NamePlateProps> = ({
  name,
  role,
  accentColor = "#F5A11E",
  nameColor = "#FFFFFF",
  anchor = "lower_third_safe",
  widthPct = 0.42,
  namePx,
  rolePx,
  backdropColor,
  sideMarginPx,
  // Named explicitly rather than collected with `...timing`, matching all 26
  // dispatched MGs: a rest-spread here types as an index signature and stops
  // satisfying MGTimingProps, so the timing contract would go unchecked.
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
}) => {
  const { width, height } = useVideoConfig();
  // useMGPhase REQUIRES its defaults object — calling it with one argument is a
  // TypeError at mount (`Cannot destructure property 'defaultEnterFrames' of
  // undefined`), which is how this component would have taken a user's whole
  // video down the first time it was ever dispatched. RULE_FRAMES is the
  // authored entrance; the exit is shorter because a plate leaves faster than
  // it arrives. Both are re-based to ms by the smooth-graphics floor.
  const { phase, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: RULE_FRAMES, defaultExitFrames: EXIT_FRAMES },
  );
  if (phase === "before" || phase === "after") return null;

  const landscape = width >= height;
  // Landscape gets broadcast title-safe margins; vertical keeps the platform-UI
  // band. Same idea, different danger — see _safe_zones_for in handler.py.
  // The design system resolves BOTH doctrines already (design_system.safe_zones),
  // so when it supplies an inset we obey it rather than re-deriving. It is
  // clamped to 15% of the frame so a design system built for a different canvas
  // can never push the plate off the one we are actually rendering.
  const defaultMargin = landscape ? Math.round(width * 0.05) : 60;
  const sideMargin = Number.isFinite(sideMarginPx as number)
    ? Math.max(0, Math.min(Math.round(sideMarginPx as number), Math.round(width * 0.15)))
    : defaultMargin;
  const bandY = anchor === "upper_third_safe"
    ? Math.round(height * (landscape ? 0.10 : 0.14))
    : Math.round(height * (landscape ? 0.78 : 0.72));

  const enter = easeOutCubic(clamp01(enterProgress));
  const out = 1 - clamp01(exitProgress);
  const ruleW = interpolate(enter, [0, 1], [0, Math.round(width * widthPct)]);
  const nameRise = interpolate(enter, [0, 1], [18, 0]);
  const roleRise = interpolate(clamp01(enter * 1.25 - 0.25), [0, 1], [14, 0]);

  // The design system's resolved px win over the component's canvas fractions:
  // it resolved the ratios ONCE against the canvas it was built for, precisely
  // so consumers do not each re-derive and drift (see brand_components._ds_parts).
  const nameSize = Number.isFinite(namePx as number) && (namePx as number) > 0
    ? Math.round(namePx as number)
    : Math.round(height * (landscape ? 0.052 : 0.034));
  const roleSize = Number.isFinite(rolePx as number) && (rolePx as number) > 0
    ? Math.round(rolePx as number)
    : Math.round(nameSize * 0.52);
  // A long name must WRAP inside the safe area, never bleed off the frame.
  const blockMaxWidth = Math.max(120, width - sideMargin * 2);
  const pad = Math.round(nameSize * 0.28);

  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{
        position: "absolute", left: sideMargin, top: bandY,
        maxWidth: blockMaxWidth, display: "inline-block",
        padding: backdropColor ? `${pad}px ${Math.round(pad * 1.4)}px` : 0,
      }}>
        {/* LEGIBILITY SCRIM, only when the palette gave us a base colour. Its
            own opacity — never a colour-with-alpha — so any CSS colour string
            the palette produces works unparsed. Text sits above it. */}
        {backdropColor ? (
          <div style={{
            position: "absolute", inset: 0, background: backdropColor,
            borderRadius: Math.round(pad * 0.6), opacity: 0.66 * enter,
          }} />
        ) : null}
        <div style={{ position: "relative" }}>
          <div style={{ width: ruleW, height: Math.max(3, Math.round(height * 0.004)),
                        background: accentColor, borderRadius: 2 }} />
          <div style={{ overflow: "hidden", marginTop: Math.round(nameSize * 0.34) }}>
            <div style={{ transform: `translateY(${nameRise}px)`, color: nameColor,
                          fontFamily: MG_FONTS.anton, fontWeight: 800,
                          fontSize: nameSize, lineHeight: 1.04, letterSpacing: "-0.02em",
                          overflowWrap: "break-word" }}>
              {asText(name)}
            </div>
          </div>
          {role ? (
            <div style={{ overflow: "hidden",
                          marginTop: Math.round(roleSize * 0.32) + TEXT_STAGGER }}>
              <div style={{ transform: `translateY(${roleRise}px)`, color: accentColor,
                            fontFamily: MG_FONTS.inter, fontWeight: 600,
                            fontSize: roleSize, letterSpacing: "0.06em",
                            textTransform: "uppercase", overflowWrap: "break-word" }}>
                {asText(role)}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
