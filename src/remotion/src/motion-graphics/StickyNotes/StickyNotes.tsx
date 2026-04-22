import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import type { StickyNotesProps } from "./types";


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

  const appearFrame = msToFrames(startMs, fps);
  const disappearFrame = msToFrames(startMs + durationMs, fps);

  if (frame < appearFrame - 10) return null;
  if (frame > disappearFrame + 10) return null;

  const elapsed = frame - appearFrame;

  const fogOpacity = interpolate(elapsed, [-5, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fogFadeOut = interpolate(
    frame,
    [disappearFrame, disappearFrame + 10],
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
          const noteDelay = 5 * i;
          const noteElapsed = elapsed - noteDelay - 2;

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
            Math.sin(noteElapsed * swayFreq) * 45 * swayAmount * swayDir;

          const rockAmount = interpolate(
            fallProgress,
            [0, 0.3, 0.7, 1],
            [0, 1, 0.4, 0],
          );
          const rockAngle =
            Math.sin(noteElapsed * swayFreq + 0.5) * 18 * rockAmount;
          const enterRotation = note.rotation + rockAngle;

          const tiltAmount = interpolate(
            fallProgress,
            [0, 0.4, 0.8, 1],
            [0, 1, 0.3, 0],
          );
          const tiltX =
            Math.sin(noteElapsed * swayFreq * 1.3) * 25 * tiltAmount;
          const tiltY =
            Math.cos(noteElapsed * swayFreq * 0.9) * 15 * tiltAmount;

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

          const exitDelay = (2 - i) * 3;
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
                  <span
                    style={{
                      fontSize: noteFontSize * 0.8,
                      color: "#1A1A1A",
                      marginBottom: 2,
                      fontFamily: noteFontFamily,
                    }}
                  >
                    ✓
                  </span>
                ) : null}

                <span
                  style={{
                    fontFamily: noteFontFamily,
                    fontSize: noteFontSize,
                    fontWeight: 400,
                    color: "#1A1A1A",
                    textAlign: "center",
                    lineHeight: 1.1,
                    fontStyle: i === 2 ? "italic" : "normal",
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
