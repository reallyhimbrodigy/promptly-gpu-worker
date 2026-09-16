#!/usr/bin/env python3
"""SMOKE — plan_only stops before the builds and still produces all six values
the ChatCut path reads.

THE MEASUREMENT THAT MOTIVATED IT. The planner's 346.2s wall splits
model_thinking 179.84s (52.2%) and tool:execute_plan 147.36s (42.7%), and the
ChatCut path NEVER OPENS THE RENDERED FILE — it rebuilds the edit in ChatCut
from the rulings. So 117.9s of builds plus 29.5s unattributed produce an mp4
that is measured, inspected and thrown away.

IT LOOKED ENTANGLED AND WAS NOT. `led["caption_render"]` is written on the line
AFTER `_mark(led, "build_alpha_layer", ...)`, so the style and page count read
like outputs of a 37.9s render when they are DECIDED just above it. The cut
point is exact: everything before `_cap_t0 = time.time()` is a decision,
everything after is a render.

Legs, each RED-proven:
  STOPS     plan_only returns before render_remotion_batch is reached
  KEEPS     it still writes every value the ChatCut path reads
  WITHDRAWN inspect_output is removed from the tools, because it probes a file
            that will not exist — a tool whose precondition this path never
            satisfies is a trap, not a capability
  TOLD      the prompt says so, and countermands the verify-and-rerun steps
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

# every key blueshirt_launch.py and plan_for_chatcut.py read out of the ruling
NEEDED = ["keep_spans", "caption_render", "caption_composited"]


def fn_src(name):
    for n in ast.walk(TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.unparse(n)
    return ""


def legs(src=None, tree=None):
    src = src if src is not None else SRC
    bad = []
    if "plan_only: bool = False" not in src:
        bad.append(("param", "edit() has no plan_only parameter"))

    # ── FIDELITY GRADES THE RULINGS ON A PLAN-ONLY RUN ─────────────────────
    # The prefix tells the agent "your rulings are the deliverable"; the grade
    # has to agree. Graded against `placements` — what BUILT — a plan_only run
    # that ruled card and text perfectly reads SHORT, because plan_only builds
    # nothing by design. "Not ruled" and "ruled on a path that renders nothing"
    # are opposite facts and they rendered identically.
    #
    # Checked on the POPULATION SELECTION, not on a spelling: the branch under
    # `if plan_only:` that assigns `_fid_pl` must read a verdict source.
    # THE ASSIGNMENT, NOT THE BRANCH. My first version read the whole
    # `if plan_only:` body and the mutation walked straight past it: the
    # REPORTING line two statements down also spells `executed_verdicts`, so
    # swapping the population for `placements` left the leg green. A leg
    # satisfied by a sentence it did not mean — the same shape as six legs
    # caught in one stretch on 2026-09-11.
    _sel = ""
    for n in ast.walk(tree if tree is not None else TREE):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) \
                and n.test.id == "plan_only":
            for _st in n.body:
                if isinstance(_st, ast.Assign) and any(
                        isinstance(t2, ast.Name) and t2.id == "_fid_pl"
                        for t2 in _st.targets):
                    _sel = ast.unparse(_st.value)
    if not _sel:
        bad.append(("fidelity", "nothing under `if plan_only:` rebinds _fid_pl "
                                "— fidelity still grades what BUILT on a path "
                                "that builds nothing"))
    elif not ("executed_verdicts" in _sel or "beat_verdicts" in _sel):
        bad.append(("fidelity", "the plan_only fidelity population does not "
                                "read a verdict source: %s" % _sel[:120]))

    ep = ""
    for n in ast.walk(tree if tree is not None else TREE):
        if isinstance(n, ast.FunctionDef) and n.name == "execute_plan":
            ep = ast.unparse(n)
            break
    if not ep:
        return [("build", "execute_plan not found")]

    # STOPS — the guard exists and returns
    if "if plan_only:" not in ep:
        bad.append(("stops", "execute_plan has no plan_only guard"))
    else:
        head = ep[:ep.index("if plan_only:")]
        tail = ep[ep.index("if plan_only:"):]
        if "render_remotion_batch" in head:
            bad.append(("stops", "a render runs BEFORE the plan_only guard — "
                                 "the guard is downstream of the cost"))
        if "return" not in tail.split("\n_cap_t0")[0][:1400]:
            bad.append(("stops", "the guard does not return"))

    # KEEPS — every value the ChatCut path reads is still written
    guard = ep[ep.index("if plan_only:"):] if "if plan_only:" in ep else ""
    blk = guard[:guard.find("_cap_t0 = time.time()")] if "_cap_t0" in guard \
        else guard[:2000]
    for k in NEEDED:
        if k == "keep_spans":
            if "build_cut" not in ep:
                bad.append(("keeps", "build_cut does not run, so keep_spans "
                                     "is never produced"))
        # NO QUOTE STYLE. `ast.unparse` normalises "x" to 'x', so a leg
        # looking for the double-quoted key finds nothing in code that writes
        # it — the reader wrong about correct source because of how it chose
        # to render it. Match the NAME.
        elif not re.search(r"\b%s\b" % re.escape(k), blk):
            bad.append(("keeps", "%s is not written before the guard returns" % k))

    # WITHDRAWN
    if 't.get("name") != "inspect_output"' not in src:
        bad.append(("withdrawn", "inspect_output is still offered on a path "
                                 "with no rendered file"))
    # TOLD
    if "PLAN-ONLY" not in src or "inspect_output` is NOT available" not in src:
        bad.append(("told", "the prompt does not tell the agent the run is "
                            "plan-only"))
    return bad


if __name__ == "__main__":
    bad = legs()
    for k, w in bad:
        print("  [FAIL] %-10s %s" % (k, w))
    if not bad:
        print("  [ok] edit() takes plan_only")
        print("  [ok] the guard returns BEFORE any render_remotion_batch call")
        print("  [ok] keep_spans, caption_render and caption_composited all "
              "survive it")
        print("  [ok] inspect_output is withdrawn, and the prompt says why")

    print("\n  RED PROOF")
    red = True
    for label, mut, kind in (
            ("the guard moved below the render",
             lambda s: s.replace("            if plan_only:\n",
                                 "            if False:\n"), "stops"),
            ("caption_render no longer written before it",
             lambda s: s.replace('led["caption_render"] = {\n'
                                 '                    "seq"',
                                 'led["_dropped"] = {\n                    "seq"'),
             "keeps"),
            ("inspect_output offered again",
             lambda s: s.replace('t.get("name") != "inspect_output"',
                                 'True'), "withdrawn"),
            ("the prompt no longer says so",
             lambda s: s.replace("inspect_output` is NOT available",
                                 "all tools remain"), "told"),
            # AIMED AT THE POPULATION, NOT THE SPELLING. The anchor is the
            # one line naming the verdict source inside the plan_only branch;
            # swapping it for `placements` puts the grade back on what BUILT,
            # which on this path is always empty.
            ("fidelity grades the BUILD again on plan_only",
             lambda s: s.replace(
                 '                   for _v in (led.get("executed_verdicts")\n'
                 '                              or led.get("beat_verdicts") or [])\n',
                 '                   for _v in (led.get("placements") or [])\n'),
             "fidelity")):
        m = mut(SRC)
        try:
            r = legs(m, ast.parse(m))
        except SyntaxError:
            print("    %-36s -> mutation did not parse" % label)
            red = False
            continue
        hit = any(k == kind for k, _ in r)
        print("    %-36s -> %d leg(s) red, names %s: %s"
              % (label, len(r), kind, hit))
        red &= hit

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
