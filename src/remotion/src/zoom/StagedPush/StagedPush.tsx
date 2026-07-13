import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { Video } from "@remotion/media";
import { msToFrames } from "../shared/timing";
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
  const { fps } = useVideoConfig();

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
    const st = stages.map((s) => ({ peak: msToFrames(s.atMs, fps), scale: s.scale }));
    const first = st[0];
    const last = st[st.length - 1];

    const beginF = first.peak - pushF; // the first push starts here (back-timed so peak = word)
    const releaseStartF = last.peak + holdF;
    const releaseEndF = releaseStartF + releaseF;

    // outside this event's whole span → this event contributes nothing here
    const spanEndF = ev.cutTerminated ? releaseStartF : releaseEndF;
    if (frame < beginF || frame > spanEndF) continue;

    let s = 1;
    let prevScale = 1;
    let resolved = false;

    for (let i = 0; i < st.length; i++) {
      const pushStartF = st[i].peak - pushF;
      if (frame < pushStartF) {
        // in the HOLD between the previous stage's peak and this stage's push
        s = prevScale;
        resolved = true;
        break;
      }
      if (frame <= st[i].peak) {
        // PUSHING into stage i: prevScale → st[i].scale, smooth-fast (ease-out cubic),
        // completing exactly on the word (frame === peak → progress 1)
        s = interpolate(frame, [pushStartF, st[i].peak], [prevScale, st[i].scale], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        resolved = true;
        break;
      }
      prevScale = st[i].scale; // passed this stage's peak; carry its scale forward
    }

    if (!resolved) {
      // past the final peak: HOLD at full push, then adaptive release
      if (frame <= releaseStartF || ev.cutTerminated) {
        // hold at full push (and, if cut-terminated, stay there — the cut ends the clip)
        s = last.scale;
      } else {
        // continuing: smooth MODERATE ease-out back toward baseline
        s = interpolate(frame, [releaseStartF, releaseEndF], [last.scale, 1], {
          easing: Easing.inOut(Easing.cubic),
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
