/**
 * THE EMITTED CAP AGAINST THE MODULE ITSELF, NUMERICALLY.
 *
 * The byte-compare proves the blobs were GENERATED. It does not prove the
 * generated JS still COMPUTES what the TypeScript computes — a stripper change,
 * or a `.replace` in the emitter that ate a line, would pass a byte-compare
 * against its own output forever. Node runs the .ts directly (type stripping),
 * so both sides are executable here and the equivalence is MEASURED.
 *
 * Exact equality, not a tolerance: this is the same arithmetic on the same
 * doubles, so any difference at all is a defect, not variance.
 */
import { emitCap, BEGIN, END } from "./emit_zoom_cap.mjs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const ts = await import(join(ROOT, "src/remotion/src/zoom/shared/velocity-cap.ts"));

// The emitted section, evaluated exactly as a component body would evaluate it.
const body = emitCap().split("\n").filter((l) => !l.startsWith(BEGIN) && l !== END
  && !/^\s{3}(source|sha256|re-emit|The 11px|punch\/glide)/.test(l)).join("\n");
const js = new Function(`${body}\nreturn { cornerPx, trapezoidEasing, peakDisplacementPx, planCappedRampIn, planCappedRelease, PEAK_DISPLACEMENT_CAP_PX, SKEW_GLIDE, SKEW_PUNCH, CAP_REFERENCE_FPS, MIN_BLEND_FRACTION };`)();

const diffs = [];
const eq = (what, a, b) => { if (!Object.is(a, b)) diffs.push(`${what}: ts=${a} js=${b}`); };

for (const k of ["PEAK_DISPLACEMENT_CAP_PX", "SKEW_GLIDE", "SKEW_PUNCH", "CAP_REFERENCE_FPS", "MIN_BLEND_FRACTION"]) {
  eq(k, ts[k], js[k]);
}
let n = 0;
for (const w of [1080, 1920, 540]) for (const h of [1920, 1080, 960]) for (const ox of [0, 0.35, 0.5, 1]) {
  eq(`cornerPx(${w},${h},${ox})`, ts.cornerPx(w, h, ox, 0.5), js.cornerPx(w, h, ox, 0.5)); n++;
}
for (const blend of [0, 0.25, 0.5, 0.7, 1]) for (const skew of [0.05, 0.25, 0.5, 0.75, 0.95]) {
  const a = ts.trapezoidEasing(blend, skew), b = js.trapezoidEasing(blend, skew);
  for (let i = 0; i <= 20; i++) { eq(`trapezoid(${blend},${skew})@${i}`, a(i / 20), b(i / 20)); n++; }
}
for (const fps of [24, 30, 59.94, 60]) for (const to of [1.05, 1.2, 1.6, 2.4]) for (const land of [5, 18, 45, 120]) {
  const args = { fromScale: 1, toScale: to, landFrame: land, earliestFrame: 0,
                 authoredFrames: Math.max(1, Math.round(land * 0.6)), fps,
                 corner: ts.cornerPx(1080, 1920, 0.5, 0.5), skew: ts.SKEW_PUNCH };
  const a = ts.planCappedRampIn(args), b = js.planCappedRampIn(args);
  for (const f of ["frames", "beta", "skew", "toScale", "peakPx", "amplitudeReduced", "startFrame"]) {
    eq(`rampIn(${fps},${to},${land}).${f}`, a[f], b[f]); n++;
  }
  for (let i = 0; i <= 10; i++) { eq(`rampIn(${fps},${to},${land}).easing@${i}`, a.easing(i / 10), b.easing(i / 10)); n++; }
  const rel = { fromScale: to, toScale: 1, startFrame: land, latestFrame: land + 90,
                authoredFrames: 12, fps, corner: ts.cornerPx(1080, 1920, 0.5, 0.5), skew: ts.SKEW_GLIDE };
  const c = ts.planCappedRelease(rel), d = js.planCappedRelease(rel);
  for (const f of ["frames", "beta", "toScale", "peakPx", "endFrame"]) {
    eq(`release(${fps},${to},${land}).${f}`, c[f], d[f]); n++;
  }
}
console.log(JSON.stringify({ comparisons: n, differences: diffs.length, first: diffs.slice(0, 5) }));
process.exit(diffs.length ? 1 : 0);
