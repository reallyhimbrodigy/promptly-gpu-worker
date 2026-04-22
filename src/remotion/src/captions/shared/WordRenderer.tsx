import React from "react";
import type { TikTokToken } from "./types";

interface WordRendererProps {
  tokens: TikTokToken[];
  currentTimeMs: number;
  renderWord: (
    token: TikTokToken,
    index: number,
    isActive: boolean,
    progress: number,
  ) => React.ReactNode;
}

/**
 * Iterates through tokens and calls renderWord for each,
 * providing timing-aware isActive and progress values.
 */
export const WordRenderer: React.FC<WordRendererProps> = ({
  tokens,
  currentTimeMs,
  renderWord,
}) => {
  return (
    <>
      {tokens.map((token, index) => {
        const isActive =
          currentTimeMs >= token.fromMs && currentTimeMs < token.toMs;
        const tokenDuration = token.toMs - token.fromMs;
        const progress =
          tokenDuration > 0
            ? Math.max(
                0,
                Math.min(1, (currentTimeMs - token.fromMs) / tokenDuration),
              )
            : 0;

        return (
          <React.Fragment key={index}>
            {renderWord(token, index, isActive, progress)}
          </React.Fragment>
        );
      })}
    </>
  );
};
