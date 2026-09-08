#!/usr/bin/env python3
"""SMOKE: no density rate reaches the agent — not as a target, not as prose.

ZAC'S RULING. The reference rates are a GRADING INSTRUMENT ONLY. They must never
reach the agent as a target, appear in the prompt, or be enforced as a floor at
ruling time. The agent places components where they fit; the rubric asks
afterwards whether the result is in the plausible range. A run that places two
zooms because two moments deserved them is correct, and a rubric that calls it
short is the rubric's problem.

WHY A CHECK AND NOT JUST THE EDIT. The removal touched three surfaces — prompt
prose, the spec structure, and the tool schema — and after it landed, ONE
SURVIVED:

    "Overlay text is the WORKHORSE (~7.5 per 25s). Emphasis and SFX are RARE
     (~0.5 per 25s). If your edit has more zooms than text, it is inverted."

still sitting in _KNOWLEDGE_SYSTEM, a block the agent reads. The removal was
careful and the summary said "system prompt rate-as-demand: NONE". Prose that
merely DESCRIBES a rate reads as harmless next to a schema field that demands
one, which is exactly why it survived a pass that removed the demands. Rates in
the prompt come back the same way — one plausible sentence at a time.

WHAT THIS ASSERTS: no per-25s rate literal in any string the agent can read.
Qualitative shape is untouched and welcome — "text is the workhorse, emphasis
and sfx are rare" is editorial guidance and carries no number to hit.

THE LEDGER IS NOT THE AGENT. spec_shortfall still computes target_per_25s and
rate_regimes still runs; both are read at end of run by the grader and neither is
returned to a tool call. Grading is the permitted use and this check must not
fire on it — a check that forbids measuring is not what the ruling asked for.
"""
import ast
import re
import sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

# "7.5 per 25s", "0.35/25s", "4.75 per-25s" — a NUMBER bound to the 25s window.
RATE = re.compile(r"\d+(?:\.\d+)?\s*(?:per[\s-]*25\s*s|/\s*25\s*s)", re.I)

# Module-level string constants the agent reads, plus every tool description and
# schema description. Derived, not listed: a new prompt block added tomorrow is
# covered without anyone remembering this file.
AGENT_FACING_NAMES = {"SYSTEM", "_KNOWLEDGE_SYSTEM", "KNOWLEDGE_SYSTEM"}

fails = []


def scan(text, where):
    for m in RATE.finditer(text or ""):
        line = (text[:m.start()].count("\n"))
        snippet = (text or "").split("\n")[line].strip()[:100]
        fails.append(f"{where}: {m.group(0)!r} in — {snippet}")


# 1. named module-level prompt constants
for node in TREE.body:
    if isinstance(node, ast.Assign):
        name = getattr(node.targets[0], "id", "")
        if name in AGENT_FACING_NAMES or name.endswith("_SYSTEM") or name.endswith("_PROMPT"):
            try:
                scan(ast.literal_eval(node.value), f"prompt constant {name}")
            except Exception:
                pass

# 2. every tool description / schema description string, wherever it lives
for node in ast.walk(TREE):
    if not isinstance(node, ast.Dict):
        continue
    for k, v in zip(node.keys, node.values):
        if not (isinstance(k, ast.Constant) and k.value == "description"):
            continue
        try:
            scan(ast.literal_eval(v), "tool/schema description")
        except Exception:
            pass

# 3. the grading path must SURVIVE — this check must not have banned measuring
grading_alive = all(s in SRC for s in
                    ("REFERENCE_PER_25S", "rate_regime", "spec_shortfall"))
if not grading_alive:
    fails.append("the GRADING instrument is gone (REFERENCE_PER_25S / "
                 "rate_regime / spec_shortfall) — the ruling removed the rates "
                 "from the AGENT, not the rubric from the round")

if fails:
    print(f"NO-RATES-IN-PROMPT: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("NO-RATES-IN-PROMPT: PASS (prompt constants + every tool/schema "
      "description; grading path intact)")
