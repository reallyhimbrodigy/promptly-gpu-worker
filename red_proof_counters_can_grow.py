#!/usr/bin/env python3
"""RED proof for smoke_counters_can_grow.py, in a throwaway worktree.

EVERY MUTATION HERE MUTATES AN ARTIFACT THE GATE READS — the app or the census
— NEVER THE GATE ITSELF, and that is a correction worth keeping. The first
version mutated the SMOKE's own legs and reported 4 of 5 "NOT RED": weakening a
check makes it PASS, so `mutant passed` was the EXPECTED outcome and the
harness was reading it as a failure. A red proof whose expectation points the
wrong way measures nothing in either direction.

So: plant the offender, and the UNMUTATED gate must reject it.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

import red_proof_anchor

SMOKE = pathlib.Path("smoke_counters_can_grow.py").resolve()
CENSUS = pathlib.Path("zero_counters_census.md").resolve()
APPNAME = "agentic_editor_app.py"
CENSUSNAME = CENSUS.name
# (label, target, old, new, expected message)
MUTATIONS = [
    ("the phantom shape returns to the app", APPNAME,
     '    led["inputs"] = _inputs',
     '    led["phantom_probe"] = led.get("phantom_probe", 0)\n    led["inputs"] = _inputs',
     "no ledger key is assigned from its own"),
    ("a counter disappears from the census", CENSUSNAME,
     "| `knowledge_reads` |", "| `knowledge_READS_renamed` |",
     "every always-zero counter from the census is named"),
    ("the census drops its denominator", CENSUSNAME,
     "**Denominator: 28 ledgers, rounds 51-60**",
     "**Denominator: some ledgers**",
     "states the denominator"),
    ("the census stops recording the phantom as FIXED", CENSUSNAME,
     "**NO WIRE — FIXED 2026-09-11**", "**NO WIRE**",
     "recorded as FIXED"),
    ("a counter's row loses its classification", CENSUSNAME,
     "| `cmds` | UNREACHED |", "| `cmds` |  |",
     "every row carries one of the three classifications"),
    ("a whole class stops being used by any row", CENSUSNAME,
     "| **NO WIRE — FIXED 2026-09-11** |", "| UNREACHED |",
     "class is actually used by a row"),
    # THE READER DENOMINATOR. Both reader zeros had ONE cause: every run was
    # Haiku and the judgment-only filter strips them, so the counters were
    # offered in 0 of 37 runs. A zero without its chances is not a measurement.
    ("the reader denominator stops being recorded", APPNAME,
     '    led["readers_offered"] = sorted(',
     '    _dropped_offered = sorted(',
     "readers_offered"),
    ("the denominator is ledgered but never printed", APPNAME,
     '    print("  READERS         : offered %s   withheld %s%s"',
     '    print("  readers_renamed : offered %s   withheld %s%s"',
     "PRINTED"),
    ("the denominator is restated from the model name instead of read off the "
     "tool list the agent actually got", APPNAME,
     '        {t.get("name") for t in tools} & _READERS)',
     '        (set() if _judgment_only else _READERS))',
     "read off the tool list itself"),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="ctr_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    _orig = {n: (pathlib.Path(_wt) / n).read_text()
             for n in (APPNAME, CENSUSNAME)}
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, target, old, new, expect in MUTATIONS:
        _tgt = pathlib.Path(_wt) / target
        _mode, _m = red_proof_anchor.apply_one(_tgt.read_text(), old, new)
        if _m is None:
            harness.append(f"{label}: anchor {_mode}")
            print(f"  HARNESS FAILURE  {label}  :: anchor {_mode}"); continue
        if _mode != red_proof_anchor.EXACT:
            print(f"  note             {label}  :: matched {_mode}")
        if target.endswith(".py"):
            try:
                ast.parse(_m)
            except SyntaxError as e:
                harness.append(f"{label}: mutant does not parse")
                print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})")
                continue
        _tgt.write_text(_m); mrc, mout = run(_wt); _tgt.write_text(_orig[target])
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
