import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import type { PillMarqueeFontKey, PillMarqueeProps } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

// House DNA — legibility-first stacked shadows.
const PILL_TEXT_SHADOW =
  "0 0 12px rgba(0,0,0,0.72), 0 0 30px rgba(0,0,0,0.45), 1px 2px 5px rgba(0,0,0,0.5)";
const NEUTRAL_FILL =
  "linear-gradient(180deg, rgba(34,37,47,0.62) 0%, rgba(15,17,23,0.66) 100%)";
const CHAR_W = 0.6; // generous advance estimate so text fits the fixed-width pill
const DEFAULT_PALETTE = [
  "#5B8DEF",
  "#22C55E",
  "#F59E0B",
  "#EF4444",
  "#A855F7",
  "#06B6D4",
  "#EC4899",
  "#F5D90A",
];

const FONT_FAMILY: Record<PillMarqueeFontKey, string> = {
  inter: MG_FONTS.inter,
  oswald: MG_FONTS.oswald,
};

const rotate = <T,>(arr: T[], by: number): T[] => {
  const n = arr.length;
  if (n === 0) return arr;
  const k = ((by % n) + n) % n;
  return arr.slice(k).concat(arr.slice(0, k));
};

export const PillMarquee: React.FC<PillMarqueeProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  pills,
  rows = 3,
  hashtag = true,
  speed = 2.2,
  firstDirection = 1,
  fontKey = "inter",
  fontSize = 46,
  uppercase = false,
  textColor = "#FFFFFF",
  colorMode = "single",
  accentColor = "#FF6A3D",
  palette = DEFAULT_PALETTE,
  pillColor,
  glass = true,
  gap = 18,
  rowGap = 24,
  paddingX = 34,
  paddingY = 20,
  edgeFade = 200,
  offsetY = 0,
}) => {
  const { width } = useVideoConfig();
  const { visible, localFrame, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 16 },
  );

  if (!visible) return null;
  if (pills.length === 0) return null;

  const estPillW = (label: string): number => {
    const text = hashtag ? `#${label}` : label;
    return Math.ceil(text.length * fontSize * CHAR_W) + paddingX * 2 + 4;
  };

  const opacity =
    easeOutCubic(enterProgress) *
    interpolate(exitProgress, [0, 0.9], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  const renderPill = (label: string, key: string, hue: string) => {
    // Clean monochrome pill; the single accent shows only on the "#".
    const accent = colorMode === "varied" ? hue : accentColor;
    return (
      <div
        key={key}
        style={{
          flexShrink: 0,
          width: estPillW(label),
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          whiteSpace: "nowrap",
          padding: `${paddingY}px 0`,
          borderRadius: 999,
          background: pillColor ?? NEUTRAL_FILL,
          border: "1px solid rgba(255,255,255,0.22)",
          boxShadow:
            "inset 0 1px 0 rgba(255,255,255,0.16), inset 0 -1px 1px rgba(0,0,0,0.3)",
          ...(glass
            ? {
                backdropFilter: "blur(8px) saturate(120%)",
                WebkitBackdropFilter: "blur(8px) saturate(120%)",
              }
            : {}),
        }}
      >
        <span
          style={{
            fontFamily: FONT_FAMILY[fontKey],
            fontSize,
            fontWeight: 600,
            color: textColor,
            textTransform: uppercase ? "uppercase" : "none",
            letterSpacing: uppercase ? "0.06em" : "-0.01em",
            lineHeight: 1,
            textShadow: PILL_TEXT_SHADOW,
          }}
        >
          {hashtag ? <span style={{ color: accent }}>#</span> : null}
          {label}
        </span>
      </div>
    );
  };

  const fadeMask = `linear-gradient(90deg, transparent 0, #000 ${edgeFade}px, #000 calc(100% - ${edgeFade}px), transparent 100%)`;

  const pillH = fontSize + paddingY * 2;
  const bandH = rows * pillH + (rows - 1) * rowGap + 96;
  const scrimBg =
    "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.5) 26%, rgba(0,0,0,0.5) 74%, rgba(0,0,0,0) 100%)";

  return (
    <AbsoluteFill style={{ opacity }}>
      {/* Single soft backing shadow behind every row */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          transform: `translateY(${offsetY}px)`,
        }}
      >
        <div
          style={{
            height: bandH,
            background: scrimBg,
            filter: "blur(7px)",
            maskImage: fadeMask,
            WebkitMaskImage: fadeMask,
          }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "stretch",
          gap: rowGap,
          transform: `translateY(${offsetY}px)`,
          zIndex: 1,
        }}
      >
        {Array.from({ length: rows }).map((_, r) => {
        const dir = (r % 2 === 0 ? 1 : -1) * firstDirection;
        const rowPills = rotate(pills, r * 2);

        // Seamless period = one full list (sum of fixed pill widths + a gap each).
        const unitW = rowPills.reduce((acc, p) => acc + estPillW(p) + gap, 0);
        const copies = Math.ceil(width / unitW) + 2;

        const scroll = (localFrame * speed) % unitW;
        const baseX = dir > 0 ? scroll - unitW : -scroll;

        return (
          <div
            key={r}
            style={{
              position: "relative",
              width: "100%",
              overflow: "hidden",
              maskImage: fadeMask,
              WebkitMaskImage: fadeMask,
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                gap,
                width: "max-content",
                transform: `translateX(${baseX.toFixed(2)}px)`,
                willChange: "transform",
              }}
            >
              {Array.from({ length: copies }).flatMap((__, c) =>
                rowPills.map((p, i) => {
                  const origIdx = (i + r * 2) % pills.length;
                  const hue = palette[origIdx % palette.length];
                  return renderPill(p, `${r}-${c}-${i}`, hue);
                }),
              )}
            </div>
          </div>
        );
        })}
      </div>
    </AbsoluteFill>
  );
};
