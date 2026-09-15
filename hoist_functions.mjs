// Move every top-level function-valued declaration above the statements that
// use it. Nothing else moves, and no statement is re-printed — only its
// original source slice is repositioned.
//
// WHY. ChatCut refused IMessageBubble with
//
//   Undefined identifier "TypingIndicatorBubble" / "MessageBubble" / "Tail"
//
// All three ARE declared in the blob — after the component that renders them.
// In the original Remotion module that is legal and ordinary: those are
// module-level `var`s, all assigned before React ever calls anything. The wrap
// then puts the whole module body INSIDE `Component`, and ChatCut's validator
// reads the result as a lexical scope where a name is used before it exists.
// (At runtime it would in fact work — the assignments run before the final
// return — which is exactly why nothing local caught it.)
//
// SAFE BECAUSE FUNCTION BODIES DO NOT EVALUATE AT DEFINITION. A hoisted
// component can reference a constant still declared below it; the constant is
// only read when the component is CALLED, which is after the whole body has
// run. Parameter defaults are the same — evaluated per call, not per
// definition. So the relative order of everything else is preserved exactly.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require_ = createRequire(
  "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/x.js");
const { parse } = require_("@babel/parser");

const FN = new Set(["ArrowFunctionExpression", "FunctionExpression"]);

// A BLANKET HOIST TRADES ONE USE-BEFORE-DECLARE FOR ANOTHER. The first version
// moved every function-valued declaration to the very top, which fixed
// IMessageBubble's three helpers and immediately broke EditorialQuote and
// MouseDrag: `var useSmoothGraphics = () => __useCtx(SmoothGraphicsContext)`
// went above `var SmoothGraphicsContext = __ctx(false)`, and the validator
// flagged the constant instead. Two components recovered, two lost, same
// error class — the fix has to be an ORDERING, not a direction.
//
// So: a stable topological sort of the top-level statements. A statement that
// READS a name another statement DECLARES is emitted after it; everything else
// keeps its original position. A cycle (mutual recursion) keeps source order,
// which is what the module already relied on.
function namesDeclared(st) {
  const out = [];
  if (st.type === "FunctionDeclaration" && st.id) out.push(st.id.name);
  if (st.type === "ClassDeclaration" && st.id) out.push(st.id.name);
  if (st.type === "VariableDeclaration")
    for (const d of st.declarations)
      if (d.id && d.id.type === "Identifier") out.push(d.id.name);
  return out;
}

function namesRead(st) {
  // GENUINE READS, FROM THE AST. The first version matched identifier-shaped
  // TOKENS in the statement's source and called the over-reporting harmless:
  // "an edge that was already true of the original order". It was not.
  // `var MG_POSITION_CONFIG = { Notification: { topExempt: true } }` has an
  // object KEY named Notification, and a component called Notification is
  // declared further down the file — so the token scan invented a dependency
  // on a LATER statement and sorted the constant below its own consumer.
  // StatCard, IMessageBubble and ten others were refused for exactly that.
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

export function hoistFunctions(code) {
  const ast = parse(code, { sourceType: "script", plugins: ["jsx"] });
  const stmts = ast.program.body;
  const declaredBy = new Map();                 // name -> statement index
  stmts.forEach((st, i) => {
    for (const n of namesDeclared(st)) if (!declaredBy.has(n)) declaredBy.set(n, i);
  });
  const isFn = (st) =>
    st.type === "FunctionDeclaration"
    || (st.type === "VariableDeclaration" && st.declarations.length === 1
        && st.declarations[0].init && FN.has(st.declarations[0].init.type));

  // Edges: i must come after j when statement i reads a name declared by j.
  // Only function-valued declarations are allowed to MOVE; everything else is
  // pinned, so a constant never migrates past code with side effects.
  const deps = stmts.map((st, i) => {
    const out = new Set();
    for (const n of namesRead(st)) {
      const j = declaredBy.get(n);
      if (j !== undefined && j !== i) out.add(j);
    }
    return out;
  });

  const order = [], done = new Set(), inProgress = new Set();
  const visit = (i) => {
    if (done.has(i) || inProgress.has(i)) return;   // cycle -> source order
    inProgress.add(i);
    for (const j of [...deps[i]].sort((a, b) => a - b))
      if (isFn(stmts[j]) || j < i) visit(j);
    inProgress.delete(i);
    done.add(i);
    order.push(i);
  };
  for (let i = 0; i < stmts.length; i++) visit(i);

  const moved = order.filter((v, k) => v !== k).length;
  const out = order.map((i) => code.slice(stmts[i].start, stmts[i].end))
    .join("\n");
  return { code: out, moved };
}

if (process.argv[1] && process.argv[1].endsWith("hoist_functions.mjs")) {
  const [, , inPath, outPath] = process.argv;
  const { code, moved } = hoistFunctions(readFileSync(inPath, "utf8"));
  if (outPath) writeFileSync(outPath, code);
  console.log(JSON.stringify({ moved }));
}
