import React, { createContext, useContext } from "react";

/**
 * Single reversible switch for the whole shared motion-token system.
 *
 * Provided ONCE at the top of the render tree from `input.motionTokens`. Every
 * migrated component reads `useMotionTokens()` and branches: false → its
 * preserved LEGACY_* config (today's exact pixels), true → the shared token.
 * Default false, so any tree that forgets the provider renders the legacy look
 * rather than silently changing motion.
 */
const MotionTokensContext = createContext<boolean>(false);

export const MotionTokensProvider: React.FC<{
  enabled: boolean;
  children: React.ReactNode;
}> = ({ enabled, children }) => (
  <MotionTokensContext.Provider value={enabled}>
    {children}
  </MotionTokensContext.Provider>
);

/** True when the Flare motion-token system is active for this render. */
export const useMotionTokens = (): boolean => useContext(MotionTokensContext);
