"""120s cap ruling (Zac 2026-07-11): make-it-honest + MEASURE-it.

The intake duration reject stays at 120s, but every rejection must emit a
grep-stable `intake_rejected` measurement (reason + measured source length)
so the weekly table can count how many real uploads the 2-minute limit turns
away — that count is the data for whether the limit should rise. Deterministic,
offline (no LLM / render)."""
import contextlib
import io
import sys

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


if not hasattr(H, "_log_intake_reject"):
    print("  FAIL  _log_intake_reject not implemented yet (RED)")
    print("\n=== RESULT: 0 passed, 1 failed ===")
    sys.exit(1)


# ─── the measurement fires with reason + measured source length + cap ───────
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    H._log_intake_reject("CLIP_TOO_LONG", 149.9, 120.0)
_out = _buf.getvalue()
check("emits a grep-stable intake_rejected event",
      "action=intake_rejected" in _out and "component=intake" in _out, _out)
check("carries the reason", "reason=CLIP_TOO_LONG" in _out, _out)
check("carries the measured source length", "149.9" in _out, _out)
check("carries the cap", "120" in _out, _out)

# ─── structured ledger entry (the weekly-table source, flushed to S3) ───────
_before = len(H._DIVERGENCE_LOG)
with contextlib.redirect_stdout(io.StringIO()):
    H._log_intake_reject("CLIP_TOO_LONG", 200.0, 120.0)
check("appends a structured ledger entry", len(H._DIVERGENCE_LOG) == _before + 1)
_last = H._DIVERGENCE_LOG[-1]
check("ledger tagged component=intake action=intake_rejected",
      _last.get("component") == "intake" and _last.get("action") == "intake_rejected", _last)
check("ledger carries the measured source length",
      (_last.get("original") or {}).get("source_s") == 200.0, _last)

# ─── fail-open: a measurement must NEVER raise into a reject ─────────────────
try:
    with contextlib.redirect_stdout(io.StringIO()):
        H._log_intake_reject("CLIP_TOO_LONG", None, None)
    check("fail-open on None source length (never raises)", True)
except Exception as e:
    check("fail-open on None source length (never raises)", False, repr(e))

# ─── WIRED at the 120s reject site, and BEFORE the raise ────────────────────
_src = open("handler.py").read()
check("wired at the 120s reject site",
      '_log_intake_reject("CLIP_TOO_LONG", source_duration' in _src)
# the measurement must precede the raise (measured, THEN rejected)
_seam = _src.split("if mode == \"full\" and source_duration > _MAX_SOURCE_DURATION_S:", 1)
if len(_seam) == 2:
    _w = _seam[1][:400]
    check("measurement precedes the raise",
          "_log_intake_reject(" in _w and _w.index("_log_intake_reject(") < _w.index("raise RuntimeError"), _w)
else:
    check("reject site present", False, "cap guard not found")


print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL INTAKE-REJECT MEASURE CASES PASS")
