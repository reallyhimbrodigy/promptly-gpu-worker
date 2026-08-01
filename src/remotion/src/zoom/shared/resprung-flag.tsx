import React, { createContext, useContext } from "react";

/**
 * Single reversible switch for the re-sprung zoom settle (Zac ruling 2026-07-31).
 *
 * Provided ONCE at the top of the render tree from `input.resprungZooms`. The two
 * clamped zoom components (SnapReframe, FocusWindow) read `useResprungZooms()`
 * and branch their spring config:
 *   false → today's exact pixels: overshootClamping:true, the frozen hard-stop
 *           settle (the "de-sprung" bug — a clamped spring never overshoots and
 *           freezes at rest).
 *   true  → clamp removed + damping lowered (SnapReframe 28→22 ζ≈0.881,
 *           FocusWindow 24→19.5 ζ≈0.869) so the approach to rest is a smooth
 *           exponential. Mass is UNTOUCHED on purpose: raising mass would drop
 *           ω_n (20.8→16.1) and slow the animation — the opposite of punch.
 *           Lowering damping keeps ω_n and adds the (subtle, ~0.3-0.4%) overshoot.
 *           ζ≈0.87-0.89 is the ceiling: any lower and the overshoot peak lands
 *           below the 8-frame floor at 30fps and renders stepped.
 *
 * Default false, so any tree that forgets the provider renders today's clamped
 * look rather than silently changing the zoom settle.
 */
const ResprungZoomsContext = createContext<boolean>(false);

export const ResprungZoomsProvider: React.FC<{
  enabled: boolean;
  children: React.ReactNode;
}> = ({ enabled, children }) => (
  <ResprungZoomsContext.Provider value={enabled}>
    {children}
  </ResprungZoomsContext.Provider>
);

/** True when the re-sprung (un-clamped, lower-damping) zoom settle is active. */
export const useResprungZooms = (): boolean => useContext(ResprungZoomsContext);
