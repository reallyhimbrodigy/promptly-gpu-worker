// MG catalogue render-proof. Bundles once, renderStill across a component's
// entrance/settle window via the existing MGAttackProbe (flat plate, startMs=0).
// No source video — the catalogue components are pure type. Usage:
//   node render-mg-proof.mjs <Type> <before|after>
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "mg-proof-out");
fs.mkdirSync(outDir, { recursive: true });

const TYPE = process.argv[2] || "StatCard";
const TAG = process.argv[3] || "before";
const BG = process.argv[4]; // optional footage filename in public/ (contrast-floor check)

// Palette like the job's deterministic extractor. Over FOOTAGE the overlay ink is
// LIGHT (the palette's video-overlay colour) so it reads on any luminance; on the
// flat gray PLATE (before/after comparison) dark ink shows the composition best.
const PAL = BG
  ? { number: "#FEFCFD", label: "#FEFCFD", accent: "#F4903E" }
  : { number: "#14141A", label: "#14141A", accent: "#8B350D" };
const PROPS = {
  StatCard: { value: 100000, label: "SUBSCRIBERS", numberColor: PAL.number, labelColor: PAL.label, accentColor: PAL.accent, anchor: "center" },
  Stamp: { text: "SOLD OUT", color: PAL.accent, anchor: "center" },
  PillCluster: { tags: ["mindset", "focus", "discipline", "grit", "habits", "growth"], accentColor: PAL.accent, textColor: PAL.number, anchor: "center" },
  // Production-faithful spec (pulled from a real 14d recipe; palette re-inked
  // for the plate). EmojiCard is spec-driven (FrameCompSpec), not MG-props.
  EmojiCard: { spec: { kind: "EmojiCard", bg: "#C7AB92", fg: "#121218", accent: "#8B350D",
    cap_px: 163, emoji_px: 521, tilt_deg: -7, entrance: "scale", at_seconds: 0, duration_s: 1.5,
    legibility: { shadow_offset_px: 3, shadow_blur_px: 7, shadow_opacity: 0.35 },
    emoji: "🏎️", words: ["RACE", "CAR"] } },
  Reticle: { label: "THE SPOT", accentColor: PAL.accent, anchor: "center" },
  NamePlate: { name: "Siddharth Ramakrishnan", role: "Founder & CEO", accentColor: PAL.accent, nameColor: PAL.number, startMs: 0, durationMs: 4000 },
  EditorialQuote: { text: "most people quit right before it works", author: "JANE DOE", role: "Founder",
    accentColor: PAL.accent, textColor: PAL.number, anchor: "center" },
  PullQuote: { text: "most people quit right before the breakthrough", keywords: ["quit", "breakthrough"],
    accentColor: PAL.accent, textColor: PAL.number, highlightStyle: "bar", anchor: "center" },
  RankedList: { items: [
    { label: "Consistency", value: "daily" },
    { label: "Focus", value: "deep" },
    { label: "Discipline", value: "hard" },
  ], accentColor: PAL.accent, labelColor: PAL.number, anchor: "center" },
}[TYPE] || {};
const FRAMES = { StatCard: [4, 14, 28, 46], Stamp: [3, 8, 16, 46], PillCluster: [3, 12, 24, 46], EmojiCard: [3, 8, 16, 40], RankedList: [8, 20, 34, 50], EditorialQuote: [6, 18, 36, 56], PullQuote: [6, 16, 30, 50], Reticle: [8, 18, 30, 50], NamePlate: [4, 10, 30, 50] }[TYPE] || [4, 14, 28, 46];

console.log(`[mg-proof] ${TYPE} (${TAG}) — bundling…`);
const serveUrl = await bundle({ entryPoint: path.resolve(__dirname, "src/index.ts") });
const inputProps = { type: TYPE, props: PROPS, motionBlur: true, ...(BG ? { bgVideo: BG } : {}) };
const composition = await selectComposition({ serveUrl, id: "MGCraftProbe", inputProps });
for (const frame of FRAMES) {
  const output = path.join(outDir, `${TYPE}_${TAG}_f${String(frame).padStart(2, "0")}.png`);
  await renderStill({ composition, serveUrl, output, frame, inputProps, chromiumOptions: { gl: "angle" } });
  console.log("[mg-proof] wrote", path.basename(output));
}
console.log("[mg-proof] DONE →", outDir);
