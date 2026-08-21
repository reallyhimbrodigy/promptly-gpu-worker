// EVERY RENDER-TREE TSX MUST ACTUALLY PARSE.
//
// THE GAP THIS CLOSES. There is no tsc in this repo, and the wiring smokes
// (brand-mg-wiring, frame-comp-wiring) are REGEX readers — they can confirm a
// symbol is mentioned, never that the file compiles. Twice now a syntactically
// broken render tree passed every check and was caught only by a render:
//
//   * `sourceUrl` used in JSX but never bound -> SymbolicateableError
//     [ReferenceError] -> RENDER_FATAL, 196s of wall, no artifact.
//   * an import list left as `interpolate,\n, staticFile} from "remotion";`
//     while adding staticFile — malformed, and both wiring smokes passed it.
//
// A render is a ten-minute, ~$0.30 syntax checker. This is a 10ms one.
//
// esbuild is already a dependency (Remotion bundles with it), so this adds
// nothing to the image. It PARSES ONLY — externals are stubbed, no type
// checking, no resolution of the component graph. A file that parses can still
// be wrong; a file that does not parse is always wrong.
import { build } from "esbuild";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(__dirname, "src");

const files = fs.readdirSync(SRC).filter((f) => f.endsWith(".tsx"));
if (files.length === 0) {
  console.error("FAIL: found ZERO .tsx files — the matcher is broken, and a "
    + "check that inspects nothing passes everything");
  process.exit(1);
}

let failed = 0;
for (const f of files) {
  try {
    await build({
      entryPoints: [path.join(SRC, f)],
      outfile: path.join(process.platform === "win32" ? "NUL" : "/dev/null"),
      bundle: true,
      write: false,
      logLevel: "silent",
      // Stub every import: we are asserting SYNTAX, not the module graph.
      plugins: [{
        name: "stub-all",
        setup(b) {
          b.onResolve({ filter: /.*/ }, (args) =>
            args.kind === "entry-point" ? null : { path: args.path, external: true });
        },
      }],
    });
  } catch (e) {
    failed++;
    const msg = (e && e.errors && e.errors[0])
      ? `${e.errors[0].text} @ ${e.errors[0].location?.line ?? "?"}`
      : String(e).slice(0, 200);
    console.error(`FAIL ${f}: ${msg}`);
  }
}

if (failed) {
  console.error(`\ntsx-parses: ${failed}/${files.length} FAILED TO PARSE`);
  process.exit(1);
}
console.log(`tsx-parses: ${files.length} render-tree file(s) parse`);
