// no-use-before-define, the SCOPE-ANALYSIS way — {functions:false, classes:false,
// variables:false} in eslint's vocabulary.
//
// WHY NOT A REGEX. Builder 1 wrote this rule twice with brace-counting and both
// versions refused 37 of 37 bodies ChatCut had ACCEPTED. Deciding whether a
// reference is deferred needs to know WHICH FUNCTION ENCLOSES IT and whether
// that function body runs before the declaration. That is a scope analysis, and
// eslint-scope is the thing that does it — the same library eslint's own rule
// stands on.
//
// WHAT IT REPORTS: a reference to a let/const/class binding that appears BEFORE
// the declaration IN THE SAME FUNCTION. That is the temporal dead zone, and it
// is what ChatCut's validator refuses.
// WHAT IT IGNORES: a reference from a NESTED function to a later outer
// declaration. Legal and ubiquitous — every callback in these bodies does it —
// and flagging it is precisely how the brace-counting versions convicted 37
// correct components.
import { parse } from "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/@babel/parser/lib/index.js";
import eslintScope from "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion/node_modules/eslint-scope/lib/index.js";
import fs from "node:fs";

export function findUseBeforeDefine(code, file) {
  let ast;
  try {
    ast = parse(code, { sourceType: "script", errorRecovery: false,
      plugins: ["jsx", "estree"], ranges: true });
  } catch (e) {
    // DO NOT LOOSEN THE RULE ON A PARSE FAILURE. Report exactly what it choked
    // on: an unparseable body is an UNKNOWN, never a pass.
    return { state: "PARSE_ERROR", detail: `${e.message}`, findings: [] };
  }
  let manager;
  try {
    manager = eslintScope.analyze(ast.program || ast, {
      ecmaVersion: 2022, sourceType: "script", ignoreEval: true,
      nodejsScope: false, childVisitorKeys: null, fallback: "iteration" });
  } catch (e) {
    return { state: "SCOPE_ERROR", detail: `${e.message}`, findings: [] };
  }
  const findings = [];
  const walk = (scope) => {
    for (const ref of scope.references) {
      const v = ref.resolved;
      if (!v || !v.defs.length) continue;
      const def = v.defs[0];
      const kind = def.parent && def.parent.kind;            // let / const / var
      const isTdz = kind === "let" || kind === "const" || def.type === "ClassName";
      if (!isTdz) continue;                                   // var hoists; functions:false
      const declStart = (def.name && def.name.range) ? def.name.range[0] : null;
      const useStart = ref.identifier.range ? ref.identifier.range[0] : null;
      if (declStart === null || useStart === null) continue;
      if (useStart >= declStart) continue;                    // declared first: fine
      // variables:false — a reference from a NESTED function to a later outer
      // declaration is deferred and legal. Same variableScope means same
      // function, which is the case that actually throws.
      if (ref.from.variableScope !== v.scope.variableScope) continue;
      const line = code.slice(0, useStart).split("\n").length;
      const declLine = code.slice(0, declStart).split("\n").length;
      findings.push({ name: v.name, useLine: line, declLine, kind });
    }
    scope.childScopes.forEach(walk);
  };
  manager.scopes.filter((s) => s.type === "global").forEach(walk);
  return { state: findings.length ? "USE_BEFORE_DEFINE" : "CLEAN",
           detail: "", findings };
}

if (process.argv[1] && process.argv[1].endsWith("check_use_before_define.mjs")) {
  const files = process.argv.slice(2);
  let bad = 0;
  for (const f of files) {
    const r = findUseBeforeDefine(fs.readFileSync(f, "utf8"), f);
    if (r.state === "CLEAN") continue;
    bad++;
    console.log(`${f}: ${r.state} ${r.detail}`);
    for (const x of r.findings) {
      console.log(`    '${x.name}' (${x.kind}) used line ${x.useLine}, declared line ${x.declLine}`);
    }
  }
  console.log(`${files.length - bad}/${files.length} clean`);
  process.exit(bad ? 1 : 0);
}
