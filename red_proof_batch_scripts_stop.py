#!/usr/bin/env python3
"""RED PROOF for smoke_batch_scripts_stop: a verdict module that waves an API
refusal through, and a batch script that drops pipefail, must each turn the
gate red."""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_batch_scripts_stop.py")
VERDICT = os.path.join(HERE, "scripts", "batch_verdict.py")
BATCH = os.path.join(HERE, "scripts", "h_batch.sh")

MUTATIONS = [
    ("an API refusal is no longer a stop", VERDICT,
     '    if t in ("API ERROR", "PREFLIGHT REFUSED"):\n        return 2, line',
     '    if t in ("PREFLIGHT REFUSED",):\n        return 2, line',
     "API ERROR and PREFLIGHT REFUSED are stops (2)"),
    ("a cold write at call 1 is no longer A-red", VERDICT,
     '    if t == "CACHE MISS" or cw.get("cold"):',
     '    if t == "CACHE MISS":',
     "a cold write at call 1 is A-red (1) — the cross-run half"),
    ("the batch drops pipefail", BATCH,
     "set -u\nset -o pipefail\n",
     "set -u\n",
     "h_batch.sh sets pipefail"),
]
ORIG = {}


def run():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    for p in (VERDICT, BATCH):
        ORIG[p] = io.open(p, encoding="utf-8").read()
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: the unmutated gate is not green (rc=%d)\n%s" % (rc, out[-600:]))
        sys.exit(2)
    red = 0
    for label, path, old, new, leg in MUTATIONS:
        src = ORIG[path]
        if src.count(old) != 1:
            print("HARNESS FAILURE: %s — anchor %dx" % (label, src.count(old)))
            sys.exit(2)
        mutant = src.replace(old, new)
        if path.endswith(".py"):
            try:
                ast.parse(mutant)
            except SyntaxError as e:
                print("HARNESS FAILURE: %s — mutant will not parse: %s" % (label, e))
                sys.exit(2)
        io.open(path, "w", encoding="utf-8").write(mutant)
        try:
            rc2, out2 = run()
        finally:
            io.open(path, "w", encoding="utf-8").write(src)
        hit = rc2 != 0 and ("[FAIL] %s" % leg) in out2
        print("  [%s] %s (rc=%d, leg named=%s)" % ("RED" if hit else "NOT RED", label, rc2, ("[FAIL] %s" % leg) in out2))
        red += 1 if hit else 0
    residue = [p for p in ORIG if io.open(p, encoding="utf-8").read() != ORIG[p]]
    for p in residue:
        io.open(p, "w", encoding="utf-8").write(ORIG[p]); print("RESIDUE: %s left mutated — restored" % os.path.relpath(p, HERE))
    print("%d/%d RED-proven" % (red, len(MUTATIONS)))
    sys.exit(0 if red and red == len(MUTATIONS) and not residue else 1)


if __name__ == "__main__":
    main()
