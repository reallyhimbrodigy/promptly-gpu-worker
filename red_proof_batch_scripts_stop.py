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
STAGE = os.path.join(HERE, "scripts", "h_stage.sh")
BRIEFS = os.path.join(HERE, "scripts", "batch_briefs.py")

MUTATIONS = [
    ("an API refusal is no longer a stop", VERDICT,
     '    if t in ("API ERROR", "PREFLIGHT REFUSED"):\n        return 2, line',
     '    if t in ("PREFLIGHT REFUSED",):\n        return 2, line',
     "API ERROR and PREFLIGHT REFUSED are stops (2)"),
    ("a cold write at call 1 is no longer A-red", VERDICT,
     '    if cw.get("cold"):\n        return 1, line',
     '    if False:\n        return 1, line',
     "a cold write at call 1 is A-red (1) — the cross-run half"),
    ("the batch drops pipefail", BATCH,
     "set -u\nset -o pipefail\n",
     "set -u\n",
     "h_batch.sh sets pipefail"),
    # ZAC'S BATCH (2026-09-18)
    ("the ping fires after G", BATCH,
     "if at ping; then ping warm; fi\n# 2. G at 2 fps with its negative control (the control's call is the first job-shaped call after the ping: a cold write here is the cross-run fault, before H1 spends)\nif at probe2; then\nprobe probe2 || exit 4\nverdict $B/probe2.json; rc=$?; [ $rc -eq 0 ] || { log \"STOP: A is red on G (rc=$rc)\"; exit 5; }\nsheets probe-rewatch-2fps probe2; cap_or_stop\nfi\n",
     "# 2. G at 2 fps with its negative control (the control's call is the first job-shaped call after the ping: a cold write here is the cross-run fault, before H1 spends)\nif at probe2; then\nprobe probe2 || exit 4\nverdict $B/probe2.json; rc=$?; [ $rc -eq 0 ] || { log \"STOP: A is red on G (rc=$rc)\"; exit 5; }\nsheets probe-rewatch-2fps probe2; cap_or_stop\nfi\nif at ping; then ping warm; fi\n",
     "the batch runs in Zac's order: ping, G 2fps, G 1fps, H1 off, H1 low, no-speech, Zac's clip, no-watch, briefs"),
    ("G's control is no longer gated", BATCH,
     'verdict $B/probe2.json; rc=$?; [ $rc -eq 0 ] || { log "STOP: A is red on G (rc=$rc)"; exit 5; }',
     'verdict $B/probe2.json; rc=$?',
     "the batch gates on G's control verdict before H1"),
    ("a cold control review is waved through", VERDICT,
     '    if (c.get("cold_write") or {}).get("cold"):\n        return 1, line',
     '    if False:\n        return 1, line',
     "a cold write on the probe's control review is A-red (1)"),
    ("the no-watch cold is red again", VERDICT,
     '    if cw.get("cold") and rl.get("no_watch"):',
     '    if False:',
     "a cold write on the no-watch arm is by design (0), the line says so"),
    ("the 1 fps arm runs at 2", STAGE,
     '--out /tmp/bs/probe1.json --density-fps 1"',
     '--out /tmp/bs/probe1.json --density-fps 2"',
     "h_stage runs G at 2 fps and at 1 fps into distinct records"),
    ("Builder-2's class is not read", BRIEFS,
     '    kind = str(_first(row, "request_class", "kind", "category", "class", "type", "slot") or "").lower()',
     '    kind = str(_first(row, "kind", "category", "class", "type", "slot") or "").lower()',
     "Builder-2's request_class is read, a preset brief carrying 'without captions' fills the constraint slot, and each ask's means travels with the pick"),
    ("an unrunnable row is renamed", BRIEFS,
     'report("UNRUNNABLE", rid,',
     'report("SKIPPED", rid,',
     "the reader names an unrunnable row UNRUNNABLE by id"),
    ("the surplus preset is picked too", BRIEFS,
     '        if slot in picked:\n            report("SKIPPED", rid, "slot %s already filled by %s" % (slot, picked[slot])); continue\n',
     '',
     "the reader picks one row per slot, in file order, and exits 0"),
]
ORIG = {}


def run():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    for p in (VERDICT, BATCH, STAGE, BRIEFS):
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
