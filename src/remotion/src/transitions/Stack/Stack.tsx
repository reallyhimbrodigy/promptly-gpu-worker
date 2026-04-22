import React from "react";
import { AbsoluteFill, interpolate, Easing, OffthreadVideo } from "remotion";
import type { StackProps } from "../types";

/**
 * Stack — Full iOS-style task switcher visual.
 * Dark blurred wallpaper background, stacked cards with rounded corners
 * and depth shadows, Clip A card slides left while Clip B card comes
 * forward from the stack behind it.
 */

const CARD_RADIUS = 40;
const CARD_SCALE = 0.82;

// Fake "other app" cards in the stack — positioned to the RIGHT of B
// because in an iOS switcher, the apps ahead of your current next-app
// sit further right. The whole row shifts LEFT together during a swipe.
// offsetX is in % of frame width to stay consistent with A/B's %-based
// translates. Depth is conveyed by scale + shadow, not by transparency.
const GHOST_CARDS = [
  { offsetX: -115, scale: 0.72 }, // one slot left of B
  { offsetX: -180, scale: 0.68 }, // two slots left of B
];

// Total horizontal shift of the whole stack during the slide phase.
// Matches how far B travels (-55% → 0% = +55%), so every card in the row
// moves by the same amount — that's what makes the row feel coherent.
const STACK_SHIFT = 55;

export const Stack: React.FC<StackProps> = ({
  clipA,
  clipB,
  progress,
  style,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const ease = Easing.bezier(0.32, 0.72, 0, 1);

  const enterSwitcher = interpolate(progress, [0, 0.3], [0, 1], {
    easing: ease,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const exitSwitcher = interpolate(progress, [0.7, 1], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const slideProgress = interpolate(progress, [0.3, 0.7], [0, 1], {
    easing: Easing.bezier(0.25, 0.46, 0.45, 0.94),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bgOpacity = interpolate(
    progress,
    [0, 0.25, 0.75, 1],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scaleA = interpolate(enterSwitcher, [0, 1], [1, CARD_SCALE], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const radiusA = interpolate(enterSwitcher, [0, 1], [0, CARD_RADIUS], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // A travels with the rest of the row for most of the slide (0 → +STACK_SHIFT),
  // then keeps going past the right edge as it fades out. Same velocity as
  // B/ghosts so the whole row reads as one coherent scroll.
  const slideXA = interpolate(slideProgress, [0, 0.7, 1], [0, STACK_SHIFT, 110], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacityA = interpolate(slideProgress, [0.6, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Card B: comes in from the right at the SAME size as A (CARD_SCALE)
  // during the slide phase, then zooms to full screen in phase 3. This
  // avoids the mismatch where A and B were different sizes mid-slide.
  const slideXB = interpolate(slideProgress, [0, 1], [-55, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const finalScaleB = interpolate(exitSwitcher, [0, 1], [CARD_SCALE, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scaleBTotal = progress < 0.7 ? CARD_SCALE : finalScaleB;
  const radiusB = interpolate(exitSwitcher, [0, 1], [CARD_RADIUS, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacityB = interpolate(progress, [0.15, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ghostOpacity = interpolate(
    progress,
    [0.1, 0.3, 0.7, 0.9],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#0a0a0f", ...style }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at 50% 30%, #1a1a30 0%, #0a0a0f 70%)",
          opacity: bgOpacity,
        }}
      />

      {GHOST_CARDS.map((ghost, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: ghostOpacity,
            transform: `translateX(${ghost.offsetX + slideProgress * STACK_SHIFT}%) scale(${ghost.scale})`,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              width: "92%",
              height: "85%",
              borderRadius: CARD_RADIUS,
              background: "#ffffff",
              boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
            }}
          />
        </div>
      ))}

      <AbsoluteFill
        style={{
          transform: `translateX(${slideXB}%) scale(${scaleBTotal})`,
          borderRadius: radiusB,
          overflow: "hidden",
          opacity: opacityB,
          boxShadow:
            progress > 0.15 && progress < 0.95
              ? `0 20px 60px rgba(0,0,0,0.5)`
              : "none",
        }}
      >
        <OffthreadVideo
          src={clipB}
          startFrom={startFromB}
          playbackRate={playbackRateB}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      {opacityA > 0.01 && (
        <AbsoluteFill
          style={{
            transform: `translateX(${slideXA}%) scale(${scaleA})`,
            borderRadius: radiusA,
            overflow: "hidden",
            opacity: opacityA,
            boxShadow: `0 20px 60px rgba(0,0,0,${0.5 * (1 - slideProgress)})`,
          }}
        >
          <OffthreadVideo
            src={clipA}
            startFrom={startFromA}
            playbackRate={playbackRateA}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}

      <div
        style={{
          position: "absolute",
          bottom: 18,
          left: "50%",
          transform: "translateX(-50%)",
          width: 140,
          height: 5,
          borderRadius: 3,
          backgroundColor: `rgba(255,255,255,${0.7 * bgOpacity})`,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
