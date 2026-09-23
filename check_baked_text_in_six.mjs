// Does any VIEWER-VISIBLE text in these six come from anywhere but a property?
// Read from the REGISTERED code (port/build for these six — they are not in
// chatcut_registry_baked.json), by AST, because a regex cannot tell a text
// child from an argument and both of my regex attempts got that wrong.
import { parse } from "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/@babel/parser/lib/index.js";
import fs from "node:fs";

const SIX = ["CaptionMatch", "EmojiCard", "PlainText", "QuoteCard", "Stamp", "TornPaper"];

function textChildren(ast) {
  const out = []; const seen = new Set();
  (function walk(node, parent) {
    if (!node || typeof node !== "object" || seen.has(node)) return;
    if (Array.isArray(node)) { for (const c of node) walk(c, parent); return; }
    if (!node.type) return; seen.add(node);
    const inJsx = parent && (parent.type === "JSXElement" || parent.type === "JSXFragment");
    if (inJsx && node.type === "JSXExpressionContainer") out.push({ kind: "expr", node: node.expression });
    if (inJsx && node.type === "JSXText" && node.value.trim()) out.push({ kind: "literal", node });
    for (const k of Object.keys(node)) {
      if (k === "loc" || k === "leadingComments" || k === "trailingComments") continue;
      walk(node[k], node);
    }
  })(ast.program, null);
  return out;
}

// Any string literal that reaches the screen as words. A style value is never
// a text child, so position already excludes it.
function literals(e, acc = []) {
  if (!e) return acc;
  if (e.type === "StringLiteral") { if (/[A-Za-z]{2,}/.test(e.value)) acc.push(e.value); return acc; }
  if (e.type === "TemplateLiteral") {
    for (const q of e.quasis) if (/[A-Za-z]{2,}/.test(q.value.raw)) acc.push(q.value.raw);
    for (const x of e.expressions) literals(x, acc); return acc;
  }
  // NOT `object`. `styles[captionStyle]` draws the VALUE it looks up, never the
  // table — and following the object harvested every key of CaptionMatch's
  // style map ("CleanCut", "Cove", "Gadzhi"...) and reported them as baked
  // copy. That would have pulled a clean component off the run-two menu on a
  // finding about a lookup table. The container is not the content.
  for (const k of ["left", "right", "consequent", "alternate", "argument"]) if (e[k]) literals(e[k], acc);
  if (e.type === "CallExpression") for (const a of e.arguments) literals(a, acc);
  return acc;
}

const rows = [];
for (const n of SIX) {
  const p = `port/build/${n}.jsx`;
  if (!fs.existsSync(p)) { rows.push([n, "NO REGISTERED BODY FOUND", ""]); continue; }
  const code = fs.readFileSync(p, "utf8");
  const ast = parse(code, { sourceType: "module", plugins: ["jsx"], errorRecovery: true });
  const found = new Set();
  for (const c of textChildren(ast)) {
    if (c.kind === "literal") found.add(c.node.value.trim());
    else for (const s of literals(c.node)) found.add(s);
  }
  // A baked ARRAY/OBJECT literal assigned into the mapped props.
  const bakedArrays = [...code.matchAll(/^\s{4}(\w+):\s*(\[[\s\S]*?\]|\{[\s\S]*?\}),$/gm)]
    .filter((m) => /["'][^"']*[A-Za-z]{2,}[^"']*["']/.test(m[2])).map((m) => m[1]);
  rows.push([n, [...found], bakedArrays]);
}
console.log("%s", "component".padEnd(14) + "ANSWER".padEnd(8) + "viewer-visible text not from a property");
for (const [n, lits, baked] of rows) {
  const bad = (Array.isArray(lits) ? lits : []).concat(baked || []);
  const yes = bad.length > 0;
  console.log(n.padEnd(14) + (yes ? "YES" : "no").padEnd(8)
    + (yes ? bad.map((x) => JSON.stringify(x)).join(", ").slice(0, 80) : "—"));
}
