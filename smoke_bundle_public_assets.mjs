// A CACHED BUNDLE MUST STILL SEE ASSETS WRITTEN AFTER IT WAS BUILT.
//
// THE BUG THIS PINS. build_zoom extracts a per-clip file to
// /promptly-remotion/public/zsrc<N>.mp4 at RUN time and hands the component
// `src: "zsrc0.mp4"`. Remotion serves public/ out of the BUNDLE directory, and
// the bundle cache sets `serveUrl = cacheDir` — a directory built by an earlier
// run, whose public/ is a snapshot from bundle time. So on a cache HIT the file
// the component needs does not exist under the serve root:
//
//     SnapReframe render failed: Received a status code of 404 while
//     downloading file http://localhost:3000/public/zsrc0.mp4
//
// On a cache MISS the same code works, because bundle() copies public/ as it
// builds. That is why the failure looked random: within one round, containers
// with a cold cache built zoom and containers with a warm cache 404'd. Present
// in rounds 36, 37, 38, 39, 40 and 41, across SnapReframe, SmoothPush,
// LetterboxPush and StepZoom — every zoom type, because it is not a component
// bug at all. It is the cache I added for the shared Remotion process.
//
// THE SHAPE OF THE DEFECT IS "a speedup that silently changed a contract".
// Nothing errored in the bundler, nothing errored in Python, and the family
// simply stopped arriving — ruled and never built, which is the exact class
// this lane already has a violation name for.
//
//   node smoke_bundle_public_assets.mjs      exit 0 = cached serve dir sees it
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const mod = await import("./remotion_batch.mjs");

let failures = [];
const log = (ok, msg) => {
  console.log(`  [${ok ? "ok" : "FAIL"}] ${msg}`);
  if (!ok) failures.push(msg);
};

if (typeof mod.syncPublicAssets !== "function") {
  console.log("  [FAIL] remotion_batch.mjs does not export syncPublicAssets().");
  console.log("         On a cache hit serveUrl is a stale bundle dir and any");
  console.log("         file written to <root>/public at run time is a 404.");
  console.log("         Nothing reconciles the two, so zoom cannot build.");
  process.exit(1);
}

// A ROOT AND A CACHE DIR THAT ARE GENUINELY DIFFERENT DIRECTORIES, which is the
// whole condition — a test that points both at one path proves nothing.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pubassets-"));
const root = path.join(tmp, "remotion");
const cacheDir = path.join(tmp, "cache", "abc123");
fs.mkdirSync(path.join(root, "public"), { recursive: true });
fs.mkdirSync(path.join(cacheDir, "public"), { recursive: true });

// The bundle-time snapshot: one file that existed when the bundle was built.
fs.writeFileSync(path.join(root, "public", "old.txt"), "at bundle time");
fs.writeFileSync(path.join(cacheDir, "public", "old.txt"), "at bundle time");

// Written AFTER the bundle — this is zsrc0.mp4's situation exactly.
fs.writeFileSync(path.join(root, "public", "zsrc0.mp4"), "runtime bytes");
fs.writeFileSync(path.join(root, "public", "zsrc1.mp4"), "runtime bytes 1");

log(!fs.existsSync(path.join(cacheDir, "public", "zsrc0.mp4")),
    "premise: before the sync, the cached serve dir does NOT have zsrc0.mp4");

mod.syncPublicAssets(root, cacheDir);

log(fs.existsSync(path.join(cacheDir, "public", "zsrc0.mp4")),
    "after the sync, the cached serve dir HAS zsrc0.mp4");
log(fs.existsSync(path.join(cacheDir, "public", "zsrc1.mp4")),
    "every runtime asset, not just the first");
log(fs.readFileSync(path.join(cacheDir, "public", "zsrc0.mp4"), "utf8")
      === "runtime bytes",
    "and its CONTENT matches the source (not an empty placeholder)");
log(fs.existsSync(path.join(cacheDir, "public", "old.txt")),
    "the bundle-time file is still there (sync adds, never wipes the bundle)");

// Re-running must be safe: the batch renderer may sync more than once per
// container, and a second call that throws on an existing file is a new outage.
let threw = null;
try { mod.syncPublicAssets(root, cacheDir); } catch (e) { threw = e; }
log(threw === null, `idempotent — a second sync does not throw${threw ? ` (${threw.message})` : ""}`);

// serveUrl === root is the cache-MISS case and must remain a no-op, not a
// self-copy that could recurse or clobber.
let threw2 = null;
try { mod.syncPublicAssets(root, root); } catch (e) { threw2 = e; }
log(threw2 === null && fs.readFileSync(path.join(root, "public", "zsrc0.mp4"), "utf8") === "runtime bytes",
    "serveUrl === root (cache miss) is a safe no-op");

fs.rmSync(tmp, { recursive: true, force: true });

console.log("");
if (failures.length) {
  console.log(`${failures.length} failure(s)`);
  process.exit(1);
}
console.log("a cached serve dir sees runtime-written public assets");
