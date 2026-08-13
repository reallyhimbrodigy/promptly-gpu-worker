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
const TEXT_STAGGER = 3;

export const NamePlate: React.FC<NamePlateProps> = ({
  name,
  role,
  accentColor = "#F5A11E",
  nameColor = "#FFFFFF",
  anchor = "lower_third_safe",
  widthPct = 0.42,
  ...timing
}) => {
  const { width, height } = useVideoConfig();
  const { phase, enterProgress, exitProgress } = useMGPhase(timing);
  if (phase === "before" || phase === "after") return null;

  const landscape = width >= height;
  // Landscape gets broadcast title-safe margins; vertical keeps the platform-UI
  // band. Same idea, different danger — see _safe_zones_for in handler.py.
  const sideMargin = landscape ? Math.round(width * 0.05) : 60;
  const bandY = anchor === "upper_third_safe"
    ? Math.round(height * (landscape ? 0.10 : 0.14))
    : Math.round(height * (landscape ? 0.78 : 0.72));

  const enter = easeOutCubic(clamp01(enterProgress));
  const out = 1 - clamp01(exitProgress);
  const ruleW = interpolate(enter, [0, 1], [0, Math.round(width * widthPct)]);
  const nameRise = interpolate(enter, [0, 1], [18, 0]);
  const roleRise = interpolate(clamp01(enter * 1.25 - 0.25), [0, 1], [14, 0]);

  const nameSize = Math.round(height * (landscape ? 0.052 : 0.034));
  const roleSize = Math.round(nameSize * 0.52);

  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{ position: "absolute", left: sideMargin, top: bandY }}>
        <div style={{ width: ruleW, height: Math.max(3, Math.round(height * 0.004)),
                      background: accentColor, borderRadius: 2 }} />
        <div style={{ overflow: "hidden", marginTop: Math.round(nameSize * 0.34) }}>
          <div style={{ transform: `translateY(${nameRise}px)`, color: nameColor,
                        fontFamily: MG_FONTS.anton, fontWeight: 800,
                        fontSize: nameSize, lineHeight: 1.04, letterSpacing: "-0.02em" }}>
            {asText(name)}
          </div>
        </div>
        {role ? (
          <div style={{ overflow: "hidden", marginTop: Math.round(roleSize * 0.32) }}>
            <div style={{ transform: `translateY(${roleRise}px)`, color: accentColor,
                          fontFamily: MG_FONTS.inter, fontWeight: 600,
                          fontSize: roleSize, letterSpacing: "0.06em",
                          textTransform: "uppercase" }}>
              {asText(role)}
            </div>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
