import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo } from "remotion";
import type { StepPushProps } from "../types";

export const STEP_PUSH_PEAK_PROGRESS = 0.5;

/**
 * StepPush — keynote-style slide push. Both panels travel together in
 * the same direction: clipA exits, clipB enters to take its place. A
 * subtle shadow gradient on the trailing edge sells the "two slides
 * sliding past each other" feel.
 *
 * Cubic ease-in-out matches real presentation software (Keynote,
 * PowerPoint, Slides) — confident departure, confident arrival.
 *
 * Direction: "left" = standard forward step (clipA → left, clipB from right).
 */
export const StepPush: React.FC<StepPushProps> = ({
  clipA,
  clipB,
  progress,
  style,
  direction = "left",
  separatorShadow = true,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const ease = Easing.bezier(0.65, 0, 0.35, 1);
  const p = interpolate(progress, [0, 1], [0, 1], {
    easing: ease,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const isHorizontal = direction === "left" || direction === "right";
  const sign = direction === "left" || direction === "up" ? -1 : 1;

  const translateA = sign * 100 * p; // percent
  const translateB = sign * (-100 + 100 * p);

  const transformA = isHorizontal
    ? `translateX(${translateA}%)`
    : `translateY(${translateA}%)`;
  const transformB = isHorizontal
    ? `translateX(${translateB}%)`
    : `translateY(${translateB}%)`;

  const shadowVisible = separatorShadow && p > 0.02 && p < 0.98;

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      <AbsoluteFill
        style={{
          transform: transformA,
          willChange: "transform",
        }}
      >
        <OffthreadVideo
          src={clipA}
          startFrom={startFromA}
          playbackRate={playbackRateA}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        {shadowVisible ? (
          <div
            style={{
              position: "absolute",
              [direction === "left" ? "right" : direction === "right" ? "left" : ""]:
                isHorizontal ? 0 : undefined,
              [direction === "up" ? "bottom" : direction === "down" ? "top" : ""]:
                !isHorizontal ? 0 : undefined,
              [isHorizontal ? "top" : "left"]: 0,
              [isHorizontal ? "width" : "height"]: 28,
              [isHorizontal ? "height" : "width"]: "100%",
              background:
                direction === "left"
                  ? "linear-gradient(90deg, transparent, rgba(0,0,0,0.4))"
                  : direction === "right"
                    ? "linear-gradient(-90deg, transparent, rgba(0,0,0,0.4))"
                    : direction === "up"
                      ? "linear-gradient(0deg, transparent, rgba(0,0,0,0.4))"
                      : "linear-gradient(180deg, transparent, rgba(0,0,0,0.4))",
              pointerEvents: "none",
            }}
          />
        ) : null}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          transform: transformB,
          willChange: "transform",
        }}
      >
        <OffthreadVideo
          src={clipB}
          startFrom={startFromB}
          playbackRate={playbackRateB}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
