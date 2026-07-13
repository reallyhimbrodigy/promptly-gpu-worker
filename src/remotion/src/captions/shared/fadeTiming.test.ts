// ITEM 3 — WS2 caption fade-bound (Zac 2026-07-12). A caption's fade must never
// consume more than FADE_WINDOW_FRACTION of the window it is shown for; on fast
// speech a longer fade is still resolving when the word is already spoken, so it
// reads as lag instead of landing on the beat. Pure, unit-agnostic (caller keeps
// base + window in the same unit — frames or ms). Run: `node fadeTiming.test.ts`.
import { boundedFade, FADE_WINDOW_FRACTION, MAX_ENTRANCE_MS } from "./fadeTiming.ts";

let pass = 0;
const fails: string[] = [];
function check(name: string, cond: boolean, detail = "") {
  if (cond) pass++;
  else fails.push(name + (detail ? ` :: ${detail}` : ""));
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${name}`);
}

// the fraction is the WS2 contract: a quarter of the display window, no more.
check("FADE_WINDOW_FRACTION is 0.25", FADE_WINDOW_FRACTION === 0.25, String(FADE_WINDOW_FRACTION));

// long window (slow speech): the base fade fits comfortably under 25% → unchanged.
// e.g. 50ms base on a 1000ms word: 25% = 250ms, base is far under → keep 50.
check("base under the bound is returned unchanged (slow speech)",
  boundedFade(50, 1000) === 50, String(boundedFade(50, 1000)));

// short window (fast speech): base exceeds 25% → clamp to window*0.25.
// e.g. 80ms base on a 200ms word: 25% = 50ms → clamp to 50 (word crisp ≥75%).
check("base over the bound is clamped to 25% of the window (fast speech)",
  boundedFade(80, 200) === 50, String(boundedFade(80, 200)));

// exact boundary: base == 25% of window → unchanged (no spurious clamp).
check("base exactly at the bound is unchanged",
  boundedFade(50, 200) === 50, String(boundedFade(50, 200)));

// frames unit works identically (caller keeps units consistent):
// 5-frame base on a 12-frame page: 25% = 3 → clamp to 3.
check("frames unit: 5f base on a 12f window clamps to 3f",
  boundedFade(5, 12) === 3, String(boundedFade(5, 12)));

// zero / negative window guard: never divide the fade into nothing → 0, not NaN.
check("zero window returns 0 (guard, not NaN)", boundedFade(80, 0) === 0, String(boundedFade(80, 0)));
check("negative window returns 0 (guard)", boundedFade(80, -5) === 0, String(boundedFade(80, -5)));

// never returns more than the base even on a huge window (bound is a ceiling only).
check("bound never inflates the fade above base", boundedFade(10, 100000) === 10, String(boundedFade(10, 100000)));

// UNIVERSAL ABSOLUTE CAP (Zac 2026-07-12): no entrance exceeds MAX_ENTRANCE_MS,
// even on a long window where the 25% bound wouldn't bite — the slow-base bug.
check("MAX_ENTRANCE_MS is 80", MAX_ENTRANCE_MS === 80, String(MAX_ENTRANCE_MS));
check("Prime base 160 on a 1000ms window caps to 80 (was 160)", boundedFade(160, 1000) === 80, String(boundedFade(160, 1000)));
check("Typewriter base 90 on a 2000ms page caps to 80 (was 90)", boundedFade(90, 2000) === 80, String(boundedFade(90, 2000)));
check("fast-speech still wins when tighter than the cap", boundedFade(160, 200) === 50, String(boundedFade(160, 200)));

console.log(`\n=== RESULT: ${pass} passed, ${fails.length} failed ===`);
if (fails.length) { console.log("FAILURES:", fails); process.exit(1); }
console.log("ALL FADE-BOUND CASES PASS");
