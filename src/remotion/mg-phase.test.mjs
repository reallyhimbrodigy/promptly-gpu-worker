/**
 * GATE for the useMGPhase enter-window clamp (2026-08-26).
 *
 * Runs the ACTUAL shipped module (node --experimental-strip-types imports the
 * .ts directly) — never a mirror. The clamp: the effective enter window ends
 * at least 1 frame before exit onset, so the entrance always COMPLETES and
 * 'holding' is always reachable whenever the window allows any hold.
 *
 *   node src/remotion/mg-phase.test.mjs
 *
 * Both directions, which is the whole point:
 *   • BROKEN-WITHOUT-CLAMP cases (the live SectionDivider numbers): the
 *     unclamped truth table — computed inline here exactly as the pre-fix
 *     hook did — shows "entering" during exit and no holding frame; the
 *     shipped function must show neither.
 *   • IDENTITY cases: for every healthy window (enter <= exitStart − 1) the
 *     shipped function must match the unclamped truth table on EVERY frame —
 *     the clamp may not touch working components.
 */
import assert from "node:assert";
import { resolveMGPhaseFrames } from "./src/motion-graphics/shared/mg-phase-frames.ts";

// The pre-fix phase computation, verbatim semantics (the truth table the
// identity direction is judged against, and the broken direction proven from).
const unclamped = ({ localFrame, durationFrames, enterFrames, exitFrames }) => {
  const exitStartFrame = durationFrames - exitFrames;
  let phase;
  if (localFrame < 0) phase = "before";
  else if (localFrame < enterFrames) phase = "entering";
  else if (localFrame < exitStartFrame) phase = "holding";
  else if (localFrame < durationFrames) phase = "exiting";
  else phase = "after";
  return { phase, exitStartFrame };
};

// ── Direction 1: the broken class, on the exact live numbers ────────────────
// SectionDivider live 1.52s @30fps: durationFrames 46, smooth enter 50, exit 24.
{
  const base = { durationFrames: 46, enterFrames: 50, exitFrames: 24 };

  // Pre-fix truth: phase reads "entering" AFTER exit onset (f30 > 22)…
  assert.equal(unclamped({ ...base, localFrame: 30 }).phase, "entering");
  // …and no frame of the whole life is "holding".
  const preHold = [];
  for (let f = 0; f < 46; f++) preHold.push(unclamped({ ...base, localFrame: f }).phase);
  assert.ok(!preHold.includes("holding"), "pre-fix truth table must lack holding for this case");

  // Shipped: entrance completes before exit onset, holding reachable, and
  // "entering" never overlaps the exit window.
  const r30 = resolveMGPhaseFrames({ ...base, localFrame: 30 });
  assert.equal(r30.phase, "exiting");
  assert.equal(r30.exitStartFrame, 22);
  assert.equal(r30.effectiveEnterFrames, 21);
  const phases = [];
  for (let f = 0; f < 46; f++) phases.push(resolveMGPhaseFrames({ ...base, localFrame: f }).phase);
  assert.ok(phases.includes("holding"), "clamp must make holding reachable");
  for (let f = 22; f < 46; f++) {
    assert.notEqual(
      resolveMGPhaseFrames({ ...base, localFrame: f }).phase,
      "entering",
      `phase may never read "entering" during the exit window (f=${f})`,
    );
  }
}

// ── Direction 2: identity on every healthy window ───────────────────────────
// Grid sweep: wherever enter <= exitStart − 1, the shipped function must match
// the unclamped truth table frame-for-frame.
{
  let identityCases = 0;
  for (let durationFrames = 10; durationFrames <= 300; durationFrames += 7) {
    for (let enterFrames = 4; enterFrames <= 100; enterFrames += 9) {
      for (let exitFrames = 4; exitFrames <= 50; exitFrames += 7) {
        const exitStartFrame = durationFrames - exitFrames;
        const healthy = enterFrames <= exitStartFrame - 1;
        for (let f = -3; f <= durationFrames + 3; f++) {
          const inputs = { localFrame: f, durationFrames, enterFrames, exitFrames };
          const shipped = resolveMGPhaseFrames(inputs);
          if (healthy) {
            const truth = unclamped(inputs);
            assert.equal(
              shipped.phase,
              truth.phase,
              `identity violated at d=${durationFrames} e=${enterFrames} x=${exitFrames} f=${f}`,
            );
            assert.equal(shipped.effectiveEnterFrames, enterFrames);
          } else if (exitStartFrame >= 3) {
            // Unhealthy but holdable window: the invariants, everywhere.
            assert.ok(
              shipped.effectiveEnterFrames <= exitStartFrame - 1,
              "entrance must complete before exit onset",
            );
            if (f >= exitStartFrame && f < durationFrames) {
              assert.notEqual(shipped.phase, "entering");
            }
          }
          assert.ok(shipped.effectiveEnterFrames >= 1, "interpolate range must stay valid");
        }
        if (healthy) identityCases++;
      }
    }
  }
  assert.ok(identityCases > 200, `grid must actually exercise identity (${identityCases})`);
}

console.log("mg-phase gate: PASS (broken-case corrected + identity preserved)");
