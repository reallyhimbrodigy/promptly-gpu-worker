#!/usr/bin/env python3
"""RED proof for the capability-router legs in smoke_five_families.py.

The mutations are the ways a router quietly picks for the user: the additive
rule collapsing so "add a shot over this" throws their edit away, an in-frame
change routed to a clip generator that cannot serve it, an ambiguous request
resolved silently, the built route becoming the default for anything
unrecognised, and a cost figure appearing for a path nobody has ever run.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_five_families.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("the additive rule collapses — 'add a shot over this' discards the edit",
     '        if any(_k in _b for _k in _ADDITIVE_MARKERS):',
     '        if False:',
     "does not route to hybrid", _INJECTS),
    ("an in-frame change is routed to a clip generator",
     '    if unsupported_class == "change_in_frame":',
     '    if False:',
     "routes to a CLIP GENERATOR", _INJECTS),
    ("an ambiguous generate request is answered silently",
     '        return (ROUTE_GENERATE, "AMBIGUOUS",\n'
     '                "footage that does not exist is needed',
     '        return (ROUTE_GENERATE, "MEASURED",\n'
     '                "footage that does not exist is needed',
     "answered silently instead of asked", _INJECTS),
    ("an unrecognised mode resolves silently instead of recording ambiguity",
     '        return (ROUTE_EDIT, "AMBIGUOUS",\n'
     '                "mode %r is not a routing answer',
     '        return (ROUTE_EDIT, "MEASURED",\n'
     '                "mode %r is not a routing answer',
     "resolves silently rather than recording", _INJECTS),
    ("an unrecognised mode defaults to an UNBUILT route",
     '        return (ROUTE_EDIT, "AMBIGUOUS",\n'
     '                "mode %r is not a routing answer',
     '        return (ROUTE_GENERATE, "AMBIGUOUS",\n'
     '                "mode %r is not a routing answer',
     "does not default to the BUILT route", _INJECTS),
    ("a path nobody has run is given a cost figure",
     '_ROUTE_COST = {\n    ROUTE_EDIT:',
     '_ROUTE_COST = {\n    ROUTE_GENERATE: {"state": "MEASURED", "wall_p50_s": 120.0,\n'
     '                     "wall_max_s": 300.0, "usd_observed": [0.5, 2.0], "n": 0,\n'
     '                     "src": "a vendor page"},\n    ROUTE_EDIT:',
     "quotes a cost figure", _INJECTS),
    ("the edit route's cost loses its denominator",
     '"usd_observed": [0.1016, 0.2549], "n": 15,',
     '"usd_observed": [0.1016, 0.2549], "n": 0,',
     "MEASURED with its denominator", _INJECTS),
    ("ABSENT stops saying what must be measured first",
     '                "why": "%s has never been run here; four things must be "',
     '                "why": "%s is not priced"  #',
     "does not say what must be measured", _INJECTS),
    ("the route stops being counted",
     '                        led["route_demand"][_rt] = led["route_demand"].get(_rt, 0) + 1',
     '                        pass',
     "nothing INCREMENTS", _INJECTS),
    ("the hybrid route terminates the run like the others",
     '                        if _rt == ROUTE_HYBRID:', '                        if False:',
     "TERMINATES the run", _INJECTS),
    ("an insert request stops recording itself unfilled",
     '            "state": "UNFILLED",', '            "state": "ok",',
     "record itself UNFILLED", _INJECTS),
    # AIMED AT THE NEGATION, not the explanation. The first version replaced
    # the sentence AFTER "I can create" — which truncated the explanation and
    # left "isn't something I can create" fully intact, so the message still
    # said the right thing and the mutant correctly passed. The mutation was
    # wrong, not the leg: to test whether the message states the negation, the
    # mutation has to remove the negation.
    # AIMED AT THE NEGATION, and anchored uniquely. Two earlier attempts
    # failed differently and both are worth keeping: the first replaced the
    # sentence AFTER "I can create", which truncated the explanation and left
    # the negation intact — the mutation was wrong, not the leg. The second
    # aimed at the negation itself and came back "anchor Nx", because BOTH
    # messages compute it the same way. Anchored through the PARTIAL branch's
    # own unique line.
    ("the hybrid message stops saying the insert did not happen",
     '"for is in there."\n            % ("shot" if _n == 1 else "%d shots" % _n,\n               "isn\'t" if _n == 1 else "aren\'t"))',
     '"for is in there."\n            % ("shot" if _n == 1 else "%d shots" % _n,\n               "is" if _n == 1 else "are"))',
     "does not say, as a phrase, that the insert", _INJECTS),
    ("a hybrid whose edit also failed is reported as a partial delivery",
     '    if not edit_ok:\n        return ("REFUSED",',
     '    if False:\n        return ("REFUSED",',
     "there is nothing to hand over", _INJECTS),
    ("a run with no inserts is treated as a hybrid delivery",
     '    if not _n:\n        return ("ABSENT", "")',
     '    if False:\n        return ("ABSENT", "")',
     "treated as a hybrid delivery", _INJECTS),
    # THE CARD CATALOGUE'S WIDTH
    ("the condition stops selecting a component — the catalogue narrows to two",
     "        if condition:\n            _cands = condition_components(condition, one_field_only=True)",
     "        if False:\n            _cands = condition_components(condition, one_field_only=True)",
     "components are reachable from language alone", _INJECTS),
    ("card_props stop selecting their component — the prop table goes dark again",
     "    if len(_owned) == 1:", "    if False:",
     "reachable by sending content props", _INJECTS),
    ("a condition with two bare-phrase components picks one on a proxy",
     "            if len(_cands) > 1:", "            if False:",
     "picks one on a proxy", _INJECTS),
    ("props naming a component outside the stated condition are accepted",
     "        if condition and _c not in (MG_CONDITIONS.get(condition) or []):",
     "        if False:",
     "silently resolved instead of refused", _INJECTS),
    ("keys from two components are silently resolved to one",
     "    if len(_owned) > 1:", "    if False:",
     "silently resolved to one", _INJECTS),
    ("omitting the condition changes the existing answer",
     '        return ("PullQuote", "a short claim with no figure and no condition "',
     '        return ("Stamp", "a short claim with no figure and no condition "',
     "changed the existing answer", _INJECTS),
    ("the condition enum stops being derived and is hand-typed",
     "MG_CONDITION_ENUM = list(MG_CONDITIONS)",
     'MG_CONDITION_ENUM = ["WHEN A NUMBER LANDS"]',
     "condition enum is not 8 wide", _INJECTS),
    ("card_props is no longer offered on the ruling surface",
     '                                 "card_props": {\n                                     "type": "object",',
     '                                 "_card_props_unused": {\n                                     "type": "object",',
     "card_props is not offered", _INJECTS),
    ("an AMBIGUOUS route stops failing loudly",
     '                            fail("route_ambiguous",',
     '                            _note("route_ambiguous",',
     "does not fail loudly", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="router_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    APP = pathlib.Path(_wt) / APPNAME
    ORIG = APP.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, old, new, expect, precond in MUTATIONS:
        _mode, _m = red_proof_anchor.apply_one(APP.read_text(), old, new)
        if _m is None:
            harness.append(f"{label}: anchor {_mode}")
            print(f"  HARNESS FAILURE  {label}  :: anchor {_mode}"); continue
        if _mode != red_proof_anchor.EXACT:
            print(f"  note             {label}  :: matched {_mode}")
        try:
            ast.parse(_m)
        except SyntaxError as e:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})"); continue
        APP.write_text(_m); mrc, mout = run(_wt); APP.write_text(ORIG)
        if mrc == 0:
            print(f"  NOT RED          {label}  :: the mutant PASSED")
            harness.append(f"{label}: mutant passed")
        elif expect not in mout:
            print(f"  WRONG REASON     {label}  :: expected '{expect}'")
            harness.append(f"{label}: wrong reason")
        else:
            red += 1
            print(f"  RED              {label}\n                   caught by: {expect}")
    frc, _ = run(_wt)
    print(f"\nRESTORED exit={frc}")
finally:
    subprocess.run(["git", "worktree", "remove", "--force", _wt], capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"isolated worktree removed: {not pathlib.Path(_wt).exists()}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
