// mgSchedule — 60fps-authored choreography keyframes, made fps-relative and
// DURATION-AWARE (pass #9, the DropCard recipe extracted for the catalogue).
//
// The absolute-frame-schedule class (confirmed across every audited component):
// raw frame constants are authored against the 60fps judging probe, then
// interpreted at production's 30fps — every beat runs 2x slower in real time —
// and they are blind to the component's actual window, so a short live
// placement reaches its payoff exactly at (or after) exit onset. The 60fps/4s
// probe masks all of it.
//
// K = mgSchedule({...}) maps an authored 60fps frame constant to render frames:
//   1. fps-relative: k * (fps / 60) — same real-time speed at any fps
//      (REMOTION_CONVENTIONS forward law);
//   2. compressed: if the authored choreography would not complete by
//      settleBy * window (window = the pre-exit frames), the whole schedule
//      scales down proportionally so the LAST authored keyframe lands there —
//      the payoff always settles with hold time before exit begins.
// At 60fps with a long window the mapping is identity, so existing 60fps
// before/after proof frames stay directly comparable.
export const mgSchedule = (opts: {
  fps: number;
  /** Pre-exit window in frames: exitStartFrame from useMGPhase. */
  window: number;
  /** The LAST authored keyframe (60fps frames) of the enter choreography. */
  authoredEnd: number;
  /** Fraction of the window the choreography must complete by. Default 0.85. */
  settleBy?: number;
}): ((f60: number) => number) => {
  const { fps, window, authoredEnd, settleBy = 0.85 } = opts;
  const scale = fps / 60;
  const scaledEnd = Math.max(1, authoredEnd * scale);
  const c = Math.min(1, (settleBy * Math.max(1, window)) / scaledEnd);
  return (f60: number) => f60 * scale * c;
};
