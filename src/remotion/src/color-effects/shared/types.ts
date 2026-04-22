// Shared types for color effects.
//
// Convention: every color effect wraps children (footage) and applies a
// graded look via CSS filters + blend-mode layers. Effects support two
// timing modes:
//   - persistent: fades in once, holds the look for the whole clip
//   - pulsed: beat-synced hits that fade in / hold / fade out
//
// Intensity (0..1) scales the effect so one component can be subtle or strong
// without forking the look.

export interface ColorPulse {
  // Frame at which the pulse peak is reached.
  peakFrame: number;
  // Frames to ramp in before the peak. Default: component-defined.
  attackFrames?: number;
  // Frames to hold at peak. Default: component-defined.
  holdFrames?: number;
  // Frames to fade out after hold. Default: component-defined.
  releaseFrames?: number;
  // Peak intensity (0..1). Overrides the base intensity when set.
  intensity?: number;
}

export type ColorTimingMode =
  | { mode: "persistent"; fadeInFrames?: number }
  | { mode: "pulsed"; pulses: ColorPulse[] };

export interface ColorPhaseState {
  // Effective intensity for this frame, 0..1.
  intensity: number;
  // True when intensity > 0.
  active: boolean;
}
