/**
 * THE VELOCITY CAP, EMITTED FOR A CHATCUT MOTION GRAPHIC. ONE SOURCE, N COPIES.
 *
 * WHY A BUILD STEP AND NOT SEVEN HAND-WRITTEN COPIES (Zac, 2026-09-19). A ChatCut
 * motion graphic is one inline blob with no imports, so the 316-line cap has to
 * travel INSIDE each ported zoom. Seven hand-maintained copies of one rule is the
 * August agent-config incident exactly: a file duplicated five times that no
 * longer agreed with itself. So the blobs are GENERATED from the module and never
 * hand-edited, and the gate re-emits and byte-compares. Any edit to the cap
 * re-emits all seven or fails.
 *
 * THE STRIP IS NODE'S OWN. `module.stripTypeScriptTypes` is the same transform
 * Node applies when it executes the .ts file, so the emitted JS is not a
 * translation of the module — it is the module, with the types removed by the
 * tool that removes them anyway. A hand-written regex stripper would have been a
 * second implementation of the thing we are trying not to have two of.
 *
 * Usage:  node port/emit_zoom_cap.mjs            -> the section on stdout
 *         node port/emit_zoom_cap.mjs --sha      -> just the source sha256
 */
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { stripTypeScriptTypes } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const CAP_SOURCE = "src/remotion/src/zoom/shared/velocity-cap.ts";
export const BEGIN = "/* ── PROMPTLY VELOCITY CAP — EMITTED, DO NOT EDIT ──";
export const END = "/* ── END VELOCITY CAP ── */";

export function capSha() {
  return createHash("sha256").update(readFileSync(join(ROOT, CAP_SOURCE))).digest("hex");
}

export function emitCap() {
  const src = readFileSync(join(ROOT, CAP_SOURCE), "utf8");
  // Node's own stripper, then the module keywords the blob has no use for. The
  // stripper pads with spaces rather than reflowing, so trailing whitespace goes
  // too — otherwise the emitted bytes carry the type annotations' shadows.
  const js = stripTypeScriptTypes(src, { mode: "strip" })
    .split("\n")
    .map((l) => l.replace(/^export\s+/, "").replace(/\s+$/, ""))
    .filter((l, i, a) => !(l === "" && a[i - 1] === ""))
    .join("\n")
    .trim();
  return [
    BEGIN,
    "   source:  " + CAP_SOURCE,
    "   sha256:  " + capSha(),
    "   re-emit: node port/emit_zoom_cap.mjs",
    "   The 11px/frame peak-displacement cap, the trapezoid easing and the",
    "   punch/glide register. Edit the SOURCE and re-emit; never edit here. */",
    js,
    END,
  ].join("\n");
}

if (process.argv[2] === "--sha") process.stdout.write(capSha());
else if (import.meta.url === `file://${process.argv[1]}`) process.stdout.write(emitCap());
