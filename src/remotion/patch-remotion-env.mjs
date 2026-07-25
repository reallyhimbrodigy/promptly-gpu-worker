#!/usr/bin/env node
/**
 * IMAGE-BUILD patch of the bundled @remotion/renderer (pinned 4.0.450) for
 * the Modal container environment. Runs in modal_app.py's image build right
 * after `npm install` (which would restore pristine files). Idempotent.
 * W1-FIX-DEEP Class B — evidence: job 7f09fe28 + the 2026-07-21 e2e capture
 * (8/8 parallel chunk renders dead on one container, all with the same
 * stderr shape).
 *
 * PATCH 1 — browser-connect deadline 25000 → 120000 ms.
 *   The real RENDER_FATAL killer: `TimeoutError: Timed out after 25000 ms
 *   while trying to connect to the browser!`. All 8 parallel
 *   chrome-headless-shell spawns on a cold container produced their FIRST
 *   stderr output ~25s after spawn (cold image-FS materialization + 8-way
 *   simultaneous first-exec contention) and none hit the DevTools endpoint
 *   inside Remotion's HARD-CODED 25s deadline (no option / env var exists
 *   in 4.0.450 — `timeout: 25000` at the openBrowser call). The same
 *   container launched Chrome fine ~2 minutes later (stripped-rung render
 *   succeeded in 127.6s), so the deadline — not the host — was fatal.
 *   120s only defines the failure deadline; healthy launches connect in
 *   <3s, so good-host behavior is unchanged.
 *
 * PATCH 2 — cgroup memory sentinel → null (prefer /proc/meminfo).
 *   Modal exposes ~2^63 bytes via cgroup (an "unlimited" sentinel, not a
 *   limit). Remotion's getAvailableMemory then logs the multi-line
 *   "Detected differing memory amounts / Memory reported by CGroup:
 *   8796093016236.07 MB" WARNING at the top of every render's stderr.
 *   That warning is harmless to the render (the code takes
 *   min(nodeMemory, cgroupMemory) = nodeMemory either way — behavior
 *   preserving, proven by cert_remotion_env_patch.py) but it BURIED the
 *   real error under downstream truncation: the RENDER_FATAL forensic
 *   envelope for 7f09fe28 kept only the memory lines and the class was
 *   misfiled as a memory failure. A >1 PiB reading is a sentinel, never a
 *   limit — report "no cgroup data" so the /proc/meminfo path is used and
 *   the misleading warning never fires.
 *
 * Applies to EVERY @remotion/renderer/dist copy under the given root
 * (npm may nest copies under @remotion/cli etc.); FAILS THE BUILD (exit 1)
 * if the top-level copy does not end up patched — a Remotion version bump
 * that changes these code shapes must break the build loudly, not silently
 * ship unpatched.
 *
 * Usage: node patch-remotion-env.mjs [node_modules_root]
 */
import fs from "fs";
import path from "path";

const ROOT = process.argv[2] || "/remotion/node_modules";
const SENTINEL_BYTES = "1125899906842624"; // 1 PiB — no real machine; Modal sentinel is ~2^63

const PATCHES = [
  {
    name: "browser-connect-deadline",
    file: ["dist", "esm", "index.mjs"],
    from: "timeout: 25000,",
    to: "timeout: 120000, /* PROMPTLY_PATCH: was 25000 — 8-way cold-container Chrome spawns exceed 25s on Modal (job 7f09fe28); healthy launches connect in <3s, only the failure deadline moves */",
  },
  {
    name: "browser-connect-deadline-cjs",
    file: ["dist", "open-browser.js"],
    from: "timeout: 25000,",
    to: "timeout: 120000, /* PROMPTLY_PATCH: was 25000 — see esm note */",
  },
  {
    name: "cgroup-sentinel",
    file: ["dist", "esm", "index.mjs"],
    from: "const cgroupMemory = getAvailableMemoryFromCgroup();",
    to: `const cgroupMemory = (() => { const v = getAvailableMemoryFromCgroup(); return v !== null && v > ${SENTINEL_BYTES} ? null : v; })(); /* PROMPTLY_PATCH: >1PiB cgroup reading is an "unlimited" sentinel (Modal ~2^63), not a limit — use /proc/meminfo and never print the misleading differing-memory warning */`,
  },
  {
    name: "cgroup-sentinel-cjs",
    file: ["dist", "memory", "get-available-memory.js"],
    from: "const cgroupMemory = (0, from_docker_cgroup_1.getAvailableMemoryFromCgroup)();",
    to: `const cgroupMemory = (() => { const v = (0, from_docker_cgroup_1.getAvailableMemoryFromCgroup)(); return v !== null && v > ${SENTINEL_BYTES} ? null : v; })(); /* PROMPTLY_PATCH: see esm note */`,
  },
];

function findRendererDirs(root) {
  const out = [];
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      if (!e.isDirectory() || e.name === ".bin") continue;
      const p = path.join(dir, e.name);
      if (e.name === "renderer" && path.basename(dir) === "@remotion") {
        out.push(p);
      } else {
        stack.push(p);
      }
    }
  }
  return out;
}

const rendererDirs = findRendererDirs(ROOT);
if (rendererDirs.length === 0) {
  console.error(`[patch-remotion-env] FATAL: no @remotion/renderer under ${ROOT}`);
  process.exit(1);
}

let summary = [];
for (const rdir of rendererDirs) {
  for (const p of PATCHES) {
    const f = path.join(rdir, ...p.file);
    if (!fs.existsSync(f)) continue;
    const src = fs.readFileSync(f, "utf8");
    if (src.includes(p.to)) {
      summary.push(`${p.name}: already patched (${f})`);
      continue;
    }
    if (!src.includes(p.from)) {
      summary.push(`${p.name}: PATTERN NOT FOUND (${f})`);
      continue;
    }
    fs.writeFileSync(f, src.split(p.from).join(p.to));
    summary.push(`${p.name}: patched (${f})`);
  }
}
summary.forEach((s) => console.log(`[patch-remotion-env] ${s}`));

// The TOP-LEVEL renderer (the one render-full.mjs resolves) MUST carry every
// patch — fail the image build otherwise.
const top = path.join(ROOT, "@remotion", "renderer");
let failed = false;
for (const p of PATCHES) {
  const f = path.join(top, ...p.file);
  if (!fs.existsSync(f) || !fs.readFileSync(f, "utf8").includes(p.to)) {
    console.error(`[patch-remotion-env] FATAL: top-level ${p.name} NOT applied (${f}) — Remotion code shape changed? Re-derive the patch before shipping.`);
    failed = true;
  }
}
if (failed) process.exit(1);
console.log(`[patch-remotion-env] OK — ${rendererDirs.length} renderer copies scanned, top-level fully patched`);
