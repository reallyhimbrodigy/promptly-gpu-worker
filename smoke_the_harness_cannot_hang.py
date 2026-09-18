#!/usr/bin/env python3
"""run_timed's timeout actually fires, and a big first message cannot deadlock it.

BOTH DEFECTS WERE MEASURED, and both became reachable when the single agent's
first message grew to 27.6 MB by carrying the ten reference sheets.

  1. THE DEADLINE ONLY TICKED WHEN OUTPUT ARRIVED. It was checked inside
     `for line in p.stdout`, so a child that goes SILENT — the exact failure a
     timeout exists for — blocked that loop forever and the check never ran.
     Measured: a 5-second timeout still running at 30 seconds. The run then
     burns to the container timeout and `killed` comes back False, so the
     record says the agent finished rather than that it hung.

  2. THE FIRST MESSAGE WAS WRITTEN SYNCHRONOUSLY, BEFORE ANY DRAIN STARTED.
     Harmless while it fitted in the 64K pipe buffer. At 27.6 MB the parent
     blocks until the child reads — and if the child writes before it reads,
     both sides block with neither the stderr drain nor the watchdog yet
     alive. Measured: a 10-second timeout had not returned at 60 seconds.

I GOT THIS WRONG IN BOTH DIRECTIONS BEFORE MEASURING IT, which is why the legs
below drive real subprocesses rather than reading the source. I first moved the
write to a thread on a hypothesis; a test appeared to confirm it and was wrong
in its own CHILD (`sys.stdin.read()` waits for EOF, where the real CLI reads
one line); I reverted on that bad evidence; then the child-shape table above
showed the hazard is real for one shape and absent for the other. A source-text
check would have been satisfied at every one of those steps.

THE LEGS:
  1. a SILENT child is killed on the deadline
  2. a child that WRITES BEFORE READING does not hang the parent
  3. a NORMAL child completes and is NOT killed — a timeout that fires on
     correct runs is not a timeout either

RED-proven at the bottom, against mutated copies of turn_clock.
"""
import ast
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CHILD = os.path.join(HERE, "smoke_fixtures", "hang_child.py")
SRC = open(os.path.join(HERE, "turn_clock.py"), encoding="utf-8").read()
fail = []

# big enough to exceed the pipe buffer by orders of magnitude, small enough to
# keep the smoke quick. The real message is 27.6 MB; 4 MB is the same regime.
BIG = json.dumps({"type": "user",
                  "message": {"content": [{"type": "text",
                                           "text": "A" * 4_000_000}]}})

RUNNER = r'''
import json, os, sys, time, threading
sys.path.insert(0, %(here)r)
threading.Thread(target=lambda: (time.sleep(%(outer)d),
                                 print("OUTER_TIMEOUT", flush=True),
                                 os._exit(9)), daemon=True).start()
ns = {"__name__": "tc_mutant"}
exec(compile(open(%(tc)r, encoding="utf-8").read(), "<tc>", "exec"), ns)
big = json.dumps({"type":"user","message":{"content":[
        {"type":"text","text":"A"*%(payload)d}]}})
t0 = time.time()
rc, err, wall, killed = ns["run_timed"](
    [sys.executable, %(child)r, %(mode)r], "/tmp",
    "/tmp/_hang_stream.jsonl", "/tmp/_hang_timing.json", %(timeout)d,
    stdin_first=big)
print(json.dumps({"elapsed": round(time.time()-t0, 1), "killed": bool(killed),
                  "rc": rc}), flush=True)
'''


def scenario(mode, timeout, outer, tc_path, payload=4_000_000):
    """Run one child shape against one copy of turn_clock. -> dict or None."""
    code = RUNNER % {"here": HERE, "tc": tc_path, "child": CHILD, "mode": mode,
                     "timeout": timeout, "outer": outer, "payload": payload}
    # ITS OWN PROCESS GROUP, KILLED WHOLE. The runner exits with os._exit on
    # OUTER_TIMEOUT, but the child it was timing inherits the captured pipes
    # and lives on — and capture_output then waits for EOF that never comes.
    # Measured 2026-09-17: this smoke sat 16 minutes inside the suite.
    import os as _os, signal as _sig
    _pp = subprocess.Popen([sys.executable, "-u", "-c", code],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, start_new_session=True)
    try:
        _out, _err = _pp.communicate(timeout=outer + 20)
    except subprocess.TimeoutExpired:
        _os.killpg(_pp.pid, _sig.SIGKILL)
        _out, _err = _pp.communicate()
        return {"hung": True, "note": "runner group killed after %ds" % (outer + 20)}
    finally:
        try:
            _os.killpg(_pp.pid, _sig.SIGKILL)
        except Exception:                                         # noqa: BLE001
            pass
    class _R:
        pass
    r = _R()
    r.stdout, r.stderr = _out, _err
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("{"):
            return json.loads(ln)
        if ln.strip() == "OUTER_TIMEOUT":
            return {"hung": True}
    return {"error": (r.stderr or "")[-200:]}


def legs(tc_path):
    out = []
    # 1. A SILENT CHILD IS KILLED ON THE DEADLINE
    s = scenario("silent", 4, 25, tc_path)
    if s.get("hung") or not s.get("killed"):
        out.append(("deadline",
                    "a child that printed once and went quiet was not killed "
                    "on a 4s deadline: %r" % s))
    elif s["elapsed"] > 12:
        out.append(("deadline",
                    "the deadline fired %.1fs late (4s timeout)" % s["elapsed"]))

    # 2. A CHILD THAT WRITES BEFORE READING DOES NOT HANG THE PARENT
    s = scenario("writes_first", 4, 25, tc_path)
    if s.get("hung"):
        out.append(("deadlock",
                    "the parent never returned: a multi-megabyte first "
                    "message written before any drain starts deadlocks "
                    "against a child that writes before it reads"))
    elif s.get("error"):
        out.append(("deadlock", "the run errored: %s" % s["error"]))

    # 3. A NORMAL CHILD COMPLETES AND IS NOT KILLED
    s = scenario("normal", 20, 30, tc_path)
    if s.get("hung") or s.get("error"):
        out.append(("normal", "a well-behaved child did not complete: %r" % s))
    elif s.get("killed"):
        out.append(("normal",
                    "a well-behaved child was KILLED — a deadline that fires "
                    "on correct runs is not a deadline"))
    return out


_TC = os.path.join(HERE, "turn_clock.py")
for k, m in legs(_TC):
    fail.append("[%s] %s" % (k, m))

# ── RED PROOF ────────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("the deadline goes back inside the output loop", "deadline",
     lambda s: s.replace("    threading.Thread(target=_watchdog, "
                         "daemon=True).start()", "    pass")),
    ("the first message is written synchronously again", "deadlock",
     lambda s: s.replace(
         "        threading.Thread(target=_write_first, daemon=True).start()",
         "        _write_first()")),
)
_tmp = os.path.join(HERE, "smoke_fixtures", "_tc_mutant.py")
for label, kind, mut in MUT:
    m = mut(SRC)
    if m == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        ast.parse(m)
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    # THE MUTANT IS A SEPARATE FILE, NEVER THE SHIPPED ONE. A red proof that
    # mutates the module in place and is killed between mutate and restore
    # leaves the mutant on disk — and no relocation of a backup reaches that.
    open(_tmp, "w", encoding="utf-8").write(m)
    try:
        hits = legs(_tmp)
    finally:
        try:
            os.remove(_tmp)
        except OSError:
            pass
    hit = any(k == kind for k, _ in hits)
    print("    %-48s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

if not MUT:
    print("  *** NO MUTATIONS — this proof asserts nothing")
    red += 1
for m in fail:
    print("  *** " + m)
print("\nsmoke_the_harness_cannot_hang: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red or not MUT) else 0)
