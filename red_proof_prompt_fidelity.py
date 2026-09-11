#!/usr/bin/env python3
"""RED proof for smoke_prompt_fidelity.py, in a throwaway worktree.

The mutations are the ways an unfaithful edit reads as a successful run: the
missing direction going unmeasured, an overreach being tolerated, a cut-only
request always reading SHORT, and UNSCOPED quietly becoming a pass.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_prompt_fidelity.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("the MISSING direction stops being measured",
     "    _missing = sorted(_asked - _built)", "    _missing = []",
     "delivering nothing is SHORT", _INJECTS),
    ("an overreach is tolerated",
     "    _unasked = sorted(_built - _asked)", "    _unasked = []",
     "also ships zooms has OVERREACHED", _INJECTS),
    ("a cut-only request always reads SHORT",
     '    if cut_made:\n        _built.add("cut")', "    if False:\n        pass",
     "FAITHFUL when only a cut happened", _INJECTS),
    ("UNSCOPED quietly becomes a pass",
     '        return (FIDELITY_UNSCOPED, [], sorted(_built),',
     '        return (FIDELITY_OK, [], sorted(_built),',
     "full_edit is UNSCOPED, not FAITHFUL", _INJECTS),
    ("captions are disconnected from the ledger — a constant keeps every substring",
     '        captions_made=bool(led.get("caption_composited")))',
     '        captions_made=False)',
     "passes captions_made from the ledger", _INJECTS),
    ("cut_made becomes presence again — the round-52 whole-source span reads as a cut",
     '    _cut_made = bool(led.get("keep_spans")) and _srcd > 0 and _kept < (_srcd - 0.05)',
     '    _cut_made = bool(led.get("keep_spans"))',
     "kept total < source duration", _INJECTS),
    ("the overreach stops failing loudly",
     '        fail("fidelity_overreached",', '        _quiet("fidelity_overreached",',
     "OVERREACHED fails loudly", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="fid_")
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
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
