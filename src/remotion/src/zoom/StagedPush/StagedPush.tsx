import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { Video } from "@remotion/media";
import { msToFrames, msToFramesFloor } from "../shared/timing";
import { useSmoothGraphics } from "../../motion-graphics/shared/smooth-graphics-flag";
import { cornerPx, planCappedRampIn, planCappedRelease } from "../shared/velocity-cap";
import type { StagedPushProps } from "../types";

/**
 * StagedPush — the multi-stage emphasis zoom (2- or 3-part stepped push-in).
 *
 * A short punchy phrase of 2-3 CONSECUTIVE building emphasis words gets a stepped
 * push: a smooth-fast push-in that COMPLETES exactly on each word, holds through the
 * pause to the next word, pushes tighter, and after the final word holds at full push
 * then releases adaptively. Equal steps (each stage adds the same increment) so the
 * cumulative zoom stays tight-but-not-absurd. "10 [push] Million [push tighter] dollars
 * [push tightest] — hold — release."
 *
 * The hard requirement: each stage's PEAK lands on its word's audible onset. Since the
 * push has DURATION, its start is back-timed by pushMs so the peak arrives ON the word
 * (stage.atMs is the word onset; the push runs [atMs - pushMs, atMs]). Peaks land on
 * msToFrames(atMs) = round(atMs*fps/1000) — the SAME clock every other component fires on.
 *
 * The release adapts (Zac's rule — the ending is the risk):
 *   • cutTerminated (phrase ends at a hard cut): NO release animation — hold at full push;
 *     the cut resets the zoom cleanly. Do not step on the climax with a release.
 *   • continuing (mid-sentence): after a brief hold at full push (so the payoff word lands
 *     and sits), a SMOOTH MODERATE ease-out back to baseline — not a snap (glitch), not a
 *     slow drift (drags). A graceful ease that feels intentional.
 */
export const StagedPush: React.FC<StagedPushProps> = ({ src, events, style }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();
  // VELOCITY CAP (Zac 2026-08-01). OFF -> today's exact cubic pixels.
  const smooth = useSmoothGraphics();

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  for (const ev of events) {
    const stages = ev.stages ?? [];
    if (stages.length < 2) continue; // a staged push needs at least 2 stages
    originX = ev.originX ?? 0.5;
    originY = ev.originY ?? 0.5;

    const pushF = Math.max(1, msToFrames(ev.pushMs ?? 280, fps)); // smooth-fast push into each stage
    const holdF = Math.max(0, msToFrames(ev.holdMs ?? 260, fps)); // hold at full push before release
    const releaseF = Math.max(1, msToFrames(ev.releaseMs ?? 360, fps)); // moderate ease-out if continuing

    // each stage's PEAK lands on its word's onset frame (the component clock)
    const st = stages.map((s) => ({ peak: msToFramesFloor(s.atMs, fps), scale: s.scale }));
    const first = st[0];
    const last = st[st.length - 1];

    // VELOCITY CAP. Every stage peak is nailed to its own word, so each push may
    // only grow BACKWARDS into the hold that precedes it (stage 0 into the clip
    // head). Solved cumulatively, because stage i's travel starts from whatever
    // scale stage i-1 actually reached after ITS cap.
    const corner = cornerPx(width, height, originX, originY);
    const staged = st.map(() => ({ start: 0, scale: 1, easing: undefined as
      ((t: number) => number) | undefined }));
    let cum = 1;
    for (let i = 0; i < st.length; i++) {
      const c = smooth
        ? planCappedRampIn({
            fromScale: cum,
            toScale: st[i].scale,
            landFrame: st[i].peak,
            earliestFrame: i === 0 ? 0 : st[i - 1].peak,
            authoredFrames: pushF,
            fps,
            corner,
          })
        : null;
      staged[i] = {
        start: c ? c.startFrame : st[i].peak - pushF,
        scale: c ? c.toScale : st[i].scale,
        easing: c ? c.easing : undefined,
      };
      cum = staged[i].scale;
    }
    const lastScale = staged[staged.length - 1].scale;

    const beginF = staged[0].start; // the first push starts here (back-timed so peak = word)
    const releaseStartF = last.peak + holdF;
    const capRelease = smooth
      ? planCappedRelease({
          fromScale: lastScale,
          toScale: 1,
          startFrame: releaseStartF,
          latestFrame: durationInFrames,
          authoredFrames: releaseF,
          fps,
          corner,
        })
      : null;
    const releaseEndF = capRelease ? capRelease.endFrame : releaseStartF + releaseF;

    // outside this event's whole span → this event contributes nothing here
    const spanEndF = ev.cutTerminated ? releaseStartF : releaseEndF;
    if (frame < beginF || frame > spanEndF) continue;

    let s = 1;
    let prevScale = 1;
    let resolved = false;

    for (let i = 0; i < st.length; i++) {
      const pushStartF = staged[i].start;
      if (frame < pushStartF) {
        // in the HOLD between the previous stage's peak and this stage's push
        s = prevScale;
        resolved = true;
        break;
      }
      if (frame <= st[i].peak) {
        // PUSHING into stage i: prevScale → staged[i].scale, velocity-capped,
        // completing exactly on the word (frame === peak → progress 1)
        s = interpolate(frame, [pushStartF, st[i].peak], [prevScale, staged[i].scale], {
          easing: staged[i].easing ?? Easing.out(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        resolved = true;
        break;
      }
      prevScale = staged[i].scale; // passed this stage's peak; carry its scale forward
    }

    if (!resolved) {
      // past the final peak: HOLD at full push, then adaptive release
      if (frame <= releaseStartF || ev.cutTerminated) {
        // hold at full push (and, if cut-terminated, stay there — the cut ends the clip)
        s = lastScale;
      } else {
        // continuing: smooth MODERATE ease-out back toward baseline
        s = interpolate(frame, [releaseStartF, releaseEndF], [lastScale, 1], {
          easing: capRelease ? capRelease.easing : Easing.inOut(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      }
    }

    scale = s;
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      <Video
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
    </AbsoluteFill>
  );
};
