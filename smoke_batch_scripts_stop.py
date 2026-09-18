#!/usr/bin/env python3
"""THE PIPE RULE, MECHANICAL (Zac, Part 3 item G): every batch and probe script
sets pipefail and reads every verdict bare; the verdict module returns the
exit codes the batch reasons about; and a failing verdict planted behind a
`| tee` still stops a script that follows the rule."""
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import batch_verdict as BV                                       # noqa: E402

bad = []
def check(name, ok, why=""):
    print("  [%s] %s%s" % ("ok" if ok else "FAIL", name, ("" if ok else " :: " + why)))
    if not ok: bad.append(name)

# THE BATCH SCRIPTS ONLY (h_*.sh): scripts/ also holds other lanes' deploy.sh and smoke.sh
scripts = sorted(glob.glob(os.path.join(HERE, "scripts", "h_*.sh")))
check("there are batch scripts to check (population)", len(scripts) >= 3, "%d" % len(scripts))
for p in scripts:
    src = io.open(p, encoding="utf-8").read()
    code = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("#"))   # prose does not count (the rule's own comment matched the pattern)
    check("%s sets pipefail" % os.path.basename(p), "set -o pipefail" in code)
    check("%s never reads a verdict through a pipe" % os.path.basename(p), not re.search(r"verdict[^\n]*\|\s*tee", code), "a `verdict … | tee` would report tee's status")
# the verdict module's exit codes, driven
def rec(kind=None, cold=False, verdict=None):
    return {"three_turns": {"terminal": ({"kind": kind} if kind else None), "cold_write": {"cold": cold, "write": 1 if cold else 0, "read": 0 if cold else 1}, "verdict": verdict}, "run_line": {"api_calls": 4, "usd_cli": 1.0, "request_mb": [22.5]}}
check("a clean run is 0", BV.verdict(rec(verdict="export at turn 2 (clean)"))[0] == 0)
check("CACHE MISS is A-red (1)", BV.verdict(rec("CACHE MISS"))[0] == 1)
check("a cold write at call 1 is A-red (1) — the cross-run half", BV.verdict(rec(cold=True))[0] == 1)
check("API ERROR and PREFLIGHT REFUSED are stops (2)", BV.verdict(rec("API ERROR"))[0] == 2 and BV.verdict(rec("PREFLIGHT REFUSED"))[0] == 2)
check("TURN CAP alone is not a cache fault (0)", BV.verdict(rec("TURN CAP"))[0] == 0)
# a failing verdict planted behind a tee: the batch's own verdict() shape must still stop
d = tempfile.mkdtemp(prefix="pipe_")
r = json.dump(rec("API ERROR"), open(os.path.join(d, "r.json"), "w"))
script = """#!/bin/sh
set -u
set -o pipefail
python3 %s %s > %s/v.txt; rc=$?; cat %s/v.txt | tee -a %s/ledger >/dev/null
[ $rc -eq 0 ] || { echo STOPPED; exit 5; }
echo CONTINUED
""" % (os.path.join(HERE, "scripts", "batch_verdict.py"), os.path.join(d, "r.json"), d, d, d)
open(os.path.join(d, "s.sh"), "w").write(script)
out = subprocess.run(["sh", os.path.join(d, "s.sh")], capture_output=True, text=True)
check("a failing verdict behind a tee stops the script (exit 5, STOPPED, never CONTINUED)",
      out.returncode == 5 and "STOPPED" in out.stdout and "CONTINUED" not in out.stdout, "rc=%d out=%r" % (out.returncode, out.stdout[:80]))
# and the anti-pattern really does lie, so the rule is about something
bad_script = "#!/bin/sh\npython3 %s %s | tee -a %s/ledger2 >/dev/null; rc=$?\n[ $rc -eq 0 ] || exit 5\necho CONTINUED\n" % (os.path.join(HERE, "scripts", "batch_verdict.py"), os.path.join(d, "r.json"), d)
open(os.path.join(d, "bad.sh"), "w").write(bad_script)
out2 = subprocess.run(["sh", os.path.join(d, "bad.sh")], capture_output=True, text=True)
check("(control) the piped form without pipefail CONTINUES past the same failing verdict", "CONTINUED" in out2.stdout, out2.stdout[:80])
print("%d failure(s)" % len(bad) if bad else "all legs green")
sys.exit(1 if bad else 0)
