import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { Video } from "@remotion/media";
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
  /** Optional footage behind the component — a filename in public/ or a URL. Used
   *  to verify the contrast floor over REAL video, not just the flat gray plate. */
  bgVideo?: string;
  /** Footage for source-composing components (EvidenceCard/DeviceMockup): a
   *  filename in public/ or a URL, resolved here to the adapter's sourceUrl —
   *  the adapters are needsSource and render null without it. */
  sourceVideo?: string;
  /** Component window in ms (default 4000). Set to a LIVE placement's duration
   *  (with the 30fps probe composition) to prove timing defects the 60fps/4s
   *  probe masks — the absolute-frame-schedule class. */
  durationMs?: number;
}
const PLATE = "#808080";
export const MGCraftProbe: React.FC<MGCraftProbeProps> = ({ type, props, motionBlur, bgVideo, sourceVideo, durationMs }) => {
  const Comp = MG_MAP[type];
  const bgSrc = bgVideo
    ? (/^https?:\/\//.test(bgVideo) ? bgVideo : staticFile(bgVideo))
    : undefined;
  const sourceUrl = sourceVideo
    ? (/^https?:\/\//.test(sourceVideo) ? sourceVideo : staticFile(sourceVideo))
    : undefined;
  return (
    <MotionBlurProvider enabled={motionBlur ?? true} samples={10} shutterAngle={180}>
      <SmoothGraphicsProvider enabled={true}>
        <AbsoluteFill style={{ backgroundColor: bgSrc ? "#000" : PLATE }}>
          {bgSrc ? (
            <AbsoluteFill>
              <Video src={bgSrc} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </AbsoluteFill>
          ) : null}
          {Comp ? (
            // Precedence (render-caught): a PROPS entry may carry its own
            // durationMs; the probe-level override must beat it — the effect
            // leg of the clamp proof silently ran at 4s until it did.
            <Comp
              {...{
                startMs: 0,
                durationMs: 4000,
                ...props,
                ...(sourceUrl ? { sourceUrl } : {}),
                ...(durationMs != null ? { durationMs } : {}),
              }}
            />
          ) : null}
        </AbsoluteFill>
      </SmoothGraphicsProvider>
    </MotionBlurProvider>
  );
};
