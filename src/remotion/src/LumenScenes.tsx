import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";
import type { GeneratedSceneSpec } from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// LUMEN DESIGNED SCENES (Increment 3, Zac 2026-07-17) — the pivot.
//
// A scene is a Remotion-DESIGNED composition — typography, layout, palette and
// motion authored as code — into which the image model contributes at most ONE
// hero asset on a clean field (alpha-recovered). What this makes
// unconstructible, by construction:
//   · garbled text  — every glyph is composited type; the model never draws one
//   · off-palette   — palette is applied in code from the palette input; it is
//                     never serialized into an image prompt (hint-leak law)
//   · static frames — the shell applies idle motion + a camera move + motion
//                     blur to EVERYTHING; a motionless scene cannot be authored
//
// The aliveness grammar (the base, not a per-scene choice):
//   · continuous idle motion on every element (slow float/bob/drift — sin-based,
//     deterministic per frame)
//   · a camera move on every scene (gentle push or sweep, eased — never linear)
//   · CameraMotionBlur wraps all animated layers — this + continuous easing IS
//     the "shot at 240fps" property
//   · scene duration discipline (~1.5-2.5s) is enforced by the Python projector
// ─────────────────────────────────────────────────────────────────────────────

const clamp01 = (t: number) => Math.max(0, Math.min(1, t));

/** Bare paths resolve via staticFile; URLs pass through (mirrors resolveSrc). */
const src = (s: string): string =>
  /^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//") ? s : staticFile(s);

/** Deterministic idle drift — every element breathes. phase de-syncs siblings. */
const idle = (frame: number, fps: number, phase = 0, ampPx = 6, periodS = 3.2) => {
  const w = (2 * Math.PI) / (periodS * fps);
  return {
    y: Math.sin(frame * w + phase) * ampPx,
    x: Math.cos(frame * w * 0.7 + phase * 1.3) * ampPx * 0.45,
    r: Math.sin(frame * w * 0.5 + phase) * 0.8, // degrees
  };
};

/** Palette with safe fallbacks — colors arrive as code values, never prompts. */
// Lighten a too-dark color toward legibility on a dark background while KEEPING
// its hue (brand character). A scene label whose accent falls back to a dark bg
// color must never render dark-on-dark — it was invisible before this.
const legibleOnDark = (hex: string | null | undefined) => {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(hex || "");
  if (!m) return "#C9D6F0";
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b; // 0..255
  if (lum >= 150) return `#${m[1]}`; // already light enough
  const mix = (ch: number) => Math.round(ch + (255 - ch) * 0.72); // blend toward white, keep hue
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
};

const pal = (colors: string[] | null | undefined) => {
  const c = (colors || []).filter(Boolean);
  return {
    a: c[0] || "#4F9DF7",
    b: c[1] || c[0] || "#101018",
    accent: c[2] || c[0] || "#4F9DF7",
    // the label/UI accent — always legible on the dark scene world
    labelInk: legibleOnDark(c[2] || c[0] || "#4F9DF7"),
    ink: "#FFFFFF",
  };
};

// ── The shell: background world + camera + blur — every scene lives inside ──
const LumenShell: React.FC<{
  colors: string[] | null | undefined;
  camera: "push" | "sweep";
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ colors, camera, durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pal(colors);
  // Camera: gentle, eased, spans the whole scene — never linear, never still.
  const prog = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  const camScale = camera === "push" ? 1.02 + 0.07 * prog : 1.06;
  const camX = camera === "sweep" ? interpolate(prog, [0, 1], [26, -26]) : 0;
  const camRotY = camera === "sweep" ? interpolate(prog, [0, 1], [2.2, -2.2]) : 0;
  // Boundary fade-out (matches the b-roll ~67ms out).
  const fadeFrames = Math.max(1, Math.round(fps * 0.067));
  const fadeOut = interpolate(
    frame,
    [durationInFrames - fadeFrames, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const glowDrift = idle(frame, fps, 1.1, 30, 7);
  return (
    <AbsoluteFill style={{ opacity: fadeOut, backgroundColor: p.b, overflow: "hidden" }}>
      {/* code-built world: deep gradient + a live glow that never sits still */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(160deg, ${p.b} 0%, ${p.a}26 58%, ${p.b} 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: `calc(50% + ${glowDrift.x * 4}px)`,
          top: `calc(42% + ${glowDrift.y * 3}px)`,
          width: "115%",
          aspectRatio: "1",
          transform: "translate(-50%,-50%)",
          background: `radial-gradient(circle, ${p.a}55 0%, ${p.a}18 34%, transparent 62%)`,
          filter: "blur(6px)",
        }}
      />
      <CameraMotionBlur samples={6} shutterAngle={180}>
        <AbsoluteFill
          style={{
            transform: `perspective(1100px) rotateY(${camRotY}deg) translateX(${camX}px) scale(${camScale})`,
            transformOrigin: "center",
          }}
        >
          {children}
        </AbsoluteFill>
      </CameraMotionBlur>
    </AbsoluteFill>
  );
};

// ── TypoStat — designed typographic stat; the count LANDS on the word ───────
const TypoStat: React.FC<{ spec: GeneratedSceneSpec }> = ({ spec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pal(spec.background.colors);
  const st = spec.stat || {};
  const target = Number(st.value ?? 0);
  // VALUE-LANDING (the proven Flare doctrine): the number reaches its final
  // figure exactly at landFrame — the emphasis word's onset on the shared clock.
  const landF = Math.max(1, spec.landFrame ?? Math.round(spec.durationInFrames * 0.4));
  const t = clamp01(frame / landF);
  const eased = 1 - Math.pow(1 - t, 3);
  const current = target * eased;
  const decimals = Number.isInteger(target) ? 0 : 1;
  const display = `${st.prefix || ""}${current.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${st.suffix || ""}`;
  // settle pulse ON the landing — the punch is the value arriving
  const pulse = interpolate(frame, [landF, landF + 4, landF + 10], [1, 1.055, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const drift = idle(frame, fps, 0.4, 5);
  const lineIn = spring({ frame: frame - Math.round(fps * 0.12), fps, config: { damping: 16, stiffness: 130, mass: 0.8 } });
  return (
    <LumenShell colors={spec.background.colors} camera="sweep" durationInFrames={spec.durationInFrames}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            transform: `translate(${drift.x}px, ${drift.y}px) rotate(${drift.r * 0.4}deg) scale(${pulse})`,
            textAlign: "center",
            padding: "0 70px",
          }}
        >
          <div
            style={{
              fontFamily: "Inter, Helvetica, sans-serif",
              fontWeight: 900,
              fontSize: 210,
              lineHeight: 0.96,
              letterSpacing: "-0.03em",
              color: p.ink,
              fontVariantNumeric: "tabular-nums",
              textShadow: `0 0 90px ${p.a}66, 0 10px 44px rgba(0,0,0,0.55)`,
            }}
          >
            {display}
          </div>
          {st.label ? (
            <div
              style={{
                marginTop: 20,
                fontFamily: "Inter, Helvetica, sans-serif",
                fontWeight: 700,
                fontSize: 44,
                letterSpacing: "0.24em",
                color: p.labelInk,
                textTransform: "uppercase",
                opacity: lineIn,
                transform: `translateY(${(1 - lineIn) * 26}px)`,
              }}
            >
              {st.label}
            </div>
          ) : null}
          {st.supporting_line ? (
            <div
              style={{
                marginTop: 14,
                fontFamily: "Inter, Helvetica, sans-serif",
                fontWeight: 500,
                fontSize: 34,
                color: `${p.ink}CC`,
                opacity: lineIn,
                transform: `translateY(${(1 - lineIn) * 34}px)`,
              }}
            >
              {st.supporting_line}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </LumenShell>
  );
};

// ── HeroObject — one clean-field generated asset in a code glow void ────────
const ORBIT: Array<{ x: string; y: string }> = [
  { x: "18%", y: "24%" },
  { x: "74%", y: "30%" },
  { x: "16%", y: "68%" },
  { x: "72%", y: "72%" },
];

const HeroObject: React.FC<{ spec: GeneratedSceneSpec }> = ({ spec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pal(spec.background.colors);
  const drift = idle(frame, fps, 0, 12, 4.2);
  const enter = spring({ frame, fps, config: { damping: 15, stiffness: 110, mass: 0.9 } });
  return (
    <LumenShell colors={spec.background.colors} camera="push" durationInFrames={spec.durationInFrames}>
      {/* hero asset — alpha PNG floating with weight; drop-shadow seats it */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        {spec.subject.imageUrl ? (
          <Img
            src={src(spec.subject.imageUrl)}
            style={{
              maxWidth: "64%",
              maxHeight: "52%",
              objectFit: "contain",
              transform: `translate(${drift.x}px, ${drift.y}px) rotate(${drift.r}deg) scale(${0.9 + 0.1 * enter})`,
              opacity: enter,
              filter: `drop-shadow(0 34px 70px rgba(0,0,0,0.6)) drop-shadow(0 0 60px ${p.a}44)`,
            }}
          />
        ) : null}
      </AbsoluteFill>
      {/* orbit words — composited type popping ON their VO word frames */}
      {(spec.textLayers || []).slice(0, 4).map((t, i) => {
        const at = t.popFrame ?? Math.round(spec.durationInFrames * (0.18 + i * 0.16));
        const pop = spring({ frame: frame - at, fps, config: { damping: 13, stiffness: 240, mass: 0.6 } });
        const wDrift = idle(frame, fps, i * 1.7, 7, 3.6);
        const pos = ORBIT[i % ORBIT.length];
        if (frame < at) return null;
        return (
          <div
            key={`ho-${i}`}
            style={{
              position: "absolute",
              left: pos.x,
              top: pos.y,
              transform: `translate(-50%,-50%) translate(${wDrift.x}px, ${wDrift.y}px) scale(${pop})`,
              fontFamily: "Inter, Helvetica, sans-serif",
              fontWeight: 800,
              fontSize: 54,
              letterSpacing: "-0.01em",
              color: p.ink,
              textShadow: `0 4px 26px rgba(0,0,0,0.6), 0 0 40px ${p.a}55`,
              whiteSpace: "nowrap",
            }}
          >
            {t.content}
          </div>
        );
      })}
    </LumenShell>
  );
};

// ── PhotoCard — real imagery in tilted spring cards, continuously afloat ────
const CARD_TILT = [-6.5, 5.5, -3.5];

const PhotoCard: React.FC<{ spec: GeneratedSceneSpec }> = ({ spec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pal(spec.background.colors);
  const photos = (spec.photos || []).slice(0, 3);
  const caption = (spec.textLayers || [])[0];
  const capIn = spring({ frame: frame - Math.round(fps * 0.3), fps, config: { damping: 15, stiffness: 140, mass: 0.8 } });
  return (
    <LumenShell colors={spec.background.colors} camera="push" durationInFrames={spec.durationInFrames}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        {photos.map((url, i) => {
          const enter = spring({
            frame: frame - Math.round(i * fps * 0.14),
            fps,
            config: { damping: 14, stiffness: 150, mass: 0.9 },
          });
          const drift = idle(frame, fps, i * 2.1, 8, 4.6);
          const off = (i - (photos.length - 1) / 2) * 300;
          return (
            <div
              key={`pc-${i}`}
              style={{
                position: "absolute",
                transform:
                  `translate(${off + drift.x}px, ${drift.y + (1 - enter) * 190}px) ` +
                  `rotate(${CARD_TILT[i % 3] + drift.r}deg) scale(${0.85 + 0.15 * enter})`,
                opacity: enter,
                background: "#FFFFFF",
                padding: "16px 16px 52px 16px",
                borderRadius: 10,
                boxShadow: `0 30px 80px rgba(0,0,0,0.55), 0 0 60px ${p.a}33`,
              }}
            >
              <Img
                src={src(url)}
                style={{ width: 430, height: 540, objectFit: "cover", borderRadius: 4, display: "block" }}
              />
            </div>
          );
        })}
        {caption ? (
          <div
            style={{
              position: "absolute",
              bottom: "12%",
              left: 0,
              right: 0,
              textAlign: "center",
              fontFamily: "Inter, Helvetica, sans-serif",
              fontWeight: 800,
              fontSize: 58,
              color: p.ink,
              textShadow: "0 6px 30px rgba(0,0,0,0.65)",
              opacity: capIn,
              transform: `translateY(${(1 - capIn) * 40}px)`,
              padding: "0 60px",
            }}
          >
            {caption.content}
          </div>
        ) : null}
      </AbsoluteFill>
    </LumenShell>
  );
};

/** The dispatcher — PromptlyRender routes typed scenes here; legacy full-frame
 * stays on the old GeneratedScene path. */
export const LumenScene: React.FC<{ spec: GeneratedSceneSpec }> = ({ spec }) => {
  switch (spec.sceneType) {
    case "typo_stat":
      return <TypoStat spec={spec} />;
    case "hero_object":
      return <HeroObject spec={spec} />;
    case "photo_card":
      return <PhotoCard spec={spec} />;
    default:
      return null;
  }
};
