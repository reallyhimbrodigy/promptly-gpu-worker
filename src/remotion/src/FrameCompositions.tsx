import React from "react";
import { AbsoluteFill, Freeze, interpolate, useCurrentFrame } from "remotion";
import { Video } from "@remotion/media";

// ── GENERATION-FREE COMPOSITIONS ────────────────────────────────────────────
//
// Four insert scenes built ENTIRELY from the user's own footage. No image
// model, no Vertex call, no quota, no per-scene latency, no generated-asset
// failure mode — the still is a frame of the video we are already rendering.
//
// WHY THIS MATTERS BEYOND COST. generated_scenes measured 0/779 planned jobs,
// and the prompt-v2 A/B just showed the planner asking for ZERO scenes even
// when handed a schema that could express one — so the decline is not a
// vocabulary problem. A composition the planner can ground in something it can
// SEE (a word index, pointing at a frame that certainly exists) asks far less
// of it than inventing a background/subject/motion triple for an image model.
//
// THE DESIGN LANGUAGE IS ART_DIRECTION.md §4, not invention:
//   · the still is TILTED 5-8 degrees, hard-edged, with a real drop shadow —
//     a physical object on a surface, never a full-bleed wallpaper;
//   · THREE DEPTH PLANES: background type -> still -> foreground type;
//   · elements OVERLAP AND OCCLUDE. "A stack of centred, non-overlapping boxes
//     reads as a slide. Tilt, overlap and depth read as design."
//   · flat near-white ground (#FEFCFD), palette colours supplied per job.
//
// EVERY TIME FIELD IS A WORD INDEX upstream; by the time props arrive here the
// worker has already derived the source SECOND for each still. Components never
// see a word index and never do clock arithmetic — there is one clock in this
// pipeline and it is not in the renderer.

const NEAR_WHITE = "#FEFCFD";
const INK = "#101014";

export interface SourceStillProps {
  sourceUrl: string;
  /** SECONDS into the source. Derived by the worker from a word index. */
  atSeconds: number;
  fps: number;
  tiltDeg?: number;
  widthPct?: number;
  style?: React.CSSProperties;
  label?: string;
}

/**
 * ONE FROZEN FRAME OF THE USER'S VIDEO, treated as a physical print.
 *
 * `Freeze` is what makes this generation-free AND cheap: the video element is
 * mounted at a fixed frame, so the still costs a seek rather than a decode of
 * the whole span, and it can never drift out of sync with the edit because it
 * IS the edit's source.
 */
export const SourceStill: React.FC<SourceStillProps> = ({
  sourceUrl, atSeconds, fps, tiltDeg = 0, widthPct = 62, style, label,
}) => {
  const frame = Math.max(0, Math.round((atSeconds || 0) * (fps || 30)));
  return (
    <div
      aria-label={label}
      style={{
        width: `${widthPct}%`,
        aspectRatio: "9 / 16",
        transform: `rotate(${tiltDeg}deg)`,
        // Hard edge + real shadow: a print on a surface, not a floating layer.
        boxShadow: "0 26px 60px rgba(16,16,20,0.34), 0 2px 6px rgba(16,16,20,0.22)",
        overflow: "hidden",
        background: INK,
        ...style,
      }}
    >
      <Freeze frame={frame}>
        <Video
          src={sourceUrl}
          startFrom={frame}
          // Muted and unlooped: this is a photograph, not a second playback.
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Freeze>
    </div>
  );
};

/** Shared entrance. Deliberately ONE motion for all four: §4's texture comes
 *  from composition, and a different entrance per component is the "uniform at
 *  a different rate" failure the doctrine names. */
const useRise = (durationFrames: number) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [0, Math.min(10, durationFrames)], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  return { opacity: p, translateY: (1 - p) * 34 };
};

export interface EvidenceCardProps {
  sourceUrl: string; fps: number; durationInFrames: number;
  atSeconds: number;
  claim: string;
  caption?: string;
  accent?: string;
}

/**
 * EVIDENCE CARD — "here is the thing I just said, on screen."
 *
 * The claim sits BEHIND the still as background type and the caption overlaps
 * it in front: three planes, occlusion in both directions, which is what stops
 * it reading as a slide.
 */
export const EvidenceCard: React.FC<EvidenceCardProps> = ({
  sourceUrl, fps, durationInFrames, atSeconds, claim, caption, accent = "#FF4D2E",
}) => {
  const { opacity, translateY } = useRise(durationInFrames);
  return (
    <AbsoluteFill style={{ background: NEAR_WHITE, opacity }}>
      {/* PLANE 1 — background type, cropped by the frame edge on purpose */}
      <div style={{
        position: "absolute", top: "12%", left: "-4%", right: "-4%",
        fontSize: 132, fontWeight: 800, lineHeight: 0.92, color: INK,
        letterSpacing: "-0.03em", opacity: 0.14, textTransform: "uppercase",
      }}>{claim}</div>
      {/* PLANE 2 — the user's own frame, tilted */}
      <AbsoluteFill style={{
        alignItems: "center", justifyContent: "center",
        transform: `translateY(${translateY}px)`,
      }}>
        <SourceStill sourceUrl={sourceUrl} atSeconds={atSeconds} fps={fps}
          tiltDeg={-6} widthPct={58} label="EvidenceCard.still" />
      </AbsoluteFill>
      {/* PLANE 3 — foreground type OVERLAPPING the still */}
      <div style={{
        position: "absolute", bottom: "16%", left: "6%", right: "10%",
        fontSize: 62, fontWeight: 800, color: INK, lineHeight: 1.02,
        letterSpacing: "-0.02em",
        textShadow: `0 2px 0 ${NEAR_WHITE}, 0 8px 26px rgba(16,16,20,0.28)`,
      }}>
        <span style={{ boxShadow: `inset 0 -0.34em 0 ${accent}55` }}>
          {caption || claim}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export interface DeviceMockupProps {
  sourceUrl: string; fps: number; durationInFrames: number;
  atSeconds: number;
  label?: string;
  accent?: string;
}

/**
 * DEVICE MOCKUP — the user's own frame inside a phone shell.
 *
 * For "here's what it looks like in the app / on my phone". The shell is drawn,
 * never an asset: an image would need fetching, versioning and a failure mode,
 * and a rounded rect with a bezel is the whole of it.
 */
export const DeviceMockup: React.FC<DeviceMockupProps> = ({
  sourceUrl, fps, durationInFrames, atSeconds, label, accent = "#FF4D2E",
}) => {
  const { opacity, translateY } = useRise(durationInFrames);
  return (
    <AbsoluteFill style={{ background: NEAR_WHITE, opacity }}>
      <div style={{
        position: "absolute", top: "9%", left: "6%",
        fontSize: 108, fontWeight: 800, color: accent, opacity: 0.16,
        letterSpacing: "-0.03em", textTransform: "uppercase",
      }}>{label || ""}</div>
      <AbsoluteFill style={{
        alignItems: "center", justifyContent: "center",
        transform: `translateY(${translateY}px)`,
      }}>
        {/* the shell — drawn, not fetched */}
        <div style={{
          padding: 14, borderRadius: 46, background: "#0B0B0F",
          transform: "rotate(5deg)",
          boxShadow: "0 34px 70px rgba(16,16,20,0.38), 0 2px 8px rgba(16,16,20,0.3)",
        }}>
          <SourceStill sourceUrl={sourceUrl} atSeconds={atSeconds} fps={fps}
            widthPct={100} label="DeviceMockup.still"
            style={{ width: 430, borderRadius: 34, boxShadow: "none" }} />
        </div>
      </AbsoluteFill>
      {label ? (
        <div style={{
          position: "absolute", bottom: "14%", left: "8%",
          fontSize: 54, fontWeight: 800, color: INK, letterSpacing: "-0.02em",
          textShadow: `0 2px 0 ${NEAR_WHITE}`,
        }}>{label}</div>
      ) : null}
    </AbsoluteFill>
  );
};

export interface BeforeAfterProps {
  sourceUrl: string; fps: number; durationInFrames: number;
  beforeSeconds: number;
  afterSeconds: number;
  beforeLabel?: string;
  afterLabel?: string;
  accent?: string;
}

/**
 * BEFORE / AFTER — two stills from THEIR OWN video, overlapping.
 *
 * The two frames overlap rather than sitting in tidy halves, for the §4 reason:
 * a split screen is a slide, an overlap is a composition. The second still
 * arrives late so the eye reads an order rather than a pair.
 */
export const BeforeAfter: React.FC<BeforeAfterProps> = ({
  sourceUrl, fps, durationInFrames, beforeSeconds, afterSeconds,
  beforeLabel = "BEFORE", afterLabel = "AFTER", accent = "#FF4D2E",
}) => {
  const f = useCurrentFrame();
  const { opacity } = useRise(durationInFrames);
  const second = interpolate(f, [6, 18], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const tag: React.CSSProperties = {
    position: "absolute", fontSize: 34, fontWeight: 800, letterSpacing: "0.08em",
    color: NEAR_WHITE, background: INK, padding: "6px 16px",
  };
  return (
    <AbsoluteFill style={{ background: NEAR_WHITE, opacity }}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ position: "relative", width: "86%", height: "70%" }}>
          <div style={{ position: "absolute", left: 0, top: "6%", width: "56%" }}>
            <SourceStill sourceUrl={sourceUrl} atSeconds={beforeSeconds} fps={fps}
              tiltDeg={-7} widthPct={100} label="BeforeAfter.before" />
            <div style={{ ...tag, left: 12, top: 12 }}>{beforeLabel}</div>
          </div>
          <div style={{
            position: "absolute", right: 0, bottom: "4%", width: "56%",
            opacity: second,
            transform: `translateY(${(1 - second) * 40}px)`,
          }}>
            <SourceStill sourceUrl={sourceUrl} atSeconds={afterSeconds} fps={fps}
              tiltDeg={5} widthPct={100} label="BeforeAfter.after" />
            <div style={{ ...tag, right: 12, bottom: 12, background: accent }}>
              {afterLabel}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export interface FrameCalloutProps {
  sourceUrl: string; fps: number; durationInFrames: number;
  atSeconds: number;
  /** 0..1 of the frame, the point being pointed at. */
  focusX: number;
  focusY: number;
  note?: string;
  accent?: string;
}

/**
 * FRAME CALLOUT — the frame, plus a magnified crop of the bit that matters.
 *
 * "Look at this part" is one of the most common things a creator says and the
 * screen never answers it. The crop is the SAME still scaled and re-origined,
 * so there is nothing to generate and nothing to fetch.
 */
export const FrameCallout: React.FC<FrameCalloutProps> = ({
  sourceUrl, fps, durationInFrames, atSeconds, focusX, focusY, note,
  accent = "#FF4D2E",
}) => {
  const { opacity, translateY } = useRise(durationInFrames);
  const fx = Math.min(1, Math.max(0, focusX));
  const fy = Math.min(1, Math.max(0, focusY));
  return (
    <AbsoluteFill style={{ background: NEAR_WHITE, opacity }}>
      <AbsoluteFill style={{
        alignItems: "center", justifyContent: "center",
        transform: `translateY(${translateY}px)`,
      }}>
        <div style={{ position: "relative", width: "62%" }}>
          <SourceStill sourceUrl={sourceUrl} atSeconds={atSeconds} fps={fps}
            tiltDeg={-4} widthPct={100} label="FrameCallout.still" />
          {/* the reticle, on the frame itself */}
          <div style={{
            position: "absolute", left: `${fx * 100}%`, top: `${fy * 100}%`,
            width: 118, height: 118, marginLeft: -59, marginTop: -59,
            border: `5px solid ${accent}`, borderRadius: "50%",
          }} />
          {/* the magnified crop, OVERLAPPING the frame's edge */}
          <div style={{
            position: "absolute", right: "-18%", bottom: "-12%",
            width: 300, height: 300, overflow: "hidden", borderRadius: "50%",
            border: `6px solid ${accent}`, background: INK,
            boxShadow: "0 22px 50px rgba(16,16,20,0.36)",
          }}>
            <div style={{
              position: "absolute", width: "260%", height: "260%",
              left: `${-fx * 260 + 50}%`, top: `${-fy * 260 + 50}%`,
            }}>
              <SourceStill sourceUrl={sourceUrl} atSeconds={atSeconds} fps={fps}
                widthPct={100} label="FrameCallout.crop"
                style={{ width: "100%", height: "100%", boxShadow: "none" }} />
            </div>
          </div>
        </div>
      </AbsoluteFill>
      {note ? (
        <div style={{
          position: "absolute", bottom: "12%", left: "8%", right: "34%",
          fontSize: 52, fontWeight: 800, color: INK, lineHeight: 1.04,
          letterSpacing: "-0.02em", textShadow: `0 2px 0 ${NEAR_WHITE}`,
        }}>{note}</div>
      ) : null}
    </AbsoluteFill>
  );
};

export const FRAME_COMPOSITIONS = {
  EvidenceCard, DeviceMockup, BeforeAfter, FrameCallout,
} as const;
