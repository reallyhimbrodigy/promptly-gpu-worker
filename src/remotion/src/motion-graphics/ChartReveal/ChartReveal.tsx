import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { ChartRevealProps, DataPoint } from "./types";


const TITLE_GAP = 32;
const VALUE_LABEL_GAP = 14;
const CATEGORY_LABEL_GAP = 16;
const DEFAULT_TEXT_SHADOW =
  "0 2px 8px rgba(0,0,0,0.85), 0 10px 28px rgba(0,0,0,0.5)";
const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

interface Pt {
  x: number;
  y: number;
}
interface CubicSegment {
  p0: Pt;
  p1: Pt;
  p2: Pt;
  p3: Pt;
}

function cubicPoint(p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: number): Pt {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const t2 = t * t;
  const a = mt2 * mt;
  const b = 3 * mt2 * t;
  const c = 3 * mt * t2;
  const d = t2 * t;
  return {
    x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    y: a * p0.y + b * p1.y + c * p2.y + d * p3.y,
  };
}
function cubicLength(p0: Pt, p1: Pt, p2: Pt, p3: Pt, samples = 24): number {
  let len = 0;
  let prev = p0;
  for (let i = 1; i <= samples; i++) {
    const t = i / samples;
    const cur = cubicPoint(p0, p1, p2, p3, t);
    const dx = cur.x - prev.x;
    const dy = cur.y - prev.y;
    len += Math.sqrt(dx * dx + dy * dy);
    prev = cur;
  }
  return len;
}
function buildCatmullRom(points: Pt[], tension = 0.5): CubicSegment[] {
  const segments: CubicSegment[] = [];
  if (points.length < 2) return segments;
  const tangent = (prev: Pt, next: Pt): Pt => ({
    x: ((next.x - prev.x) / 2) * tension,
    y: ((next.y - prev.y) / 2) * tension,
  });
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i];
    const p1 = points[i + 1];
    const prevAnchor = i === 0 ? points[0] : points[i - 1];
    const nextAnchor =
      i + 2 >= points.length ? points[i + 1] : points[i + 2];
    const t0 = tangent(prevAnchor, p1);
    const t1 = tangent(p0, nextAnchor);
    const c1: Pt = { x: p0.x + t0.x, y: p0.y + t0.y };
    const c2: Pt = { x: p1.x - t1.x, y: p1.y - t1.y };
    segments.push({ p0, p1: c1, p2: c2, p3: p1 });
  }
  return segments;
}
function cubicsToPath(segments: CubicSegment[]): string {
  if (segments.length === 0) return "";
  const first = segments[0];
  let d = `M ${first.p0.x.toFixed(2)} ${first.p0.y.toFixed(2)}`;
  for (const s of segments) {
    d +=
      ` C ${s.p1.x.toFixed(2)} ${s.p1.y.toFixed(2)},` +
      ` ${s.p2.x.toFixed(2)} ${s.p2.y.toFixed(2)},` +
      ` ${s.p3.x.toFixed(2)} ${s.p3.y.toFixed(2)}`;
  }
  return d;
}
function totalCubicLength(segments: CubicSegment[]): number {
  let sum = 0;
  for (const s of segments) sum += cubicLength(s.p0, s.p1, s.p2, s.p3, 24);
  return sum;
}

function mapLinePoints(data: DataPoint[], plotW: number, plotH: number): Pt[] {
  if (data.length === 0) return [];
  const values = data.map((d) => d.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const pad = (maxV - minV) * 0.1 || 1;
  const lo = minV - pad;
  const hi = maxV + pad;
  const range = hi - lo || 1;
  if (data.length === 1) {
    return [{ x: plotW / 2, y: plotH - ((data[0].value - lo) / range) * plotH }];
  }
  return data.map((d, i) => ({
    x: (i / (data.length - 1)) * plotW,
    y: plotH - ((d.value - lo) / range) * plotH,
  }));
}

function formatValue(
  value: number,
  prefix: string,
  suffix: string,
  decimals: number,
): string {
  const rounded = decimals > 0
    ? value.toFixed(decimals)
    : Math.round(value).toLocaleString();
  return `${prefix}${rounded}${suffix}`;
}

export const ChartReveal: React.FC<ChartRevealProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  chartType = "bar",
  data,
  title,
  prefix = "",
  suffix = "",
  decimals = 0,
  width = 900,
  height = 560,
  accentColor = "#C8551F",
  highlight,
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition({
    anchor,
    offsetX,
    offsetY,
    scale,
  });
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 40, defaultExitFrames: 12 },
  );

  if (!visible) return null;

  const exitDriftY = exitProgress * -16;
  const exitOpacity = 1 - exitProgress;

  const titleFadeIn = interpolate(localFrame, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(localFrame, [0, 6], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const BAR_START = 8;
  const BAR_STAGGER = 4;
  const BAR_SPRING_FRAMES = 14;
  const barCount = chartType === "bar" ? data.length : 0;
  const barSlot = barCount > 0 ? width / barCount : 0;
  const barWidth = barSlot * 0.7;
  const barGap = barSlot * 0.3;

  const barMax =
    barCount > 0 ? Math.max(...data.map((d) => Math.max(0, d.value))) : 1;
  const barScale = (value: number): number =>
    barMax > 0 ? (Math.max(0, value) / barMax) * height : 0;

  const barSpringValues: number[] =
    chartType === "bar"
      ? data.map((_, i) =>
          spring({
            fps,
            frame: localFrame - (BAR_START + i * BAR_STAGGER),
            config: SPRING_SNAPPY,
            durationInFrames: BAR_SPRING_FRAMES,
          }),
        )
      : [];

  const lastBarLanded =
    chartType === "bar"
      ? BAR_START + (data.length - 1) * BAR_STAGGER + BAR_SPRING_FRAMES
      : 28;

  const linePoints =
    chartType === "line" ? mapLinePoints(data, width, height) : [];
  const lineSegments =
    chartType === "line" ? buildCatmullRom(linePoints) : [];
  const linePathD = cubicsToPath(lineSegments);
  const linePathLength = totalCubicLength(lineSegments);
  const lineDrawRaw = interpolate(localFrame, [8, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lineDrawEased = easeOutCubic(lineDrawRaw);
  const lineDashOffset = linePathLength * (1 - lineDrawEased);

  const labelStart = chartType === "bar" ? lastBarLanded + 2 : 22;
  const labelEnd = labelStart + 8;
  const categoryFadeIn = interpolate(localFrame, [labelStart, labelEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const calloutStart = labelEnd + 2;
  const calloutSpring = spring({
    fps,
    frame: localFrame - calloutStart,
    config: SPRING_SNAPPY,
    durationInFrames: 8,
  });
  const calloutScale = interpolate(calloutSpring, [0, 1], [0, 1]);
  const calloutFadeIn = interpolate(
    localFrame,
    [calloutStart, calloutStart + 6],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const highlightIndex = highlight?.index ?? -1;
  const highlightDataPoint =
    highlightIndex >= 0 && highlightIndex < data.length
      ? data[highlightIndex]
      : null;
  const highlightLabel = highlightDataPoint
    ? highlight?.label ??
      formatValue(highlightDataPoint.value, prefix, suffix, decimals)
    : "";

  const svgPadTop = 4;
  const svgPadBottom = 4;
  const svgW = width;
  const svgH = height + svgPadTop + svgPadBottom;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          width,
          transform: `translateY(${exitDriftY}px)`,
          opacity: exitOpacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {title ? (
          <div
            style={{
              fontFamily: MG_FONTS.anton,
              fontSize: 64,
              fontWeight: 400,
              color: "#FFFFFF",
              letterSpacing: "0.01em",
              textTransform: "uppercase",
              lineHeight: 1,
              marginBottom: TITLE_GAP,
              opacity: titleFadeIn,
              transform: `translateY(${titleY}px)`,
              textShadow,
              textAlign: "center",
            }}
          >
            {title}
          </div>
        ) : null}

        <div style={{ position: "relative", width, height }}>
          <svg
            width={svgW}
            height={svgH}
            viewBox={`0 ${-svgPadTop} ${svgW} ${svgH}`}
            style={{
              display: "block",
              overflow: "visible",
              filter: "drop-shadow(0 8px 20px rgba(0,0,0,0.45))",
            }}
          >
            {chartType === "bar"
              ? data.map((d, i) => {
                  const full = barScale(d.value);
                  const sp = Math.max(0, barSpringValues[i] ?? 0);
                  const x = i * barSlot + barGap / 2;
                  const y = height - full;
                  const isPeak = i === highlightIndex;
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={y}
                      width={barWidth}
                      height={full}
                      rx={10}
                      ry={10}
                      fill={isPeak ? "#FFFFFF" : accentColor}
                      style={{
                        transform: `scaleY(${sp})`,
                        transformOrigin: `${(x + barWidth / 2).toFixed(2)}px ${height}px`,
                        transformBox: "view-box",
                      }}
                    />
                  );
                })
              : null}

            {chartType === "line" && lineSegments.length > 0 ? (
              <path
                d={linePathD}
                fill="none"
                stroke={accentColor}
                strokeWidth={8}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={linePathLength}
                strokeDashoffset={lineDashOffset}
              />
            ) : null}

            {chartType === "line"
              ? linePoints.map((pt, i) => {
                  const markerStart = 8 + (i / Math.max(1, linePoints.length - 1)) * 14 + 2;
                  const markerSpring = spring({
                    fps,
                    frame: localFrame - markerStart,
                    config: SPRING_SNAPPY,
                    durationInFrames: 6,
                  });
                  const markerScale = Math.max(0, markerSpring);
                  const isPeak = i === highlightIndex;
                  return (
                    <circle
                      key={i}
                      cx={pt.x}
                      cy={pt.y}
                      r={isPeak ? 14 : 9}
                      fill={isPeak ? "#FFFFFF" : accentColor}
                      stroke={isPeak ? accentColor : "#FFFFFF"}
                      strokeWidth={isPeak ? 5 : 0}
                      style={{
                        transform: `scale(${markerScale})`,
                        transformOrigin: `${pt.x.toFixed(2)}px ${pt.y.toFixed(2)}px`,
                        transformBox: "view-box",
                      }}
                    />
                  );
                })
              : null}
          </svg>

          {chartType === "bar"
            ? data.map((d, i) => {
                const sp = Math.max(0, Math.min(1, barSpringValues[i] ?? 0));
                const full = barScale(d.value);
                const animatedValue = d.value * sp;
                const display = formatValue(
                  animatedValue,
                  prefix,
                  suffix,
                  decimals,
                );
                const x = i * barSlot + barSlot / 2;
                const labelY = height - full * sp - VALUE_LABEL_GAP;
                const isPeak = i === highlightIndex;
                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      left: x,
                      top: labelY,
                      transform: "translate(-50%, -100%)",
                      fontFamily: MG_FONTS.anton,
                      fontSize: isPeak ? 48 : 36,
                      fontWeight: 400,
                      color: isPeak ? "#FFFFFF" : "#F2E9D6",
                      letterSpacing: "-0.01em",
                      lineHeight: 1,
                      whiteSpace: "nowrap",
                      fontVariantNumeric: "tabular-nums",
                      opacity: sp,
                      textShadow,
                    }}
                  >
                    {display}
                  </div>
                );
              })
            : null}

          {chartType === "line" && highlightDataPoint ? (
            <div
              style={{
                position: "absolute",
                left: linePoints[highlightIndex]?.x ?? 0,
                top: (linePoints[highlightIndex]?.y ?? 0) - 24,
                transform: `translate(-50%, -100%) scale(${calloutScale})`,
                transformOrigin: "50% 100%",
                opacity: calloutFadeIn,
                fontFamily: MG_FONTS.anton,
                fontSize: 72,
                fontWeight: 400,
                color: "#FFFFFF",
                letterSpacing: "-0.01em",
                lineHeight: 1,
                whiteSpace: "nowrap",
                textShadow,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {highlightLabel}
            </div>
          ) : null}
        </div>

        <div
          style={{
            position: "relative",
            width: "100%",
            marginTop: CATEGORY_LABEL_GAP,
            height: 28,
            opacity: categoryFadeIn,
          }}
        >
          {chartType === "bar"
            ? data.map((d, i) => {
                const cx = i * barSlot + barSlot / 2;
                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      left: cx,
                      top: 0,
                      transform: "translateX(-50%)",
                      fontFamily: MG_FONTS.inter,
                      fontSize: 22,
                      fontWeight: 600,
                      color: "#B8B0A1",
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      lineHeight: 1,
                      whiteSpace: "nowrap",
                      textShadow,
                    }}
                  >
                    {d.label ?? ""}
                  </div>
                );
              })
            : null}

          {chartType === "line" && data.length > 0 ? (
            <>
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  fontFamily: MG_FONTS.inter,
                  fontSize: 22,
                  fontWeight: 600,
                  color: "#B8B0A1",
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  lineHeight: 1,
                  textShadow,
                }}
              >
                {data[0].label ?? ""}
              </div>
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  top: 0,
                  fontFamily: MG_FONTS.inter,
                  fontSize: 22,
                  fontWeight: 600,
                  color: "#B8B0A1",
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  lineHeight: 1,
                  textShadow,
                }}
              >
                {data[data.length - 1].label ?? ""}
              </div>
            </>
          ) : null}
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
