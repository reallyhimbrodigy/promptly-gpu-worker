import React, { CSSProperties } from "react";
import {
  AbsoluteFill,
  interpolate,
  Easing,
  OffthreadVideo,
  Img,
} from "remotion";
import type { CrossfadeZoomProps } from "../types";

const isImage = (src: string) => /\.(jpe?g|png|gif|webp|avif|bmp)$/i.test(src);

const MediaLayer: React.FC<{
  src: string;
  style: CSSProperties;
  startFrom?: number;
  playbackRate?: number;
}> = ({ src, style, startFrom, playbackRate }) =>
  isImage(src)
    ? <Img src={src} style={style} />
    : <OffthreadVideo src={src} startFrom={startFrom} playbackRate={playbackRate} style={style} />;

export const CrossfadeZoom: React.FC<CrossfadeZoomProps> = ({
  clipA, clipB, progress, style,
  startFromA, startFromB, playbackRateA = 1, playbackRateB = 1,
}) => {
  const ease = Easing.bezier(0.25, 0.46, 0.45, 0.94);

  const scaleA = interpolate(progress, [0, 1], [1, 1.12], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacityA = interpolate(progress, [0.1, 0.7], [1, 0], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const scaleB = interpolate(progress, [0, 1], [1.12, 1], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacityB = interpolate(progress, [0.3, 0.9], [0, 1], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const mediaStyle: CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  };

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      <AbsoluteFill style={{ transform: `scale(${scaleB})`, opacity: opacityB }}>
        <MediaLayer src={clipB} startFrom={startFromB} playbackRate={playbackRateB} style={mediaStyle} />
      </AbsoluteFill>
      {opacityA > 0.01 && (
        <AbsoluteFill style={{ transform: `scale(${scaleA})`, opacity: opacityA }}>
          <MediaLayer src={clipA} startFrom={startFromA} playbackRate={playbackRateA} style={mediaStyle} />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
