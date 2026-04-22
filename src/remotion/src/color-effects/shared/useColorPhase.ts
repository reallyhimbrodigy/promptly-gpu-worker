import { useCurrentFrame, interpolate } from "remotion";
import type {
  ColorPhaseState,
  ColorPulse,
  ColorTimingMode,
} from "./types";

interface Options {
  // Intensity applied when timing mode is "persistent", or the ceiling for
  // pulses that don't override intensity themselves.
  baseIntensity: number;
  defaultAttackFrames: number;
  defaultHoldFrames: number;
  defaultReleaseFrames: number;
  defaultFadeInFrames: number;
}

function pulseValue(
  frame: number,
  pulse: ColorPulse,
  opts: Options,
): number {
  const attack = pulse.attackFrames ?? opts.defaultAttackFrames;
  const hold = pulse.holdFrames ?? opts.defaultHoldFrames;
  const release = pulse.releaseFrames ?? opts.defaultReleaseFrames;
  const peak = pulse.intensity ?? opts.baseIntensity;

  const start = pulse.peakFrame - attack;
  const holdEnd = pulse.peakFrame + hold;
  const end = holdEnd + release;

  if (frame < start || frame > end) return 0;
  if (frame < pulse.peakFrame) {
    return interpolate(frame, [start, pulse.peakFrame], [0, peak], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  }
  if (frame <= holdEnd) return peak;
  return interpolate(frame, [holdEnd, end], [peak, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
}

export function useColorPhase(
  timing: ColorTimingMode,
  options: Options,
): ColorPhaseState {
  const frame = useCurrentFrame();

  if (timing.mode === "persistent") {
    const fadeIn = timing.fadeInFrames ?? options.defaultFadeInFrames;
    const intensity = interpolate(
      frame,
      [0, fadeIn],
      [0, options.baseIntensity],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
    return { intensity, active: intensity > 0.001 };
  }

  // pulsed: sum of all pulses (clamped to 1)
  let value = 0;
  for (const pulse of timing.pulses) {
    value = Math.max(value, pulseValue(frame, pulse, options));
  }
  return { intensity: Math.min(1, value), active: value > 0.001 };
}
