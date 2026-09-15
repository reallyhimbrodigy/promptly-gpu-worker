// Every identifier a wrapped blob READS but never DECLARES, offline.
//
// WHY THIS EXISTS. IMessageBubble was refused by ChatCut with
//
//   Undefined identifier "TypingIndicatorBubble". Declare it locally, read it
//   from props, or use one of the supported MG globals.
//   ... "MessageBubble" ... "Tail"
//
// Three helper components the flatten simply did not carry. Nothing about the
// blob looked wrong: it wrapped clean, it passed the seven static contract
// rules, and it registered as ABSENT beside components that had registered and
// drawn nothing — two failure classes wearing one word. The refusal cost a
// full render-check cycle to read, because the only instrument that knew was
// the remote validator.
//
// So ask the same question here. The allowlist of globals is not guessed: it
// is what a probe MG printed from inside ChatCut's own renderer (bisect C,
// 2026-09-14), each one confirmed `function` or `object` at render time.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require_ = createRequire(
  "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/x.js");
const { parse } = require_("@babel/parser");

// MEASURED INSIDE CHATCUT, not read from documentation. bisect C rendered
// `typeof X` for each of these and every one came back defined.
export const CHATCUT_GLOBALS = new Set([
  "AbsoluteFill", "interpolate", "spring", "Easing", "interpolateColors",
  "Img", "continueRender", "delayRender", "Sequence", "random", "staticFile",
  "React", "useCurrentFrame", "useVideoConfig",
]);

const JS_GLOBALS = new Set([
  "Math", "JSON", "Object", "Array", "String", "Number", "Boolean", "Date",
  "RegExp", "Map", "Set", "WeakMap", "WeakSet", "Promise", "Symbol", "Error",
  "TypeError", "RangeError", "Infinity", "NaN", "undefined", "isNaN",
  "isFinite", "parseInt", "parseFloat", "encodeURIComponent",
  "decodeURIComponent", "Intl", "BigInt", "console", "structuredClone",
  "arguments", "globalThis",
]);

export function freeIdentifiers(code) {
  const ast = parse(code, {
    sourceType: "script",
    plugins: ["jsx"],
    errorRecovery: false,
  });
  // One walk, tracking a scope chain. Declarations are hoisted per function
  // scope for `var`/function and per block for let/const/class — but for THIS
  // question (is the name declared anywhere it could be seen?) a single
  // collect-then-compare pass is both simpler and safe in the conservative
  // direction: it can only UNDER-report, never invent a missing name.
  const declared = new Set();
  const read = new Map();                       // name -> first line

  const declare = (node) => {
    if (!node) return;
    switch (node.type) {
      case "Identifier": declared.add(node.name); break;
      case "ObjectPattern":
        for (const p of node.properties)
          declare(p.type === "RestElement" ? p.argument : p.value);
        break;
      case "ArrayPattern":
        for (const el of node.elements) declare(el);
        break;
      case "AssignmentPattern": declare(node.left); break;
      case "RestElement": declare(node.argument); break;
      default: break;
    }
  };

  const walk = (node, parent) => {
    if (!node || typeof node.type !== "string") return;
    switch (node.type) {
      case "VariableDeclarator": declare(node.id); break;
      case "FunctionDeclaration":
      case "FunctionExpression":
      case "ArrowFunctionExpression":
        if (node.id) declared.add(node.id.name);
        for (const p of node.params) declare(p);
        break;
      case "ClassDeclaration":
      case "ClassExpression":
        if (node.id) declared.add(node.id.name);
        break;
      case "CatchClause": declare(node.param); break;
      case "Identifier": {
        // a read, not a write target or a property name
        const isMemberProp = parent && parent.type === "MemberExpression"
          && parent.property === node && !parent.computed;
        const isObjKey = parent && parent.type === "ObjectProperty"
          && parent.key === node && !parent.computed;
        const isJsxAttr = parent && parent.type === "JSXAttribute";
        if (!isMemberProp && !isObjKey && !isJsxAttr && !read.has(node.name))
          read.set(node.name, node.loc ? node.loc.start.line : 0);
        break;
      }
      case "JSXIdentifier": {
        // <Foo/> reads Foo; <div/> does not. JSX lowercases are intrinsics.
        const isElementName = parent
          && (parent.type === "JSXOpeningElement"
              || parent.type === "JSXClosingElement")
          && parent.name === node;
        if (isElementName && /^[A-Z]/.test(node.name) && !read.has(node.name))
          read.set(node.name, node.loc ? node.loc.start.line : 0);
        break;
      }
      default: break;
    }
    for (const k of Object.keys(node)) {
      if (k === "loc" || k === "leadingComments" || k === "trailingComments")
        continue;
      const v = node[k];
      if (Array.isArray(v)) { for (const c of v) walk(c, node); }
      else if (v && typeof v.type === "string") walk(v, node);
    }
  };
  walk(ast, null);

  const free = [];
  for (const [name, line] of read) {
    if (declared.has(name)) continue;
    if (CHATCUT_GLOBALS.has(name)) continue;
    if (JS_GLOBALS.has(name)) continue;
    free.push({ name, line });
  }
  return free.sort((a, b) => a.line - b.line);
}



// ── USED BEFORE DECLARED ──────────────────────────────────────────────────
// The second question the remote validator asks and nothing local did.
// ChatCut flags a name mentioned by a statement that appears BEFORE the
// statement declaring it — even when the mention is inside a function body
// that could not run until later. That is stricter than JavaScript, and it is
// the rule that refused IMessageBubble's three helpers, so it is the rule to
// check against.
function stmtReads(st) {
  const out = new Set();
  const walk = (node, parent) => {
    if (!node || typeof node.type !== "string") return;
    if (node.type === "Identifier") {
      const isMemberProp = parent && parent.type === "MemberExpression"
        && parent.property === node && !parent.computed;
      const isObjKey = parent
        && (parent.type === "ObjectProperty" || parent.type === "ObjectMethod")
        && parent.key === node && !parent.computed;
      const isJsxAttr = parent && parent.type === "JSXAttribute";
      if (!isMemberProp && !isObjKey && !isJsxAttr) out.add(node.name);
    }
    if (node.type === "JSXIdentifier" && parent
        && (parent.type === "JSXOpeningElement"
            || parent.type === "JSXClosingElement")
        && parent.name === node && /^[A-Z]/.test(node.name))
      out.add(node.name);
    for (const k of Object.keys(node)) {
      if (k === "loc") continue;
      const v = node[k];
      if (Array.isArray(v)) { for (const c of v) walk(c, node); }
      else if (v && typeof v.type === "string") walk(v, node);
    }
  };
  walk(st, null);
  return out;
}

export function usedBeforeDeclared(code) {
  const ast = parse(code, { sourceType: "script", plugins: ["jsx"] });
  // LOOK INSIDE `Component`, NOT AT THE FILE. The wrapped blob has exactly ONE
  // top-level statement by contract — `const Component = ({item}) => {...}` —
  // so scanning `program.body` finds one node, zero cross-statement edges, and
  // reports a clean [] for a file ChatCut refuses. It did exactly that for
  // StatCard's `MG_POSITION_CONFIG`: the check written to make this class
  // impossible passed the next instance of the class, because it was asking
  // about the wrong scope. The statements that matter are the ones the wrap
  // moved INTO the function body.
  let stmts = ast.program.body;
  if (stmts.length === 1) {
    const d = stmts[0];
    const init = d.type === "VariableDeclaration" && d.declarations[0]
      ? d.declarations[0].init : null;
    if (init && (init.type === "ArrowFunctionExpression"
                 || init.type === "FunctionExpression")
        && init.body && init.body.type === "BlockStatement")
      stmts = init.body.body;
  }
  const declaredAt = new Map();
  stmts.forEach((st, i) => {
    const push = (n) => { if (!declaredAt.has(n)) declaredAt.set(n, i); };
    if (st.type === "FunctionDeclaration" && st.id) push(st.id.name);
    if (st.type === "ClassDeclaration" && st.id) push(st.id.name);
    if (st.type === "VariableDeclaration")
      for (const d of st.declarations)
        if (d.id && d.id.type === "Identifier") push(d.id.name);
  });
  const bad = [];
  stmts.forEach((st, i) => {
    // READS FROM THE AST, NOT TOKENS. The token version matched inside STRING
    // LITERALS: `resolveMGPosition({...}, undefined, "StatCard")` counted as a
    // read of the component StatCard, declared far below, and the scan
    // reported a violation that was never there. Same mistake as the sort's
    // object-key edge, one file along — twice in one session, both from
    // treating source text as if it were syntax.
    const own = new Set();
    if (st.type === "VariableDeclaration")
      for (const d of st.declarations)
        if (d.id && d.id.type === "Identifier") own.add(d.id.name);
    if (st.type === "FunctionDeclaration" && st.id) own.add(st.id.name);
    for (const n of stmtReads(st)) {
      if (own.has(n)) continue;
      const j = declaredAt.get(n);
      if (j !== undefined && j > i && !bad.some((b) => b.name === n))
        bad.push({ name: n, usedAtStatement: i, declaredAtStatement: j });
    }
  });
  return bad;
}

if (process.argv[1] && process.argv[1].endsWith("free_identifiers.mjs")) {
  const code = readFileSync(process.argv[2], "utf8");
  // BOTH QUESTIONS THE REMOTE VALIDATOR ASKS, in one answer. A name that does
  // not exist and a name that exists too late are the same refusal from
  // ChatCut and were the same word — ABSENT — in the render check.
  const free = freeIdentifiers(code);
  const late = usedBeforeDeclared(code).map((b) => ({
    name: b.name, line: 0,
    why: `declared at statement ${b.declaredAtStatement}, used at ${b.usedAtStatement}`,
  }));
  const all = [...free, ...late];
  console.log(JSON.stringify(all));
  process.exit(all.length ? 1 : 0);
}
