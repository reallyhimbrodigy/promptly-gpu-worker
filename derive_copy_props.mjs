// WHICH PROPS ARE VIEWER-READ COPY — derived from the BODY, by AST.
//
// A SECOND, INDEPENDENT DERIVATION. B1 derives his from the REGISTRY: every
// registered defaultValue, minus empty ones, minus style-valued ones filtered
// by their value. This one never looks at a default. It asks the only question
// that decides the matter: IS THIS VALUE RENDERED AS TEXT THE VIEWER READS —
// a JSXExpressionContainer whose parent is a JSXElement, i.e. a text child.
//
// Two derivations agreeing is the strongest evidence available that a rule is
// real and neither was invented; a disagreement says which one is wrong.
//
// AND IT HAS TO BE AN AST. My first two passes were regexes and both were
// wrong in the same direction: `>{showFog ? <div…` reads as a text child, and
// so does `{ anchor, offsetX, offsetY, scale }` once a nested style brace
// closes in the right place. They reported booleans, offsets and colours as
// copy. Only the parse distinguishes a child from an argument.
import { parse } from "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/@babel/parser/lib/index.js";
import fs from "node:fs";
import path from "node:path";

const LIVE = ["PlainText","CaptionMatch","LowerThird","QuoteCard","TornPaper","StickyNotes",
              "EmojiCard","StatCard","Stamp","PillCluster","RankedList","Reticle"];
const reg = JSON.parse(fs.readFileSync("chatcut_registry_baked.json", "utf8")).components;

function bodyFor(n) {
  if (reg[n]) return { code: reg[n].code, keys: new Set(reg[n].properties.map((p) => p.key)), from: "baked registry" };
  for (const d of ["port/build", "port/bodies"]) {
    const p = path.join(d, `${n}.jsx`);
    if (fs.existsSync(p)) {
      const code = fs.readFileSync(p, "utf8");
      const keys = new Set([...code.matchAll(/props\??\.([A-Za-z_$][\w$]*)/g)].map((m) => m[1]));
      return { code, keys, from: d };
    }
  }
  return null;
}

// Walk, tracking parents, and collect the expression of every JSX text child.
function textChildExpressions(ast) {
  const out = [];
  const seen = new Set();
  (function walk(node, parent) {
    if (!node || typeof node !== "object" || seen.has(node)) return;
    if (Array.isArray(node)) { for (const c of node) walk(c, parent); return; }
    if (!node.type) return;
    seen.add(node);
    if (node.type === "JSXExpressionContainer" && parent
        && (parent.type === "JSXElement" || parent.type === "JSXFragment")) {
      out.push(node.expression);
    }
    for (const k of Object.keys(node)) {
      if (k === "loc" || k === "leadingComments" || k === "trailingComments") continue;
      walk(node[k], node);
    }
  })(ast.program, null);
  return out;
}

// From a child expression, the NAMES whose value the viewer reads. A ternary
// contributes both branches; a ?? contributes its left side; a member
// expression contributes `obj.field`. A logical && is a GUARD, not copy — its
// left side decides whether to draw, and only its right side is drawn.
function namesIn(e, acc = []) {
  if (!e) return acc;
  switch (e.type) {
    case "Identifier": acc.push(e.name); break;
    case "MemberExpression":
      if (!e.computed && e.object.type === "Identifier" && e.property.type === "Identifier")
        acc.push(`${e.object.name}.${e.property.name}`);
      break;
    case "ConditionalExpression": namesIn(e.consequent, acc); namesIn(e.alternate, acc); break;
    case "LogicalExpression":
      if (e.operator === "??" || e.operator === "||") { namesIn(e.left, acc); namesIn(e.right, acc); }
      else namesIn(e.right, acc);   // && : the left is the guard
      break;
    case "TemplateLiteral": for (const x of e.expressions) namesIn(x, acc); break;
    case "CallExpression": for (const a of e.arguments) namesIn(a, acc); break;
    // STRING CONCATENATION IS STILL COPY. QuoteCard draws its author as
    // {"\u2014 " + attribution} and the first version of this file MISSED IT
    // entirely — the prop most likely to carry a real person's name, dropped
    // because it was glued to an em dash.
    case "BinaryExpression": namesIn(e.left, acc); namesIn(e.right, acc); break;
    case "UnaryExpression": namesIn(e.argument, acc); break;
    default: break;
  }
  return acc;
}

const result = {};
for (const n of LIVE) {
  const b = bodyFor(n);
  if (!b) { result[n] = { error: "no body found" }; continue; }
  let ast;
  try {
    ast = parse(b.code, { sourceType: "module", plugins: ["jsx"], errorRecovery: true });
  } catch (err) { result[n] = { error: `parse failed: ${err.message}` }; continue; }
  const names = new Set();
  for (const e of textChildExpressions(ast)) for (const nm of namesIn(e)) names.add(nm);
  // A LOCAL COUNTS WHEN IT TRACES BACK TO A PROP, THROUGH ANY NUMBER OF HOPS.
  // One hop was not enough and the misses were the interesting ones:
  // EmojiCard's captionText is the TRUNCATED caption (captionRaw <- prop) and
  // PillCluster's `tag` is a map parameter over rendered <- tags.slice(0,12)
  // <- prop. Both are the text a viewer reads; both were invisible to a
  // same-line `props.` test. "One hop of indirection is still scope" is
  // already a standing rule here — this is the third place it has applied.
  const rhs = new Map();
  for (const m of b.code.matchAll(/(?:const|var|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;]*);/g)) {
    rhs.set(m[1], new Set([...m[2].matchAll(/([A-Za-z_$][\w$]*)/g)].map((x) => x[1])));
  }
  // Map parameters: `X.map((p, i) => …)` makes p an element of X.
  for (const m of b.code.matchAll(/([A-Za-z_$][\w$]*)\s*\.map\(\s*\(?\s*([A-Za-z_$][\w$]*)/g)) {
    const cur = rhs.get(m[2]) || new Set();
    cur.add(m[1]);
    rhs.set(m[2], cur);
  }
  const tracesToProp = (nm, seen = new Set()) => {
    if (b.keys.has(nm)) return true;
    if (seen.has(nm)) return false;          // a cycle is not a path to a prop
    seen.add(nm);
    const r = rhs.get(nm);
    if (!r) return false;
    if (r.has("props")) return true;
    for (const x of r) if (tracesToProp(x, seen)) return true;
    return false;
  };
  const fromProp = new Set();
  for (const nm of names) {
    if (nm.includes(".")) continue;
    if (tracesToProp(nm)) fromProp.add(nm);
  }
  // SPLIT THE ANSWER, because the two halves are checked differently. A
  // REGISTERED PROP can be overridden at placement, so it is what a
  // sample-text check tests. A DERIVED LOCAL or BAKED item is drawn and
  // cannot be overridden — PillCluster's tags and RankedList's items are
  // literals in the code, so their copy is fixed at registration and a
  // placement cannot change it. Reporting them together would make a
  // sample-text check look like it covers text nobody can pass in.
  const props_ = [...fromProp].filter((x) => b.keys.has(x)).sort();
  const derived = [...fromProp].filter((x) => !b.keys.has(x)).sort();
  result[n] = {
    body_from: b.from,
    copy_props: props_,
    copy_derived_or_baked: derived,
    copy: [...fromProp].sort(),
    item_fields: [...names].filter((x) => x.includes(".")).sort(),
    rendered_but_not_a_prop: [...names].filter((x) => !fromProp.has(x) && !x.includes(".")).sort(),
  };
}
console.log("%s", "component".padEnd(13) + "COPY PROPS (overridable)".padEnd(34) + "DERIVED / BAKED".padEnd(30) + "item fields");
for (const n of LIVE) {
  const r = result[n];
  if (r.error) { console.log(n.padEnd(13) + r.error); continue; }
  console.log(n.padEnd(13) + (r.copy_props.join(", ") || "-").padEnd(34)
    + (r.copy_derived_or_baked.join(", ") || "-").padEnd(30)
    + (r.item_fields.join(", ") || "-"));
}
fs.writeFileSync("measured/COPY_PROPS.json", JSON.stringify(result, null, 1));
