import type { SpringConfig } from "remotion";

// Tuned to land near Apple's iMessage pop-in feel: damping ratio ≈ 0.7,
// roughly 15% overshoot then settle. Previously damping=15 produced a
// critically-damped spring (no overshoot) that read as "robotic / utility
// transition." The bounce here is what sells "alive."
//   ζ = damping / (2·√(stiffness·mass)) = 10 / (2·√(200·0.5)) ≈ 0.71
export const SPRING_SNAPPY: SpringConfig = {
  damping: 10,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false,
};
