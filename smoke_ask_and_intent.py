#!/usr/bin/env python3
"""Nothing is placed without a ruling, and an ambiguous request ASKS.

THREE PROPERTIES, one theme: every pixel this editor adds traces to a decision
the agent made on the record, and when the request does not determine the
decision the run stops instead of guessing.

1. THE SECOND CHANNEL IS CLOSED. `build_overlays` treated caller-supplied items
   as additive — "a hand-authored overlay that is not a beat ruling still
   lands" — reachable through the repair tool. That is placing without intent.
   An item now lands only if its instant falls inside a beat ruled `text`;
   otherwise REFUSED, printed, and fail()ed.

2. THE RECORD FOLLOWS THE BUILD. `beat_verdicts` is MUTATED after the fact:
   the half-ruling stripper rewrites `treatment` in place, and a later ruling
   pass replaces entries. Round 54 talking_head beat 0 ended up reading
   ['cutaway'] while the overlay at 0.0s had been built from a ruling that
   named text — so the judgment sheet called the agent's own placement BUILT
   BUT NOT RULED. `executed_verdicts` is the frozen copy execute_plan built
   from.

3. AN AMBIGUOUS REQUEST ASKS (K5). "Cut the part where I stumble" on a source
   with three stumbles is two materially different edits. `set_spec
   .clarification` stops the run — no plan, no render, no charge — and
   `result_agentic` returns NEEDS_INPUT, a fourth state beside DONE / RUNNING /
   FAILED. Karpathy §1 "if something is unclear, stop, name what is confusing,
   ask"; Zac's ruling for ambiguous re-edit instructions, 2026-09-10.

RED-proven by red_proof_ask_and_intent.py.
"""
import ast
import pathlib
import sys

import modal_stub                                              # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                 # noqa: E402

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


def _fn(name):
    return next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _has_const(node, val):
    return any(isinstance(x, ast.Constant) and x.value == val
               for x in ast.walk(node))


# ── 1. NO PLACEMENT WITHOUT A RULING ────────────────────────────────────────
_bo = _fn("build_overlays")
check("build_overlays exists and is drivable", _bo is not None)
check("a caller-supplied overlay is refused when no beat ruled text at its instant",
      _bo is not None and any(isinstance(n, ast.Name) and n.id == "_unruled_refused"
                              for n in ast.walk(_bo)),
      "the refusal list must exist inside build_overlays")
# The candidate beats must be FILTERED BY THE RULING. The first draft of this
# leg looked for "text" and _text_windows in ONE assignment; they are two
# (_text_beats filters, _text_windows maps to output time), so it read FAIL on
# correct code — a check measuring the layout of the source, again.
_tb = [n for n in ast.walk(_bo) if isinstance(n, ast.Assign)
       and any(getattr(t, "id", "") == "_text_beats" for t in n.targets)] if _bo else []
_tw = [n for n in ast.walk(_bo) if isinstance(n, ast.Assign)
       and any(getattr(t, "id", "") == "_text_windows" for t in n.targets)] if _bo else []
check("the refusal is built against windows of beats RULED text, not all beats",
      bool(_tb) and bool(_tw)
      and any(_has_const(a_, "text") and _has_const(a_, "treatment") for a_ in _tb),
      "the candidate set must be filtered on a treatment naming text")
check("the old 'additive' passthrough sentence is gone from the source",
      "still lands." not in src,
      "the comment that licensed the second channel")
_prints = [n for n in ast.walk(_bo) if isinstance(n, ast.Call)
           and getattr(n.func, "id", "") == "print"
           and "OVERLAY REFUSED" in ast.unparse(n)] if _bo else []
check("the refusal is PRINTED in the same commit that adds it", bool(_prints))
_fails_c = [n for n in ast.walk(_bo) if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "fail"
            and "overlay_unruled_refused" in ast.unparse(n)] if _bo else []
check("and fail()s loudly, so it is a defect and not a taste call", bool(_fails_c))

# ── 2. THE RECORD FOLLOWS THE BUILD ─────────────────────────────────────────
_ev = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
       and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
               and t.slice.value == "executed_verdicts" for t in n.targets)]
check("execute_plan freezes the rulings it built from as executed_verdicts",
      bool(_ev))
check("it is a DEEP COPY — beat_verdicts is mutated in place downstream",
      any("deepcopy" in ast.unparse(a_.value) for a_ in _ev),
      "a shallow reference would be rewritten by the half-ruling stripper")
check("and the count is printed", "EXECUTED FROM" in src)
# the mutation it defends against is real and still present
check("the half-ruling stripper still rewrites treatment in place "
      "(the reason the snapshot exists)",
      '_v4["treatment"] = _tr or ["none"]' in src)

# ── 3. AN AMBIGUOUS REQUEST ASKS ────────────────────────────────────────────
check("K5 is in the working-discipline block", "K5." in src)
check("K5 says to stop and ask rather than pick",
      "STOP AND ASK" in src and "set_spec.clarification" in src)
check("K5 is in the prompt-section fingerprint, so its removal is visible",
      '"K5."' in src and src.count('"K5."') >= 2)
_ss = next((n for n in ast.walk(tree) if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "name"
                    for k in n.keys)
            and any(isinstance(v, ast.Constant) and v.value == "set_spec"
                    for v in n.values)), None)
check("set_spec publishes a `clarification` field", _ss is not None
      and _has_const(_ss, "clarification"))
check("the dispatch reads it and sets the terminal",
      'led["terminal"] = "needs_input"' in src and 'led["needs_input"] = {' in src)
# ast.unparse renders single quotes, so a leg written against the double-quoted
# literal never matches. Read the dict node.
_ni_assign = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                      and t.slice.value == "needs_input" for t in n.targets)]
def _dict_val(node, key):
    for d in ast.walk(node):
        if isinstance(d, ast.Dict):
            for k, v in zip(d.keys, d.values):
                if isinstance(k, ast.Constant) and k.value == key:
                    return v
    return None
check("asking charges nothing",
      bool(_ni_assign) and any(
          isinstance(_dict_val(a_, "credit_charged"), ast.Constant)
          and _dict_val(a_, "credit_charged").value is False for a_ in _ni_assign))
check("it stops the run through the SAME mechanism as unsupported",
      src.count("_unsupported_stop = True") == 2,
      "one stop path, two reasons — a second bespoke stop is a second thing to break")
_ra = _fn("result_agentic")
check("result_agentic returns NEEDS_INPUT as a fourth state",
      _ra is not None and _has_const(_ra, "NEEDS_INPUT"))
check("NEEDS_INPUT carries the question, not just a flag",
      _ra is not None and any(
          isinstance(n, ast.Return) and _has_const(n, "NEEDS_INPUT")
          and _has_const(n, "question") for n in ast.walk(_ra)))
check("and it is distinct from DONE — no plan comes back with a question",
      _ra is not None and any(
          isinstance(n, ast.Return) and _has_const(n, "NEEDS_INPUT")
          and any(isinstance(x, ast.Constant) and x.value == 0 for x in ast.walk(n))
          for n in ast.walk(_ra)))
check("the wire contract documents it for the server half",
      "NEEDS_INPUT" in pathlib.Path("CONTRACT_agentic_wire.md").read_text())

print()
if fails:
    print("ASK-AND-INTENT: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("ASK-AND-INTENT: PASS — no overlay without a ruling, the executed rulings "
      "are frozen, and an ambiguous request stops and asks for free")
