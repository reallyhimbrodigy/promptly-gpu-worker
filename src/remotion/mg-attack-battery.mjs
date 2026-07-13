// WS1 MG entrance-arrival battery — bundle ONCE, renderMedia each MG type's
// entrance to a small clip on a flat plate. measure_mg_attack.py then reads the
// presence curve per clip and reports the visual-arrival (attack) ms per type.
// Usage: node mg-attack-battery.mjs <outDir>
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(__dirname, "mg-attack-out");
fs.mkdirSync(outDir, { recursive: true });

// Best-effort sample props per type (content is irrelevant to the ENTRANCE
// timing; a component that renders blank on a missing prop shows a flat
// presence curve and is flagged). anchor centers each for a clean measure.
const A = { anchor: "center" };
const TYPES = {
  StatCard: { value: 100000, label: "SUBSCRIBERS", ...A },
  AnnotationArrow: { start: { x: 0.3, y: 0.35 }, end: { x: 0.7, y: 0.6 }, ...A },
  Notification: { notifications: [{ app: "venmo", appName: "Venmo", title: "Sarah paid you", body: "$200.00" }], ...A },
  ProgressBar: { percentage: 73, label: "PROGRESS", ...A },
  ChatThread: { messages: [{ sender: "them", text: "you up?" }, { sender: "me", text: "always" }], ...A },
  StickyNotes: { notes: [{ text: "big idea", color: "#FFD54A", rotation: -4 }] },
  RecordingFrame: { ...A },
  TweetBubble: { name: "Jane Doe", handle: "jane", text: "this changed everything", verified: true, stats: { replies: 12, reposts: 40, likes: 1200, views: 50000 }, ...A },
  InstagramComment: { username: "jane", comment: "obsessed with this", likes: 1200, ...A },
  IMessageBubble: { text: "Delivered", messageType: "incoming", ...A },
  TikTokComment: { username: "jane", comment: "no way this is real", likes: 1200, ...A },
  Timeline: { items: [{ label: "Start" }, { label: "Mid" }, { label: "End" }], ...A },
  Reticle: { ...A },
  RankedList: { items: [{ label: "Focus" }, { label: "Discipline" }, { label: "Consistency" }], ...A },
  PullQuote: { text: "most people quit right before the breakthrough", keywords: ["quit"], ...A },
  PillCluster: { pills: ["mindset", "focus", "discipline"], ...A },
  Stamp: { text: "SOLD OUT", ...A },
  BarRace: { bars: [{ label: "A", value: 80 }, { label: "B", value: 55 }, { label: "C", value: 30 }], ...A },
  SectionDivider: { title: "CHAPTER ONE", ...A },
  EditorialQuote: { text: "the quiet part out loud", author: "Someone", ...A },
  StepDivider: { title: "First step", step: 1, ...A },
  DropBanner: { text: "NEW DROP", ...A },
  DropCard: { title: "Limited", subtitle: "Drop 01", ...A },
  PillMarquee: { pills: ["mindset", "focus", "discipline", "habits", "growth", "grit"], ...A },
  TimelineRoadmap: { items: [{ label: "Phase 1" }, { label: "Phase 2" }, { label: "Phase 3" }], ...A },
  MouseDrag: { ...A },
};

const bundled = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts"), onProgress: () => {} });

let ok = 0, fail = 0;
for (const [type, props] of Object.entries(TYPES)) {
  const out = path.join(outDir, `${type}.mp4`);
  try {
    const composition = await selectComposition({ serveUrl: bundled, id: "MGAttackProbe", inputProps: { type, props } });
    await renderMedia({
      composition, serveUrl: bundled, outputLocation: out, codec: "h264",
      inputProps: { type, props },
      scale: 0.3,                 // timing is resolution-independent — render small + fast
      logLevel: "error",
      overwrite: true,
    });
    ok++;
    console.log(`MG_OK ${type}`);
  } catch (err) {
    fail++;
    console.log(`MG_FAIL ${type} :: ${String(err).slice(0, 200)}`);
  }
}
console.log(`MG_BATTERY_DONE ok=${ok} fail=${fail} out=${outDir}`);
process.exit(0);
