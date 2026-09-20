import { classify } from "./registered_diff.mjs";
let fail = 0;
const leg = (name, got, want) => {
  const ok = got === want;
  if (!ok) fail++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}  ::  got ${got}, want ${want}`);
};
const BASE = [
  'const Component = ({ item }) => {',
  '  const props = (item && item.props) || {};',
  '  const GhostTile = ({ n }) => <div key={n} />;',
  '  const TileContainer = ({ from, left, top, w, h }) => <div style={{ left, top }} />;',
  '  const scale = Number(props.scale);',
  '  return <div><GhostTile n={1} /><TileContainer from={0} left={0} top={0} w={1} h={1} /></div>;',
  '};',
].join("\n");
const sub = (s, a, b) => { if (!s.includes(a)) throw new Error("anchor gone: " + a); return s.replace(a, b); };

// 1. GREEN LEG — the real observed rewrite, on two nested components at once.
let reg = sub(BASE, '({ n })', '({ n, item })');
reg = sub(reg, '({ from, left, top, w, h })', '({ from, left, top, w, h, item })');
let r = classify(BASE, reg);
leg("the real two-component injection is STRIPPED", r.verdict, "STRIPPED");
leg("  ...and is attributed to injection, not to a fallback", `${r.explained.injection}/${r.explained.fallback}`, "2/0");

// 2. an injection that is USED is a behavioural change, not a documented rewrite
let used = sub(BASE, '({ n })', '({ n, item })');
used = sub(used, '<div key={n} />', '<div key={n} title={item} />');
leg("an injected item that is READ is DIVERGED", classify(BASE, used).verdict, "DIVERGED");

// 3. a DIFFERENT parameter appended is not the documented rewrite
leg("a different appended parameter is DIVERGED",
    classify(BASE, sub(BASE, '({ n })', '({ n, frame })')).verdict, "DIVERGED");

// 4. item added to the TOP-LEVEL component's own call site, not a nested pattern
leg("an item added outside a destructuring pattern is DIVERGED",
    classify(BASE, sub(BASE, '<GhostTile n={1} />', '<GhostTile n={1} item={2} />')).verdict, "DIVERGED");

// 5. a real fallback strip still reads STRIPPED and is attributed to fallback
r = classify(BASE.replace('Number(props.scale);', 'Number(props.scale) || 1.3;'), BASE);
leg("a fallback strip is STRIPPED and attributed to fallback", `${r.verdict}:${r.explained.fallback}`, "STRIPPED:1");

// 6. injection PLUS an unrelated edit is still DIVERGED
let both = sub(BASE, '({ n })', '({ n, item })');
both = sub(both, 'left, top', 'top, left');
leg("injection plus an unrelated edit is DIVERGED", classify(BASE, both).verdict, "DIVERGED");

// 7. identical is untouched
leg("identical source and registered is IDENTICAL", classify(BASE, BASE).verdict, "IDENTICAL");
// ---- 9. THE CLI, END TO END. ------------------------------------------------
// Legs 1-8 call classify() with two strings this file builds, so NONE of them
// touches the CLI's own source-side read — and that is exactly where the defect
// was: it read the WHOLE .jsx, doc header and all, while ChatCut stores only
// the component, so every real pair came back DIVERGED with ~31 unexplained
// removals. An eight-leg proof that never runs the shipped entrypoint is a
// proof of the library, not of the tool.
import { execFileSync } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join as pjoin } from "node:path";
import { componentOnly } from "./registered_diff.mjs";

const dir = mkdtempSync(pjoin(tmpdir(), "b2-regdiff-"));
const HEADER = "/* A doc header of the kind every ported body carries.\n * It is never sent to ChatCut.\n */\n";
const cliSrc = componentOnly(BASE);
const cliReg = sub(cliSrc, "({ n })", "({ n, item })");
writeFileSync(pjoin(dir, "reg.jsx"), cliReg);

// Stand in for port/build/<Name>.jsx: header + component, as the real files are.
const fakeBuild = pjoin(process.cwd(), "port", "build", "__RedProofProbe.jsx");
writeFileSync(fakeBuild, HEADER + cliSrc);
let cliOut = "", cliCode = 0;
try {
  cliOut = execFileSync("node", ["port/registered_diff.mjs", "__RedProofProbe", pjoin(dir, "reg.jsx")],
                        { encoding: "utf8" });
} catch (e) { cliOut = (e.stdout || "") + (e.stderr || ""); cliCode = e.status; }
const parsed = (() => { try { return JSON.parse(cliOut); } catch { return {}; } })();
leg("the CLI strips the doc header before comparing", parsed.verdict, "STRIPPED");
leg("  ...and the CLI exits 0 on an injection-only difference", String(cliCode), "0");
leg("  ...and attributes it to the injection", `${parsed.explained && parsed.explained.injection}`, "1");
try { execFileSync("rm", ["-f", fakeBuild]); } catch {}

console.log(fail ? `\n${fail} LEG(S) FAILED` : "\nall 11 legs green");
process.exit(fail ? 1 : 0);
