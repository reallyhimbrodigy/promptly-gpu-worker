/**
 * ZOOM VELOCITY CAP (Zac 2026-08-01) — bound the PER-FRAME DISPLACEMENT of every
 * ramp zoom, in pixels, at the delivery fps.
 *
 * WHY. "Choppy" is not gateable; pixels per frame are. A zoom is
 * `transform: scale(s)` about `transformOrigin (ox, oy)` on a full-canvas
 * element, so a source point (u, v) lands at
 *     ( W*(ox + s*(u-ox)) , H*(oy + s*(v-oy)) )
 * and between two delivered frames (s0 -> s1, ds = s1-s0) it moves
 *     ( W*(u-ox)*ds , H*(v-oy)*ds ).
 * A point is on screen iff |u-ox| <= max(ox,1-ox)/s (same for v), so the largest
 * displacement any VISIBLE pixel suffers in one frame is at the far visible
 * corner:
 *     d = |ds|/s * CORNER,   CORNER = hypot(W*max(ox,1-ox), H*max(oy,1-oy))
 * For a centred origin on 1080x1920, CORNER = 1101.45 px.
 *
 * MEASURED BEFORE (30fps, production defaults, centred origin):
 *     SmoothPush 1.22/1200ms .... 50.5 px/frame   (peak on frame 0)
 *     LetterboxPush 1.25/1400ms . 50.3 px/frame
 *     StagedPush +8%/280ms ...... 28.7 px/frame
 *     DepthPull 1.25/2200ms ..... 33.8 px/frame (x0.6 effective amplitude)
 * The DELIVERY_FPS 60->30 flip DOUBLED every one of those (same curve, half the
 * samples) — this is that regression, in pixels.
 *
 * THE CURVE IS MOST OF THE BUG. Every ramp uses cubic easing, whose peak
 * velocity is 3x the linear average, and `Easing.out` puts that 3x on the FIRST
 * frame. Note that `Easing.inOut(Easing.cubic)` does NOT fix this — it also
 * peaks at 3x, it merely moves the peak to the middle (50.5 -> 46.6 px/f,
 * measured). What actually cuts peak velocity is a TRAPEZOIDAL profile: ramp
 * velocity up, cruise, ramp down, peak = 1/(1-b/2) for blend budget b.
 * At b=0.5 that is 1.333x instead of 3x — a 2.3x cut for free, with no change
 * to timing or amplitude.
 *
 * THE PUNCH/GLIDE REGISTER SURVIVES because b sets the peak and the SKEW sets
 * only where that peak sits (SKEW_GLIDE = energy early / decelerate into the
 * word; SKEW_PUNCH = energy late / accelerate into it). Cap and register are
 * orthogonal knobs, so capping never silently flattens the vibe.
 *
 * THE THREE LEVERS, in the order we are willing to spend them:
 *   1. CURVE    — trapezoid instead of cubic. Free.
 *   2. LEAD-IN  — start the ramp EARLIER. The landing frame is a product law
 *                 (peak-on-word, see ZOOM_PEAK_REACH_MS), so ramps grow
 *                 BACKWARDS and releases grow FORWARDS. Costs screen-time only.
 *   3. AMPLITUDE— last resort, only when there is no headroom left. Costs the
 *                 zoom's perceptibility, so it is reported, never silent.
 *
 * Everything here is computed at the RENDER fps, so the cap is fps-INDEPENDENT:
 * at 60fps the same cap needs half the lead-in. Fixed frame counts were the root
 * of this whole class of bug.
 */

/** Largest distance any visible pixel may travel between two delivered frames. */
export const PEAK_DISPLACEMENT_CAP_PX = 11;

/**
 * The cap is solved at 30fps ALWAYS, whatever the render fps.
 *
 * Per-frame displacement is the physically correct judder invariant, so a naive
 * px/frame cap would let a 60fps render move TWICE AS FAST for the same
 * smoothness — the zoom would become a different edit at a different fps
 * (measured: 0.967s ramp at 30fps vs 0.483s at 60fps). Delivery is 30fps, so the
 * 30fps solution is canonical and every other fps reproduces its TIMING and
 * renders strictly smoother than the cap. This is the same ms-base decision
 * useMGPhase makes, for the same reason: fps-dependent motion is the root of
 * this whole class of bug.
 */
export const CAP_REFERENCE_FPS = 30;

/**
 * Never spend less than this blend budget (betaIn+betaOut). b=0 is constant
 * velocity with a hard start and a hard stop — a velocity discontinuity at both
 * ends, which is the front-loading defect we are removing, not a fix for it.
 * b=0.5 -> peak velocity 1.333x linear; b=1.0 (fully triangular) -> 2x.
 */
export const MIN_BLEND_FRACTION = 0.5;

/** Distance from the transform origin to the farthest visible corner. */
export function cornerPx(
  canvasW: number,
  canvasH: number,
  originX: number,
  originY: number,
): number {
  return Math.hypot(
    canvasW * Math.max(originX, 1 - originX),
    canvasH * Math.max(originY, 1 - originY),
  );
}

/**
 * The PUNCH-vs-GLIDE register, preserved under the cap.
 *
 * A SYMMETRIC trapezoid is neither punchy nor glidey, so capping naively would
 * silently delete the vibe register (viral = PUNCH, accelerate INTO the word;
 * everything else = GLIDE, decelerate into it). Skewing where the velocity peak
 * SITS keeps the register at an unchanged velocity ceiling: the blend budget
 * `b = betaIn + betaOut` alone sets peak velocity (k = 1/(1-b/2)), while the
 * split between the two ends sets the feel. So the cap and the register are
 * orthogonal — exactly what lets both be honoured at once.
 */
export const SKEW_GLIDE = 0.25;   // short ramp-up, long ramp-down: energy EARLY
export const SKEW_PUNCH = 0.75;   // long ramp-up, short ramp-down: energy LATE
export const SKEW_NEUTRAL = 0.5;

/**
 * Trapezoidal velocity profile as a Remotion easing (position, 0->1).
 * Velocity smoothsteps 0->1 over [0,betaIn], cruises, smoothsteps back to 0 over
 * [1-betaOut,1]. Peak velocity is exactly 1/(1-b/2) x the linear average with
 * b = betaIn+betaOut, and velocity is ZERO at both endpoints — no slam-in, no
 * slam-to-stop. `skew` splits b between the ends (see SKEW_* above); it changes
 * WHERE the peak sits, never how high it is.
 */
export function trapezoidEasing(blend: number, skew: number = SKEW_NEUTRAL): (t: number) => number {
  const b = Math.min(Math.max(blend, 0), 1);
  if (b <= 0) return (t) => Math.min(Math.max(t, 0), 1);
  const w = Math.min(Math.max(skew, 0.05), 0.95);
  const bIn = b * w;
  const bOut = b * (1 - w);
  const k = 1 / (1 - b / 2);
  return (tRaw) => {
    const t = Math.min(Math.max(tRaw, 0), 1);
    if (t < bIn) {
      const x = t / bIn;
      return k * bIn * (x ** 3 - 0.5 * x ** 4);
    }
    if (t <= 1 - bOut) {
      return k * (bIn * 0.5 + (t - bIn));
    }
    const x = (1 - t) / bOut;
    return 1 - k * bOut * (x ** 3 - 0.5 * x ** 4);
  };
}

/** Peak per-frame displacement (px) of a sampled scale ramp. */
export function peakDisplacementPx(scales: number[], corner: number): number {
  let peak = 0;
  for (let i = 0; i < scales.length - 1; i++) {
    const ds = scales[i + 1] - scales[i];
    const sMid = 0.5 * (scales[i] + scales[i + 1]);
    peak = Math.max(peak, (Math.abs(ds) * corner) / Math.max(sMid, 1e-9));
  }
  return peak;
}

function sampleRamp(
  frames: number,
  from: number,
  to: number,
  easing: (t: number) => number,
): number[] {
  const out: number[] = [];
  for (let f = 0; f <= frames; f++) out.push(from + (to - from) * easing(f / frames));
  return out;
}

export interface CappedRamp {
  /** Frames the move occupies, at the RENDER fps. */
  frames: number;
  /** Blend budget actually used (betaIn+betaOut). */
  beta: number;
  /** Register skew applied (SKEW_GLIDE / SKEW_PUNCH / SKEW_NEUTRAL). */
  skew: number;
  /** Target scale after any amplitude surrender (lever 3). */
  toScale: number;
  /** The easing to hand to Remotion's interpolate(). */
  easing: (t: number) => number;
  /** Peak per-frame displacement achieved, px. */
  peakPx: number;
  /** True when lever 3 fired — amplitude had to be surrendered. */
  amplitudeReduced: boolean;
}

interface PlanOpts {
  fromScale: number;
  toScale: number;
  /** Span available to grow into, in REFERENCE frames. */
  maxFrames: number;
  /** Minimum length in REFERENCE frames; we never SHORTEN an authored move. */
  minFrames: number;
  corner: number;
  cap?: number;
  skew?: number;
}

/**
 * Solve for the shortest C1 move that respects the cap, growing AWAY from the
 * anchor (backwards for a ramp-in, forwards for a release) and only surrendering
 * amplitude once the bound is hit.
 */
function solve(opts: PlanOpts): CappedRamp {
  const cap = opts.cap ?? PEAK_DISPLACEMENT_CAP_PX;
  const minFrames = Math.max(1, opts.minFrames);
  // Never SHORTEN an authored move, even when the bound leaves no headroom
  // (overlapping events, a zoom against the clip head). With no room to grow we
  // hold the authored length and fall through to lever 3 instead.
  const maxFrames = Math.max(minFrames, opts.maxFrames);
  const skew = opts.skew ?? SKEW_NEUTRAL;
  // Widest blend first = smoothest corners; fall back toward the C1 floor only
  // as the cap demands. The register (skew) is held FIXED throughout, so a
  // punchy zoom stays punchy at every blend the solver picks.
  const betas = [1.0, 0.85, 0.7, 0.6, MIN_BLEND_FRACTION];

  for (let n = minFrames; n <= maxFrames; n++) {
    for (const beta of betas) {
      const easing = trapezoidEasing(beta, skew);
      const peak = peakDisplacementPx(
        sampleRamp(n, opts.fromScale, opts.toScale, easing),
        opts.corner,
      );
      if (peak <= cap) {
        return {
          frames: n, beta, skew, toScale: opts.toScale,
          easing, peakPx: peak, amplitudeReduced: false,
        };
      }
    }
  }

  // Lever 3: out of headroom. Bisect the amplitude that fits at full length.
  const n = maxFrames;
  const easing = trapezoidEasing(MIN_BLEND_FRACTION, skew);
  let lo = opts.fromScale;
  let hi = opts.toScale;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const peak = peakDisplacementPx(sampleRamp(n, opts.fromScale, mid, easing), opts.corner);
    if (peak <= cap) lo = mid; else hi = mid;
  }
  return {
    frames: n, beta: MIN_BLEND_FRACTION, skew, toScale: lo,
    easing, peakPx: peakDisplacementPx(sampleRamp(n, opts.fromScale, lo, easing), opts.corner),
    amplitudeReduced: Math.abs(lo - opts.toScale) > 1e-6,
  };
}

/**
 * Solve the cap in REFERENCE (30fps) frames, then express the answer at the
 * render fps, so the move has the same DURATION at any fps.
 */
function solveAtReferenceFps(args: {
  fromScale: number;
  toScale: number;
  spanFrames: number;
  authoredFrames: number;
  fps: number;
  corner: number;
  cap?: number;
  skew?: number;
}): CappedRamp {
  const toRef = CAP_REFERENCE_FPS / args.fps;
  const r = solve({
    fromScale: args.fromScale,
    toScale: args.toScale,
    maxFrames: Math.max(1, Math.round(args.spanFrames * toRef)),
    minFrames: Math.max(1, Math.round(args.authoredFrames * toRef)),
    corner: args.corner,
    cap: args.cap,
    skew: args.skew,
  });
  return {
    ...r,
    frames: Math.max(args.authoredFrames, Math.round(r.frames / toRef)),
  };
}

/**
 * A ramp-IN that must LAND on `landFrame` (peak-on-word is a product law, so the
 * move grows backwards into `earliestFrame`, never forwards past the word).
 * Returns `startFrame` = landFrame - frames.
 */
export function planCappedRampIn(args: {
  fromScale: number;
  toScale: number;
  landFrame: number;
  earliestFrame: number;
  authoredFrames: number;
  fps: number;
  corner: number;
  cap?: number;
  /** SKEW_PUNCH / SKEW_GLIDE — the vibe register, preserved under the cap. */
  skew?: number;
}): CappedRamp & { startFrame: number } {
  const r = solveAtReferenceFps({
    fromScale: args.fromScale, toScale: args.toScale,
    spanFrames: Math.max(0, args.landFrame - args.earliestFrame),
    authoredFrames: args.authoredFrames, fps: args.fps,
    corner: args.corner, cap: args.cap, skew: args.skew,
  });
  return { ...r, startFrame: args.landFrame - r.frames };
}

/**
 * A release that STARTS at `startFrame` and may grow forwards to `latestFrame`
 * (nothing is anchored to the end of a release, so it is the cheap direction).
 * Returns `endFrame` = startFrame + frames.
 */
export function planCappedRelease(args: {
  fromScale: number;
  toScale: number;
  startFrame: number;
  latestFrame: number;
  authoredFrames: number;
  fps: number;
  corner: number;
  cap?: number;
  /** SKEW_PUNCH / SKEW_GLIDE — the vibe register, preserved under the cap. */
  skew?: number;
}): CappedRamp & { endFrame: number } {
  const r = solveAtReferenceFps({
    fromScale: args.fromScale, toScale: args.toScale,
    spanFrames: Math.max(0, args.latestFrame - args.startFrame),
    authoredFrames: args.authoredFrames, fps: args.fps,
    corner: args.corner, cap: args.cap, skew: args.skew,
  });
  return { ...r, endFrame: args.startFrame + r.frames };
}
