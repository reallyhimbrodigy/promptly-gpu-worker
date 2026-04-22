import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import type { TornPaperProps } from "./types";


const jitter = (seed: number): number => {
  const s = (seed * 16807 + 11) % 2147483647;
  return ((s & 0x7fffffff) / 0x7fffffff) * 2 - 1;
};

export const TornPaper: React.FC<TornPaperProps> = ({
  startMs,
  durationMs,
  topText,
  bottomText,
  topStripRotation = -10,
  bottomStripRotation = 7,
  stripColor = "#1A1A1A",
  stripTextColor = "#FFFFFF",
  shadowColor = "#4CAF50",
  shadowOffsetX = 10,
  shadowOffsetY = 9,
  stripFontFamily = MG_FONTS.oswald,
  stripFontSize = 72,
  stripFontWeight = 700,
  stripLetterSpacing = "0.06em",
  stripPadding = [14, 32],
  stripGap = 120,
  stripsPositionTop = "25%",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const appearFrame = msToFrames(startMs, fps);
  const disappearFrame = msToFrames(startMs + durationMs, fps);

  if (frame < appearFrame - 2) return null;
  if (frame > disappearFrame + 24) return null;

  const stopFrame = Math.floor(frame / 4) * 4;

  const paperElapsed = frame - appearFrame;
  const paperY = interpolate(paperElapsed, [0, 6], [-100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const paperOpacity = interpolate(paperElapsed, [0, 2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const paperExitDelay = 6;
  const paperExitElapsed = frame - disappearFrame - paperExitDelay;
  const paperExitY = interpolate(paperExitElapsed, [0, 6], [0, -100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const paperExitOpacity = interpolate(paperExitElapsed, [3, 6], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const paperFinalY =
    paperY + (paperExitElapsed >= 0 ? paperExitY : 0);
  const paperFinalOpacity =
    paperOpacity * (paperExitElapsed >= 0 ? paperExitOpacity : 1);

  const stripsAppear = appearFrame + 8;
  const strip1Elapsed = stopFrame - stripsAppear;
  const strip2Elapsed = stopFrame - stripsAppear - 8;

  const s1Steps = [
    { x: 500, y: -80, r: 30, o: 0 },
    { x: 120, y: -10, r: topStripRotation - 8, o: 1 },
    { x: -12, y: 5, r: topStripRotation + 3, o: 1 },
    { x: 5, y: -2, r: topStripRotation - 1, o: 1 },
    { x: 0, y: 0, r: topStripRotation, o: 1 },
  ];
  const s1StepIdx = Math.min(
    Math.max(Math.floor(strip1Elapsed / 2), 0),
    s1Steps.length - 1,
  );
  const s1 = strip1Elapsed >= 0 ? s1Steps[s1StepIdx] : s1Steps[0];

  const s2Steps = [
    { x: -500, y: 70, r: -25, o: 0 },
    { x: -100, y: 10, r: bottomStripRotation + 8, o: 1 },
    { x: 15, y: -4, r: bottomStripRotation - 3, o: 1 },
    { x: -4, y: 2, r: bottomStripRotation + 1, o: 1 },
    { x: 0, y: 0, r: bottomStripRotation, o: 1 },
  ];
  const s2StepIdx = Math.min(
    Math.max(Math.floor(strip2Elapsed / 2), 0),
    s2Steps.length - 1,
  );
  const s2 = strip2Elapsed >= 0 ? s2Steps[s2StepIdx] : s2Steps[0];

  const s1Idle =
    s1StepIdx >= s1Steps.length - 1 && stopFrame < disappearFrame;
  const s2Idle =
    s2StepIdx >= s2Steps.length - 1 && stopFrame < disappearFrame;

  const stripExitElapsed = stopFrame - disappearFrame;
  const isStripExiting = stripExitElapsed >= 0;

  const s1ExitSteps = [
    { x: 0, y: 0, r: topStripRotation, o: 1 },
    { x: 120, y: -10, r: topStripRotation - 8, o: 1 },
    { x: 500, y: -80, r: 30, o: 0 },
  ];
  const s1ExitIdx = Math.min(
    Math.max(Math.floor(stripExitElapsed / 2), 0),
    s1ExitSteps.length - 1,
  );
  const s1Exit = isStripExiting
    ? s1ExitSteps[s1ExitIdx]
    : { x: 0, y: 0, r: 0, o: 1 };

  const s2ExitSteps = [
    { x: 0, y: 0, r: bottomStripRotation, o: 1 },
    { x: -100, y: 10, r: bottomStripRotation + 8, o: 1 },
    { x: -500, y: 70, r: -25, o: 0 },
  ];
  const s2ExitIdx = Math.min(
    Math.max(Math.floor((stripExitElapsed - 2) / 2), 0),
    s2ExitSteps.length - 1,
  );
  const s2Exit = isStripExiting
    ? s2ExitSteps[s2ExitIdx]
    : { x: 0, y: 0, r: 0, o: 1 };

  const s1Final = {
    x:
      (isStripExiting ? s1Exit.x : s1.x) +
      (s1Idle ? jitter(stopFrame * 11 + 19) * 2 : 0),
    y:
      (isStripExiting ? s1Exit.y : s1.y) +
      (s1Idle ? jitter(stopFrame * 5 + 41) * 2 : 0),
    r:
      (isStripExiting ? s1Exit.r : s1.r) +
      (s1Idle ? jitter(stopFrame * 3 + 7) * 1.5 : 0),
    o: isStripExiting ? s1Exit.o : s1.o,
  };
  const s2Final = {
    x:
      (isStripExiting ? s2Exit.x : s2.x) +
      (s2Idle ? jitter(stopFrame * 17 + 37) * 2 : 0),
    y:
      (isStripExiting ? s2Exit.y : s2.y) +
      (s2Idle ? jitter(stopFrame * 7 + 59) * 2 : 0),
    r:
      (isStripExiting ? s2Exit.r : s2.r) +
      (s2Idle ? jitter(stopFrame * 9 + 23) * 1.5 : 0),
    o: isStripExiting ? s2Exit.o : s2.o,
  };

  const dotTexture = {
    backgroundImage: `
      radial-gradient(circle, rgba(255,255,255,0.15) 1.5px, transparent 1.5px),
      radial-gradient(circle, rgba(255,255,255,0.05) 1.5px, transparent 1.5px),
      radial-gradient(circle, rgba(255,255,255,0.10) 1.5px, transparent 1.5px)
    `,
    backgroundSize: "10px 10px, 10px 10px, 10px 10px",
    backgroundPosition: "0px 0px, 5px 5px, 3px 8px",
  };

  const textStyle: React.CSSProperties = {
    fontFamily: stripFontFamily,
    fontSize: stripFontSize,
    fontWeight: stripFontWeight,
    color: stripTextColor,
    textTransform: "uppercase",
    letterSpacing: stripLetterSpacing,
    lineHeight: 1.1,
    whiteSpace: "nowrap",
  };

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          overflow: "hidden",
          transform: `translateY(${paperFinalY}%)`,
          opacity: paperFinalOpacity,
        }}
      >
        <Img
          src={staticFile("torn-paper.png")}
          style={{ width: "100%", display: "block" }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: stripsPositionTop,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: stripGap,
        }}
      >
        <div
          style={{
            position: "relative",
            display: "inline-block",
            transform: `translate(${s1Final.x}px, ${s1Final.y}px) rotate(${s1Final.r}deg)`,
            opacity: s1Final.o,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: shadowOffsetY,
              left: shadowOffsetX,
              width: "100%",
              height: "100%",
              backgroundColor: shadowColor,
            }}
          />
          <div
            style={{
              position: "relative",
              backgroundColor: stripColor,
              ...dotTexture,
              padding: `${stripPadding[0]}px ${stripPadding[1]}px`,
            }}
          >
            <span style={textStyle}>{topText}</span>
          </div>
        </div>

        <div
          style={{
            position: "relative",
            display: "inline-block",
            marginLeft: 10,
            transform: `translate(${s2Final.x}px, ${s2Final.y}px) rotate(${s2Final.r}deg)`,
            opacity: s2Final.o,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: shadowOffsetY,
              left: shadowOffsetX,
              width: "100%",
              height: "100%",
              backgroundColor: shadowColor,
            }}
          />
          <div
            style={{
              position: "relative",
              backgroundColor: stripColor,
              ...dotTexture,
              padding: `${stripPadding[0]}px ${stripPadding[1]}px`,
            }}
          >
            <span style={textStyle}>{bottomText}</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
