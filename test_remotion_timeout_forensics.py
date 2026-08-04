"""RENDER_FATAL forensics — the subprocess TIMEOUT path must not discard evidence.

WHY THIS EXISTS
---------------
`_run_remotion` calls `subprocess.run(..., capture_output=True, timeout=N)`. On a
timeout CPython kills the child and raises `TimeoutExpired` — and on POSIX that
exception ALREADY CARRIES every byte the child wrote before the kill, in
`.stdout` / `.stderr`. Nothing read them. `str(TimeoutExpired)` prints only the
argv and the budget, so the render's own progress lines were thrown away unread.

That is why RENDER_FATAL was "the one class with no raw evidence": 13 of 14
prod RENDER_FATALs in the 2026-07-25..08-01 window were this timeout, and every
one of them landed in the job row as a bare
`TimeoutExpired: Command '[...]' timed out after 300 seconds`. The Modal log
buffer only retains ~1h, so by the time anyone looked the container stdout was
gone too. The evidence existed in memory and was dropped on the floor.

THE DURABILITY CONSTRAINT (why the digest must be FRONT-LOADED)
---------------------------------------------------------------
`_render_degrade_ladder` truncates the cause with `str(_render_err)[:300]`, and
that truncated string is what reaches `result.error_detail` — the only durable
record. So the forensics must fit in the first 300 characters or they do not
survive to the DB. This test pins that budget.
"""
import os
import subprocess
import sys
import tempfile

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


# A stand-in renderer that emits Remotion-shaped progress on stdout and a
# warning on stderr, then hangs past the budget — the exact geometry of a
# micro chunk that is rendering fine, just slower than its budget.
_FAKE_RENDERER = r'''
import sys, time
print("[render-full] composition=PromptlyMicroSegments (ProRes 4444 no-alpha) "
      "chunk frames 0-2249 (compositionStart=0), 41 segments, concurrency=4", flush=True)
sys.stderr.write("Detected differing memory amounts:\nMemory reported by CGroup: 999 MB\n")
sys.stderr.flush()
print("[render-full] progress 10% rendered=225 encoded=210 "
      "interval_render_fps=7.4 interval_encode_fps=7.0", flush=True)
print("[render-full] progress 20% rendered=450 encoded=441 "
      "interval_render_fps=6.1 interval_encode_fps=6.0", flush=True)
time.sleep(600)
'''

_FAKE_OK = r'''
print("[render-full] progress 100% rendered=10 encoded=10")
'''

_FAKE_CRASH = r'''
import sys
sys.stderr.write("Detected differing memory amounts:\nnoise noise noise\n")
sys.stderr.write("TypeError: Pixel format was set to yuva444p10le\n")
sys.exit(1)
'''


def _script(body):
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(body)
    return path


print("=== T0: the timeout path is reachable as a module-level helper ===")
_fn = getattr(H, "_remotion_subprocess", None)
check("handler._remotion_subprocess exists (unit-testable error path)", callable(_fn))
if not callable(_fn):
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1)

print("\n=== T1: TIMEOUT — the child's captured output survives into the raised error ===")
_p = _script(_FAKE_RENDERER)
err = None
try:
    _fn("micro-00", [sys.executable, "-u", _p], timeout=3)
except Exception as e:
    err = e
os.unlink(_p)

check("raises (does not silently succeed)", err is not None)
check("raises RuntimeError, not bare TimeoutExpired "
      "(stable shape for classify_error + the ladder signature)",
      isinstance(err, RuntimeError) and not isinstance(err, subprocess.TimeoutExpired),
      type(err).__name__)
check("chains the original TimeoutExpired as __cause__",
      isinstance(getattr(err, "__cause__", None), subprocess.TimeoutExpired),
      type(getattr(err, "__cause__", None)).__name__)

msg = str(err or "")
head = msg[:300]   # <- the ONLY part that reaches result.error_detail

check("names the failing label", "micro-00" in msg, msg[:200])
check("says TIMEOUT (not a generic failure)", "TIMEOUT" in msg.upper(), msg[:200])
check("carries the budget that was exceeded", "3" in msg and "budget" in msg.lower(), msg[:200])

# The whole point: how far did it get before the kill?
check("carries rendered-frame progress from the child's stdout",
      "rendered=450" in msg, msg[:300])
check("carries encoded-frame progress from the child's stdout",
      "encoded=441" in msg, msg[:300])
check("carries the last observed render fps",
      "6.1" in msg, msg[:300])

print("\n=== T2: the digest survives the ladder's [:300] truncation (durability) ===")
check("progress digest is inside the first 300 chars (reaches result.error_detail)",
      "rendered=450" in head and "encoded=441" in head, repr(head))
check("label is inside the first 300 chars", "micro-00" in head, repr(head))
check("TIMEOUT verdict is inside the first 300 chars", "TIMEOUT" in head.upper(), repr(head))

print("\n=== T3: the ladder wrap keeps the digest (end-to-end durability) ===")
# Exactly what _render_degrade_ladder does to the cause at rung >= 2.
_laddered = (f"RENDER_FATAL after full + retry + stripped renders: "
             f"{type(err).__name__}: {str(err)[:300]}")
check("laddered error_detail still names the composition chunk",
      "micro-00" in _laddered, _laddered[:400])
check("laddered error_detail still carries frame progress",
      "rendered=450" in _laddered, _laddered[:400])
check("laddered error_detail still classifies RENDER_FATAL",
      H.classify_error(RuntimeError(_laddered))["error_code"] == "RENDER_FATAL",
      H.classify_error(RuntimeError(_laddered))["error_code"])

print("\n=== T4: non-timeout paths unchanged (no regression) ===")
_p = _script(_FAKE_OK)
_ok_err = None
_elapsed = None
try:
    _elapsed = _fn("micro-ok", [sys.executable, "-u", _p], timeout=60)
except Exception as e:
    _ok_err = e
os.unlink(_p)
check("rc=0 returns elapsed seconds", _ok_err is None and isinstance(_elapsed, float),
      f"{_ok_err} / {_elapsed}")

_p = _script(_FAKE_CRASH)
_crash_err = None
try:
    _fn("micro-crash", [sys.executable, "-u", _p], timeout=60)
except Exception as e:
    _crash_err = e
os.unlink(_p)
check("rc!=0 still raises RuntimeError", isinstance(_crash_err, RuntimeError))
check("rc!=0 keeps SIGNATURE-FIRST ordering (real error before the memory noise)",
      _crash_err is not None
      and str(_crash_err).index("TypeError") < str(_crash_err).index("differing memory"),
      str(_crash_err)[:300])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
