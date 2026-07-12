import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { CleanCut } from "./captions/CleanCut";
import { Cove } from "./captions/Cove";
import { Gadzhi } from "./captions/Gadzhi";
import { Lumen } from "./captions/Lumen";
import { Prime } from "./captions/Prime";
import { Pulse } from "./captions/Pulse";
import { Quintessence } from "./captions/Quintessence";
import { TwoTone } from "./captions/TwoTone";
import { TypewriterReveal } from "./captions/TypewriterReveal";
import type { TikTokPage } from "./captions/shared/types";

// ---------------------------------------------------------------------------
// CaptionFadeProbe — STANDALONE WS2 fade-bound sample (not used in production).
// Renders one caption style on a FAST-SPEECH word track (words ~170ms apart —
// the regime where a fixed fade overruns the word) over a dark plate, with a
// BEAT PULSE bar that flashes white for one frame exactly at each word onset.
// The pulse is the metronome: the eye reads whether the caption SNAPS with the
// pulse (landed on the beat) or is still fading up after it (lag). Driven by
// caption-fade-battery.mjs; render before/after the fade-bound to compare.
// ---------------------------------------------------------------------------

const FADE_CAPTION_MAP: Record<string, React.FC<Record<string, unknown>>> = {
  CleanCut: CleanCut as React.FC<Record<string, unknown>>,
  Prime: Prime as React.FC<Record<string, unknown>>,
  Pulse: Pulse as React.FC<Record<string, unknown>>,
  Quintessence: Quintessence as React.FC<Record<string, unknown>>,
  TypewriterReveal: TypewriterReveal as React.FC<Record<string, unknown>>,
  Gadzhi: Gadzhi as React.FC<Record<string, unknown>>,
  Cove: Cove as React.FC<Record<string, unknown>>,
  Lumen: Lumen as React.FC<Record<string, unknown>>,
  TwoTone: TwoTone as React.FC<Record<string, unknown>>,
};

export interface CaptionFadeProbeProps {
  style: string;
  words: string[];
  keywords?: string[];
  wordMs?: number; // per-word onset spacing; default 170ms (fast speech)
  label?: string; // corner tag, e.g. "before" / "after"
}

function buildFastPage(words: string[], wordMs: number): TikTokPage {
  const tokens = words.map((text, i) => ({
    text,
    fromMs: i * wordMs,
    toMs: i * wordMs + wordMs,
  }));
  return {
    text: words.join(" "),
    startMs: 0,
    durationMs: words.length * wordMs + 700, // small tail hold
    tokens,
  };
}

const BeatPulse: React.FC<{ onsetsMs: number[] }> = ({ onsetsMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = (frame / fps) * 1000;
  // lit for the ~one frame at each onset (a hard metronome tick)
  const frameMs = 1000 / fps;
  const lit = onsetsMs.some((o) => nowMs >= o && nowMs < o + frameMs);
  return (
    <div
      style={{
        position: "absolute",
        top: 90,
        left: 0,
        right: 0,
        height: 10,
        background: lit ? "#00FF88" : "rgba(255,255,255,0.06)",
      }}
    />
  );
};

export const CaptionFadeProbe: React.FC<CaptionFadeProbeProps> = ({
  style,
  words,
  keywords = [],
  wordMs = 170,
  label,
}) => {
  const page = buildFastPage(words, wordMs);
  const Comp = FADE_CAPTION_MAP[style];
  if (!Comp) throw new Error(`CaptionFadeProbe: unknown style "${style}"`);
  const onsets = page.tokens.map((t) => t.fromMs);

  return (
    <AbsoluteFill style={{ backgroundColor: "#141414" }}>
      <BeatPulse onsetsMs={onsets} />
      <Comp
        pages={[page]}
        position="bottom"
        keywords={keywords}
        specialWords={keywords}
        boxedWords={keywords}
        shineWords={keywords}
      />
      {label ? (
        <div
          style={{
            position: "absolute",
            top: 120,
            left: 40,
            fontFamily: "monospace",
            fontSize: 34,
            color: "#00FF88",
            letterSpacing: 2,
          }}
        >
          {label}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
