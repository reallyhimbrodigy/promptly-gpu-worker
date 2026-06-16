import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { OverlayCutEffect, type OverlayCutEffectType } from "./OverlayCutEffect";

export interface OverlayCutTestProps {
  /** "none" renders without an overlay (baseline); the others render with the
   *  named overlay centered on the cut frame. */
  overlayType: "none" | OverlayCutEffectType;
  /** Window length in frames. 11 ≈ 180ms at 60fps (production target);
   *  18 ≈ 300ms (the earlier flat-color test). */
  overlayDurationInFrames: number;
  /** Whether to play the test audio WAV. Same source across all three test
   *  renders → audio bit-identity verification works trivially. */
  withAudio: boolean;
  /** If set, the test runs in REAL-FOOTAGE mode: an <OffthreadVideo> plays
   *  underneath instead of solid AbsoluteFills. The video at this URL must
   *  exist on staticFile() — copy a real talking-head clip into
   *  src/remotion/public/ and pass its filename here. */
  videoUrl?: string;
  /** Source-time start (seconds) for clipA in real-footage mode. */
  clipAStartSec?: number;
  /** Source-time start (seconds) for clipB in real-footage mode. */
  clipBStartSec?: number;
  /** Source video's encoded fps — OffthreadVideo's startFrom is in source
   *  frames. The reference video used in this isolation test is 23.976fps. */
  sourceFps?: number;
  /** SceneTitle isolation only — title text on the panel. */
  sceneTitle?: string;
  /** SceneTitle isolation only — optional kicker above the divider. */
  sceneLabel?: string;
}

/**
 * OverlayCutTest — STANDALONE isolation test for overlay-on-top-of-hard-cut.
 *
 * Two modes:
 *
 *   FLAT-COLOR MODE (videoUrl undefined): the original Step 1 test.
 *     Solid cyan clip 0-2s, solid magenta clip 2-4s, frame counter visible
 *     in each. Proves the mechanism (audio bit-identity, no growth, no
 *     freeze, overlay local to window) over the cleanest possible signal.
 *
 *   REAL-FOOTAGE MODE (videoUrl set): runs the same overlay path over a
 *     real talking-head clip. Two source segments rendered back-to-back as
 *     a hard cut at frame 120. The OffthreadVideo plays MUTED (the test
 *     audio comes from the separate <Audio> source, so audio bit-identity
 *     remains trivially verifiable across the three variants). A small
 *     frame-counter HUD in the corner preserves the no-freeze check
 *     without needing big frame numbers baked into the visible content.
 *
 * The four assertions hold identically in both modes:
 *   1. Underlying content advances continuously (no freeze)
 *   2. Overlay strictly local to its window
 *   3. Output duration == sum of clip durations (240 frames at 60fps)
 *   4. Audio waveform byte-identical across overlay variants
 */
export const OverlayCutTest: React.FC<OverlayCutTestProps> = ({
  overlayType,
  overlayDurationInFrames,
  withAudio,
  videoUrl,
  clipAStartSec = 3,
  clipBStartSec = 11,
  sourceFps = 23.976,
  sceneTitle,
  sceneLabel,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const cutFrame = 120;
  const inClipA = frame < cutFrame;

  // Source-frame startFrom values. OffthreadVideo's startFrom is in SOURCE
  // frames at the video's encoded fps (verified against handler.py's
  // production usage at handler.py:~11367).
  const clipAStartFrames = Math.round(clipAStartSec * sourceFps);
  const clipBStartFrames = Math.round(clipBStartSec * sourceFps);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {videoUrl ? (
        <>
          <Sequence from={0} durationInFrames={120}>
            <AbsoluteFill>
              <OffthreadVideo
                src={staticFile(videoUrl)}
                startFrom={clipAStartFrames}
                playbackRate={1}
                muted={true}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </AbsoluteFill>
          </Sequence>
          <Sequence from={120} durationInFrames={120}>
            <AbsoluteFill>
              <OffthreadVideo
                src={staticFile(videoUrl)}
                startFrom={clipBStartFrames}
                playbackRate={1}
                muted={true}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </AbsoluteFill>
          </Sequence>

          {/* Small HUD so we can still verify no-freeze on real footage. */}
          <div style={{
            position: "absolute",
            left: 24, top: 24,
            padding: "10px 18px",
            background: "rgba(0,0,0,0.78)",
            color: "#FFEC4A",
            fontFamily: "monospace",
            fontSize: 42,
            fontWeight: 800,
            borderRadius: 10,
            letterSpacing: 2,
            zIndex: 10,
          }}>
            {inClipA ? "A" : "B"} · f={frame} · t={(frame / 60).toFixed(3)}s
          </div>
        </>
      ) : (
        <AbsoluteFill
          style={{
            background: inClipA ? "#0BC8FF" : "#FF3FA1",
            color: "white",
            fontFamily: "monospace",
            fontSize: 120,
            fontWeight: 900,
            textAlign: "center",
            alignItems: "center",
            justifyContent: "center",
            letterSpacing: 4,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
            <div style={{ fontSize: 80, opacity: 0.9 }}>
              {inClipA ? "CLIP A" : "CLIP B"}
            </div>
            <div style={{ fontSize: 220, lineHeight: 1 }}>{frame}</div>
            <div style={{ fontSize: 56, opacity: 0.85 }}>
              t = {(frame / 60).toFixed(3)}s
            </div>
            <div style={{ fontSize: 40, opacity: 0.6, marginTop: 80 }}>
              total: {durationInFrames}f · cut at {cutFrame}f
            </div>
          </div>
        </AbsoluteFill>
      )}

      {/* The overlay layer. Renders ON TOP. Strictly local to its window. */}
      {overlayType !== "none" && (
        <OverlayCutEffect
          type={overlayType}
          atFrame={cutFrame}
          durationInFrames={overlayDurationInFrames}
          title={sceneTitle}
          label={sceneLabel}
        />
      )}

      {/* Test audio. Same source in all renders; if overlay touches audio,
          the rendered audio md5 differs from the "none" baseline. */}
      {withAudio && <Audio src={staticFile("overlay-cut-test-audio.wav")} />}
    </AbsoluteFill>
  );
};
