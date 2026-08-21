import React from "react";
import { AbsoluteFill } from "remotion";
import { MG_MAP } from "./PromptlyRender";
import { MotionBlurProvider } from "./motion-graphics/shared/motion-blur";
import { SmoothGraphicsProvider } from "./motion-graphics/shared/smooth-graphics-flag";

/**
 * MGCraftProbe — catalogue-pass render-proof harness (not used in production).
 * Same mid-gray plate + startMs=0 as MGAttackProbe, but ALSO provides the
 * MotionBlurProvider (film 180° shutter) and the smooth-graphics arm, so the
 * before/after proof shows the motion blur and eased entrances the production
 * tree (PromptlyOverlay) supplies. render-mg-proof.mjs drives it via renderStill.
 */
export interface MGCraftProbeProps {
  type: string;
  props: Record<string, unknown>;
  motionBlur?: boolean;
}
const PLATE = "#808080";
export const MGCraftProbe: React.FC<MGCraftProbeProps> = ({ type, props, motionBlur }) => {
  const Comp = MG_MAP[type];
  return (
    <MotionBlurProvider enabled={motionBlur ?? true} samples={10} shutterAngle={180}>
      <SmoothGraphicsProvider enabled={true}>
        <AbsoluteFill style={{ backgroundColor: PLATE }}>
          {Comp ? <Comp startMs={0} durationMs={4000} {...props} /> : null}
        </AbsoluteFill>
      </SmoothGraphicsProvider>
    </MotionBlurProvider>
  );
};
