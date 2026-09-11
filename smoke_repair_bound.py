#!/usr/bin/env python3
"""One repair, named contract failure only, and never on an UNVALIDATED detector.

MEASURED OVER EVERY RUN ON DISK: 19 of 25 called execute_plan more than once
— 76%. The trigger is overwhelmingly `placement_inert`, in the agent's own
words. The extra call costs 28-68% of wall (motion +68%, +$0.064 against a
$0.10 law) and in six of eight within-fixture comparisons produced FEWER
placements, never reliably more.

And the verdict it answers was mis-calibrated: the region bar was drawn when
overlays were whole sentences; the restates-speech fix made them short labels
and the bar now falls INSIDE a single tight cluster. The harness was paying
$0.06 to repair a defect that did not exist.

FOUR PROPERTIES:
  1. a placement_inert whose family's bar reads INSIDE_CLUSTER does NOT
     authorise a repair;
  2. the same violation with the bar SEPARATING DOES — the bound must not
     make a real inert placement unfixable;
  3. a contract failure the bar has nothing to do with (wrong_resolution,
     no_audio_stream) always authorises, whatever the bar says — silencing
     those would trade a false repair for an unfixable render;
  4. the bar state is COMPUTED at repair time, not read from a key the
     reporting block writes later. Reading it there would be an absent value
     behaving as a pass.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
INERT = ("placement_inert: text declared a placement over 3.25-5.00s but the "
         "region there is unchanged")

# a run whose text deltas sit in one cluster — the round-58 shape
led_cluster = {"placement_effects": [
    {"mode": "region", "family": "text", "region_delta_db": d}
    for d in (4.70, 5.09, 5.11, 5.70, 5.91, 6.24, 6.76)]}
# and one where the bar clearly splits — the population it was drawn on
led_split = {"placement_effects": [
    {"mode": "region", "family": "text", "region_delta_db": d}
    for d in (0.24, 0.31, 0.55, 18.9, 19.98)]}

st_c = A._inert_bar_state(led_cluster)
st_s = A._inert_bar_state(led_split)
if st_c.get("text", {}).get("state") != "INSIDE_CLUSTER":
    print(f"  *** the round-58 population does not read INSIDE_CLUSTER: {st_c}")
    fail += 1
if st_s.get("text", {}).get("state") != "SEPARATES":
    print(f"  *** a clearly-split population does not read SEPARATES: {st_s}")
    fail += 1

# 1 + 2
if A._unvalidated_family(INERT, st_c) != "text":
    print("  *** an inert verdict on an INSIDE_CLUSTER bar still authorises a "
          "repair — the harness would pay $0.06 for a defect that is not there")
    fail += 1
if A._unvalidated_family(INERT, st_s) is not None:
    print("  *** an inert verdict on a SEPARATING bar was refused — a real "
          "inert placement must stay fixable")
    fail += 1

# 3
for other in ("wrong_resolution: 540x960", "no_audio_stream: none",
              "speech_loss_severe: 1 of 85 words"):
    if A._unvalidated_family(other, st_c) is not None:
        print(f"  *** {other.split(':')[0]} was refused a repair over the "
              f"region bar, which does not measure it")
        fail += 1

# 4 — computed at repair time, on the AST
src = open(os.path.join(HERE, "agentic_editor_app.py")).read()
tree = ast.parse(src)
edit_fn = next((n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
gate = [n for n in ast.walk(edit_fn) if isinstance(n, ast.Assign)
        and any(isinstance(v, ast.Call)
                and getattr(v.func, "id", "") == "_inert_bar_state"
                for v in ast.walk(n))] if edit_fn else []
if not gate:
    print("  *** the repair gate does not COMPUTE the bar state — if it reads "
          "led['region_bar_separation'] instead, that key is written after "
          "the tool loop and would be absent, behaving as a pass")
    fail += 1
if "_exec_repair_ok" not in src or "repair_refused_unvalidated" not in src:
    print("  *** the refusal is not recorded — a bound nobody can count is a "
          "bound nobody can check")
    fail += 1

print(f"smoke_repair_bound: cluster={st_c.get('text', {}).get('state')}, "
      f"split={st_s.get('text', {}).get('state')}, {fail} wrong")
sys.exit(1 if fail else 0)
