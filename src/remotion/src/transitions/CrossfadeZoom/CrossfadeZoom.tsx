import React, { CSSProperties, useCallback, useEffect, useState } from "react";
import {
  AbsoluteFill,
  interpolate,
  Easing,
  OffthreadVideo,
  cancelRender,
} from "remotion";
import type { CrossfadeZoomProps } from "../types";
import { SafeImg } from "../../SafeImg";

const isImage = (src: string) => /\.(jpe?g|png|gif|webp|avif|bmp)$/i.test(src);

const MediaLayer: React.FC<{
  src: string;
  style: CSSProperties;
  startFrom?: number;
  playbackRate?: number;
  label: string;
  onUnavailable: () => void;
}> = ({ src, style, startFrom, playbackRate, label, onUnavailable }) =>
  isImage(src) ? (
    <SafeImg
      src={src}
      style={style}
      role="primary"
      label={label}
      onUnavailable={onUnavailable}
    />
  ) : (
    <OffthreadVideo src={src} startFrom={startFrom} playbackRate={playbackRate} style={style} />
  );

/**
 * ONE MISSING LAYER MUST NOT COST THE VIDEO (Zac 2026-08-02).
 *
 * A crossfade has two layers and each is PRIMARY — it IS the frame — so neither
 * may quietly degrade to nothing. But it does not follow that a failure has to
 * kill the render: with one layer gone the other can carry the whole window, and
 * the user gets a hard cut where they would have had a crossfade. Slightly wrong
 * beats absent.
 *
 * THE SUBTLETY THAT MAKES A NAIVE DROP WRONG: the two opacity ramps assume each
 * other. clipB is the base and fades IN over progress 0.3-0.9, so simply
 * dropping clipA leaves clipB at opacity 0 across the head of the segment —
 * BLACK, the exact INTEGRITY_TRIP shape we are avoiding. Same at the tail if
 * clipB goes, since clipA fades OUT. So the survivor's opacity is PINNED to 1.
 *
 * Only when BOTH layers are unloadable is there nothing left to paint, and that
 * alone cancels the render.
 */
export const CrossfadeZoom: React.FC<CrossfadeZoomProps> = ({
  clipA, clipB, progress, style,
  startFromA, startFromB, playbackRateA = 1, playbackRateB = 1,
}) => {
  const [aLost, setALost] = useState(false);
  const [bLost, setBLost] = useState(false);
  const loseA = useCallback(() => setALost(true), []);
  const loseB = useCallback(() => setBLost(true), []);

  useEffect(() => {
    if (aLost && bLost) {
      cancelRender(
        new Error(
          "CROSSFADE_BOTH_LAYERS_UNLOADABLE: neither clip could be loaded, so "
          + `there is no frame to paint (A=${clipA} B=${clipB})`,
        ),
      );
    }
  }, [aLost, bLost, clipA, clipB]);

  const ease = Easing.bezier(0.25, 0.46, 0.45, 0.94);

  const scaleA = interpolate(progress, [0, 1], [1, 1.12], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scaleB = interpolate(progress, [0, 1], [1.12, 1], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Survivor holds the window at full opacity — the transition becomes a cut.
  const opacityA = bLost
    ? 1
    : interpolate(progress, [0.1, 0.7], [1, 0], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacityB = aLost
    ? 1
    : interpolate(progress, [0.3, 0.9], [0, 1], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const mediaStyle: CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  };

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      {!bLost && (
        <AbsoluteFill style={{ transform: `scale(${scaleB})`, opacity: opacityB }}>
          <MediaLayer
            src={clipB} startFrom={startFromB} playbackRate={playbackRateB}
            style={mediaStyle} label="CrossfadeZoom.clipB" onUnavailable={loseB}
          />
        </AbsoluteFill>
      )}
      {!aLost && opacityA > 0.01 && (
        <AbsoluteFill style={{ transform: `scale(${scaleA})`, opacity: opacityA }}>
          <MediaLayer
            src={clipA} startFrom={startFromA} playbackRate={playbackRateA}
            style={mediaStyle} label="CrossfadeZoom.clipA" onUnavailable={loseA}
          />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
