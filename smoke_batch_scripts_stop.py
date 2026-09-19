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
check("CONSTRAINT VIOLATED is a withheld export, not a cache fault (0), and the line names it", BV.verdict(rec("CONSTRAINT VIOLATED"))[0] == 0 and "CONSTRAINT VIOLATED" in BV.verdict(rec("CONSTRAINT VIOLATED"))[1])
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
# ---- ZAC'S BATCH (2026-09-18): the order, the two record shapes, the cold-by-design arm, the briefs reader ----
import batch_spend as BS                                         # noqa: E402
import batch_briefs as BB                                        # noqa: E402
batch = io.open(os.path.join(HERE, "scripts", "h_batch.sh"), encoding="utf-8").read()
bcode = "\n".join(l for l in batch.split("\n") if not l.lstrip().startswith("#"))
order = ["at ping;", "at probe2;", "at probe1;", "at th0;", "at thlow;", "at motion;", "at car;", "at nowatch;", "at briefs;"]
idx = [bcode.find(o) for o in order]
check("the batch runs in Zac's order: ping, G 2fps, G 1fps, H1 off, H1 low, no-speech, Zac's clip, no-watch, briefs", all(i >= 0 for i in idx) and idx == sorted(idx), str(idx))
check("the batch gates on G's control verdict before H1", "verdict $B/probe2.json" in bcode and bcode.index("verdict $B/probe2.json") < bcode.index("at th0;") and "STOP: A is red on G" in bcode)
check("every arm after H1 stops on an API refusal", bcode.count("[ $rc -ne 2 ] ||") >= 6, str(bcode.count("[ $rc -ne 2 ] ||")))
check("the briefs come from Builder-2's file through the reader and the brief stage", "batch_briefs.py" in bcode and "fixtures/production_briefs.v1.jsonl" in bcode and "BRIEF_FILE=$bfile sh $SC/h_stage.sh brief" in bcode)
check("G's sheets come out of the results store for Zac's eye, both densities", "sheets probe-rewatch-2fps probe2" in bcode and "sheets probe-rewatch-1fps probe1" in bcode)
stg = io.open(os.path.join(HERE, "scripts", "h_stage.sh"), encoding="utf-8").read()
check("h_stage runs G at 2 fps and at 1 fps into distinct records", "--out /tmp/bs/probe2.json --density-fps 2" in stg and "--out /tmp/bs/probe1.json --density-fps 1" in stg)
check("the brief stage takes its text from a file, never the command line", "--brief-file '$BRIEF_FILE'" in stg and "--brief '$BRIEF" not in stg)
check("the off ping runs again before H1 and before the off-arm stages that follow the low ping (the preflight compares against the LAST ping)",
      re.search(r"at th0; then\nping warm", bcode) is not None and re.search(r"at motion; then ping warm;", bcode) is not None)
check("every launch of the batch carries its own run ids (last batch's job state must never be reused)", "export RUNSFX=" in bcode and bcode.count("$RUNSFX") >= 10 and "--run-id h-th-think0$RUNSFX" in stg)
check("the no-watch stage carries no ping and no pinning (cold by design)", re.search(r"nowatch\)[^\n]*--no-watch", stg) is not None and "ping " not in bcode.split("at nowatch;")[1].split("at briefs;")[0])
def prec(cold=False, api=None, head="", fp=0):
    return {"density_fps": 2.0, "control": {"cold_write": {"cold": cold, "write": 200000 if cold else 1000, "read": 1000 if cold else 226000}, "api_status": api, "api_head": head, "false_positives": fp, "wall_s": 40.0, "request_mb": 20.1},
            "review": {"named": {}, "api_status": 200, "wall_s": 41.0, "request_mb": 22.0}}
check("a clean probe is 0", BV.verdict(prec())[0] == 0)
check("a cold write on the probe's control review is A-red (1)", BV.verdict(prec(cold=True))[0] == 1)
check("a refused or failed probe call is a stop (2)", BV.verdict(prec(api=409, head="preflight_refused"))[0] == 2 and BV.verdict(prec(api=400))[0] == 2)
check("the probe's line names the false positives and the density", "false_positives=3" in BV.verdict(prec(fp=3))[1] and "density=2.0" in BV.verdict(prec())[1])
def rec2(cold, no_watch, kind=None):
    r = rec(kind=kind, cold=cold); r["run_line"]["no_watch"] = no_watch; return r
rc_nw, ln_nw = BV.verdict(rec2(True, True))
check("a cold write on the no-watch arm is by design (0), the line says so", rc_nw == 0 and "COLD BY DESIGN" in ln_nw, ln_nw[-80:])
check("a cold write with the watch is still A-red (1)", BV.verdict(rec2(True, False))[0] == 1)
check("a within-run CACHE MISS on the no-watch arm is still red", BV.verdict(rec2(False, True, "CACHE MISS"))[0] == 1)
# the reader, driven on five rows: three slots, one unrunnable fixture, one unreadable line, one surplus preset
d3 = tempfile.mkdtemp(prefix="briefs_")
rows = ['{"id": "b2-preset", "fixture": "car_mid", "request_class": "PRESET_PLUS_MODIFIER", "flags": {"negative_constraint": false}, "brief": "Make this a smooth video, add zooms", "asks": [{"n": 1, "expect": "HONORED", "means": "at least one zoom item"}, {"n": 2, "expect": "HONORED"}]}',
        '{"id": "b2-caps", "fixture": "talking_head", "request_class": "PRESET_PLUS_MODIFIER", "flags": {"negative_constraint": true}, "brief": "under one minute, without captions", "asks": [{"n": 1, "expect": "HONORED", "means": "timeline.duration_s < 60"}]}',
        '{"id": "pop-but-calm", "fixture": "talking_head", "kind": "preset+modifier", "brief": "punchy, but keep it calm in the middle", "expect": "HONORED", "means": "at least one zoom placed"}',
        '{"id": "no-caps", "fixture": "talking_head", "brief": "Tighten it up. No captions.", "expect": "HONORED", "means": "no caption track on the timeline"}',
        '{"id": "arabic-two-sources", "fixture": "pet_video", "brief": "cut the two clips together", "fixture_note": "second source not staged"}',
        'not json at all',
        '{"id": "structured-1", "fixture": "car_mid", "kind": "structured", "brief": {"goal": "a 15s teaser", "must": ["one title"]}, "expect": "NEGOTIATED"}',
        '{"id": "second-preset", "fixture": "talking_head", "kind": "preset", "brief": "cinematic with a fast open"}']
io.open(os.path.join(d3, "b.jsonl"), "w", encoding="utf-8").write("\n".join(rows) + "\n")
rb = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "batch_briefs.py"), os.path.join(d3, "b.jsonl"), os.path.join(d3, "out")], capture_output=True, text=True)
picks = [l.split("\t") for l in rb.stdout.strip().split("\n") if l.strip()]
check("the reader picks one row per slot, in file order, and exits 0", rb.returncode == 0 and [p[0] for p in picks] == ["b2-preset", "b2-caps", "structured-1"] and [p[3] for p in picks] == list(BB.SLOTS), rb.stdout[:200])
check("Builder-2's request_class is read, a preset brief carrying 'without captions' fills the constraint slot, and each ask's means travels with the pick",
      re.search(r"PICKED +b2-caps — no-captions constraint .*class PRESET_PLUS_MODIFIER .*n1 HONORED: timeline.duration_s < 60", rb.stderr) is not None
      and re.search(r"PICKED +b2-preset — preset\+modifier .*n2 HONORED: UNCHECKED \(no means\)", rb.stderr) is not None, rb.stderr[-500:])
check("the reader names an unrunnable row UNRUNNABLE by id", re.search(r"UNRUNNABLE +arabic-two-sources .*pet_video.*second source not staged", rb.stderr) is not None, rb.stderr[-300:])
check("an unreadable line is named by number, and the surplus presets are SKIPPED with the reason", "UNREADABLE line 6" in rb.stderr and re.search(r"SKIPPED +second-preset .*already filled by b2-preset", rb.stderr) is not None and re.search(r"SKIPPED +pop-but-calm .*already filled by b2-preset", rb.stderr) is not None, rb.stderr[-300:])
check("each pick maps its fixture NAME to the staged source key and writes the brief to a file", all(p[1].startswith("ab-sources/reliability-fixtures-v3/") and os.path.exists(p[2]) for p in picks))
check("a structured brief travels as JSON text the agent receives verbatim", json.loads(io.open(picks[2][2], encoding="utf-8").read()).get("goal") == "a 15s teaser")
check("a row without `means` is marked UNCHECKED", re.search(r"PICKED +structured-1 .*UNCHECKED \(no means\)", rb.stderr) is not None)
rb2 = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "batch_briefs.py"), os.path.join(d3, "none.jsonl"), os.path.join(d3, "out")], capture_output=True, text=True)
check("a missing fixture file is one UNREADABLE line and zero picks, exit 0 (the batch reports 'no briefs')", rb2.returncode == 0 and rb2.stdout.strip() == "" and "UNREADABLE" in rb2.stderr and "not landed" in rb2.stderr)
# spend counts both of G's calls
d4 = tempfile.mkdtemp(prefix="spend_")
json.dump({"density_fps": 2.0, "control": {"usage": {"cache_read_input_tokens": 1000000, "output_tokens": 0}}, "review": {"usage": {"cache_read_input_tokens": 1000000, "output_tokens": 0}}}, open(os.path.join(d4, "probe2.json"), "w"))
check("spend counts the control and the planted review (two calls)", abs(BS.total(d4, ping_logs=()) - 0.60) < 0.001, str(BS.total(d4, ping_logs=())))

print("%d failure(s)" % len(bad) if bad else "all legs green")
sys.exit(1 if bad else 0)
