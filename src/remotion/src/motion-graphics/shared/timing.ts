export function msToFrames(ms: number, fps: number): number {
  return Math.round((ms / 1000) * fps);
}
