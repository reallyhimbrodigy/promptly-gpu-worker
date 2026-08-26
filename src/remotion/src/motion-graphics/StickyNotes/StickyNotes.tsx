import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { msToFrames } from "../shared/timing";
import type { StickyNotesProps } from "./types";
import {
  canvasMeasurer,
  CHARWRAP_FALLBACK_STYLE,
} from "../../captions/shared/fit";
import { asText } from "../../shared/asText";

// F4 width-fit guarantee (sticky_note text overlay): the note is a FIXED
// square, so the fit is two-axis — the longest word must fit the inner
// width and the greedy-wrapped line stack must fit the inner height. Walk
// the scale down until both hold; below the floor, char-break (the note
// never grows, text never escapes it).
const STICKY_FIT_FLOOR = 0.35;

// Pass #12 (audited): the fit only walked DOWN from 1 — the EditorialQuote
// ceiling class. A short live note ("SAY") sat at 50px inside a 300px square
// with room for ~2.6x. The walk now starts ABOVE 1 so short text GROWS to
// own the note; the same two-axis constraints bind, so long text shrinks
// exactly as before and can never escape.
const STICKY_FIT_CEIL = 2.6;

function fitStickyNote(
  text: string,
  noteFontSize: number,
  fontFamily: string,
  noteSize: number,
  // Rendered line-height (font census 2026-08-26): non-Latin notes render
  // taller lines, so the vertical budget must check the same factor.
  lineHeightEm = 1.1,
): { scale: number; floored: boolean } {
  const font = { fontFamily, fontWeight: 400 };
  const inner = noteSize - 20 - 8; // padding(10x2) + breathing room
  const vBudget = inner - 30; // marker glyph / underline allowance
  const words = asText(text).split(/\s+/).filter(Boolean);
  if (words.length === 0) return { scale: 1, floored: false };
  for (let s = STICKY_FIT_CEIL; s >= STICKY_FIT_FLOOR - 1e-6; s -= 0.05) {
    const size = noteFontSize * s;
    const widths = words.map((w) => canvasMeasurer(w, size, font));
    if (Math.max(...widths) > inner) continue;
    const spacePx = canvasMeasurer(" ", size, font);
    let lines = 1;
    let w = 0;
    for (const ww of widths) {
      const extra = w > 0 ? spacePx + ww : ww;
      if (w > 0 && w + extra > inner) {
        lines++;
        w = ww;
      } else {
        w += extra;
      }
    }
    if (lines * size * lineHeightEm <= vBudget) {
      if (s < 1 - 1e-6) {
        console.log(
          `[caption-fit] style=StickyNotes page="${text}" action=scale(${s.toFixed(2)})`,
        );
      }
      return { scale: s, floored: false };
    }
  }
  console.log(
    `[caption-fit] style=StickyNotes page="${text}" action=charwrap`,
  );
  return { scale: STICKY_FIT_FLOOR, floored: true };
}


const NOTE_POSITIONS: [number, number][] = [
  [-310, 20],
  [0, -30],
  [305, 15],
];

export const StickyNotes: React.FC<StickyNotesProps> = ({
  startMs,
  durationMs,
  notes,
  noteSize = 300,
  noteFontSize = 50,
  noteFontFamily = MG_FONTS.caveatBrush,
  showFog = true,
  topOffset = "5%",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Pass #12 (audited): the choreography offsets were 60fps-authored raw
  // frames, fps-blind. s converts them to render frames (same real time at
  // any fps); the oscillators below run in radians per SECOND.
  const s = fps / 60;

  const appearFrame = msToFrames(startMs, fps);
  const disappearFrame = msToFrames(startMs + durationMs, fps);

  if (frame < appearFrame - 10 * s) return null;
  if (frame > disappearFrame + 10 * s) return null;

  const elapsed = frame - appearFrame;

  const fogOpacity = interpolate(elapsed, [-5 * s, 10 * s], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fogFadeOut = interpolate(
    frame,
    [disappearFrame, disappearFrame + 10 * s],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const fogOverall = Math.min(fogOpacity, fogFadeOut);

  const renderableNotes = notes.slice(0, 3);

  return (
    <AbsoluteFill>
      {showFog ? (
        <div
          style={{
            opacity: fogOverall,
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "50%",
            background:
              "linear-gradient(to bottom, rgba(255,255,255,1) 0%, rgba(255,255,255,0.85) 30%, rgba(255,255,255,0.4) 60%, transparent 100%)",
          }}
        />
      ) : null}

      <div
        style={{
          position: "absolute",
          top: topOffset,
          left: "50%",
          transform: "translateX(-50%)",
          width: noteSize * 3 + 60,
          height: noteSize + 80,
        }}
      >
        {renderableNotes.map((note, i) => {
          const noteDelay = 5 * i * s;
          const noteElapsed = elapsed - noteDelay - 2 * s;
          // Oscillator clock in 60fps-equivalent units: the sway/rock/tilt
          // rates below are authored rad-per-60fps-frame; oscT keeps the
          // real-time frequency identical at any render fps.
          const oscT = noteElapsed * (60 / fps);

          const swayFreq = [0.35, 0.28, 0.32][i] ?? 0.3;
          const swayDir = i === 1 ? -1 : 1;

          const fallProgress = spring({
            fps,
            frame: noteElapsed,
            config: {
              mass: 0.6,
              damping: 14,
              stiffness: 160,
              overshootClamping: false,
            },
          });

          const enterY = interpolate(fallProgress, [0, 1], [-350, 0]);

          const swayAmount = interpolate(
            fallProgress,
            [0, 0.3, 0.6, 1],
            [0, 1, 0.5, 0],
          );
          const swayX =
            Math.sin(oscT * swayFreq) * 45 * swayAmount * swayDir;

          const rockAmount = interpolate(
            fallProgress,
            [0, 0.3, 0.7, 1],
            [0, 1, 0.4, 0],
          );
          const rockAngle =
            Math.sin(oscT * swayFreq + 0.5) * 18 * rockAmount;
          const enterRotation = note.rotation + rockAngle;

          const tiltAmount = interpolate(
            fallProgress,
            [0, 0.4, 0.8, 1],
            [0, 1, 0.3, 0],
          );
          const tiltX =
            Math.sin(oscT * swayFreq * 1.3) * 25 * tiltAmount;
          const tiltY =
            Math.cos(oscT * swayFreq * 0.9) * 15 * tiltAmount;

          const enterScale = interpolate(
            fallProgress,
            [0, 0.5, 1],
            [1.15, 1.03, 1],
          );

          const enterOpacity = interpolate(fallProgress, [0, 0.12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          const enterShadowBlur = interpolate(fallProgress, [0, 1], [35, 6]);
          const enterShadowY = interpolate(fallProgress, [0, 1], [25, 3]);
          const enterShadowOp = interpolate(
            fallProgress,
            [0, 1],
            [0.06, 0.2],
          );

          const exitDelay = (2 - i) * 3 * s;
          const exitElapsed = frame - disappearFrame + exitDelay;
          const isExiting = exitElapsed >= 0;

          const exitProgress = spring({
            fps,
            frame: Math.max(0, exitElapsed),
            config: {
              mass: 0.4,
              damping: 16,
              stiffness: 200,
              overshootClamping: true,
            },
          });

          const windAngles = [-35, 10, 40];
          const windAngle = (windAngles[i] ?? 0) * (Math.PI / 180);
          const windDist = interpolate(exitProgress, [0, 1], [0, 500]);
          const exitX = Math.sin(windAngle) * windDist;
          const exitY = -Math.cos(windAngle) * windDist;
          const exitSpin = interpolate(
            exitProgress,
            [0, 1],
            [0, (i === 1 ? -1 : 1) * 45],
          );
          const exitTiltX = interpolate(exitProgress, [0, 1], [0, 30]);
          const exitTiltY = interpolate(
            exitProgress,
            [0, 1],
            [0, (i === 0 ? -1 : 1) * 25],
          );
          const exitScale = interpolate(exitProgress, [0, 1], [1, 0.6]);
          const exitOpacity = interpolate(
            exitProgress,
            [0, 0.5, 1],
            [1, 0.7, 0],
          );

          const finalX = isExiting ? exitX : swayX;
          const finalY = isExiting ? exitY : enterY;
          const finalRot = isExiting
            ? note.rotation + exitSpin
            : enterRotation;
          const finalTiltX = isExiting ? exitTiltX : tiltX;
          const finalTiltY = isExiting ? exitTiltY : tiltY;
          const finalScale = isExiting ? exitScale : enterScale;
          const finalOpacity = isExiting ? exitOpacity : enterOpacity;
          const finalShadowBlur = isExiting
            ? interpolate(exitProgress, [0, 1], [6, 30])
            : enterShadowBlur;
          const finalShadowY = isExiting
            ? interpolate(exitProgress, [0, 1], [3, 20])
            : enterShadowY;
          const finalShadowOp = isExiting
            ? interpolate(exitProgress, [0, 1], [0.2, 0.03])
            : enterShadowOp;

          const [xOff, yOff] = NOTE_POSITIONS[i] ?? [0, 0];
          // Note text is user text (font census 2026-08-26): route the face
          // and fit-measure in the SAME routed stack that renders.
          const noteFace = mgTextFont(note.text, "caveatBrush");
          const noteLineHeight = Math.max(
            1.1,
            mgTextMetrics(note.text).lineHeight,
          );
          const noteFit = fitStickyNote(
            note.text,
            noteFontSize,
            noteFace,
            noteSize,
            noteLineHeight,
          );

          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                width: noteSize,
                height: noteSize,
                marginLeft: xOff - noteSize / 2,
                marginTop: yOff - noteSize / 2,
                zIndex: i,
                perspective: 800,
              }}
            >
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  backgroundColor: note.color,
                  transform: `translate(${finalX}px, ${finalY}px) rotateX(${finalTiltX}deg) rotateY(${finalTiltY}deg) rotate(${finalRot}deg) scale(${finalScale})`,
                  transformOrigin: "center center",
                  opacity: finalOpacity,
                  boxShadow: `2px ${finalShadowY}px ${finalShadowBlur}px rgba(0,0,0,${finalShadowOp})`,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 10,
                }}
              >
                {i === 0 ? (
                  // Drawn check, not a glyph (pass #12, audited): U+2713 does
                  // not exist in Caveat Brush — the ✓ silently rendered in a
                  // fallback face. An inline SVG has no font dependency and
                  // keeps the hand-drawn register.
                  <svg
                    width={noteFontSize * 0.8}
                    height={noteFontSize * 0.62}
                    viewBox="0 0 40 31"
                    style={{ marginBottom: 2 }}
                  >
                    <path
                      d="M3 17 C9 22 13 26 15 28 C21 18 30 8 37 3"
                      fill="none"
                      stroke="#1A1A1A"
                      strokeWidth={4.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : null}

                <span
                  style={{
                    fontFamily: noteFace,
                    fontSize: noteFontSize * noteFit.scale,
                    fontWeight: 400,
                    color: "#1A1A1A",
                    textAlign: "center",
                    lineHeight: noteLineHeight,
                    fontStyle: i === 2 ? "italic" : "normal",
                    maxWidth: "100%",
                    ...(noteFit.floored ? CHARWRAP_FALLBACK_STYLE : {}),
                  }}
                >
                  {note.text}
                </span>

                {i === 2 ? (
                  <div
                    style={{
                      width: "60%",
                      height: 2,
                      backgroundColor: "#1A1A1A",
                      marginTop: 4,
                      borderRadius: 2,
                      opacity: 0.5,
                    }}
                  />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
