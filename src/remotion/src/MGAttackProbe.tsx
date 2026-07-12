import React from "react";
import { AbsoluteFill } from "remotion";
import { MG_MAP } from "./PromptlyRender";

/**
 * MGAttackProbe — WS1 measurement composition (not used in production).
 * Renders ONE motion-graphic type at startMs=0 on a flat mid-gray plate, so
 * mg-attack-battery.mjs can measure the ENTRANCE VISUAL ARRIVAL per type:
 * the frame at which on-screen "presence" (pixel mass distinct from the plate)
 * first reaches ~90% of its steady value — the moment the graphic has arrived,
 * robust across fade / slide / scale / spring entrances and immune to ongoing
 * content animation (count-ups, typing, marquees). durationMs is long so the
 * whole window is the ENTRANCE + hold (no exit inside the probe window).
 */
export interface MGAttackProbeProps {
  type: string;
  props: Record<string, unknown>;
  fps?: number;
}

// Flat plate the presence metric measures against. Mid-gray so both light and
// dark components register as "presence" (deviation from the plate).
const PLATE = "#808080";

export const MGAttackProbe: React.FC<MGAttackProbeProps> = ({ type, props, fps = 60 }) => {
  const Comp = MG_MAP[type];
  return (
    <AbsoluteFill style={{ backgroundColor: PLATE }}>
      {Comp ? (
        <Comp startMs={0} durationMs={4000} {...props} />
      ) : null}
    </AbsoluteFill>
  );
};
