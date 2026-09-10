#!/usr/bin/env python3
"""SMOKE: the token-composition instrument measures what it claims to.

WHY IT EXISTS. model_s = 8.36 + 0.01113 * out_tokens (R^2 0.9996, round 33's
five fixtures), so output tokens ARE the latency and "which tokens" is the only
question that matters. The instrument answering it is new, and an instrument
that miscounts produces a confident wrong number — which is worse than no
number, because it gets designed against.

WHAT MAKES IT FIRE: rulings arrive as a LIST of dicts inside ONE tool call. A
top-level-keys-only reader returns 0 bytes on exactly the tool that carries
nearly all the rationale, and prints "0% rationale" — a clean zero that is a
reader bug. That is this repo's most expensive result to trust.
"""
import json, sys, types

import sys
import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A

fails=[]
def ok(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

rb = A.rationale_bytes

# ── the shape rulings ACTUALLY arrive in ─────────────────────────────────
ruling_call = {"rulings": [
    {"beat": 0, "families": ["zoom"], "why": "the hook lands on the number"},
    {"beat": 1, "families": [],       "why": "nothing to mark; let it breathe"},
]}
n = rb(ruling_call)
ok("nested rulings are counted", n > 0,
   "a top-level-keys-only reader returns 0 on the tool carrying nearly all the "
   "rationale, and prints a confident 0% — a clean zero that is a reader bug")
ok("nested count equals the two why strings",
   n == len(json.dumps("the hook lands on the number"))
      + len(json.dumps("nothing to mark; let it breathe")),
   f"got {n}")

# ── a call with NO rationale must read zero, not something ───────────────
ok("a rationale-free call reads 0", rb({"beat": 3, "families": ["cut"]}) == 0)

# ── every documented key is actually recognised ──────────────────────────
for k in A.RATIONALE_KEYS:
    ok(f"key '{k}' is counted", rb({k: "xxxx"}) == len(json.dumps("xxxx")),
       "a key in the documented list that the walker does not count makes the "
       "share silently low")

# ── depth: rationale buried two levels down still counts ─────────────────
ok("depth-2 rationale is counted",
   rb({"plan": {"steps": [{"reason": "abc"}]}}) == len(json.dumps("abc")))

# ── a non-rationale key of the same VALUE must not be counted ────────────
ok("only rationale keys count", rb({"text": "the hook lands on the number"}) == 0,
   "counting overlay TEXT as rationale would inflate the share and point the "
   "token-reduction design at the wrong field")

# ── case-insensitive, since tool schemas are not consistent ──────────────
ok("keys are matched case-insensitively", rb({"WHY": "abc"}) == len(json.dumps("abc")))

if fails:
    print(f"TOKEN-SPLIT: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print(f"TOKEN-SPLIT: PASS ({len(A.RATIONALE_KEYS)} keys + nesting/depth/negatives driven)")
