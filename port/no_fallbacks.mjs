/**
 * NO HARDCODED FALLBACKS IN A PORTED COMPONENT'S SOURCE (Zac, 2026-09-20).
 *
 * Defaults live in the property table and NOWHERE ELSE.
 *
 * WHY IT IS A RULE AND NOT A PREFERENCE. ChatCut REWRITES the code at
 * registration — every ported component comes back with "Auto-fixed: Stripped
 * hardcoded fallbacks from props (property system provides defaults)". So the
 * blob on disk is not the blob that runs, and every guarantee the one-source
 * gate gives stops at the wire. There is no unset in ChatCut's property system:
 * the registered default IS the value the component sees, so a fallback in
 * source is DEAD CODE THAT LOOKS LIVE. When the fallback and the registered
 * default disagree, the component silently runs the default while the source
 * still reads as though the fallback applies — and nothing anywhere says so.
 *
 * With no fallbacks there is nothing to strip, so the registered code must come
 * back BYTE-IDENTICAL and port/registered_diff.mjs can assert exact equality.
 * This gate is what makes that assertion meaningful.
 *
 * ONE IMPLEMENTATION: the fallback test is imported from registered_diff.mjs,
 * not restated here. Two copies of one rule is the thing the cap's build step
 * exists to prevent, and it applies to checks as much as to components.
 *
 * Usage: node port/no_fallbacks.mjs
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readsPropWithFallback } from "./registered_diff.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const BODIES = join(HERE, "bodies");

/**
 * QUARANTINED, WITH AN OWNER AND A DATE — not exempt.
 *
 * All 13 bodies violated this rule the day it was written (89 sites). Landing
 * it unscoped would have turned nine of Builder-1's components red at once,
 * and "nine red proofs broke when the gate landed" reads as the gate being
 * wrong — a correct rule discarded on its first day for being right about
 * nothing. So it lands with the scoping already in.
 *
 * These nine are Builder-1's and are theirs to clear; the lane boundary says I
 * do not edit a body I did not author. The list SHRINKS and never grows: a
 * pinned body that has become clean FAILS this gate, so a stale pin cannot sit
 * here being read as a fact.
 */
const QUARANTINE = {
  CaptionMatch:  { owner: "Builder 1", since: "2026-09-20" },
  LowerThird:    { owner: "Builder 1", since: "2026-09-20" },
  PlainText:     { owner: "Builder 1", since: "2026-09-20" },
  QuoteCard:     { owner: "Builder 1", since: "2026-09-20" },
  SmoothPush:    { owner: "Builder 1", since: "2026-09-20" },
  StagedPush:    { owner: "Builder 1", since: "2026-09-20" },
  StepZoom:      { owner: "Builder 1", since: "2026-09-20" },
  StickyNotes:   { owner: "Builder 1", since: "2026-09-20" },
  TornPaper:     { owner: "Builder 1", since: "2026-09-20" },
};

/** Comments are not code — the rule is about what the component DOES. */
export function codeLines(src) {
  const noBlock = src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  return noBlock.split("\n").map((l) => l.replace(/\/\/.*$/, ""));
}

export function scan(src) {
  const hits = [];
  codeLines(src).forEach((line, i) => {
    if (readsPropWithFallback(line)) hits.push({ line: i + 1, text: line.trim().slice(0, 90) });
  });
  return hits;
}

export function run(dir = BODIES) {
  const names = readdirSync(dir).filter((f) => f.endsWith(".jsx")).map((f) => f.slice(0, -4)).sort();
  const rows = [];
  for (const n of names) {
    const hits = scan(readFileSync(join(dir, n + ".jsx"), "utf8"));
    const pin = QUARANTINE[n];
    let state;
    if (hits.length === 0 && !pin) state = "CLEAN";
    else if (hits.length === 0 && pin) state = "PIN IS STALE";
    else if (pin) state = "QUARANTINED";
    else state = "FAIL";
    rows.push({ name: n, hits, state, pin });
  }
  return rows;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // A DIRECTORY ARGUMENT SO THE RED PROOF NEVER MUTATES THE REAL TREE. A
  // mutating harness and the thing it verifies cannot share a worktree; a kill
  // between mutate and restore leaves exactly the residue the check exists to
  // detect, under the name of the check for it.
  const rows = run(process.argv[2] || BODIES);
  // A GATE OVER AN EMPTY POPULATION ASSERTS NOTHING.
  if (rows.length === 0) {
    console.log("HARNESS FAILURE: no bodies found — this gate asserted nothing");
    process.exit(2);
  }
  let bad = 0;
  for (const r of rows) {
    if (r.state === "CLEAN") { console.log(`  [ok ]  ${r.name.padEnd(15)} no fallbacks`); continue; }
    if (r.state === "QUARANTINED") {
      console.log(`  [pin]  ${r.name.padEnd(15)} ${r.hits.length} site(s) — ${r.pin.owner}, since ${r.pin.since}`);
      continue;
    }
    bad++;
    if (r.state === "PIN IS STALE") {
      console.log(`  [FAIL] ${r.name.padEnd(15)} is CLEAN but still pinned — remove it from QUARANTINE`);
    } else {
      console.log(`  [FAIL] ${r.name.padEnd(15)} ${r.hits.length} hardcoded fallback(s):`);
      for (const h of r.hits.slice(0, 6)) console.log(`           L${h.line}: ${h.text}`);
      if (r.hits.length > 6) console.log(`           ... and ${r.hits.length - 6} more`);
    }
  }
  const clean = rows.filter((r) => r.state === "CLEAN").length;
  const pinned = rows.filter((r) => r.state === "QUARANTINED").length;
  console.log("");
  console.log(`${rows.length} bodies — ${clean} clean, ${pinned} quarantined, ${bad} FAILING`);
  process.exit(bad ? 1 : 0);
}
