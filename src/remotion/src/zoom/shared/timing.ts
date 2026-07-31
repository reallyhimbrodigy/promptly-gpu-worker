export function msToFrames(ms: number, fps: number): number {
  return Math.round((ms / 1000) * fps);
}

// Floor variant for the zoom's PAYOFF-LANDING start (eventStart). The peak-reach
// offset (ZOOM_PEAK_REACH_MS, applied Python-side) puts the perceptual peak on the
// anchor word; flooring the start frame keeps that peak from trailing the word by
// up to half a frame — a zoom that completes one frame EARLY reads inevitable, one
// frame LATE reads mistimed. Only differs from msToFrames when the start's sub-frame
// fraction is ≥ 0.5 (the round-up-into-lateness cases). eventEnd stays msToFrames.
// Mirrors Python's _anchor_land_frame for the MG pop so an MG + zoom on the same
// payoff word land coherent. Captions keep their own never-early ceil. (Zac 2026-07-28.)
export function msToFramesFloor(ms: number, fps: number): number {
  return Math.floor((ms / 1000) * fps);
}
