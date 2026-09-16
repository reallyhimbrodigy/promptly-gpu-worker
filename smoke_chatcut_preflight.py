#!/usr/bin/env python3
"""SMOKE — a toolless container FAILS. It does not quietly edit nothing.

THE CLASS, anticipated before it could happen. An unauthenticated MCP server
leaves a Claude Code session with NO TOOLS rather than an error. The agent then
boots, finds nothing to call, produces no edit and exits 0 — indistinguishable
from an agent that watched the clip and decided it was already fine. Every
downstream instrument reports a true and useless zero: 0 placements, 0 cuts,
0 chars of reasoning. This lane has paid for that shape repeatedly, most
recently on round 69 where a single null enum refused every request and five
arms reported nothing rather than failing.

So the preflight runs over plain HTTP BEFORE the agent starts, and it RAISES.
The legs below drive the real function; they do not re-implement it.
"""
import ast
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("cj", "chatcut_job_app.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

fails = []


def check(what, ok, detail=""):
    if not ok:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if ok else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not ok and detail else ""))


# ── 1. IT RAISES ON A BAD CREDENTIAL ────────────────────────────────────────
try:
    M.preflight("not-a-real-token")
    check("preflight RAISES when the token is rejected", False,
          "it returned instead of raising — the guard is inert and a toolless "
          "container would proceed to burn a turn")
except RuntimeError as e:
    check("preflight RAISES when the token is rejected", True)
    check("and the message names the CONSEQUENCE, not just the status code",
          "NO TOOLS" in str(e) and "chose to do nothing" in str(e),
          str(e)[:120])
except Exception as e:                                            # noqa: BLE001
    check("preflight RAISES a RuntimeError (not a bare transport error)",
          False, f"{type(e).__name__}: {e}"[:120])

# ── 2. A MISSING SECRET IS ABSENT, NOT EXPIRED ──────────────────────────────
for k in ("CHATCUT_REFRESH_TOKEN", "CHATCUT_CLIENT_ID"):
    os.environ.pop(k, None)
try:
    M._access_token()
    check("_access_token RAISES when the Secret is not attached", False)
except RuntimeError as e:
    check("_access_token RAISES when the Secret is not attached", True)
    check("and distinguishes a MISSING credential from an expired one",
          "ABSENT" in str(e) and "not an expired one" in str(e), str(e)[:120])

# ── 3. THE GUARD IS WIRED AHEAD OF THE AGENT ────────────────────────────────
# Position is the property. A preflight that runs after the agent has started
# proves nothing — it would report the failure one turn too late, which is the
# same defect as RULING PASSES printing above the loop that fills it.
SRC = open("chatcut_job_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
fn = next((n for n in ast.walk(TREE)
           if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
check("the job function exists", fn is not None)
if fn is not None:
    pre_ln = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "preflight"]
    # THE LAUNCH MOVED AND THE CHECK DID NOT. This looked for
    # `subprocess.run(... "claude" ...)` inside `edit`; the launch now goes
    # through `turn_clock.run_timed`, so the leg found nothing and reported
    # FAIL on a file that launches the agent correctly — and, worse, the
    # ordering leg below it silently stopped running, so "preflight runs BEFORE
    # the agent" has been unproven ever since. Find the launch by what it IS —
    # the argv whose first element is the literal "claude" — not by the name of
    # whatever runs it.
    agent_ln = [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.List) and n.elts
                and isinstance(n.elts[0], ast.Constant)
                and n.elts[0].value == "claude"]
    check("preflight is CALLED inside the job", bool(pre_ln))
    check("the agent is launched inside the job", bool(agent_ln))
    if pre_ln and agent_ln:
        check("preflight runs BEFORE the agent — a guard that fires after the "
              "turn is spent is a report, not a guard",
              min(pre_ln) < min(agent_ln),
              f"preflight@{min(pre_ln)} agent@{min(agent_ln)}")

# ── 4. THE CRAFT IS MOUNTED AS CONTEXT, NOT RE-ENCODED AS RULES ─────────────
# Zac's standing instruction. If the harness ever starts summarising the corpus
# into thresholds, the thing that makes it edit like the references is gone and
# nothing else would notice.
for p in ("/craft/knowledge", "/craft/control_distributions.json",
          "/craft/reference_index.json"):
    check(f"{p} is mounted into the image", p in SRC)
# COUNTED, AND ON BOTH SURFACES. The disclaimer is written twice on purpose —
# once where the digest is built and once in the prompt that carries it — and
# an `in` leg is satisfied by either, so deleting the one on the surface the
# agent reads leaves this green. That is the same weakness this file's own
# next paragraph is about, in the leg above it.
_n_dis = SRC.count("never a target")
check("the distributions are handed over as DESCRIPTION, not as a target, on "
      "BOTH surfaces", _n_dis == 2 and "It DESCRIBES" in SRC,
      "the rates GRADE and never instruct; found %d disclaimer(s)" % _n_dis)

# AND THE DISCLAIMER MUST NOT SIT BESIDE A DEMAND. Presence of "never a target"
# does not exclude a target being added next to it, and that is exactly how the
# rates came back last time: "Overlay text is the WORKHORSE (~7.5 per 25s)"
# survived a careful removal because prose that DESCRIBES a rate reads as
# harmless beside a schema field that DEMANDS one, and the removal was hunting
# demands. A rate reaches the agent one plausible sentence at a time.
#
# So this checks the CRAFT PROMPT ITSELF for target-shaped language, not the
# whole file — the corpus numbers live in /craft and belong there; what must
# never appear is an instruction to hit one.
_ctx = M.CRAFT_CONTEXT
import re as _re
_rates = _re.findall(r"[~\d][\d.]*\s*(?:per|/)\s*\d*\s*s(?:ec|econds)?\b", _ctx, _re.I)
check("the craft prompt states no per-second or per-25s rate",
      not _rates, f"{_rates[:4]} — a rate in the prompt is a floor the agent "
                  f"will hit whatever the moment deserved")
_demands = [w for w in ("aim for", "aim to", "should place", "must place",
                        "at least one per", "target of", "hit the", "match the rate")
            if w in _ctx.lower()]
check("and no demand-shaped instruction",
      not _demands, f"{_demands} — the rates GRADE, they never instruct")

if fails:
    print("CHATCUT-PREFLIGHT: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CHATCUT-PREFLIGHT: PASS — a toolless container raises before the agent "
      "runs, a missing Secret reads ABSENT, and the craft is mounted not "
      "summarised")
