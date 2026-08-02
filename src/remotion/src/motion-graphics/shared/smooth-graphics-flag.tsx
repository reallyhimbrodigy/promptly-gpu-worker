import React, { createContext, useContext } from "react";

/**
 * SMOOTH-GRAPHICS (Zac 2026-08-01) — the single reversible switch for the
 * motion-smoothness system: the zoom VELOCITY CAP (zoom/shared/velocity-cap.ts),
 * eased + ms-floored MG entrances/exits (useMGPhase), and the b-roll fade.
 *
 * Provided ONCE at the top of each render tree (PromptlyOverlay and
 * PromptlyMicroSegments) from `input.smoothGraphics`. Every migrated component
 * reads `useSmoothGraphics()` and branches: false → today's exact pixels
 * (fixed-frame, bare-linear, uncapped cubic), true → the smoothed curve.
 *
 * Default false, so any tree that forgets the provider renders the legacy look
 * rather than silently changing motion — the same fail-to-legacy contract as
 * motion-flag.tsx and resprung-flag.tsx.
 */
const SmoothGraphicsContext = createContext<boolean>(false);

export const SmoothGraphicsProvider: React.FC<{
  enabled: boolean;
  children: React.ReactNode;
}> = ({ enabled, children }) => (
  <SmoothGraphicsContext.Provider value={enabled}>
    {children}
  </SmoothGraphicsContext.Provider>
);

/** True when the smoothness system is active for this render. */
export const useSmoothGraphics = (): boolean => useContext(SmoothGraphicsContext);
