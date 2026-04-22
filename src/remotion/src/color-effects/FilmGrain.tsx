import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, random } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface FilmGrainProps {
  children: React.ReactNode;
  // Grain density 0..1 — how opaque the noise layer sits. Default 0.3.
  grainStrength?: number;
  // Grain scale — lower = finer, higher = coarser. Default 0.9.
  grainScale?: number;
  // Number of octaves for the noise — more = richer/slower. Default 2.
  grainOctaves?: number;
  // Add a subtle exposure flicker each frame. Default true.
  flicker?: boolean;
  // Keep grain monochrome. Default true.
  monochrome?: boolean;
  // How many frames pass between grain re-seeds. 1 = every frame (fast,
  // jittery), 3 = every 3 frames (~10 updates/sec at 30fps, calmer).
  // Default 3.
  grainStep?: number;
  // Avg dust specks per frame. Default 5.
  dustDensity?: number;
  // Avg emulsion scratches per frame. Default 0.8 — occasional flicker.
  scratchDensity?: number;
  intensity?: number;
  timing?: ColorTimingMode;
}

const DUST_LIFETIME = 2;
// Max scratch lookback — individual scratches pick their own 1-2f life.
const SCRATCH_MAX_LIFE = 2;
const rx = (key: string) => random(key);

interface Dust {
  x: number;
  y: number;
  size: number;
  born: number;
  life: number;
}

// Film-gate "scratches" as seen in real prints and pro plugins (AE Grain
// Damage, DaVinci Film Damage) are NOT long straight vertical bars. They
// are short curved hairline marks — a hair or fiber briefly caught in the
// gate, a grit scratch from a single frame-bump. A few percent of frame
// length, gently curved, thin as a hair, visible for 1-2 frames only.
interface Scratch {
  pathD: string; // SVG path in 0..100 viewbox coords
  thickness: number; // stroke width in px
  bright: boolean;
  opacity: number;
  born: number;
  life: number;
}

function buildDust(bornFrame: number, i: number): Dust {
  const base = `dust-${bornFrame}-${i}`;
  return {
    x: rx(`${base}-x`),
    y: rx(`${base}-y`),
    size: 2 + rx(`${base}-s`) * 4,
    born: bornFrame,
    life: DUST_LIFETIME + Math.floor(rx(`${base}-l`) * 2),
  };
}

function buildScratch(bornFrame: number, i: number): Scratch {
  const base = `scratch-${bornFrame}-${i}`;
  // Short segment length, 2-6 viewbox units — grit-trace scale
  const len = 2 + rx(`${base}-len`) * 4;
  const sx = 5 + rx(`${base}-sx`) * 90;
  const sy = 5 + rx(`${base}-sy`) * 90;
  const theta = rx(`${base}-theta`) * Math.PI * 2;
  const ex = sx + Math.cos(theta) * len;
  const ey = sy + Math.sin(theta) * len;

  // Cubic bezier with TWO control points (S-curve) — way more organic
  // than a single-curve Q arc. Real hair debris never bows once and
  // stops; it snakes. Control points placed at 1/3 and 2/3 of the line,
  // offset perpendicular in opposing directions.
  const perpX = -Math.sin(theta);
  const perpY = Math.cos(theta);
  const bow1 = (rx(`${base}-c1`) - 0.5) * len * 0.55;
  const bow2 = (rx(`${base}-c2`) - 0.5) * len * 0.55;

  const p1x = sx + (ex - sx) * 0.33 + perpX * bow1;
  const p1y = sy + (ey - sy) * 0.33 + perpY * bow1;
  const p2x = sx + (ex - sx) * 0.66 + perpX * bow2;
  const p2y = sy + (ey - sy) * 0.66 + perpY * bow2;

  const pathD = `M ${sx.toFixed(2)} ${sy.toFixed(2)} C ${p1x.toFixed(2)} ${p1y.toFixed(2)} ${p2x.toFixed(2)} ${p2y.toFixed(2)} ${ex.toFixed(2)} ${ey.toFixed(2)}`;

  return {
    pathD,
    thickness: 0.5 + rx(`${base}-t`) * 0.7,
    bright: rx(`${base}-b`) > 0.55,
    opacity: 0.55 + rx(`${base}-o`) * 0.4,
    born: bornFrame,
    life: 1 + Math.floor(rx(`${base}-l`) * 2),
  };
}

// Cinema film grain + authentic emulsion damage. Two animated grain layers
// for the core texture, plus occasional dust specks and short hairline
// scratches at random positions and slight angles — the kind of artefacts
// that accumulate on real film prints. All deterministic per frame.
export const FilmGrain: React.FC<FilmGrainProps> = ({
  children,
  grainStrength = 0.3,
  grainScale = 0.9,
  grainOctaves = 2,
  flicker = true,
  monochrome = true,
  grainStep = 3,
  dustDensity = 5,
  scratchDensity = 0.8,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const frame = useCurrentFrame();
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 4,
    defaultHoldFrames: 12,
    defaultReleaseFrames: 10,
    defaultFadeInFrames: 12,
  });

  // Bucket the frame so grain only re-seeds every `grainStep` frames.
  const grainTick = Math.floor(frame / Math.max(1, grainStep));

  const grainShiftX = useMemo(
    () => (random(`fg-x-${grainTick}`) - 0.5) * 60,
    [grainTick],
  );
  const grainShiftY = useMemo(
    () => (random(`fg-y-${grainTick}`) - 0.5) * 60,
    [grainTick],
  );

  const flickerBrightness = flicker
    ? 1 + (random(`fg-b-${frame}`) - 0.5) * 0.04 * k
    : 1;
  const contrast = 1 + 0.04 * k;

  const { dust, scratches } = useMemo(() => {
    const dustOut: Dust[] = [];
    const scratchesOut: Scratch[] = [];
    const maxLife = Math.max(DUST_LIFETIME + 2, SCRATCH_MAX_LIFE + 2);

    for (let bf = frame - maxLife; bf <= frame; bf++) {
      if (bf < 0) continue;

      // Dust
      const dWhole = Math.floor(dustDensity);
      const dFrac = dustDensity - dWhole;
      for (let i = 0; i < dWhole; i++) {
        const d = buildDust(bf, i);
        if (frame >= d.born && frame < d.born + d.life) dustOut.push(d);
      }
      if (dFrac > 0 && rx(`dust-spawn-${bf}`) < dFrac) {
        const d = buildDust(bf, dWhole);
        if (frame >= d.born && frame < d.born + d.life) dustOut.push(d);
      }

      // Scratches
      const sWhole = Math.floor(scratchDensity);
      const sFrac = scratchDensity - sWhole;
      for (let i = 0; i < sWhole; i++) {
        const sc = buildScratch(bf, i);
        if (frame >= sc.born && frame < sc.born + sc.life) scratchesOut.push(sc);
      }
      if (sFrac > 0 && rx(`scratch-spawn-${bf}`) < sFrac) {
        const sc = buildScratch(bf, sWhole);
        if (frame >= sc.born && frame < sc.born + sc.life) scratchesOut.push(sc);
      }
    }
    return { dust: dustOut, scratches: scratchesOut };
  }, [frame, dustDensity, scratchDensity]);

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `contrast(${contrast}) brightness(${flickerBrightness})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Main grain — overlay */}
      <ColorEffectLayer
        style={{
          opacity: grainStrength * k,
          mixBlendMode: "overlay",
          transform: `translate(${grainShiftX}px, ${grainShiftY}px) scale(1.15)`,
        }}
      >
        <svg
          width="100%"
          height="100%"
          xmlns="http://www.w3.org/2000/svg"
          style={{ display: "block" }}
        >
          <filter id="film-grain">
            <feTurbulence
              type="fractalNoise"
              baseFrequency={grainScale}
              numOctaves={grainOctaves}
              stitchTiles="stitch"
              seed={grainTick % 211}
            />
            {monochrome && <feColorMatrix type="saturate" values="0" />}
          </filter>
          <rect width="100%" height="100%" filter="url(#film-grain)" />
        </svg>
      </ColorEffectLayer>

      {/* Fine grain — soft-light */}
      <ColorEffectLayer
        style={{
          opacity: grainStrength * 0.45 * k,
          mixBlendMode: "soft-light",
          transform: `translate(${-grainShiftY * 0.6}px, ${grainShiftX * 0.6}px) scale(1.2)`,
        }}
      >
        <svg
          width="100%"
          height="100%"
          xmlns="http://www.w3.org/2000/svg"
          style={{ display: "block" }}
        >
          <filter id="film-grain-fine">
            <feTurbulence
              type="fractalNoise"
              baseFrequency={grainScale * 1.6}
              numOctaves={1}
              stitchTiles="stitch"
              seed={(grainTick * 7) % 257}
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#film-grain-fine)" />
        </svg>
      </ColorEffectLayer>

      {/* Dust specks */}
      <ColorEffectLayer style={{ opacity: k, mixBlendMode: "multiply" }}>
        {dust.map((d, i) => (
          <div
            key={`d-${d.born}-${i}`}
            style={{
              position: "absolute",
              left: `${d.x * 100}%`,
              top: `${d.y * 100}%`,
              width: d.size,
              height: d.size,
              borderRadius: "50%",
              background: "rgba(8,6,4,0.9)",
              transform: "translate(-50%, -50%)",
              filter: "blur(0.6px)",
            }}
          />
        ))}
      </ColorEffectLayer>

      {/* Emulsion scratches — short S-curved hairlines. Each path is
          rendered three times: (1) a wide soft blurred halo for "glow/
          spread", (2) the main stroke, (3) a thin bright core down the
          middle for sub-pixel sparkle. `pathLength=1` + `strokeDasharray`
          crops 15% off each end so the scratch tapers instead of
          terminating flat — matches what a real grit trail looks like.
          Bright and dark scratches split into their own blend-mode SVGs. */}
      <ColorEffectLayer style={{ opacity: k, mixBlendMode: "screen" }}>
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, overflow: "visible" }}
        >
          <defs>
            <filter id="fg-scratch-glow">
              <feGaussianBlur stdDeviation="0.35" />
            </filter>
          </defs>
          {scratches
            .filter((s) => s.bright)
            .map((s, i) => (
              <g key={`sb-${s.born}-${i}`}>
                {/* halo */}
                <path
                  d={s.pathD}
                  stroke={`rgba(255,240,215,${s.opacity * 0.18})`}
                  strokeWidth={s.thickness * 2.6}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  filter="url(#fg-scratch-glow)"
                  pathLength={1}
                  strokeDasharray="0.7 1"
                  strokeDashoffset="-0.15"
                />
                {/* main */}
                <path
                  d={s.pathD}
                  stroke={`rgba(255,248,230,${s.opacity * 0.42})`}
                  strokeWidth={s.thickness}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  pathLength={1}
                  strokeDasharray="0.7 1"
                  strokeDashoffset="-0.15"
                />
                {/* bright core */}
                <path
                  d={s.pathD}
                  stroke={`rgba(255,255,255,${s.opacity * 0.55})`}
                  strokeWidth={Math.max(0.3, s.thickness * 0.45)}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  pathLength={1}
                  strokeDasharray="0.55 1"
                  strokeDashoffset="-0.225"
                />
              </g>
            ))}
        </svg>
      </ColorEffectLayer>
      <ColorEffectLayer style={{ opacity: k, mixBlendMode: "multiply" }}>
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, overflow: "visible" }}
        >
          <defs>
            <filter id="fg-scratch-shadow">
              <feGaussianBlur stdDeviation="0.4" />
            </filter>
          </defs>
          {scratches
            .filter((s) => !s.bright)
            .map((s, i) => (
              <g key={`sd-${s.born}-${i}`}>
                {/* soft shadow */}
                <path
                  d={s.pathD}
                  stroke={`rgba(0,0,0,${s.opacity * 0.35})`}
                  strokeWidth={s.thickness * 2.4}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  filter="url(#fg-scratch-shadow)"
                  pathLength={1}
                  strokeDasharray="0.7 1"
                  strokeDashoffset="-0.15"
                />
                {/* main */}
                <path
                  d={s.pathD}
                  stroke={`rgba(8,5,3,${s.opacity})`}
                  strokeWidth={s.thickness}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  pathLength={1}
                  strokeDasharray="0.7 1"
                  strokeDashoffset="-0.15"
                />
                {/* dark core */}
                <path
                  d={s.pathD}
                  stroke={`rgba(0,0,0,${s.opacity * 0.9})`}
                  strokeWidth={Math.max(0.25, s.thickness * 0.4)}
                  fill="none"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  pathLength={1}
                  strokeDasharray="0.55 1"
                  strokeDashoffset="-0.225"
                />
              </g>
            ))}
        </svg>
      </ColorEffectLayer>
    </AbsoluteFill>
  );
};
