#!/usr/bin/env python3
"""NEVER DOUBLE THE CAPTIONS. `[ART_DIRECTION §3, Rule 1]`

THE DEFECT (2026-08-17, seen by the owner in the trigger-source render).
Promptly stacked its own yellow captions on top of the source's burned-in white
ones, in the same band, overlapping. That one defect made the output read as
broken regardless of every other decision in it.

THE CAUSE WAS NOT A MISSING SIGNAL — IT WAS THREE SIGNALS AND THE WEAKEST ONE
GATING CAPTIONS:

    zoom gate      _burned_text["regions"][].class == "captions", or a wide
                   non-corner signage band            -> BROAD. Fired correctly,
                   suppressing 4 zooms on that render.
    caption gate   _burned_text["has_burned_captions"] ONLY
                                                      -> NARROW. Did not fire.
    the model      declared source_text_regions: ["bottom"] in the same plan —
                   but that field was normalised AFTER the suppression decision,
                   so it could not influence it at all.

Three descriptions of one fact. Two gates. Different answers.

THE FIX IS STRUCTURAL, NOT ADDITIVE. A fourth `or` clause would have fixed this
render and left the class alive. Instead there is ONE predicate,
`_burned_text_caption_block()`, and every caption-suppression decision routes
through it — so a future gate cannot read a narrower signal than the zoom gate
without this check going red.

ART_DIRECTION §3 is absolute: burned-in text present => caption_style "none".
There is no reduce and no reposition. The single exception is an EXPLICIT user
request for captions, which outranks our inference about their footage.

    python3 cert_never_double_captions.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")
PRED = "_burned_text_caption_block"


def _parents(tree):
    out = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            out[id(c)] = n
    return out


def _enclosing_fn(node, parents):
    cur = parents.get(id(node))
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
        cur = parents.get(id(cur))
    return None


def main():
    src = open(HANDLER).read()
    tree = ast.parse(src)
    parents = _parents(tree)
    fails = []

    # 1. THE PREDICATE EXISTS.
    pred = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == PRED:
            pred = n
    if pred is None:
        print(f"CERT NEVER-DOUBLE-CAPTIONS: FAIL\n  - {PRED}() is gone; caption "
              f"suppression has no shared predicate")
        return 1

    # 2. IT READS ALL THREE SIGNALS — CHECKED STRUCTURALLY, NOT BY SUBSTRING.
    #    The first version of this check used `needle in source`, and three of
    #    four RED mutations passed it: gutting the regions loop left the literal
    #    "captions" on a surviving line, and blanking the W3 read left
    #    source_text_regions on another. Substring presence proves a token is in
    #    the file, never that it is load-bearing — the exact class that has now
    #    produced 11 false results in this repo.
    #
    #    Each blocking signal is one `return True, ...` branch. Counting the
    #    branches means deleting a signal DELETES A RETURN, which no surviving
    #    literal can disguise.
    #    EACH BRANCH NAMES ITS OWN SIGNAL, and the cert asserts the NAMES.
    #    A count threshold was the previous attempt and it was vacuous: the
    #    predicate has FIVE blocking branches and the check required four, so
    #    deleting any one still passed. Deleting a branch deletes its name, and
    #    a name cannot be left behind by an unrelated surviving line the way a
    #    literal can.
    signals = set()
    for n in ast.walk(pred):
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple) \
                and len(n.value.elts) >= 3 \
                and isinstance(n.value.elts[0], ast.Constant) \
                and n.value.elts[0].value is True \
                and isinstance(n.value.elts[2], ast.Constant):
            signals.add(n.value.elts[2].value)
    REQUIRED = {
        "stage0": "the model's Stage-0 existing_caption_region read",
        "w3_declared": "the model's W3 source_text_regions declaration — the "
                       "signal that was normalised AFTER the decision and so "
                       "could never fire",
        "detector": "the detector's has_burned_captions flag",
        "detector_region": "the detector's REGION class — the BROAD signal the "
                           "zoom gate used and the caption gate did not, which "
                           "is the whole defect",
        "detector_bands": "the detector's own band list",
    }
    for name, why in REQUIRED.items():
        if name not in signals:
            fails.append(f"{PRED}() lost its {name!r} blocking branch ({why})")

    #    ...AND THE BRANCH MUST BE REACHABLE. Name-presence alone was still
    #    vacuous: `for r in ():` and `if False:` both leave the return in the
    #    AST while making it dead code. A signal that cannot fire is the same
    #    defect as a signal that was never written — that is literally what
    #    shipped here, since the W3 branch existed and ran too late to matter.
    def _guards(node):
        out, cur = [], parents_p.get(id(node))
        while cur is not None and cur is not pred:
            if isinstance(cur, ast.If):
                out.append(cur.test)
            elif isinstance(cur, (ast.For, ast.AsyncFor)):
                out.append(cur.iter)
            cur = parents_p.get(id(cur))
        return out

    parents_p = {}
    for n in ast.walk(pred):
        for c in ast.iter_child_nodes(n):
            parents_p[id(c)] = n
    for n in ast.walk(pred):
        if not (isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
                and len(n.value.elts) >= 3
                and isinstance(n.value.elts[0], ast.Constant)
                and n.value.elts[0].value is True
                and isinstance(n.value.elts[2], ast.Constant)):
            continue
        nm = n.value.elts[2].value
        for g in _guards(n):
            dead = (isinstance(g, ast.Constant) and not g.value) or \
                   (isinstance(g, (ast.Tuple, ast.List, ast.Set)) and not g.elts)
            if dead:
                fails.append(f"{PRED}()'s {nm!r} branch is UNREACHABLE — its "
                             f"guard is a constant-false/empty literal, so the "
                             f"signal can never fire")

    #    ...and each key is genuinely READ inside the predicate.
    read_keys = set()
    for n in ast.walk(pred):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "get" \
                and n.args and isinstance(n.args[0], ast.Constant):
            read_keys.add(n.args[0].value)
    for key, why in (("existing_caption_region", "the model's Stage-0 read"),
                     ("source_text_regions", "the model's W3 declaration"),
                     ("has_burned_captions", "the detector's caption flag"),
                     ("regions", "the detector's REGION list — the broad signal")):
        if key not in read_keys:
            fails.append(f"{PRED}() no longer reads {key} ({why})")

    # 3. EVERY CAPTION burned_suppress DECISION ROUTES THROUGH IT.
    n_caption_sites = 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fname = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        if fname != "_record_divergence":
            continue
        args = [a for a in n.args if isinstance(a, ast.Constant)]
        vals = [a.value for a in args]
        if "caption" not in vals or "burned_suppress" not in vals:
            continue
        n_caption_sites += 1
        fn = _enclosing_fn(n, parents)
        if fn is None:
            fails.append(f"caption burned_suppress at line {n.lineno} sits "
                         f"outside any function")
            continue
        calls = {getattr(c.func, "id", None) or getattr(c.func, "attr", None)
                 for c in ast.walk(fn) if isinstance(c, ast.Call)}
        if PRED not in calls:
            fails.append(f"the caption burned_suppress at line {n.lineno} is in "
                         f"{fn.name}(), which never calls {PRED}() — it is "
                         f"deciding on its own signal, which is exactly how a "
                         f"second caption track shipped over the source's own")

    if n_caption_sites < 2:
        fails.append(f"only {n_caption_sites} caption burned_suppress site(s); "
                     f"the fresh-plan span AND the re-edit revalidation must "
                     f"both suppress, or a re-edit re-adds what the first pass "
                     f"removed")

    # 4. THE PROHIBITION IS ABSOLUTE — the predicate returns a block, and the
    #    only permitted override is an explicit user request.
    #    Resolved as a CALL, not a substring: renaming the function to
    #    `_vibe_requests_captions_REMOVED` left the old name as a prefix and
    #    sailed through the substring version of this check.
    override_calls = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and (
                getattr(n.func, "id", None) == "_vibe_requests_captions"):
            override_calls += 1
    if override_calls < 2:
        fails.append(f"the explicit-user-request override is called at "
                     f"{override_calls} site(s), needs >=2 (fresh + re-edit) — "
                     f"a user who ASKS for captions must still get them")

    if fails:
        print("CERT NEVER-DOUBLE-CAPTIONS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT NEVER-DOUBLE-CAPTIONS: PASS")
    print(f"  one predicate {PRED}(), reading all three signals")
    print(f"  {n_caption_sites} caption suppression sites, every one routed through it")
    print("  explicit user request still outranks our inference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
