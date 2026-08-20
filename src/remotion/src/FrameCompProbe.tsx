import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { MG_MAP } from "./PromptlyRender";
import { MotionBlurProvider } from "./motion-graphics/shared/motion-blur";
import type { FrameCompSpec } from "./FrameCompositions";

/**
 * FrameCompProbe — standalone render harness for the generation-free frame
 * compositions (EvidenceCard / DeviceMockup / EmojiCard). NOT used in
 * production. Renders ONE frame comp at the production target (1080x1920@30fps)
 * with a real spec + source, wrapped in a MotionBlurProvider so the proof shows
 * the entrance, the film-shutter motion blur, AND the §4 depth together.
 * render-frame-comp-proof.mjs drives it via renderStill across the entrance
 * window; the eye compares the frames against REF-2.
 */
export interface FrameCompProbeProps {
  kind: string;
  spec: FrameCompSpec;
  sourceUrl?: string;
  motionBlur?: boolean;
}

export const FrameCompProbe: React.FC<FrameCompProbeProps> = ({
  kind,
  spec,
  sourceUrl,
  motionBlur,
}) => {
  const Comp = MG_MAP[kind];
  // In production sourceUrl is a remote CDN URL; for the local proof it is a
  // bare filename in public/, which the source layer can only load once it is
  // resolved to the served static path.
  const src = sourceUrl
    ? (/^https?:\/\//.test(sourceUrl) ? sourceUrl : staticFile(sourceUrl))
    : undefined;
  return (
    <MotionBlurProvider enabled={motionBlur ?? true} samples={10} shutterAngle={180}>
      <AbsoluteFill>
        {Comp ? <Comp spec={spec} sourceUrl={src} fps={30} /> : null}
      </AbsoluteFill>
    </MotionBlurProvider>
  );
};
