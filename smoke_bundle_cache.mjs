/**
 * SMOKE: the bundle cache DECIDES correctly — driven, not read.
 *
 * The sibling smoke (smoke_shared_process.py) checks the batch renderer by
 * text-matching its source. That is the repo's most expensive check class: a
 * substring is satisfied by a comment, and "yuva444p10le" in the file proves
 * only that the string is in the file. This one imports the SHIPPED function
 * and drives it against real directories.
 *
 * What makes it fire: a stale key (authoring a component and getting the
 * previous bundle back) and a false-complete cache (a dir left by a process
 * killed mid-bundle read as usable). Both are silent failures that produce a
 * plausible video, which is why they need a check that can fail.
 */
import { bundleDecision } from "./remotion_batch.mjs";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const fails = [];
const ok = (label, cond, detail = "") => {
  if (!cond) fails.push(label + (detail ? `  :: ${detail}` : ""));
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "rbundle-smoke-"));
const root = path.join(tmp, "proj");
const cacheRoot = path.join(tmp, "cache");
fs.mkdirSync(path.join(root, "src", "nested"), { recursive: true });
fs.writeFileSync(path.join(root, "src", "index.ts"), "export const a = 1;\n");
fs.writeFileSync(path.join(root, "src", "nested", "Comp.tsx"), "export const Comp = () => null;\n");

// ── the key is stable for an unchanged tree ────────────────────────────────
const d1 = bundleDecision(root, cacheRoot);
const d2 = bundleDecision(root, cacheRoot);
ok("an unchanged tree yields a stable key", d1.key === d2.key,
   `${d1.key} != ${d2.key} — every process would re-bundle and the cache is inert`);

// ── a fresh cache is NOT considered cached ─────────────────────────────────
ok("an absent cache dir is not 'cached'", d1.cached === false,
   "a missing bundle read as present would serve a serveUrl that does not exist");

// ── a dir WITHOUT the marker is not usable (killed mid-bundle) ─────────────
fs.mkdirSync(d1.cacheDir, { recursive: true });
fs.writeFileSync(path.join(d1.cacheDir, "index.html"), "<html>partial</html>");
ok("a populated dir with NO marker is still not 'cached'",
   bundleDecision(root, cacheRoot).cached === false,
   "a process killed mid-bundle leaves a plausible-looking directory; without "
   + "the marker rule it is served as a complete bundle");

// ── with the marker it IS usable ───────────────────────────────────────────
fs.writeFileSync(d1.marker, d1.key);
ok("a completed cache is reused", bundleDecision(root, cacheRoot).cached === true,
   "the cache never hits, so it saves nothing");

// ── AUTHORING A COMPONENT MUST INVALIDATE IT ───────────────────────────────
// The agent writes Comp.tsx mid-run. A cache that survived that would render
// the PREVIOUS version of a component the agent had just fixed — silently.
// A SAME-LENGTH EDIT, deliberately. The first version of this test rewrote the
// file to a different length, so file SIZE alone distinguished the two versions
// and the assertion passed even with mtime removed from the key — the check
// could not detect its own failure. Changing a number, a colour or a boolean is
// the common real edit and it does not change the length; that is the case that
// must fire.
await new Promise((r) => setTimeout(r, 10));
const before = fs.readFileSync(path.join(root, "src", "nested", "Comp.tsx"), "utf8");
const edited = before.replace("null", "1234");   // same byte length
if (edited.length !== before.length) throw new Error("test bug: edit changed length");
fs.writeFileSync(path.join(root, "src", "nested", "Comp.tsx"), edited);
const d3 = bundleDecision(root, cacheRoot);
ok("editing a component changes the key", d3.key !== d1.key,
   "the agent authors components mid-run; a stale bundle renders the version "
   + "it just replaced, and the video looks plausible");
ok("editing a component makes the cache MISS", d3.cached === false,
   "stale bundle served after an edit");

// ── SAME CONTENT, NEW MTIME, SAME KEY — the thrash fix ─────────────────────
// MEASURED THRASH: in the first container run the reel got a CACHE HIT (0.7s)
// and the captions then paid a full 9.3s bundle on an unchanged source tree.
// Mount materialisation hands files fresh mtimes; the bytes do not move. A key
// that moves with mtime rebuilds the bundle for nothing, which is the whole
// saving thrown away — and it looks like a working cache, because it does hit
// sometimes.
{
  const k0 = bundleDecision(root, cacheRoot).key;
  const f = path.join(root, "src", "index.ts");
  const body = fs.readFileSync(f);
  const future = Date.now() + 60_000;
  fs.writeFileSync(f, body);                       // identical bytes
  fs.utimesSync(f, future / 1000, future / 1000);  // moved mtime
  ok("an unchanged FILE with a new mtime keeps the key",
     bundleDecision(root, cacheRoot).key === k0,
     "the key follows mtime, so a re-materialised mount rebuilds the bundle "
     + "for nothing — measured as reel CACHE HIT then captions paying 9.3s");
}

// ── a NEW file changes the key ─────────────────────────────────────────────
fs.writeFileSync(path.join(root, "src", "Added.tsx"), "export const X = 1;\n");
ok("adding a file changes the key", bundleDecision(root, cacheRoot).key !== d3.key,
   "a new component would not be bundled");

// ── node_modules must NOT be walked (it would dominate and thrash) ─────────
const beforeNM = bundleDecision(root, cacheRoot).key;
fs.mkdirSync(path.join(root, "src", "node_modules", "x"), { recursive: true });
fs.writeFileSync(path.join(root, "src", "node_modules", "x", "i.js"), "module.exports=1;");
ok("node_modules is excluded from the key",
   bundleDecision(root, cacheRoot).key === beforeNM,
   "walking node_modules makes the key change on every install and the cache never hits");

fs.rmSync(tmp, { recursive: true, force: true });

if (fails.length) {
  console.log(`BUNDLE-CACHE: ${fails.length} FAILED`);
  for (const f of fails) console.log("  - " + f);
  process.exit(1);
}
console.log("BUNDLE-CACHE: PASS (9 behaviours driven, not read)");
