/**
 * GATE for the script-aware text routing (the coverage law generalized).
 *
 * Runs the ACTUAL shipped module (node --experimental-strip-types imports
 * text-script.ts directly — React-free by construction).
 *
 *   node src/remotion/mg-text-font.test.mjs
 *
 * Asserts the routing table against the measured traffic samples (real
 * strings pulled from 14d of MG placements), the Cyrillic display-face
 * rule, the CJK flag semantics (preferred face kept — no CJK face by
 * ruling), and the metrics contract non-Latin autofits depend on.
 */
import assert from "node:assert";
import {
  detectScript,
  routeFaceKey,
  mgTextMetrics,
} from "./src/motion-graphics/shared/text-script.ts";

// Real traffic samples (14d census).
assert.equal(detectScript("माँ की उम्मीद"), "devanagari");
assert.equal(detectScript("दशरथ कृत शनि स्तोत्र"), "devanagari");
assert.equal(detectScript("పసుపు"), "telugu");
assert.equal(detectScript("৳"), "bengali");
assert.equal(detectScript("Привет мир"), "cyrillic");
assert.equal(detectScript("مرحبا"), "arabic");
assert.equal(detectScript("你好"), "cjk");
assert.equal(detectScript("INSTANT MATTE FINISH"), "latin");
assert.equal(detectScript("16 gifts for sweet 16th ✨"), "latin"); // emoji rides the stack tail, not the route

// Routing: non-Latin scripts land on their censused face regardless of the
// design's preferred face.
assert.equal(routeFaceKey("माँ की उम्मीद", "anton"), "notoSansDevanagari");
assert.equal(routeFaceKey("৳", "anton"), "notoSansBengali");
assert.equal(routeFaceKey("పసుపు", "inter"), "notoSansTelugu");
assert.equal(routeFaceKey("مرحبا", "playfairDisplay"), "notoSansArabic");

// Cyrillic: capable faces keep themselves; display faces route to Oswald.
assert.equal(routeFaceKey("Привет", "inter"), "inter");
assert.equal(routeFaceKey("Привет", "oswald"), "oswald");
assert.equal(routeFaceKey("Привет", "roboto"), "roboto");
assert.equal(routeFaceKey("Привет", "anton"), "oswald");
assert.equal(routeFaceKey("Привет", "caveatBrush"), "oswald");

// CJK: NO loaded face by coordinator ruling — the preferred face is kept
// (falls back at render; flagged for a separate ruling). This assertion is
// the ruling made executable: adding a CJK route without revisiting it
// breaks the gate.
assert.equal(routeFaceKey("你好", "anton"), "anton");
assert.equal(routeFaceKey("你好", "inter"), "inter");

// Latin: preferred face passes through untouched.
assert.equal(routeFaceKey("BREAKTHROUGH", "anton"), "anton");

// Metrics contract for autofits: non-Latin gets matra headroom, no
// uppercase, and the conservative advance; Latin keeps the measured 0.62.
const deva = mgTextMetrics("दशरथ");
assert.equal(deva.lineHeight, 1.3);
assert.equal(deva.uppercaseSafe, false);
assert.equal(deva.advanceEm, 0.42);
const lat = mgTextMetrics("SPRINT");
assert.equal(lat.lineHeight, 1.0);
assert.equal(lat.uppercaseSafe, true);
assert.equal(lat.advanceEm, 0.62);

console.log("mg-text-font gate: PASS (traffic samples routed, Cyrillic rule, CJK ruling executable, metrics contract)");
