import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { LightLeakOverlay } from "./LightLeakOverlay";
import { ShutterFlashOverlay } from "./ShutterFlashOverlay";
import { NewspaperWipeOverlay } from "./NewspaperWipeOverlay";
import { SceneTitleOverlay } from "./SceneTitleOverlay";

export type OverlayCutEffectType =
  | "lightleak"
  | "shutterflash"
  | "newspaperwipe"
  | "scenetitle";

export interface OverlayCutEffectProps {
  /** Component to render as the overlay. No clipA/clipB inputs by design. */
  type: OverlayCutEffectType;
  /** Output frame index the cut sits on. The overlay window is centered here. */
  atFrame: number;
  /** Window length in output frames. The overlay animates from progress 0 → 1
   *  across this many frames, centered on atFrame. Outside the window the
   *  component returns null (nothing rendered). */
  durationInFrames: number;
  /** SceneTitle only — required text on the panel. Ignored by other types. */
  title?: string;
  /** SceneTitle only — optional kicker above the divider. */
  label?: string;
}

/**
 * OverlayCutEffect — an in-place tight-cut transition overlay.
 *
 * Plays on TOP of an unmodified hard cut. The two adjacent clips render
 * back-to-back as a hard cut (handler.py's contiguous-splice path,
 * unchanged from commit 5da1566). This component sits ABOVE that hard cut
 * in the Remotion composition and animates a decoration over the cut
 * junction for `durationInFrames` frames centered on `atFrame`.
 *
 * STRUCTURAL GUARANTEES (the prior DipToBlack rollback failure modes):
 *   • No clipA / clipB props → cannot freeze, scrub, or rewind underlying
 *     video. The underlying video plays its real frames continuously.
 *   • No time inserted → host composition's `durationInFrames` is unchanged.
 *     This component reads `useCurrentFrame()`, computes whether it's
 *     inside the overlay window, and renders accordingly. It cannot grow
 *     the timeline.
 *   • No audio touched → this is a Remotion VISUAL component. The audio
 *     path in handler.py is not involved at all.
 *   • Outside the overlay window the component returns `null` — zero
 *     pixels written, no DOM. The decoration is strictly local to its
 *     window.
 */
export const OverlayCutEffect: React.FC<OverlayCutEffectProps> = ({
  type,
  atFrame,
  durationInFrames,
  title,
  label,
}) => {
  const frame = useCurrentFrame();
  const half = durationInFrames / 2;
  const windowStart = atFrame - half;
  const windowEnd = atFrame + half;

  if (frame < windowStart || frame >= windowEnd) {
    return null;
  }

  const localFrame = frame - windowStart;
  const progress = Math.max(0, Math.min(1, localFrame / durationInFrames));

  if (type === "lightleak") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <LightLeakOverlay progress={progress} palette="warm" direction="tl-br" intensity={1.0} />
      </AbsoluteFill>
    );
  }
  if (type === "shutterflash") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <ShutterFlashOverlay progress={progress} flashColor="#ffffff" />
      </AbsoluteFill>
    );
  }
  if (type === "newspaperwipe") {
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <NewspaperWipeOverlay progress={progress} />
      </AbsoluteFill>
    );
  }
  if (type === "scenetitle") {
    // SceneTitle is the only overlay that carries text — needs a title at
    // minimum. The isolation test passes a representative "Act Two" / "Chapter"
    // pair; the production wiring will route Gemini's emitted title/label
    // through the same path. Without a title we render nothing rather than
    // an empty panel (which would mask the cut with no payoff).
    if (!title) return null;
    return (
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <SceneTitleOverlay
          progress={progress}
          title={title}
          label={label}
          theme="dark"
          variant="full"
        />
      </AbsoluteFill>
    );
  }
  return null;
};
