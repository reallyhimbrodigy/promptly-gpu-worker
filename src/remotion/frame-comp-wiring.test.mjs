// EVERY IDENTIFIER PASSED IN JSX MUST BE BOUND — the check that would have
// caught RENDER_FATAL without spending a render.
//
// 2026-08-19: `<MotionGraphicsLayer ... sourceUrl={sourceUrl} />` was added
// inside PromptlyOverlay, which destructures its input and never bound
// sourceUrl. Nothing caught it: there is no tsc in this tree, the Python gate
// reads Python, and brand-mg-wiring reads the MG mirrors. It surfaced as
// `SymbolicateableError [ReferenceError]: sourceUrl is not defined` after a
// full image rebuild, a planning call and 196s of wall clock.
//
// Narrow on purpose: this is not a linter. It checks the ONE pattern that cost
// a render — props passed to the layers that carry the frame compositions.
import fs from "fs";

const SRC = "src/PromptlyRender.tsx";
const s = fs.readFileSync(SRC, "utf8");
let failed = 0;
const check = (name, fn) => {
  try {
    fn();
    console.log(`  ok   ${name}`);
  } catch (e) {
    failed++;
    console.log(`  FAIL ${name}\n       ${e.message}`);
  }
};

/** The component enclosing a given index, and the text before that index. */
function enclosing(idx) {
  const before = s.slice(0, idx);
  const start = Math.max(
    before.lastIndexOf("export const "),
    before.lastIndexOf("\nconst "),
  );
  return { name: s.slice(start, s.indexOf("=", start)).trim(), body: s.slice(start, idx) };
}

for (const layer of ["MotionGraphicsLayer", "MotionGraphicRenderer"]) {
  const re = new RegExp(`<${layer}\\b[^/>]*`, "g");
  let m;
  while ((m = re.exec(s))) {
    const call = m[0];
    const { name, body } = enclosing(m.index);
    for (const p of call.matchAll(/(\w+)=\{(\w+)\}/g)) {
      const ident = p[2];
      check(`${layer}: \`${ident}\` is bound in ${name.slice(0, 44)}`, () => {
        const bound = new RegExp(`\\b${ident}\\b`).test(body);
        if (!bound) {
          throw new Error(
            `${ident} is passed but never bound in the enclosing component — ` +
            `this renders as ReferenceError: ${ident} is not defined, and only ` +
            `at render time (RENDER_FATAL, 2026-08-19)`);
        }
      });
    }
  }
}

console.log(failed ? `\n${failed} FAILURE(S)` : "\nframe-comp wiring: all bound");
process.exit(failed ? 1 : 0);
