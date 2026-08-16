import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import { asText } from "../../shared/asText";
import { SafeImg } from "../../SafeImg";
import type { EndCardLine, EndCardProps } from "./types";

const clamp01 = (t: number): number => Math.max(0, Math.min(1, t));
const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const GLYPH: Record<string, string> = {
  globe: "○", phone: "✆", mail: "✉", at: "@",
};

// The card arrives slower than a lower third (it is the close, not a label) and
// leaves fast, because the video ends behind it.
const ENTER_FRAMES = 10;
const EXIT_FRAMES = 6;

export const EndCard: React.FC<EndCardProps> = ({
  kind, title, lines = [], palette, logoUrl,
  titlePx, linePx, sideMarginPx,
  // Named explicitly, not `...timing` — see the note in NamePlate.
  startMs, durationMs, enterFrames, exitFrames,
}) => {
  const { width, height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  // useMGPhase REQUIRES its defaults object; one argument is a TypeError at
  // mount, which would have killed the render the first time the card was ever
  // dispatched. See the same note in NamePlate.
  const { phase, enterProgress, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: ENTER_FRAMES, defaultExitFrames: EXIT_FRAMES },
  );
  if (phase === "before" || phase === "after") return null;

  const landscape = width >= height;
  const enter = easeOutCubic(clamp01(enterProgress));
  const out = 1 - clamp01(exitProgress);
  // Design-system px win over the canvas fraction (see EndCardProps.titlePx).
  const titleSize = Number.isFinite(titlePx as number) && (titlePx as number) > 0
    ? Math.round(titlePx as number)
    : Math.round(height * (landscape ? 0.085 : 0.055));
  const lineSize = Number.isFinite(linePx as number) && (linePx as number) > 0
    ? Math.round(linePx as number)
    : Math.round(titleSize * 0.34);
  const sidePad = Number.isFinite(sideMarginPx as number)
    ? Math.max(0, Math.min(Math.round(sideMarginPx as number), Math.round(width * 0.2)))
    : Math.round(width * 0.08);

  // The sting is a spring so it lands with weight; the other kinds rise.
  const stingScale = spring({ frame, fps, config: { damping: 14, mass: 0.7 } });

  const renderLine = (l: EndCardLine, i: number) => {
    const li = clamp01(enter * 1.6 - i * 0.12);
    return (
      <div key={i} style={{
        display: "flex", alignItems: "center", gap: Math.round(lineSize * 0.5),
        opacity: li, transform: `translateY(${interpolate(li, [0, 1], [12, 0])}px)`,
        color: palette.fg, fontFamily: MG_FONTS.inter, fontWeight: 600,
        fontSize: lineSize, letterSpacing: "0.02em",
      }}>
        {l.icon ? <span style={{ color: palette.accent }}>{GLYPH[l.icon] ?? ""}</span> : null}
        <span>{asText(l.text)}</span>
      </div>
    );
  };

  return (
    <AbsoluteFill style={{
      background: palette.bg, opacity: out,
      alignItems: "center", justifyContent: "center",
    }}>
      {kind === "logo_sting" ? (
        <div style={{ transform: `scale(${0.86 + stingScale * 0.14})`, opacity: enter }}>
          {logoUrl
            ? <SafeImg
                src={logoUrl}
                // DECORATION, deliberately. `primary` without onUnavailable
                // CANCELS THE RENDER, and a brand logo that fails to fetch must
                // never cost a user their video — the card still works as a
                // wordmark, which is the same fallback as having no logoUrl at
                // all. So the failure path and the absent path are identical.
                role="decoration"
                label="endcard-logo"
                fallback={
                  <div style={{ color: palette.fg, fontFamily: MG_FONTS.anton,
                                fontWeight: 900, fontSize: titleSize,
                                letterSpacing: "-0.03em" }}>{asText(title ?? "")}</div>
                }
                style={{ width: Math.round(width * 0.34) }}
              />
            : <div style={{ color: palette.fg, fontFamily: MG_FONTS.anton,
                            fontWeight: 900, fontSize: titleSize,
                            letterSpacing: "-0.03em" }}>{asText(title ?? "")}</div>}
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: `0 ${sidePad}px`,
                      maxWidth: width, overflowWrap: "break-word" }}>
          {title ? (
            <div style={{
              color: kind === "echo" ? palette.accent : palette.fg,
              fontFamily: MG_FONTS.anton, fontWeight: 800, fontSize: titleSize,
              lineHeight: 1.05, letterSpacing: "-0.02em",
              opacity: enter, transform: `translateY(${interpolate(enter, [0, 1], [20, 0])}px)`,
            }}>{asText(title)}</div>
          ) : null}
          {lines.length ? (
            <div style={{
              marginTop: Math.round(titleSize * 0.5), display: "flex",
              flexDirection: landscape ? "row" : "column",
              gap: Math.round(lineSize * (landscape ? 1.6 : 0.7)),
              alignItems: "center", justifyContent: "center", flexWrap: "wrap",
            }}>{lines.map(renderLine)}</div>
          ) : null}
          <div style={{
            width: interpolate(enter, [0, 1], [0, Math.round(width * 0.18)]),
            height: Math.max(3, Math.round(height * 0.005)),
            background: palette.accent, borderRadius: 2,
            margin: `${Math.round(titleSize * 0.55)}px auto 0`,
          }} />
        </div>
      )}
    </AbsoluteFill>
  );
};
