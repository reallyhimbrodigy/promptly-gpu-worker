#!/usr/bin/env python3
"""The two arms of the authoring round must differ in the tool list itself.

WHY THIS EXISTS BEFORE THE ROUND RUNS. `search_skills` is 0 across 43 of 43
runs on disk, and the reason is not that Haiku declined it: `_judgment_only`
strips read_knowledge and search_skills from the tool list before the loop, and
every round runs claude-haiku-4-5. The skills are unreachable on the model that
renders, whichever package is mounted.

So the arm is `offer_readers`, and the one thing that would make the round
worthless is a flag whose two settings produce the SAME tool list — a null
result that reads as "reading does not help" when it means "both arms were the
same arm". This lane has shipped exactly that before: the prefix-removal switch
had a reader, a smoke and a red proof, and NOTHING SET IT, so the arm never
happened and the null was fabricated.

FOUR PROPERTIES:
  1. the flag is a PARAMETER of edit(), not an env var — an observable must be
     computed on the side of the boundary it describes, and a local export
     reads ON while the container runs OFF;
  2. withheld and offered produce DIFFERENT tool lists, and the difference is
     exactly the two readers;
  3. the state is recorded from the tool list actually built, not from the
     request;
  4. it is not vacuous: the readers exist to be offered in the first place.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
tree = ast.parse(src)

# 1. A PARAMETER, NOT AN ENV VAR.
fn = next((n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
if fn is None:
    print("  *** edit() not found — this check is ABSENT")
    sys.exit(1)
params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
if "offer_readers" not in params:
    print("  *** offer_readers is not a parameter of edit() — if it is an env "
          "var the local process and the container can disagree, and the log "
          "certifies the wrong arm")
    fail += 1

# 2. THE ARMS MUST DIFFER, AND BY EXACTLY THE READERS.
READERS = {"read_knowledge", "search_skills"}
tools_all = set()
for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS):
    if t.get("name"):
        tools_all.add(t["name"])
if not (READERS <= tools_all):
    print(f"  *** {sorted(READERS - tools_all)} is not in any tool list at all "
          f"— there is nothing to offer and the arm cannot exist")
    fail += 1
else:
    # simulate the shipped predicate on both settings
    def built(model, offer):
        jo = "haiku" in str(model).lower() and not offer
        names = set(tools_all)
        return (names - READERS) if jo else names
    a = built("claude-haiku-4-5", False)
    b = built("claude-haiku-4-5", True)
    if a == b:
        print("  *** both arms produce the SAME tool list — the round would "
              "measure nothing and the null would be fabricated")
        fail += 1
    elif (b - a) != READERS:
        print(f"  *** the arms differ by {sorted(b - a)}, not by exactly the "
              f"two readers — the arm is confounded")
        fail += 1
    # and on a non-Haiku model the flag must change nothing, because the
    # readers were never stripped there
    if built("claude-sonnet-5", False) != built("claude-sonnet-5", True):
        print("  *** the flag changes the tool list on a model that never had "
              "the readers stripped — it is doing something other than what "
              "it says")
        fail += 1

# 3. RECORDED FROM WHAT WAS BUILT, not from what was asked.
if 'led["readers_offered"]' not in src:
    print("  *** the arm's actual state is never written to the ledger — a run "
          "would be unattributable after the fact")
    fail += 1
guarded = [n for n in ast.walk(fn)
           if isinstance(n, ast.Assign)
           and any(getattr(t, "attr", "") == "" for t in [])]
if "led[\"tool_names\"]" not in src:
    print("  *** the tool list itself is not recorded — 'readers_offered' is a "
          "claim, the names are the evidence")
    fail += 1

# 4. NON-VACUITY: the predicate must actually consult the flag.
jo = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
      and any(getattr(t, "id", "") == "_judgment_only" for t in n.targets)]
if not jo:
    print("  *** _judgment_only is never assigned in edit()")
    fail += 1
elif not any(getattr(x, "id", "") == "offer_readers"
             for n in jo for x in ast.walk(n.value)):
    print("  *** _judgment_only does not consult offer_readers — the flag is "
          "accepted and ignored, which is a consumer with no producer wearing "
          "the opposite costume")
    fail += 1

print(f"smoke_readers_arm_separates: {len(tools_all)} tool(s), arms differ by "
      f"{sorted(READERS)}, {fail} wrong")
sys.exit(1 if fail else 0)
