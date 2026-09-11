#!/usr/bin/env python3
"""RED proof for smoke_beat_text_slice.py, in a throwaway worktree.

The mutations are the four producer defects returning, plus the two ways the
new measurement could go quiet: the halves copy the parent again, the figure
loses its instant, the brief hides it, the card anchors on the beat start
again, the placement record drops its moment, the lead mixes clocks, and the
print is demoted to a logger nobody reads.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_beat_text_slice.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("both halves copy the parent's sentence again",
     '            left["text"], right["text"] = split_beat_text(b, t, words)',
     '            left["text"], right["text"] = (str(b.get("text") or ""),) * 2',
     "halves with their own words", _INJECTS),
    ("the figure loses its instant",
     '        _b["figure_t"] = figure_instant(_b, _numeric_ts) if _b["has_number"] else None',
     '        _b["figure_t"] = None',
     "assigned FROM figure_instant", _INJECTS),
    ("the brief hides the instant",
     '            return "  (figure: %s spoken @%.2fs)" % (b["figure"], float(b["figure_t"]))',
     '            return "  (figure: %s)" % b["figure"]',
     "figure_note shows the instant", _INJECTS),
    ("the card anchors on the beat start again",
     '            at = src_to_out(_card_src_t, merged)',
     '            at = src_to_out(b["t_start"], merged)',
     "src_to_out of that chosen instant", _INJECTS),
    ("the placement record drops its moment",
     '                         "t_moment": _it2.get("anchor_s", _it2.get("t")),\n',
     '',
     "carries t_moment", _INJECTS),
    ("the lead mixes clocks — output anchor minus source instant",
     '                 "lead_s": (round(float(at) - float(_ft_out), 2) if _ft_out is not None else None),',
     '                 "lead_s": (round(float(at) - float(_ft), 2) if _ft is not None else None),',
     "ON THE OUTPUT CLOCK", _INJECTS),
    ("the print is demoted to a logger nobody reads",
     '        print("  CARD vs FIGURE  : n=%d',
     '        logging.debug("  CARD vs FIGURE  : n=%d',
     "PRINTED, reading the ledgered list", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="bts_")
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
            print(f"  WRONG REASON     {label}  :: expected '{expect}'\n{mout[-500:]}")
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
