#!/usr/bin/env python3
"""SMOKE: the round collector must read the producer's contract verdict verbatim.

MEASURED, round 23: the end-of-run escalation fired 12 times across 4 of 5
fixtures — spec_shortfall_unresolved, a member of CONTRACT_FAILURES whose own
comment says "the reliability gate refuses a round carrying any of these" — and
the round scored GREEN=True, "all five green".

The collector did not read a violations list. It scraped the log for a HARDCODED
ENUM of five kinds. CONTRACT_FAILURES has seven. The two it did not know were
invisible, and invisible looked exactly like clean. Adding a contract failure was
therefore a no-op, silently — the same shape as wrong_resolution annotating four
green rounds, and as spec_shortfall being popped by the check that only warns.

The categorical fix is that the READER OWNS NO VOCABULARY: the producer prints
the verdict, the reader takes it. This smoke pins that, and pins the two ways it
could regress — a re-introduced enum, and absence rendered as success.
"""
import re, subprocess, sys, tempfile, os, pathlib

RUNNER = pathlib.Path(__file__).with_name("run_round.sh").read_text()

fails = []
def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))

# ── 1. THE READER DECLARES NO KINDS OF ITS OWN ────────────────────────────
# Any contract-failure name hardcoded on the reading side is vocabulary that
# can fall behind the producer. The only mentions allowed are in comments.
code = "\n".join(l for l in RUNNER.split("\n") if not l.strip().startswith("#"))
for kind in ("wrong_resolution", "no_audio_stream", "output_has_no_speech",
             "no_output", "speech_loss_severe", "spec_shortfall_unresolved"):
    check(f"the collector does not hardcode `{kind}`",
          kind not in code,
          "a reader that re-declares the producer's vocabulary drifts from it")

# ── 2. IT PARSES THE PRODUCER'S LINE ──────────────────────────────────────
check("the collector reads the CONTRACT VIOLATIONS line",
      "CONTRACT VIOLATIONS:" in RUNNER)

# ── 3. THE PARSE ITSELF, on the real shapes ───────────────────────────────
m = re.search(r'cvm = re\.search\(r"([^"]+)"', RUNNER)
check("the verdict regex is extractable", m is not None)
if m:
    rx = m.group(1).encode().decode("unicode_escape")
    dirty = ("  SPEC EXITS      : accepted=—  outstanding=['text']\n"
             "  CONTRACT VIOLATIONS: 2\n"
             "     - spec_shortfall_unresolved: built with a shortfall\n"
             "     - wrong_resolution: 540x960\n"
             "  WALL BY STAGE   : 40.0s total\n")
    clean = "  CONTRACT VIOLATIONS: 0  — none\n  WALL BY STAGE   : 40.0s total\n"

    g = re.search(rx, dirty)
    check("a dirty run's violations are SEEN", g is not None)
    if g:
        got = [l.strip()[2:] for l in g.group(2).split("\n") if l.strip().startswith("- ")]
        check("both violations parsed", len(got) == 2, str(got))
        check("the escalation kind survives the parse",
              any("spec_shortfall_unresolved" in x for x in got), str(got))
        check("the count matches the list (no silent truncation)",
              len(got) == int(g.group(1)), f"{g.group(1)} vs {len(got)}")

    g2 = re.search(rx, clean)
    check("a clean run parses as zero", g2 is not None and int(g2.group(1)) == 0)
    if g2:
        got2 = [l for l in g2.group(2).split("\n") if l.strip().startswith("- ")]
        check("a clean run yields no violations", not got2, str(got2))

# ── 4. ABSENCE IS NOT SUCCESS ─────────────────────────────────────────────
check("a run with NO verdict line is not treated as clean",
      "no_contract_verdict" in RUNNER,
      "a missing line means the run never reached its summary — not that it passed")

if fails:
    print(f"COLLECTOR-VERDICT: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("COLLECTOR-VERDICT: PASS")
