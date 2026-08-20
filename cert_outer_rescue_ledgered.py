#!/usr/bin/env python3
"""cert_outer_rescue_ledgered.py — THE RESCUE THAT FIRES MUST APPEAR IN THE LEDGER.

MEASURED, ON REAL TRAFFIC. Across 781 jobs (2026-08-16..18) the divergence
ledgers contained ZERO rows with component=outer — while 128 of those jobs
(16.4%) recorded the rescue's CONSEQUENCE as
`recipe:safe_edit_fallback original={'reason': 'outer:UNKNOWN'}`. The single
loudest event in a job's life — "everything failed, we re-ran it as a bare
mechanical cut so the user would get something" — was the one event the ledger
could not see.

THE MECHANISM, because it is not obvious and the naive fix does not work:

    _outer_safe_rescue()  ->  _record_divergence("outer", ...)   appended
                          ->  handler(job)                        RE-ENTRY
                              -> _DIVERGENCE_LOG.clear()          WIPED
                              -> ... -> flush to S3               rescue absent

Recording harder at the rescue site cannot fix this. The record must be
re-emitted INSIDE the run whose ledger actually flushes, which is why the marker
rides on input_data["_rescue_ledger"] and handler() re-records it immediately
after the clear.

CLAUSES:

  1  THE CARRY EXISTS. The rescue writes _rescue_ledger onto input_data, and it
     carries the error_code.
  2  THE RE-EMIT EXISTS, AND IS AFTER THE CLEAR. handler() re-records the carry,
     positioned after _DIVERGENCE_LOG.clear() — before it, the clear would wipe
     the re-emit too, which is the same bug with more steps.
  3  END TO END. Drive a real rescue with a real raised exception and assert a
     component=outer row is in _DIVERGENCE_LOG at the moment the inner run would
     flush. NOTE ITS LIMIT, so nobody trusts it for more than it proves: the
     stand-in inner run performs the clear-then-re-emit itself, so clause 3
     proves the CARRY survives a clear — it does not prove handler() re-emits.
     Clause 2 is what proves that, and clause 2 is what caught the original
     defect when it was re-introduced.
  4  UNKNOWN IS NAMED. The record carries exc_type, exc_msg and the INNERMOST
     frame. `traceback` is not module-scope in handler.py, so a missing local
     import silently loses the frame inside the fail-open except — clause 4 is
     what makes that regression loud.

    python3 cert_outer_rescue_ledgered.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")


def main():
    import handler as H
    src = open(H.__file__, encoding="utf-8").read()
    fails = []

    # ── 1: the carry ────────────────────────────────────────────────────────
    if 'input_data["_rescue_ledger"] = _detail' not in src:
        fails.append("the rescue does not write _rescue_ledger onto input_data — "
                     "nothing survives the inner run's clear")
    print(f"  [1] carry written by the rescue      : "
          f"{'input_data[\"_rescue_ledger\"] = _detail' in src}")

    # ── 2: the re-emit, AFTER the clear ─────────────────────────────────────
    i_clear = src.find("_DIVERGENCE_LOG.clear()   # LEDGER")
    i_reemit = src.find('_resc = input_data.get("_rescue_ledger")')
    ok_order = i_clear != -1 and i_reemit != -1 and i_reemit > i_clear
    print(f"  [2] re-emit exists and follows clear : {ok_order} "
          f"(clear@{i_clear}, re-emit@{i_reemit})")
    if not ok_order:
        fails.append("handler() does not re-record the carry AFTER "
                     "_DIVERGENCE_LOG.clear() — the rescue stays invisible")

    # ── 3: end to end, with a REAL exception ────────────────────────────────
    H._DIVERGENCE_LOG.clear()
    captured = {}

    def _fake_inner(job):
        # stands in for the inner handler run: clear (as handler does), then
        # re-emit the carry exactly as handler() now does.
        H._DIVERGENCE_LOG.clear()
        _resc = job["input"].get("_rescue_ledger")
        if isinstance(_resc, dict):
            H._record_divergence("outer", _resc, "safe_edit_rescue", reason="cert")
        captured["log"] = list(H._DIVERGENCE_LOG)
        return {"status": "success"}

    job = {"input": {"job_id": "cert", "video_url": "s3://x/y.mp4"}}
    state = {"mode": "full", "ready": True, "t0": __import__("time").time(),
             "dur": 30.0}
    try:
        raise ValueError("cert-injected orchestration failure")
    except ValueError:
        H._outer_safe_rescue(job, job["input"], {"error_code": "UNKNOWN"},
                             state, run_fn=_fake_inner)

    rows = [r for r in (captured.get("log") or [])
            if r.get("component") == "outer" and r.get("action") == "safe_edit_rescue"]
    print(f"  [3] component=outer rows after the inner clear: {len(rows)}")
    if not rows:
        fails.append("NO component=outer row survived the inner run's clear — "
                     "this is the original 0-of-781 defect")

    # ── 4: UNKNOWN is named ─────────────────────────────────────────────────
    if rows:
        d = rows[0].get("original") or {}
        print(f"      exc_type={d.get('exc_type')}  frame={d.get('frame')}")
        print(f"      exc_msg={str(d.get('exc_msg'))[:70]}")
        for field in ("exc_type", "exc_msg", "frame"):
            if not d.get(field):
                fails.append(f"the rescue record carries no `{field}` — UNKNOWN "
                             f"stays unnamed (check the local `import traceback` "
                             f"inside the capture block)")
        if d.get("exc_type") and d["exc_type"] != "ValueError":
            fails.append(f"captured the wrong exception: {d['exc_type']}")
        if d.get("frame") and not re.match(r"^[\w.]+:\d+:\w+$", d["frame"]):
            fails.append(f"frame is not file:line:function -> {d['frame']!r}")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT OUTER-RESCUE-LEDGERED: FAIL")
        return 1
    print("  CERT OUTER-RESCUE-LEDGERED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
