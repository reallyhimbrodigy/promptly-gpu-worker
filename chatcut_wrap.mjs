// Take a FLATTENED Remotion component and package it to ChatCut's MG contract.
//
// NOTHING ABOUT THE MOTION CHANGES. Remotion renders these inside our own app,
// where they may import, share a library, load fonts and root on AbsoluteFill.
// ChatCut takes one self-contained blob with none of that. Same JSX, different
// packaging — and the packaging is six mechanical rules, learned from the
// validator rather than from documentation:
//
//   1. exactly ONE top-level component, and NO top-level constants
//   2. the root must be a plain div, never an AbsoluteFill
//   3. every editable value read through an identifier literally named `props`
//   4. no React.createContext
//   5. no Freeze (fixed Remotion allowlist)
//   6. no imperative loadFont()   (and no `void` operator, handled upstream)
//
// RULES 1 AND 2 FALL TO ONE MOVE: put the whole flattened module INSIDE the
// Component function. Its consts stop being top-level, its helper components
// stop being top-level components, and the adapter's div becomes the root.
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { hoistFunctions } from "./hoist_functions.mjs";

export function destructuredProps(code, name) {
  // the component's own parameter list — the names ChatCut must declare
  const re = new RegExp("var " + name + " = \\(\\{([^]*?)\\}\\)\\s*=>");
  const m = re.exec(code);
  if (!m) {
    // THREE COMPONENTS TAKE `(props)` DIRECTLY and destructure in the body —
    // ProgressBar, SpeechBubble, Stamp. They are CLOSER to the contract than
    // the destructured ones, not further from it: the identifier is already
    // named `props`. Read the names from the body instead of declaring the
    // component unreadable.
    const sig = new RegExp("var " + name + " = \\(props\\)\\s*=>");
    if (!sig.test(code)) return null;
    const names = new Set();
    const body = code.slice(code.search(sig));
    const inner = /const \{([^]*?)\} = props/.exec(body);
    if (inner) {
      for (const t of inner[1].split(",")) {
        const k = t.trim().split(/[=:]/)[0].trim();
        if (/^[A-Za-z_$][\w$]*$/.test(k)) names.add(k);
      }
    }
    for (const mm of body.matchAll(/\bprops\.([A-Za-z_$][\w$]*)/g)) {
      names.add(mm[1]);
    }
    return names.size ? [...names] : null;
  }
  // STRIP COMMENTS BEFORE SPLITTING ON COMMAS. NamePlate is the only component
  // whose parameter list carries a comment, and that comment contains commas
  // ("...matching all 26 // dispatched MGs: a rest-spread here types as an
  // index signature, and..."). Splitting the raw text made the token after
  // each comma a sentence fragment, the identifier filter dropped it, and
  // `startMs` silently left the mapping. The component then read
  // `timing.startMs === undefined`, msToFrames returned NaN, `visible` went
  // false and it returned null — a blank frame with no error anywhere. One
  // comma inside a comment, one component that never drew.
  return m[1]
    .replace(/\/\*[^]*?\*\//g, "")
    .replace(/\/\/[^\n]*/g, "")
    .split(",")
    .map((s) => s.trim().split(/[=:]/)[0].trim())
    .filter((s) => /^[A-Za-z_$][\w$]*$/.test(s));
}

// THE COMPONENT'S NAME IS IN THE CODE, NOT IN THE FILENAME. Gadzhi.tsx
// exports `GadzhiStyle`, so wrapping by basename emitted `<Gadzhi {...} />`
// against a declaration that did not exist — an undefined identifier the
// local scan caught only because it had been taught to ask. Resolve the name
// from the source, preferring an exact match and falling back to the last
// declaration that starts with it.
export function resolveName(code, base) {
  if (new RegExp("\\bvar " + base + " = \\(").test(code)) return base;
  const m = [...code.matchAll(
    new RegExp("^var (" + base + "\\w*) = \\(", "gm"))];
  if (m.length) return m[m.length - 1][1];
  return base;
}

export function wrap(code, name) {
  name = resolveName(code, name);
  const violations = [];
  // STRIP THE PREVIOUS ADAPTER. port_mg.mjs already appends a
  // `const Component = ({ item })` wrapper; wrapping again would produce
  // TWO top-level components, the one thing the contract refuses outright.
  let out = code.replace(/\n\/\/ ── ChatCut adapter \(generated\)[^]*$/, "\n");
  out = out.replace(/\n\/\/ THE CHATCUT ADAPTER[^]*$/, "\n");

  // 4. createContext -> a plain value. The context is only ever read with its
  //    DEFAULT in this corpus (SmoothGraphics=false, MotionBlur=DISABLED), and
  //    a context created inside a render function would be new every frame
  //    anyway. Collapsing it to the default is both legal and correct.
  // The prelude ALIASES them first (`const createContext = React.createContext`)
  // and only then calls them, so replacing the call site alone leaves the
  // forbidden name sitting in an assignment the validator still reads.
  out = out.replace(/^const (createContext|useContext)\d* = React\.\w+;\s*$/gm, "");
  out = out.replace(/React\.createContext/g, "__ctx");
  out = out.replace(/React\.useContext/g, "__useCtx");
  out = out.replace(/\bcreateContext\d*\(/g, "__ctx(");
  out = out.replace(/\buseContext\d*\(/g, "__useCtx(");

  // 7. BLOCKED GLOBALS ARE BLOCKED NAMES. `window` here is not a global at
  //    all — `mgSchedule` destructures a property CALLED window
  //    (`const { fps, window, authoredEnd } = opts`) — and the validator
  //    refuses the identifier on sight, exactly as it matches `props` by name.
  //    Only the real validator found this; my static gate had six rules and
  //    there were seven. Renamed everywhere it appears as a local.
  out = out.replace(/\bwindow\b/g, "__win");

  // 7b. A REAL DOM CALL IS NOT A NAME COLLISION. StickyNotes measures text with
  //     `document.createElement("canvas")` — genuinely blocked, and renaming it
  //     would break it rather than fix it. But the function already carries the
  //     fallback the corpus uses everywhere else (`text.length * fontSize *
  //     0.62`, the latin advance from mgTextMetrics), reached when the context
  //     is null. So force that branch instead of rewriting the measurement:
  //     the estimate is the one this codebase already trusts.
  // THE WHOLE MEASUREMENT, not just the line that names the blocked global.
  // Replacing only `document.createElement("canvas")` with a throw left the
  // NEXT line — `_ctx = canvas.getContext("2d")` — still referring to a
  // binding that no longer existed, and ChatCut refused StickyNotes for an
  // undefined `canvas`. Setting the context to null forces the em-estimate
  // branch the corpus already trusts, and the local disappears with it.
  out = out.replace(
    /const canvas = document\.createElement\("canvas"\);\s*\n\s*_ctx = canvas\.getContext\("2d"\);/g,
    '_ctx = null; // no canvas in ChatCut — the em estimate is the fallback');
  out = out.replace(
    /const canvas = document\.createElement\("canvas"\);/g,
    '_ctx = null; // no canvas in ChatCut');

  // 9. SafeImg PROBES AN IMAGE AND CHATCUT HAS NOTHING TO PROBE WITH. It calls
  //    `new Image()` behind a `setTimeout`, holding the frame open with
  //    delayRender and bailing out through cancelRender. Measured against the
  //    validator: setTimeout, requestAnimationFrame and fetch are BLOCKED
  //    globals; clearTimeout, Image, cancelRender and URL do not exist at all.
  //    Five components (TweetBubble, ChatThread, EndCard, InstagramComment,
  //    TikTokComment) were refused for exactly that block.
  //
  //    ChatCut's own <Img> does the loading, and the contract asks only that a
  //    media source be GUARDED. So the probe is replaced by the thing it was
  //    protecting: render the image when there is one, fall back when there is
  //    not. Same signature, same job, none of the machinery.
  {
    const at = out.indexOf("var SafeImg = (");
    if (at >= 0) {
      let i = out.indexOf("{", out.indexOf("=>", at));
      let depth = 0, end = -1;
      for (let j = i; j < out.length; j++) {
        if (out[j] === "{") depth++;
        else if (out[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
      }
      if (end > 0) {
        const tail = out.indexOf(";", end);
        out = out.slice(0, at)
          + "var SafeImg = ({ src, role, fallback = null, label, "
          + "onUnavailable, ...rest }) => (src ? <Img src={src} {...rest} /> "
          + ": fallback);"
          + out.slice(tail + 1);
      }
    }
  }

  // 7c. `globalThis` IS A BLOCKED NAME TOO, and it appears in exactly one
  //     place across the corpus: a strict-mode feature flag read that is FALSE
  //     everywhere except a Remotion test harness
  //     (`typeof globalThis !== "undefined" && globalThis.REMOTION_FIT_STRICT`).
  //     The read is collapsed to its value here rather than renamed, because
  //     the flag has no meaning in ChatCut and a renamed `__globalThis` would
  //     be an undefined identifier one rule later.
  out = out.replace(
    /typeof globalThis !== "undefined" && globalThis\.\w+/g, "false");
  out = out.replace(/\bglobalThis\b/g, "__globalThis");

  // 6. loadFont is refused BY NAME even when it is already a local shim.
  out = out.replace(/\bloadFont(\d*)\b/g, "__font$1");

  // 8. DECLARED BEFORE USED. Flattening preserves the bundler's order, which
  //    is fine for a module and illegal for a function body: three of IMessage-
  //    Bubble's helpers were declared after the component that renders them,
  //    and ChatCut refused all three by name. Function-valued declarations move
  //    up; nothing else moves.
  const _h = hoistFunctions(out);
  out = _h.code;

  const props = destructuredProps(out, name);
  if (!props) violations.push(`could not read ${name}'s parameter list`);

  // 10. AN INNER COMPONENT WHOSE PARAMETER IS LITERALLY `props` COLLIDES WITH
  //     THE CONTRACT. ChatCut matches `props.X` STATICALLY by name, so it
  //     cannot tell the wrapper's item props from a helper's own parameter.
  //     ProgressBar takes `(props)` directly and reads `props.width`,
  //     `props.accentColor`, `props.formatValue` in its body; every one was
  //     reported as an undeclared item prop, and baking them out of __mapped
  //     removed the declaration while leaving the read. Rename the inner
  //     parameter — the collision is the whole problem, and the outer `props`
  //     identifier the contract demands is untouched.
  {
    const re2 = new RegExp("(var " + name + " = \\()props(\\)\\s*=>)");
    if (re2.test(out)) {
      const at = out.search(re2);
      let i = out.indexOf("{", out.indexOf("=>", at));
      let depth = 0, end = -1;
      for (let j = i; j < out.length; j++) {
        if (out[j] === "{") depth++;
        else if (out[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
      }
      if (end > 0) {
        const body = out.slice(at, end + 1)
          .replace(re2, "$1__own$2")
          .replace(/\bprops\??\./g, "__own.")
          .replace(/=\s*props\b/g, "= __own");
        out = out.slice(0, at) + body + out.slice(end + 1);
      }
    }
  }


  const mapped = (props || [])
    .map((p) => `    ${p}: props.${p},`)
    .join("\n");

  const body = out
    .split("\n")
    .map((l) => (l.trim() ? "  " + l : l))
    .join("\n");

  const wrapped = `const Component = ({ item }) => {
  const props = (item && item.props) || {};
  // 5. Freeze is not in ChatCut's Remotion allowlist. It is referenced only
  //    inside CameraMotionBlur, which is unreachable while motion blur is
  //    disabled — but the validator scans statically, so it needs a binding.
  const Freeze = ({ children }) => children;
  // 4. the context shims: read returns the default, which is what this corpus
  //    always reads.
  const __ctx = (d) => ({ __default: d });
  const __useCtx = (c) => (c && c.__default !== undefined ? c.__default : c);

${body}

  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const __mapped = {
${mapped}
  };
  return <div style={rootStyle}><${name} {...__mapped} /></div>;
};
`;
  return { code: wrapped, props: props || [], violations };
}

export function contractCheck(code) {
  const v = [];
  if ((code.match(/const Component = \(/g) || []).length !== 1)
    v.push("not exactly one top-level component");
  const tops = code
    .split("\n")
    .filter((l) => /^(const|let|var|function)\s/.test(l) && !l.startsWith("const Component"));
  if (tops.length) v.push(`top-level declarations survive: ${tops.slice(0, 3).join(" | ")}`);
  if (!/return <div style=\{rootStyle\}>/.test(code)) v.push("root is not a plain div");
  // NO AbsoluteFill LEG. The contract forbids AbsoluteFill as the OUTERMOST
  // element only — it is explicitly legal as an inner layer, which is what
  // every wrapped component now has. A leg matching `return <AbsoluteFill`
  // anywhere fired on all 28 of them: a pattern tight enough to reject a
  // CORRECT implementation, in the gate written to stop exactly that. The
  // root is proven by the div leg above and nothing else is needed.
  // COMMENTS ARE NOT CODE. Every pattern below scans the blob as TEXT, so a
  // comment explaining a fix matches it. RankedList was refused for "blocked
  // global name survives: document" by a comment that said "paint order stays
  // document order" — a correct component refused for its own explanation.
  // FOURTH instance in one session (the NO STILL scan, the currentColor grep,
  // the zIndex A/B, and now the contract itself), so the strip is shared
  // rather than added case by case.
  //
  // It strips comments ONLY for the identifier scans. The structural legs
  // above still read the real text, because a comment cannot satisfy them.
  const codeNoComments = code
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p1) => p1);
  if (!/const props = \(item && item\.props\)/.test(code)) v.push("no `props` identifier");
  if (/\bcreateContext\b/.test(codeNoComments)) v.push("createContext survives");
  if (/\bloadFont\b/.test(codeNoComments)) v.push("loadFont survives");
  if (/\bvoid\s/.test(codeNoComments)) v.push("the void operator survives");
  for (const g of ["window", "document", "globalThis", "eval", "localStorage"])
    if (new RegExp("\\b" + g + "\\b").test(codeNoComments))
      v.push(`blocked global name survives: ${g}`);
  return v;
}

if (process.argv[1] && process.argv[1].endsWith("chatcut_wrap.mjs")) {
  const [, , inPath, outPath] = process.argv;
  const name = basename(inPath).replace(/\.jsx?$/, "");
  const src = readFileSync(inPath, "utf8");
  const { code, props, violations } = wrap(src, name);
  const contract = contractCheck(code);
  if (outPath) writeFileSync(outPath, code);
  console.log(JSON.stringify({
    name, props, wrap_violations: violations, contract_violations: contract,
    ok: violations.length === 0 && contract.length === 0,
    bytes: code.length,
  }, null, 1));
  process.exit(violations.length || contract.length ? 1 : 0);
}
