/**
 * THE SOURCE WE BUILT AGAINST THE CODE CHATCUT ACTUALLY REGISTERED.
 *
 * WHY THIS EXISTS (Zac, 2026-09-20). Registering a ported component returns:
 *
 *     Auto-fixed: Stripped hardcoded fallbacks from props
 *     (property system provides defaults)
 *
 * ChatCut REWRITES the code on the way in. So the blob on disk — the one the
 * emitter built, the one the hash leg guards, the one every review reads — is
 * NOT necessarily the blob that runs. Every guarantee the one-source gate gives
 * stops at the wire, and nothing downstream of it was ever checked.
 *
 * The rule that makes the check trivial: NO HARDCODED FALLBACKS IN SOURCE.
 * Defaults live in the property table and nowhere else. A component with no
 * fallbacks has nothing to strip, so ChatCut has no reason to rewrite it, and
 * the registered code must come back BYTE-IDENTICAL. Any difference at all is
 * then a finding rather than a thing to argue about.
 *
 * VERDICTS, three states and not two:
 *   IDENTICAL    registered === source. The only passing state.
 *   STRIPPED     the differences are ALL removals of a props fallback and
 *                nothing else. Reported, and FAILS — it means a fallback
 *                survived into source, which is the rule this enforces.
 *   DIVERGED     anything else. The registered code differs in a way nobody
 *                documented, which is the case this file exists to surface.
 *
 * Usage: node port/registered_diff.mjs <Name> <file-with-registered-code>
 */
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * A line that READS A PROP AND SUPPLIES A HARDCODED DEFAULT FOR IT.
 *
 * THE TEST IS THE RIGHT-HAND OPERAND, and it took two wrong versions to get
 * there — one loose in each direction, which is the shape of this whole class.
 *
 *   v1, TOO TIGHT: required the operator to follow the read directly, so
 *   `Number(props.scale) || 1.3` did not match — a closing paren sits between
 *   them, and that is the most common shape in the entire port. It reported
 *   DIVERGED on a textbook strip.
 *
 *   v2, TOO LOOSE: "reads a prop AND contains ||" flagged
 *   `props.punch === true || props.punch === "true"`, which is a boolean
 *   COERCION between two comparisons and supplies no default at all. It failed
 *   four correct components, and a gate that fails correct code is one that
 *   gets switched off.
 *
 * A fallback is `||` or `??` whose RIGHT OPERAND IS A BARE LITERAL that ends
 * the expression — that literal is the value the prop takes when absent. An OR
 * between two comparisons has a `props.` read on its right and never matches.
 * `=== undefined ?` is the ternary spelling of the same thing.
 */
export function readsPropWithFallback(line) {
  if (!/props\.[A-Za-z_]\w*/.test(line)) return false;
  if (/===\s*undefined\s*\?/.test(line)) return true;
  // || or ?? followed by a literal that CLOSES the expression.
  return /(\|\||\?\?)\s*(-?\d[\d._]*|"[^"]*"|'[^']*'|`[^`]*`|true|false|null|undefined|\{\s*\}|\[\s*\])\s*(;|,|\)|\]|\}|$)/.test(line);
}

export function sha(s) { return createHash("sha256").update(s, "utf8").digest("hex"); }

/** Longest-common-subsequence line diff — enough to classify, not to render. */
function lineDiff(a, b) {
  const A = a.split("\n"), B = b.split("\n");
  const n = A.length, m = B.length;
  // Bounded: these blobs are a few hundred lines. Refuse rather than hang.
  if (n * m > 4_000_000) throw new Error(`blobs too large to diff (${n}x${m})`);
  const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ side: "source", line: i + 1, text: A[i++] });
    else out.push({ side: "registered", line: j + 1, text: B[j++] });
  }
  while (i < n) out.push({ side: "source", line: i + 1, text: A[i++] });
  while (j < m) out.push({ side: "registered", line: j + 1, text: B[j++] });
  return out;
}

/**
 * Is `b` `a` with characters only DELETED — never added, never reordered?
 *
 * THIS IS WHY THE CHECK DOES NOT REIMPLEMENT CHATCUT'S STRIPPER. Writing a
 * second stripper to predict the expected output would be a second
 * implementation of the thing we cannot see, and it would agree with itself
 * forever — the same trap the cap emitter avoids by using Node's own stripper.
 * A removal is observable WITHOUT knowing the rule: stripping ` || 1.3` can
 * only delete characters. If anything was added, it was not a strip.
 */
export function deletionOnly(a, b) {
  let i = 0;
  for (const ch of b) {
    i = a.indexOf(ch, i);
    if (i < 0) return false;
    i += 1;
  }
  return true;
}

export function classify(source, registered) {
  if (source === registered) {
    return { verdict: "IDENTICAL", differences: 0, sha: sha(source), detail: [] };
  }
  const d = lineDiff(source, registered);
  // PAIR each removed source line that carried a fallback with an added
  // registered line that is the same line with characters only deleted. Both
  // halves of such a pair are EXPLAINED; everything else is not.
  const removed = d.filter((x) => x.side === "source");
  const added = d.filter((x) => x.side === "registered");
  const takenAdded = new Set();
  const explainedRemoved = new Set();
  for (let r = 0; r < removed.length; r++) {
    if (!readsPropWithFallback(removed[r].text)) continue;
    for (let a = 0; a < added.length; a++) {
      if (takenAdded.has(a)) continue;
      if (deletionOnly(removed[r].text, added[a].text)) {
        takenAdded.add(a); explainedRemoved.add(r); break;
      }
    }
  }
  const unexplained = removed.filter((_, r) => !explainedRemoved.has(r))
    .concat(added.filter((_, a) => !takenAdded.has(a)));
  return {
    verdict: unexplained.length === 0 ? "STRIPPED" : "DIVERGED",
    differences: d.length,
    unexplained: unexplained.length,
    sha_source: sha(source),
    sha_registered: sha(registered),
    detail: d.slice(0, 12).map((x) => `${x.side} L${x.line}: ${x.text.trim().slice(0, 80)}`),
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [name, regPath] = process.argv.slice(2);
  if (!name || !regPath) {
    console.error("usage: node port/registered_diff.mjs <Name> <registered-code-file>");
    process.exit(2);
  }
  const source = readFileSync(join(ROOT, "port", "build", name + ".jsx"), "utf8");
  const registered = readFileSync(regPath, "utf8");
  const r = classify(source, registered);
  console.log(JSON.stringify({ name, ...r }, null, 1));
  // IDENTICAL is the only pass. STRIPPED means a fallback reached source, which
  // is the defect; DIVERGED means something nobody documented.
  process.exit(r.verdict === "IDENTICAL" ? 0 : 1);
}
