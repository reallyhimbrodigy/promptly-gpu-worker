/**
 * RULE 1 GATE for the zoom velocity cap.
 *
 * Runs the ACTUAL shipped module (node --experimental-strip-types imports the
 * .ts directly) — never a Python/JS mirror, because mirrors drift and this repo
 * has already been burned by stale hardcoded copies of derived tables.
 *
 *   node src/remotion/velocity-cap.test.mjs
 *
 * The gate asserts BOTH directions, which is the whole point:
 *   • every production zoom, capped, stays at or under PEAK_DISPLACEMENT_CAP_PX
 *   • every production zoom, on the LEGACY cubic curve, BREACHES it
 * A check that cannot fail on the pre-fix code proves nothing.
 */
import assert from "node:assert";
import {
  PEAK_DISPLACEMENT_CAP_PX,
  MIN_BLEND_FRACTION,
  cornerPx,
  trapezoidEasing,
  peakDisplacementPx,
  planCappedRampIn,
  planCappedRelease,
} from "./src/zoom/shared/velocity-cap.ts";

const CAP = PEAK_DISPLACEMENT_CAP_PX;
const W = 1080, H = 1920;
const CORNER = cornerPx(W, H, 0.5, 0.5);

let passed = 0;
const check = (name, fn) => {
  try {
    fn();
    passed++;
    console.log(`  ok   ${name}`);
  } catch (e) {
    console.error(`  FAIL ${name}\n       ${e.message}`);
    process.exitCode = 1;
  }
};

const sample = (n, from, to, easing) =>
  Array.from({ length: n + 1 }, (_, f) => from + (to - from) * easing(f / n));

// Remotion's Easing.out(Easing.cubic) — the legacy ramp curve.
const cubicOut = (t) => 1 - (1 - t) ** 3;
// Remotion's Easing.inOut(Easing.cubic) — the curve that LOOKS like the fix.
const cubicInOut = (t) => (t < 0.5 ? ((2 * t) ** 3) / 2 : 1 - ((2 * (1 - t)) ** 3) / 2);

// Production defaults: handler.py ZOOM_NATURAL_DURATION_FRAMES / ZOOM_NATURAL_SCALE.
// ramp-in is 35% of the event for every ramp zoom (see each .tsx).
const ZOOMS = [
  { name: "SmoothPush", scale: 1.22, eventMs: 1200 },
  { name: "LetterboxPush", scale: 1.25, eventMs: 1400 },
  { name: "DepthPull", scale: 1.25, eventMs: 2200 },
];
const FPS = [30, 60];

console.log("\nzoom velocity cap — Rule 1 gate\n");

check("trapezoid easing hits both endpoints exactly", () => {
  for (const beta of [0, 0.25, 1 / 3, 0.5]) {
    const e = trapezoidEasing(beta);
    assert.ok(Math.abs(e(0) - 0) < 1e-12, `beta=${beta} e(0)=${e(0)}`);
    assert.ok(Math.abs(e(1) - 1) < 1e-12, `beta=${beta} e(1)=${e(1)}`);
  }
});

check("trapezoid easing is monotonically non-decreasing", () => {
  for (const beta of [0, 0.25, 1 / 3, 0.5]) {
    const e = trapezoidEasing(beta);
    let prev = -Infinity;
    for (let i = 0; i <= 2000; i++) {
      const v = e(i / 2000);
      assert.ok(v >= prev - 1e-12, `beta=${beta} non-monotone at t=${i / 2000}`);
      prev = v;
    }
  }
});

check("trapezoid peak velocity is 1/(1-beta) x linear, as designed", () => {
  for (const beta of [0.25, 1 / 3, 0.4, 0.5]) {
    const e = trapezoidEasing(beta);
    const N = 20000;
    let peak = 0;
    for (let i = 0; i < N; i++) peak = Math.max(peak, (e((i + 1) / N) - e(i / N)) * N);
    const expect = 1 / (1 - beta);
    assert.ok(Math.abs(peak - expect) < 0.01,
      `beta=${beta}: peak ${peak.toFixed(4)} != ${expect.toFixed(4)}`);
  }
});

check("cubic-inOut does NOT reduce peak velocity (it only relocates it)", () => {
  const N = 20000;
  const peakOf = (e) => {
    let p = 0;
    for (let i = 0; i < N; i++) p = Math.max(p, (e((i + 1) / N) - e(i / N)) * N);
    return p;
  };
  // Both cubic forms peak at 3x linear. This is why swapping ease-out for
  // ease-in-out was never going to fix the step — it is documented here so the
  // conclusion is not re-litigated.
  assert.ok(Math.abs(peakOf(cubicOut) - 3) < 0.01, `cubicOut ${peakOf(cubicOut)}`);
  assert.ok(Math.abs(peakOf(cubicInOut) - 3) < 0.01, `cubicInOut ${peakOf(cubicInOut)}`);
});

check("LEGACY cubic ramps BREACH the cap — the gate can fail on pre-fix code", () => {
  for (const fps of FPS) {
    for (const z of ZOOMS) {
      const evDur = Math.round((z.eventMs / 1000) * fps);
      const rampFrames = Math.max(1, Math.round(evDur * 0.35));
      const peak = peakDisplacementPx(sample(rampFrames, 1, z.scale, cubicOut), CORNER);
      assert.ok(peak > CAP,
        `${z.name}@${fps}fps legacy peak ${peak.toFixed(1)} should breach ${CAP}`);
    }
  }
});

check(`capped ramp-in <= ${CAP} px/frame, every zoom, 30 and 60 fps`, () => {
  for (const fps of FPS) {
    for (const z of ZOOMS) {
      const evDur = Math.round((z.eventMs / 1000) * fps);
      const authored = Math.max(1, Math.round(evDur * 0.35));
      // realistic placement: the event sits 2s into the clip, so the ramp has
      // room to grow backwards.
      const landFrame = 2 * fps + authored;
      const r = planCappedRampIn({
        fromScale: 1, toScale: z.scale, landFrame, earliestFrame: 0,
        authoredFrames: authored, fps, corner: CORNER,
      });
      const peak = peakDisplacementPx(sample(r.frames, 1, r.toScale, r.easing), CORNER);
      assert.ok(peak <= CAP + 1e-6,
        `${z.name}@${fps}fps capped peak ${peak.toFixed(2)} > ${CAP}`);
      assert.ok(!r.amplitudeReduced,
        `${z.name}@${fps}fps surrendered amplitude despite 2s of headroom`);
      assert.ok(r.frames >= authored, `${z.name}: ramp was SHORTENED`);
      assert.ok(r.beta >= MIN_BLEND_FRACTION, `${z.name}: beta below C1 floor`);
    }
  }
});

check(`capped release <= ${CAP} px/frame, every zoom`, () => {
  for (const fps of FPS) {
    for (const z of ZOOMS) {
      const evDur = Math.round((z.eventMs / 1000) * fps);
      const authored = Math.max(1, evDur - Math.round(evDur * 0.6));
      const r = planCappedRelease({
        fromScale: z.scale, toScale: 1, startFrame: 2 * fps,
        latestFrame: 2 * fps + 10 * fps, authoredFrames: authored, fps, corner: CORNER,
      });
      const peak = peakDisplacementPx(sample(r.frames, z.scale, 1, r.easing), CORNER);
      assert.ok(peak <= CAP + 1e-6,
        `${z.name}@${fps}fps release peak ${peak.toFixed(2)} > ${CAP}`);
    }
  }
});

check("no headroom -> amplitude is surrendered, never the cap", () => {
  // A zoom pinned against the clip head: nowhere to grow, so lever 3 must fire
  // AND the cap must still hold.
  const authored = 13;
  const r = planCappedRampIn({
    fromScale: 1, toScale: 1.22, landFrame: authored, earliestFrame: 0,
    authoredFrames: authored, fps: 30, corner: CORNER,
  });
  assert.ok(r.amplitudeReduced, "expected amplitude surrender with zero headroom");
  assert.ok(r.toScale < 1.22 && r.toScale > 1.0, `implausible scale ${r.toScale}`);
  const peak = peakDisplacementPx(sample(r.frames, 1, r.toScale, r.easing), CORNER);
  assert.ok(peak <= CAP + 1e-6, `capped-out peak ${peak.toFixed(2)} > ${CAP}`);
});

check("off-centre origin costs more lead-in than centred (face-locked zooms)", () => {
  const centred = cornerPx(W, H, 0.5, 0.5);
  const corner = cornerPx(W, H, 0.15, 0.2);
  assert.ok(corner > centred, "off-centre origin must have a larger corner radius");
  const mk = (c) => planCappedRampIn({
    fromScale: 1, toScale: 1.22, landFrame: 200, earliestFrame: 0,
    authoredFrames: 13, fps: 30, corner: c,
  });
  assert.ok(mk(corner).frames > mk(centred).frames,
    "off-centre zoom must be given a longer ramp");
});

check("the move has the SAME DURATION at 30 and 60 fps (CAP_REFERENCE_FPS)", () => {
  const mk = (fps) => planCappedRampIn({
    fromScale: 1, toScale: 1.22, landFrame: 5 * fps, earliestFrame: 0,
    authoredFrames: Math.round(0.42 * fps), fps, corner: CORNER,
  });
  const t30 = mk(30).frames / 30;
  const t60 = mk(60).frames / 60;
  assert.ok(Math.abs(t30 - t60) < 0.05,
    `ramp DURATION should match across fps: ${t30.toFixed(3)}s vs ${t60.toFixed(3)}s`);
});

console.log(`\n${passed} checks passed${process.exitCode ? " (with failures)" : ""}\n`);
