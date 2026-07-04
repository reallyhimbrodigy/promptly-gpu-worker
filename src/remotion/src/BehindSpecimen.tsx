import React from "react";
import { AbsoluteFill, OffthreadVideo } from "remotion";
import { StatCard } from "./motion-graphics/StatCard";
import { SectionDivider } from "./motion-graphics/SectionDivider";

// ---------------------------------------------------------------------------
// BehindSpecimen — behind-layer Phase 1 harness (BRANCH-ONLY, never deployed).
// The sandwich under test: footage (bottom) → real MG card (middle) → RVM
// matted foreground person (top, alpha video). Also the decode-cost rig for
// the alpha-format probe: `alphaUrl` accepts WebM/VP9-alpha or ProRes 4444.
// ---------------------------------------------------------------------------

export interface BehindSpecimenProps {
  footageUrl: string;
  alphaUrl: string;
  startFromS: number; // window start inside the footage
  cardValue?: number;
  cardLabel?: string;
  cardSuffix?: string;
  cardOffsetX?: number;
  cardOffsetY?: number;
  mgType?: string; // "StatCard" (default) | "SectionDivider" (act-break specimen)
  dividerTitle?: string;
  dividerLabel?: string;
  dividerNumber?: string;
}

export const BehindSpecimen: React.FC<BehindSpecimenProps> = ({
  footageUrl,
  alphaUrl,
  startFromS,
  cardValue = 10,
  cardLabel = "VIDEOS AT ONCE",
  cardSuffix = "",
  cardOffsetX = 0,
  cardOffsetY = 0,
  mgType = "StatCard",
  dividerTitle = "HOW IT\nWORKS",
  dividerLabel = "PART ONE",
  dividerNumber = "01",
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo
        src={footageUrl}
        startFrom={Math.round(startFromS * 30)}
        muted
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <AbsoluteFill>
        {mgType === "SectionDivider" ? (
          <SectionDivider
            startMs={0}
            durationMs={60_000}
            title={dividerTitle}
            label={dividerLabel}
            number={dividerNumber}
            variant="band"
            anchor="center"
            offsetX={cardOffsetX}
            offsetY={cardOffsetY}
          />
        ) : (
          <StatCard
            startMs={0}
            durationMs={60_000}
            value={cardValue}
            label={cardLabel}
            suffix={cardSuffix}
            accentColor="#F5A11E"
            anchor="center"
            offsetX={cardOffsetX}
            offsetY={cardOffsetY}
          />
        )}
      </AbsoluteFill>
      <OffthreadVideo
        src={alphaUrl}
        transparent
        muted
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};
