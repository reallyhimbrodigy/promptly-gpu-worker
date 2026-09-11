import React from "react";
import { staticFile, Img, useCurrentFrame } from "remotion";
import { Video } from "@remotion/media";

/**
 * WHERE A ZOOM'S PIXELS COME FROM — one video element, or one image per frame.
 *
 * MEASURED, same container, both arms, REAL FOOTAGE (motion-31fa2646):
 * <Video> 1,259 ms/frame against an <Img> sequence at 327 ms/frame — 3.9x.
 * On synthetic testsrc the same comparison reads 2.0x, so the source class
 * matters and is always stated with the number.
 *
 * WHY A SHARED COMPONENT AND NOT A CHANGE PER ZOOM. Seven components mount the
 * source. Editing seven is seven chances for the transform math to drift, and
 * the whole claim rests on the two arms differing ONLY in where the pixels come
 * from. One element, one prop, identical everything else.
 *
 * FALLS BACK, LOUDLY-BY-CONSTRUCTION. No `frames` prop means <Video>, which is
 * the shipped path — so a plan that does not carry a sequence renders exactly
 * as it did before, and this file cannot change any output until a caller asks
 * for it.
 */
export interface FramesRef {
  dir: string;
  count: number;
  pad?: number;
  ext?: string;
}

export const ZoomSource: React.FC<{
  src: string;
  frames?: FramesRef | null;
  style?: React.CSSProperties;
}> = ({ src, frames, style }) => {
  const frame = useCurrentFrame();
  if (frames && frames.count > 0) {
    // CLAMPED, not wrapped. A zoom held past its last extracted frame must
    // show the last frame, never frame 0 — a wrap would read as a jump cut
    // that nobody ruled.
    const n = Math.min(Math.max(frame + 1, 1), frames.count);
    const idx = String(n).padStart(frames.pad ?? 4, "0");
    return (
      <Img
        src={staticFile(`${frames.dir}/f${idx}.${frames.ext ?? "jpg"}`)}
        style={style}
      />
    );
  }
  return <Video src={src} style={style} />;
};
