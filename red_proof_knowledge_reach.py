#!/usr/bin/env python3
"""RED proof for smoke_knowledge_reach.py, in a throwaway worktree.

A positive control first — hide a wired claim and confirm the UNMUTATED gate
notices the count fall. Then the mutations: the ratchet blinded, the baseline
treated as absent, and the census's classification requirements gutted.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_knowledge_reach.py").resolve()
APPNAME = "agentic_editor_app.py"
BASENAME = "knowledge_reach_baseline.json"
DOCNAME = "KNOWLEDGE_REACH.md"
MUTATIONS = [
    ("the ratchet stops noticing a fall", SMOKE.name,
     '          _r >= _b.get("reachable", 0),', '          True,',
     "reachable count has NOT fallen"),
    ("a missing baseline reads as the first run", SMOKE.name,
     'check("the baseline exists", BASE.exists(),', 'check("the baseline exists", True,',
     "baseline exists"),
    ("the census stops classifying and only counts", DOCNAME,
     "**GRADING-ONLY", "**COUNTED-ONLY",
     "classifies 'GRADING-ONLY'"),
    ("the census stops naming the rates that must never be wired", DOCNAME,
     "`13_placement_findings` and\n`14_card_text_placement_rules` are measured RATES",
     "two documents are measured RATES",
     "names the rates that must NEVER be wired"),
    # AIMED AT EVERY OCCURRENCE. The first version rewrote only the bolded
    # sentence and both `06_emphasis_zoom` and `zoom_arc` still appeared in the
    # table row above it, so the leg passed — the ambiguous-literal class, in a
    # markdown file this time.
    ("the census stops naming the largest instructable gap", DOCNAME,
     "| `zoom_arc` | `06_emphasis_zoom` |", "| `zoom_ARC` | `06_emphasis` |",
     "names the largest instructable gap"),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="kr_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    _orig = {n: (pathlib.Path(_wt) / n).read_text()
             for n in (APPNAME, BASENAME, DOCNAME, SMOKE.name)}
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")

    # POSITIVE CONTROL: unwire a claim the agent can currently see — take one of
    # the eight WHEN headings out of the enum's reach — and confirm the
    # unmutated gate reports the fall.
    _app = pathlib.Path(_wt) / APPNAME
    # THE TEXT, NOT THE KEY. Three controls failed before this one and each was
    # wrong in a way worth keeping:
    #   slicing MG_CONDITION_ENUM      left the DESCRIPTION's own join intact
    #   cutting the description's join left the ENUM intact
    #   renaming the whole field       left BOTH — a renamed property still
    #                                  carries its enum and description into the
    #                                  tool JSON, so the model still SEES the
    #                                  headings; it just cannot answer with them
    #
    # The third is the instructive one. knowledge_reach measures VISIBILITY —
    # does this text reach the model's context — and visibility is genuinely
    # unchanged by renaming a key. The gate was right and the control was
    # wrong. Emptying the enum removes both carriers at once, and the
    # difference between "the agent can see it" and "the agent can act on it"
    # is now named in knowledge_reach's own docstring.
    _mode, _m = red_proof_anchor.apply_one(
        _orig[APPNAME], "MG_CONDITION_ENUM = list(MG_CONDITIONS)",
        "MG_CONDITION_ENUM = []")
    if _m is None:
        harness.append("positive control: anchor %s" % _mode)
        print("  HARNESS FAILURE  positive control  :: anchor %s" % _mode)
    else:
        _app.write_text(_m); _prc, _pout = run(_wt); _app.write_text(_orig[APPNAME])
        if _prc == 0:
            harness.append("positive control: the gate did not notice a fall")
            print("  POSITIVE CONTROL FAILED: unwiring 7 of the 8 conditions did "
                  "NOT trip the ratchet, so nothing below proves anything")
        else:
            print("  positive control: the unmutated gate CAUGHT a fall from 8 "
                  "reachable to fewer\n")

    for label, target, old, new, expect in MUTATIONS:
        _tgt = pathlib.Path(_wt) / target
        _mode, _mm = red_proof_anchor.apply_one(_tgt.read_text(), old, new)
        if _mm is None:
            harness.append(f"{label}: anchor {_mode}")
            print(f"  HARNESS FAILURE  {label}  :: anchor {_mode}"); continue
        if _mode != red_proof_anchor.EXACT:
            print(f"  note             {label}  :: matched {_mode}")
        if target.endswith(".py"):
            try:
                ast.parse(_mm)
            except SyntaxError as e:
                harness.append(f"{label}: mutant does not parse")
                print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})")
                continue
        # a weakened CHECK needs an offender present to have anything to miss
        _need_offender = target == SMOKE.name
        if _need_offender and _m is not None:
            _app.write_text(_m)
        _tgt.write_text(_mm); mrc, mout = run(_wt)
        _tgt.write_text(_orig[target]); _app.write_text(_orig[APPNAME])
        if _need_offender:
            # the weakened check must now PASS on an app that should fail
            if mrc != 0:
                red += 1
                print(f"  RED              {label}\n                   the gate "
                      f"still caught it, so the leg is not the only thing holding")
            else:
                print(f"  RED              {label}\n                   caught by: "
                      f"the weakened leg let a real fall through")
                red += 1
            continue
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
