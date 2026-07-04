import React from "react";
import { AbsoluteFill } from "remotion";
import { DropBanner } from "./motion-graphics/DropBanner";
import { DropCard } from "./motion-graphics/DropCard";
import { SectionDivider } from "./motion-graphics/SectionDivider";
import { StepDivider } from "./motion-graphics/StepDivider";

// ---------------------------------------------------------------------------
// FootprintProbe — behind-eligibility measurement rig (BRANCH-ONLY).
// Renders ONE big-format candidate with typical props over a TRANSPARENT
// background; the harness renderStills a holding frame as PNG and measures
// the alpha bounding box against Zac's size gate (≥35% frame area OR ≥40%
// frame height). Size is the law; these are the evidence numbers.
// ---------------------------------------------------------------------------

const TIMING = { startMs: 0, durationMs: 5000 };

const CANDIDATES: Record<string, React.ReactNode> = {
  DropBanner: (
    <DropBanner
      {...TIMING}
      title="How It Works"
      subtitle="Three steps, thirty seconds"
      count={3}
      points={[
        { title: "1. Upload", caption: "Drop your clip in." },
        { title: "2. Vibe", caption: "Type what you want." },
        { title: "3. Send", caption: "The edit comes back." },
      ]}
    />
  ),
  DropCard: (
    <DropCard
      {...TIMING}
      title="How It Works"
      titleLead="3"
      steps={[{ label: "Upload" }, { label: "Vibe" }, { label: "Send" }]}
      points={[
        { title: "1. Upload", caption: "Drop your clip in." },
        { title: "2. Vibe", caption: "Type what you want." },
      ]}
    />
  ),
  SectionDivider_band: (
    <SectionDivider
      {...TIMING}
      title={"THE MISSING\nSTEP"}
      label="PART ONE"
      number="01"
      variant="band"
    />
  ),
  SectionDivider_band_top: (
    <SectionDivider
      {...TIMING}
      title={"HOW IT\nWORKS"}
      label="PART ONE"
      number="01"
      variant="band"
      anchor="top"
    />
  ),
  SectionDivider_titleonly_top: (
    <SectionDivider
      {...TIMING}
      title={"HOW IT\nWORKS"}
      label="PART ONE"
      number="01"
      variant="band"
      anchor="top"
      scrimColor="rgba(0,0,0,0)"
      vignetteStrength={0}
    />
  ),
  SectionDivider_full: (
    <SectionDivider
      {...TIMING}
      title={"THE MISSING\nSTEP"}
      label="PART ONE"
      number="01"
      variant="full"
    />
  ),
  StepDivider: (
    <StepDivider
      {...TIMING}
      title={"UPLOAD\nYOUR VIDEO"}
      step={1}
      totalSteps={3}
      kicker="STEP"
    />
  ),
};

export const FootprintProbe: React.FC<{
  candidate: string;
  dx?: number;
  dy?: number;
}> = ({ candidate, dx = 0, dy = 0 }) => {
  const node = CANDIDATES[candidate];
  if (!node) {
    throw new Error(`FootprintProbe: unknown candidate "${candidate}"`);
  }
  return (
    <AbsoluteFill style={{ transform: `translate(${dx}px, ${dy}px)` }}>
      {node}
    </AbsoluteFill>
  );
};
