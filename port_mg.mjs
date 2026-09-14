// Port a Remotion motion graphic to a ChatCut inline-JSX blob.
//
// WHY A BUNDLER AND NOT A REWRITE. Measured across the 34 components: ZERO use
// a Remotion feature ChatCut cannot provide. The breakage is packaging only —
// TypeScript (34/34), AbsoluteFill as root (28/34), one <Sequence>, and the
// fact that ChatCut takes each MG as a SELF-CONTAINED blob with no imports.
// StatCard alone pulls 15 files and 1,515 lines transitively, so the shared
// library has to be flattened into every component. That is esbuild's job.
//
// THE RISK IS NOT THE JSX. useMGPhase reaches into zoom/shared/velocity-cap —
// 316 lines of entrance velocity cap from the smoothness rounds. A careless
// flatten renders clean, exits 0, and is silently worse. That is why the port
// is verified by frame-diff against the Remotion original, never by "it built".
// esbuild lives in the Remotion project's node_modules, not this lane's.
// Resolved by path rather than by name so the porter can live beside the
// craft it belongs to instead of inside the component tree.
const ESBUILD = process.env.ESBUILD_PATH
  || "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/esbuild/lib/main.js";
const { build } = await import(ESBUILD);
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { basename, dirname, join } from "node:path";

const [entry, outDir] = process.argv.slice(2);
if (!entry) { console.error("usage: port_mg.mjs <Component.tsx> <outDir>"); process.exit(2); }

// ChatCut pre-injects these. They must NOT be bundled and must NOT be imported.
const INJECTED = new Set(["react", "remotion"]);

// GOOGLE FONTS DO NOT CROSS. fonts.ts calls loadFont() at MODULE SCOPE for a
// dozen families, and bundling drags in the @remotion/google-fonts SDK, which
// reaches into remotion/no-react internals ChatCut does not inject. 30 of 33
// blobs carried NoReactInternals and would have crashed at render while the
// build-time checker said ok:true on all 34.
//
// ChatCut loads fonts its own way: search_fonts returns a canonical family name
// and the cloud renderer fetches it. So each loadFont becomes a shim returning
// just the family name — the component keeps its fontFamily string, which is
// the only part that ever reached the DOM.
const fontShim = {
  name: "google-fonts-shim",
  setup(b) {
    b.onResolve({ filter: /^@remotion\/google-fonts\// }, (a) => ({
      path: a.path, namespace: "gfont",
    }));
    b.onLoad({ filter: /.*/, namespace: "gfont" }, (a) => {
      const fam = a.path.split("/").pop();
      return {
        contents: `export const loadFont = () => ({ fontFamily: ${JSON.stringify(fam)} });
export const getAvailableWeights = () => [];
export const getInfo = () => ({ fontFamily: ${JSON.stringify(fam)} });
export default { loadFont };`,
        loader: "js",
      };
    });
  },
};

const res = await build({
  plugins: [fontShim],
  entryPoints: [entry],
  bundle: true,
  format: "esm",
  platform: "neutral",
  target: "es2020",
  jsx: "preserve",          // ChatCut takes JSX, not React.createElement
  loader: { ".tsx": "tsx", ".ts": "ts" },
  external: [...INJECTED],
  write: false,
  logLevel: "silent",
});

let code = res.outputFiles[0].text;

// 1. Drop the imports of things ChatCut already provides. The bound names
//    (useCurrentFrame, interpolate, spring, Easing, AbsoluteFill, ...) exist
//    as globals in its runtime, so removing the import is sufficient.
const dropped = [];
code = code.replace(/^import\s+[^;]*?from\s*["']([^"']+)["'];?\s*$/gm, (m, src) => {
  dropped.push(src);
  return `// [ported] import removed — ChatCut injects these: ${src}`;
});

// 2. No exports in a ChatCut blob.
code = code.replace(/^export\s+default\s+/gm, "const __default = ");
code = code.replace(/^export\s*\{[^}]*\};?\s*$/gm, "");
code = code.replace(/^export\s+(const|function|class)\s+/gm, "$1 ");

// THE PRELUDE. esbuild's renames and the automatic JSX runtime are both
// SILENT at build time and fatal at render, so they are repaired rather than
// merely reported: every suffixed global is aliased back to the injected one,
// React's own hooks are bound off the injected React, and jsx()/jsxs() get a
// createElement shim. Generated from what THIS bundle actually references, so
// a component that needs none of it carries none of it.
const preludeLines = [];
const suffixed = [...new Set(
  [...code.matchAll(/\b(React|spring|useCurrentFrame|useVideoConfig|interpolate|interpolateColors|Easing|AbsoluteFill|Sequence|Series|Img|Video|Audio)(\d+)\b/g)]
    .map(m => [m[0], m[1]]))];
for (const [alias, base] of suffixed) preludeLines.push(`const ${alias} = ${base};`);
// EVERY React hook the components actually reach for. useId was missing and
// exactly two of thirty-four needed it — which is why the port is run over all
// of them rather than proven on one and assumed.
// EVERY React NAMED EXPORT, not just the hooks. The first list had useX only
// and the differ caught `createContext` undefined — same class as the useId
// miss, one level wider. A hand-kept list of "the ones we use" is a second
// vocabulary that drifts the day a component reaches for another; this is
// React's actual surface, filtered to what the bundle references.
for (const hook of ["useContext", "useMemo", "useState", "useRef", "useEffect",
                    "useCallback", "useId", "useReducer", "useLayoutEffect",
                    "useImperativeHandle", "useDeferredValue", "useTransition",
                    "useSyncExternalStore", "useInsertionEffect",
                    "createContext", "createElement", "cloneElement", "memo",
                    "forwardRef", "Fragment", "Children", "isValidElement",
                    "createRef", "lazy", "Suspense", "StrictMode"]) {
  const re = new RegExp(`\\b${hook}\\d*\\s*\\(`);
  if (re.test(code)) {
    for (const m of [...new Set([...code.matchAll(new RegExp(`\\b(${hook}\\d*)\\s*\\(`, "g"))].map(x => x[1]))]) {
      preludeLines.push(`const ${m} = React.${hook};`);
    }
  }
}
if (/\bjsxs?\(/.test(code)) {
  preludeLines.push(
    "const __ch = (p) => (p && p.children !== undefined ? p.children : undefined);",
    "const jsx = (t, p) => React.createElement(t, p, __ch(p));",
    "const jsxs = (t, p) => React.createElement(t, p, __ch(p));");
}
if (preludeLines.length) {
  code = "// ── ported prelude: injected globals re-bound ──\n"
       + [...new Set(preludeLines)].join("\n") + "\n\n" + code;
}

const name = basename(entry).replace(/\.tsx?$/, "");
mkdirSync(outDir, { recursive: true });
const out = join(outDir, `${name}.jsx`);
writeFileSync(out, code);

// REPORT WHAT STILL VIOLATES THE CONTRACT, rather than claiming success.
// A port that "built" and still breaks three rules is the shape this repo
// keeps paying for.
// RE-SCANNED AFTER THE PRELUDE, on the text that actually ships.
// THE INJECTED GLOBALS, BY NAME. ChatCut provides exactly these; anything the
// bundle calls that is not defined in the blob and not on this list is
// undefined at render time.
const GLOBALS = ["React","spring","useCurrentFrame","useVideoConfig","interpolate",
  "interpolateColors","Math","random","Easing","AbsoluteFill","Sequence","Series",
  "Img","Video","Audio"];

const violations = [];

// 1. RENAMED GLOBALS. esbuild suffixes an imported name when it collides with a
//    local one — `useVideoConfig` became `useVideoConfig2` in StatCard. The
//    bundle builds, and the call is undefined the moment it renders. The first
//    version of this checker said ok:true on exactly that.
const renamed = [...new Set(
  [...code.matchAll(/\b(React|spring|useCurrentFrame|useVideoConfig|interpolate|interpolateColors|Easing|AbsoluteFill|Sequence|Series|Img|Video|Audio)(\d+)\b/g)]
    .map(m => m[0]))];
// A RENAMED GLOBAL IS ONLY A DEFECT IF NOTHING DEFINES IT. The prelude aliases
// each one back, so flagging the NAME would fail a correct port — the same
// presence-is-not-the-property error this porter was written to catch.
const unaliased = renamed.filter(r =>
  !new RegExp(`\\b(?:const|let|var)\\s+${r}\\s*=`).test(code));
if (unaliased.length) violations.push(`unaliased renamed globals: ${unaliased.join(", ")}`);

// 2. COMPILED JSX. A file using the automatic runtime turns into jsx()/jsxs()
//    calls whose import we just dropped, so they are undefined too. motion-blur
//    .tsx does this, and StatCard pulls it in.
const jsxCalls = (code.match(/\bjsxs?\(/g) || []).length;
const jsxDefined = /\b(?:const|let|var|function)\s+jsxs?\b/.test(code);
if (jsxCalls && !jsxDefined)
  violations.push(`${jsxCalls} compiled jsx()/jsxs() call(s) with no runtime`);

// 3. ANY OTHER FREE IDENTIFIER that looks like a Remotion API and is neither
//    declared here nor injected.
const declared = new Set([...code.matchAll(/\b(?:var|let|const|function|class)\s+([A-Za-z_$][\w$]*)/g)].map(m=>m[1]));
const used = new Set([...code.matchAll(/\b(use[A-Z][\w$]*)\s*\(/g)].map(m=>m[1]));
const undef = [...used].filter(u => !declared.has(u) && !GLOBALS.includes(u));
if (undef.length) violations.push(`undefined hooks: ${undef.join(", ")}`);

if (/^\s*import\s/m.test(code)) violations.push("an import survived");
if (/^\s*export\s/m.test(code)) violations.push("an export survived");
if (/<Sequence[\s>]/.test(code)) violations.push("<Sequence> inside the component");
if (/:\s*React\.FC|^\s*interface\s|^\s*type\s+[A-Z]/m.test(code)) violations.push("TypeScript survived");
const rootAF = /return\s*\(\s*<AbsoluteFill/.test(code);
if (rootAF) violations.push("AbsoluteFill is still the root");

console.log(JSON.stringify({
  component: name, out, bytes: code.length,
  lines: code.split("\n").length,
  droppedImports: [...new Set(dropped)],
  violations,
  ok: violations.length === 0,
}, null, 1));
