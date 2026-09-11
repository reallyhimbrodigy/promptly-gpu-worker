#!/usr/bin/env python3
"""RED proof for smoke_visual_vocabulary.py, in a throwaway worktree.

The mutations are the ways the silent route slides back to speech vocabulary:
a slip sentence returning inside a string literal, the block coming unwired
from the no-speech branch, breath being defined as dead air again, an eighth
axis appearing beside the seven purposes, and a read written in speech terms.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_visual_vocabulary.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("the slip sentence returns inside the block's string",
     '            "is ruled on, not cleared.\\n")',
     '            "is ruled on, not cleared. Rule on them exactly as you would '
     'rule on spoken beats.\\n")',
     "reaches no string", _INJECTS),
    ("the block comes unwired from the no-speech branch",
     '               + visual_purpose_block() + "\\n")',
     '               + "" + "\\n")',
     "wired into the NO SPEECH branch", _INJECTS),
    ("breath is dead air again",
     '"is where the eye rests. It is a beat to rule on, not dead air "\n'
     '                "to delete.",',
     '"is the visual equivalent of dead air.",',
     "BREATH is defined as a beat", _INJECTS),
    ("an eighth axis appears beside the seven purposes",
     '    "hook":     "the first look',
     '    "establish": "footage",\n    "hook":     "the first look',
     "EXACTLY the seven purposes", _INJECTS),
    ("a read is written in speech terms",
     '    "claim":    "the footage asserts something on its own: the subject in full "',
     '    "claim":    "the sentence where the speaker says what the clip is about, the words "',
     "claim: defined in footage terms", _INJECTS),
    ("the silent-route block is moved into the shared prompt",
     '               + visual_purpose_block() + "\\n")',
     '               + "\\n")',
     "wired into the NO SPEECH branch", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="vv_")
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
        print("BASELINE IS NOT GREEN:\n" + out[-1200:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, old, new, expect, precond in MUTATIONS:
        txt = APP.read_text(); n = txt.count(old)
        if n != 1:
            harness.append(f"{label}: anchor {n}x")
            print(f"  HARNESS FAILURE  {label}  :: anchor {n}x"); continue
        _m = txt.replace(old, new, 1)
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
      + (f"; HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red == len(MUTATIONS) and not harness else 1)
