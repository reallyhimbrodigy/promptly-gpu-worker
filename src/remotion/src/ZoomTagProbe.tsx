import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { FocusWindow, LetterboxPush } from "./zoom";
import type { ZoomEvent } from "./zoom/types";

/**
 * ZoomTagProbe — the before/after harness for the OffthreadVideo -> @remotion/media
 * <Video> migration. FocusWindow and LetterboxPush pass only src + style to the
 * video tag, exactly like the five components already migrated, so they carry NO
 * startFrom risk and go first.
 *
 * The verification that cannot be fooled is a FRAME-DIFF: a prop-existence check
 * cannot prove a prop is HONOURED, but rendering the same component both ways on
 * the same source can. Identical pixels + fewer ms/frame is the pass condition.
 */
export const ZoomTagProbe: React.FC<{
  component: "FocusWindow" | "LetterboxPush";
  events: ZoomEvent[];
  src?: string;
}> = ({ component, events, src }) => {
  const Comp = component === "FocusWindow" ? FocusWindow : LetterboxPush;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Comp src={staticFile(src ?? "vcap_head.mp4")} events={events} />
    </AbsoluteFill>
  );
};
