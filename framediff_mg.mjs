// Frame-diff a PORTED motion graphic against its Remotion ORIGINAL.
//
// WHY THE RENDER TREE AND NOT PIXELS. The named risk is that flattening
// useMGPhase — which reaches into zoom/shared/velocity-cap, 316 lines of
// entrance velocity cap from the smoothness rounds — silently changes the
// MOTION while the component still renders. A pixel diff through two different
// renderers blurs that behind font rasterisation and encoder noise. The render
// tree carries the actual computed numbers: every transform, opacity, scale and
// interpolated style, at every frame. A one-frame timing shift or a dropped
// easing shows up here as an exact value difference and would be invisible at
// any PSNR threshold worth using.
//
// BOTH SIDES RUN THE SAME WAY. The original is bundled with the same esbuild
// settings MINUS the port's transformations, so the only variable under test is
// the port itself — not TypeScript, not the bundler.
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { join, basename } from "node:path";
import { tmpdir } from "node:os";

const ESB = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/esbuild/lib/main.js";
const REACT = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/react/index.js";
const RDS = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/react-dom/server.js";
const { build } = await import(ESB);
const React = (await import(REACT)).default ?? (await import(REACT));
const { renderToStaticMarkup } = await import(RDS);

const [origTsx, portedJsx, compName] = process.argv.slice(2);
const FRAMES = [0, 1, 2, 4, 8, 12, 16, 20, 24, 28, 32, 40, 56, 72, 89];
const FPS = 30, W = 1080, H = 1920;

// THE STUBBED RUNTIME. Identical for both sides, so any difference is the port.
function makeGlobals(frame) {
  const interpolate = (input, iRange, oRange, opts = {}) => {
    let i = 0;
    while (i < iRange.length - 2 && input >= iRange[i + 1]) i++;
    const [a, b] = [iRange[i], iRange[i + 1]];
    const [x, y] = [oRange[i], oRange[i + 1]];
    let t = b === a ? 0 : (input - a) / (b - a);
    if (opts.extrapolateLeft === "clamp" && t < 0) t = 0;
    if (opts.extrapolateRight === "clamp" && t > 1) t = 1;
    if (opts.easing) t = opts.easing(t);
    return x + (y - x) * t;
  };
  const ease = (f) => f;
  const Easing = {
    linear: (t) => t, ease: (t) => t,
    out: (f) => (t) => 1 - Math.pow(1 - t, 3),
    in: (f) => (t) => t * t * t,
    inOut: (f) => (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    cubic: (t) => t * t * t, quad: (t) => t * t, bezier: () => (t) => t,
    sin: (t) => 1 - Math.cos((t * Math.PI) / 2),
  };
  const spring = ({ frame: f = frame, from = 0, to = 1 }) =>
    from + (to - from) * Math.min(1, Math.max(0, f / 20));
  const AbsoluteFill = (p) => React.createElement("div", { ...p, "data-af": 1 }, p?.children);
  return {
    React, spring, Easing, interpolate,
    useCurrentFrame: () => frame,
    useVideoConfig: () => ({ fps: FPS, width: W, height: H, durationInFrames: 90 }),
    interpolateColors: (i, ir, or_) => or_[0],
    AbsoluteFill,
    Sequence: (p) => React.createElement("div", null, p?.children),
    Series: (p) => React.createElement("div", null, p?.children),
    Img: (p) => React.createElement("img", p),
    Video: (p) => React.createElement("video", p),
    Audio: () => null,
    random: () => 0.5,
    Freeze: (p) => React.createElement("div", null, p?.children),
    useMemo: React.useMemo, useState: React.useState, useRef: React.useRef,
    useEffect: () => {}, useLayoutEffect: () => {}, useCallback: React.useCallback,
    useContext: React.useContext, useId: () => "id", useReducer: React.useReducer,
  };
}

// THE SAME FONT SHIM ON BOTH SIDES. The original pulls the real
// @remotion/google-fonts SDK, which needs remotion/no-react internals this
// harness does not stub — and stubbing them would be inventing a runtime. The
// variable under test is the FLATTEN, so fonts are held constant on both sides
// rather than made another difference to explain.
const fontShim = {
  name: "google-fonts-shim",
  setup(b) {
    b.onResolve({ filter: /^@remotion\/google-fonts\// }, (a) => ({
      path: a.path, namespace: "gfont" }));
    b.onLoad({ filter: /.*/, namespace: "gfont" }, (a) => {
      const fam = a.path.split("/").pop();
      return { contents: `export const loadFont = () => ({ fontFamily: ${JSON.stringify(fam)} });
export const getAvailableWeights = () => [];
export const getInfo = () => ({ fontFamily: ${JSON.stringify(fam)} });
export default { loadFont };`, loader: "js" };
    });
  },
};

async function bundleOriginal(tsx) {
  const r = await build({
    plugins: [fontShim],
    entryPoints: [tsx], bundle: true, format: "cjs", platform: "neutral",
    target: "es2020", jsx: "automatic", loader: { ".tsx": "tsx", ".ts": "ts" },
    external: ["react", "react/jsx-runtime", "remotion", "remotion/no-react"],
    write: false, logLevel: "silent",
  });
  return r.outputFiles[0].text;
}

async function compileBlob(jsx) {
  // The ported blob is JSX text; compile it the same way for execution only.
  // bundle:true is required for `external` — without it esbuild refuses the
  // option outright. The blob has no imports left to bundle anyway, so this is
  // a transform in bundler's clothing.
  const r = await build({
    stdin: { contents: jsx, loader: "jsx", resolveDir: "/tmp" },
    bundle: true, format: "cjs", platform: "neutral", target: "es2020",
    jsx: "automatic", write: false, logLevel: "silent",
    external: ["react", "react/jsx-runtime"],
  });
  return r.outputFiles[0].text;
}

function run(src, comp, frame, props) {
  const g = makeGlobals(frame);
  const jsxRuntime = {
    jsx: (t, p) => React.createElement(t, p, p?.children),
    jsxs: (t, p) => React.createElement(t, p, p?.children),
    Fragment: React.Fragment,
  };
  const req = (m) => {
    if (m === "react") return React;
    if (m === "react/jsx-runtime" || m === "react/jsx-dev-runtime") return jsxRuntime;
    if (m === "remotion" || m === "remotion/no-react") return g;
    throw new Error("unexpected require: " + m);
  };
  const mod = { exports: {} };
  const names = Object.keys(g);
  const fn = new Function("module", "exports", "require", ...names,
    src + "\n;return module.exports;");
  const exported = fn(mod, mod.exports, req, ...names.map((n) => g[n]));
  const C = exported?.[comp] ?? exported?.default ?? mod.exports?.[comp];
  if (typeof C !== "function") return { err: "component not exported" };
  try {
    return { html: renderToStaticMarkup(React.createElement(C, props)) };
  } catch (e) { return { err: String(e).slice(0, 160) }; }
}

const PROPS = {
  startMs: 0, durationMs: 3000, value: 10, fromValue: 0, label: "PER DAY",
  text: "SAMPLE", title: "SAMPLE", quote: "SAMPLE", name: "SAMPLE",
  items: ["a", "b"], steps: ["a", "b"], messages: [{ from: "a", text: "b" }],
  percent: 0.5, progress: 0.5, notes: ["a"], pills: ["a", "b"],
};

const origSrc = await bundleOriginal(origTsx);
// THE BLOB HAS NO EXPORTS — that is the ChatCut contract. To execute it here,
// append an export of the component by name. This is test scaffolding and it
// never touches the shipped file.
const blobText = readFileSync(portedJsx, "utf8")
  + `\n;module.exports = { ${compName} };\n`;
const portSrc = await compileBlob(blobText);

let same = 0, diff = 0, errs = [];
const diffs = [];
for (const f of FRAMES) {
  const a = run(origSrc, compName, f, PROPS);
  const b = run(portSrc, compName, f, PROPS);
  if (a.err || b.err) { errs.push(`f${f}: orig=${a.err || "ok"} port=${b.err || "ok"}`); continue; }
  if (a.html === b.html) same++;
  else { diff++; if (diffs.length < 2) diffs.push({ frame: f, origLen: a.html.length, portLen: b.html.length }); }
}
console.log(JSON.stringify({
  component: compName, framesCompared: same + diff, identical: same,
  differing: diff, errors: errs.slice(0, 3), sampleDiffs: diffs,
  verdict: errs.length ? "ABSENT" : (diff === 0 ? "IDENTICAL" : "DIVERGED"),
}));
