import React, { createContext, useContext } from "react";
import { CameraMotionBlur } from "@remotion/motion-blur";

/**
 * Workstream D2 — MOTION BLUR. A parallel, reversible dark-flag system that
 * mirrors motion-flag.tsx (the Flare motion-token switch).
 *
 * WHY THIS EXISTS. 1080p/30 is the delivery target (Zac's ruling — the 30-vs-
 * 60fps retest is cancelled). Smoothness at 30fps comes from MOTION BLUR at the
 * correct shutter angle: a 30fps frame carrying a proper shutter-angle smear
 * reads smoother than 60fps without it, because the eye integrates the smear.
 *
 * The codebase ALREADY has @remotion/motion-blur's CameraMotionBlur wired — but
 * ONLY on the Lumen / generated-scene path (LumenScenes.tsx + the legacy
 * GeneratedScene branch in PromptlyRender.tsx). It is NOT on Flare's own motion:
 * component entrances/exits, composite zoom moves, transitions, and b-roll
 * cutaway pushes. The smoothness lever exists; it is simply wired in the wrong
 * place. This module extends it SELECTIVELY to those Flare motion sites.
 *
 * NEVER a global full-video blur. Only motion-bearing elements/windows are
 * wrapped, because motion frames are a fraction of the total — targeted blur
 * buys the smoothness without the whole-video `samples`× bill.
 *
 * DARK DEFAULT. Provided ONCE at the top of each render tree (PromptlyOverlay
 * and PromptlyMicroSegments) from `input.motionBlur`. When OFF, `MotionBlurWrap`
 * returns its children untouched (a bare fragment → NO added DOM, NO extra
 * paint), so the OFF render is byte-identical to the pre-D2 pipeline. The
 * pre-existing Lumen / generated-scene blur is NOT routed through this system —
 * it keeps its own always-on / spec-gated path and is unaffected either way.
 */

// ── The single tunable token (put the knobs in ONE place) ────────────────────
// Film convention: a 180° shutter. `samples` is the per-frame temporal
// resolution of the smear — higher = smoother, and render cost scales ~linearly
// with it (CameraMotionBlur renders the wrapped subtree `samples` times per
// frame). `shutterAngle` sets the temporal SPREAD of the smear only and costs
// NOTHING extra — the sample count is independent of the angle, so a wider
// angle (more smear) is free. The parent sweeps samples ∈ {3,6,10} and the
// shutter angle by overriding these via the render input (see
// PromptlyRenderInput.motionBlurSamples / motionBlurShutterAngle) — no recompile
// needed; these are only the fall-through defaults when the input omits them.
export const MOTION_BLUR_DEFAULTS = {
  samples: 6,
  shutterAngle: 180,
} as const;

export interface MotionBlurConfig {
  /** True when D2 motion blur is active for this render. */
  enabled: boolean;
  /** Copies rendered per frame across the shutter fraction (cost knob). */
  samples: number;
  /** Smear spread in degrees (180 = film convention). Free to raise. */
  shutterAngle: number;
}

const DISABLED: MotionBlurConfig = {
  enabled: false,
  samples: MOTION_BLUR_DEFAULTS.samples,
  shutterAngle: MOTION_BLUR_DEFAULTS.shutterAngle,
};

const MotionBlurContext = createContext<MotionBlurConfig>(DISABLED);

export const MotionBlurProvider: React.FC<{
  enabled: boolean;
  /** Omit → MOTION_BLUR_DEFAULTS.samples (6). */
  samples?: number;
  /** Omit → MOTION_BLUR_DEFAULTS.shutterAngle (180). */
  shutterAngle?: number;
  children: React.ReactNode;
}> = ({ enabled, samples, shutterAngle, children }) => {
  const value: MotionBlurConfig = {
    enabled,
    samples: samples ?? MOTION_BLUR_DEFAULTS.samples,
    shutterAngle: shutterAngle ?? MOTION_BLUR_DEFAULTS.shutterAngle,
  };
  return (
    <MotionBlurContext.Provider value={value}>
      {children}
    </MotionBlurContext.Provider>
  );
};

/** The resolved blur config for this render (enabled + tunables). */
export const useMotionBlur = (): MotionBlurConfig => useContext(MotionBlurContext);

/**
 * Wrap a MOVING element (an entrance/exit, a zoom move, a transition, a cutaway
 * push) in this. When the flag is ON it renders the child subtree through
 * CameraMotionBlur at the render's `samples` / `shutterAngle`. When OFF it
 * returns the children unchanged inside a bare fragment — no wrapper element, no
 * extra DOM, no extra paint — so the OFF path is byte-identical.
 *
 * Put this around the SPECIFIC moving element, never the whole composition.
 *
 * LAYOUT CONSTRAINT (learned on StatCard, 2026-08-20). When ON, CameraMotionBlur
 * RE-LAYS-OUT the subtree it wraps — it renders the children `samples` times into
 * its own compositing surface, so the wrapped node no longer participates in its
 * parent's normal flow. Wrap a SELF-CONTAINED layout group (a whole card, a whole
 * stack), NOT a single child of a flex/grid whose siblings size or position off
 * it — those siblings collapse onto the wrapped element (StatCard's accent + label
 * rode up onto the number until the wrap moved to the whole card). Rule of thumb:
 * if removing this node from the DOM would move its siblings, don't wrap just it.
 */
export const MotionBlurWrap: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { enabled, samples, shutterAngle } = useMotionBlur();
  if (!enabled) return <>{children}</>;
  return (
    <CameraMotionBlur samples={samples} shutterAngle={shutterAngle}>
      {children}
    </CameraMotionBlur>
  );
};
