// Frame-comp entrance/depth PROOF. Bundles once, then renderStill across the
// entrance window for each generation-free frame comp, plus a caption frame-0-
// vs-frame-6 pair to prove the caption layer is unaffected (frame-1-is-final →
// the two frames must be pixel-identical). Usage: node render-frame-comp-proof.mjs
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "frame-comp-proof-out");
const publicDir = path.join(__dirname, "public");
fs.mkdirSync(outDir, { recursive: true });

// A design system like the deterministic extractor hands frame_compositions.py:
// near-white §4 background, dark type, a per-job accent (never a brand value).
const leg = { shadow_offset_px: 2, shadow_blur_px: 4, shadow_opacity: 0.35 };
const base = (kind, tilt, entrance) => ({
  kind, bg: "#FEFCFD", fg: "#14141A", accent: "#8B350D",
  cap_px: 96, tilt_deg: tilt, legibility: leg,
  at_seconds: 1.2, duration_s: 2, entrance,
});
const SPECS = {
  EvidenceCard: { ...base("EvidenceCard", -6, "rise"), claim: "0 CODING EXPERIENCE", caption: "0 coding experience", still_width_pct: 58 },
  DeviceMockup: { ...base("DeviceMockup", 5, "rise"), label: "THE APP", shell_radius_px: 46, still_width_px: 430 },
  EmojiCard: { ...base("EmojiCard", -7, "scale"), emoji: "\u{1F92B}", words: ["top", "secret"], emoji_px: 307 },
};
const SOURCE = "test_talking_head.mp4"; // in public/
const FRAMES = [0, 3, 6, 24]; // @30fps: arrival start / mid / near-settled / held (entrance floor ~8f)

console.log("[proof] bundling…");
const serveUrl = await bundle({ entryPoint: path.resolve(__dirname, "src/index.ts"), publicDir });

for (const [kind, spec] of Object.entries(SPECS)) {
  const inputProps = { kind, spec, sourceUrl: kind === "EmojiCard" ? "" : SOURCE, motionBlur: true };
  const composition = await selectComposition({ serveUrl, id: "FrameCompProbe", inputProps, publicDir });
  for (const frame of FRAMES) {
    const output = path.join(outDir, `${kind}_f${String(frame).padStart(2, "0")}.png`);
    await renderStill({ composition, serveUrl, output, frame, inputProps, publicDir, chromiumOptions: { gl: "angle" } });
    console.log("[proof] wrote", path.basename(output));
  }
}

// Caption UNAFFECTED: FitSpecimen (a caption style) at frame 0 and frame 6. With
// frame-1-is-final the caption has no entrance channel, so the two must match.
const capComp = await selectComposition({ serveUrl, id: "FitSpecimen", publicDir });
for (const frame of [0, 6]) {
  await renderStill({ composition: capComp, serveUrl, output: path.join(outDir, `caption_f${String(frame).padStart(2, "0")}.png`), frame, publicDir, chromiumOptions: { gl: "angle" } });
  console.log("[proof] wrote", `caption_f${String(frame).padStart(2, "0")}.png`);
}
console.log("[proof] DONE →", outDir);
