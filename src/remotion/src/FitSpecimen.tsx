import React from "react";
import { AbsoluteFill } from "remotion";
import { CleanCut } from "./captions/CleanCut";
import { Cove } from "./captions/Cove";
import { Gadzhi } from "./captions/Gadzhi";
import { Lumen } from "./captions/Lumen";
import { Prime } from "./captions/Prime";
import { Pulse } from "./captions/Pulse";
import { Quintessence } from "./captions/Quintessence";
import { TwoTone } from "./captions/TwoTone";
import { TypewriterReveal } from "./captions/TypewriterReveal";
import { StickyNotes } from "./motion-graphics/StickyNotes";
import type { TikTokPage } from "./captions/shared/types";

// ---------------------------------------------------------------------------
// FitSpecimen — STANDALONE F4 battery composition (not used in production
// renders; the OverlayCutTest precedent). Renders ONE caption style (or the
// sticky_note overlay) with a worst-case-string page over a black plate at
// production canvas size, with the fit layer's STRICT invariant armed: any
// measured overflow throws and fails the still render outright. The battery
// (fit-battery.mjs + test_caption_fit.py) renders every style × worst-case
// string and pixel-scans the margins.
// ---------------------------------------------------------------------------

const FIT_CAPTION_MAP: Record<string, React.FC<never>> = {
  Prime: Prime as React.FC<never>,
  TypewriterReveal: TypewriterReveal as React.FC<never>,
  Cove: Cove as React.FC<never>,
  Lumen: Lumen as React.FC<never>,
  Pulse: Pulse as React.FC<never>,
  Quintessence: Quintessence as React.FC<never>,
  TwoTone: TwoTone as React.FC<never>,
  CleanCut: CleanCut as React.FC<never>,
  Gadzhi: Gadzhi as React.FC<never>,
};

export interface FitSpecimenProps {
  style: string; // caption style name, or "StickyNotes"
  words: string[];
  keywords?: string[];
  position?: "top" | "center" | "bottom";
}

function buildPage(words: string[]): TikTokPage {
  // Near-simultaneous reveals so every word (and every Typewriter char) is
  // settled well before the scan frame; single-word-at-a-time styles show
  // the LAST word — battery cases put the worst word last.
  const tokens = words.map((text, i) => ({
    text,
    fromMs: i * 40,
    toMs: i * 40 + 40,
  }));
  return {
    text: words.join(" "),
    startMs: 0,
    durationMs: 60_000,
    tokens,
  };
}

export const FitSpecimen: React.FC<FitSpecimenProps> = ({
  style,
  words,
  keywords = [],
  position = "bottom",
}) => {
  // Arm the strict invariant: any post-fit overflow throws inside the
  // render browser and the battery still FAILS loudly.
  (globalThis as { REMOTION_FIT_STRICT?: boolean }).REMOTION_FIT_STRICT = true;

  const page = buildPage(words);

  let subject: React.ReactNode;
  if (style === "StickyNotes") {
    subject = (
      <StickyNotes
        startMs={0}
        durationMs={60_000}
        showFog={false} // scan cleanliness: the fog is a designed full-width wash, not text
        notes={[
          { text: words.join(" "), color: "#FFE066", rotation: -3 },
          { text: "UPLOAD VIDEO", color: "#A8E6CF", rotation: 2 },
          { text: "TYPE VIBE", color: "#FFB3BA", rotation: -1 },
        ]}
      />
    );
  } else {
    const Comp = FIT_CAPTION_MAP[style] as React.FC<Record<string, unknown>>;
    if (!Comp) {
      throw new Error(`FitSpecimen: unknown style "${style}"`);
    }
    subject = (
      <Comp
        pages={[page]}
        position={position}
        keywords={keywords}
        specialWords={keywords}
        boxedWords={keywords}
        shineWords={keywords}
      />
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>{subject}</AbsoluteFill>
  );
};
