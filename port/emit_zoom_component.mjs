/**
 * SPLICE THE EMITTED CAP INTO A PORTED ZOOM BODY. ONE SOURCE, N COPIES.
 *
 * port/bodies/<Name>.jsx is the hand-written part — the curve, the props and the
 * render. It carries a single `// @@VELOCITY_CAP@@` marker, and this step
 * replaces that line with the cap emitted from the module. The built blob in
 * port/build/<Name>.jsx is GENERATED: nothing in it is edited by hand, and
 * red_proof_the_cap_has_one_source.py re-runs this and byte-compares.
 *
 * Usage:  node port/emit_zoom_component.mjs             -> build every body
 *         node port/emit_zoom_component.mjs --check     -> exit 1 on any drift
 */
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { emitCap } from "./emit_zoom_cap.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const BODIES = join(HERE, "bodies");
const BUILD = join(HERE, "build");
export const MARKER = "// @@VELOCITY_CAP@@";

export function bodyNames() {
  return readdirSync(BODIES).filter((f) => f.endsWith(".jsx")).map((f) => f.slice(0, -4)).sort();
}

export function buildOne(name) {
  const body = readFileSync(join(BODIES, name + ".jsx"), "utf8");
  const hits = body.split("\n").filter((l) => l.trim() === MARKER).length;
  // A COMPONENT WITH NO RAMP HAS NO CAP TO APPLY — StepZoom's single discontinuity
  // IS the effect, and capping it would delete the component. But a missing cap
  // that nobody DECIDED is the exact failure this build step exists to prevent, so
  // a body without the marker must carry `NO VELOCITY CAP:` and a reason.
  if (hits === 0) {
    if (!/NO VELOCITY CAP:/.test(body)) {
      throw new Error(`${name}: no ${MARKER} and no "NO VELOCITY CAP:" reason — say which`);
    }
    return body;
  }
  if (hits !== 1) {
    throw new Error(`${name}: expected at most one ${MARKER} line, found ${hits}`);
  }
  const cap = emitCap();
  // Indented to the marker's own column so the blob reads as one function body.
  const line = body.split("\n").find((l) => l.trim() === MARKER);
  const pad = line.slice(0, line.indexOf("/"));
  const indented = cap.split("\n").map((l) => (l ? pad + l : l)).join("\n");
  return body.replace(line, indented);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  mkdirSync(BUILD, { recursive: true });
  const check = process.argv[2] === "--check";
  let bad = 0;
  for (const name of bodyNames()) {
    const built = buildOne(name);
    const path = join(BUILD, name + ".jsx");
    if (check) {
      let have = null;
      try { have = readFileSync(path, "utf8"); } catch { have = null; }
      if (have === null) { console.log(`DRIFT ${name}: no built blob — run the emitter`); bad++; }
      else if (have !== built) { console.log(`DRIFT ${name}: built blob differs from a fresh emit`); bad++; }
      else console.log(`ok    ${name}: ${built.split("\n").length} lines, in sync`);
    } else {
      writeFileSync(path, built);
      console.log(`built ${name}: ${built.split("\n").length} lines`);
    }
  }
  process.exit(bad ? 1 : 0);
}
