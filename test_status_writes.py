"""Always-tell (P2) — terminal status writes fire on every exit path.

Flag-ON harness: a stub supabase client records every patch; the REAL
write_job_status and the REAL handler() failure paths are driven end to end.
"""
import contextlib
import io
import os
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

class StubSupabase:
    """Models the fence: `.not_.in_(status_col, vals)` declines when the row's
    current status is in vals — mirroring PostgREST's conditional UPDATE.
    row_status defaults to 'processing' so every pre-fence case still lands."""
    def __init__(self):
        self.patches = []      # (table, patch, job_id)
        self.raise_next = False
        self.row_status = "processing"
    def table(self, name):
        outer = self
        class _Resp:
            def __init__(self, data):
                self.data = data
        class _T:
            def update(self, patch):
                class _U:
                    def eq(self, col, jid):
                        class _E:
                            @property
                            def not_(_s):
                                class _N:
                                    def in_(_n, col2, vals):
                                        class _F:
                                            def execute(_f):
                                                if outer.raise_next:
                                                    outer.raise_next = False
                                                    raise RuntimeError("supabase down")
                                                if outer.row_status in tuple(vals):
                                                    return _Resp([])  # fence declines
                                                outer.patches.append((name, patch, jid))
                                                return _Resp([{"id": jid}])
                                        return _F()
                                return _N()
                            def execute(_s):
                                # unfenced legacy chain (kept so a regression to it FAILS loudly)
                                if outer.raise_next:
                                    outer.raise_next = False
                                    raise RuntimeError("supabase down")
                                outer.patches.append((name, patch, jid, "UNFENCED"))
                                return _Resp([{"id": jid}])
                        return _E()
                return _U()
        return _T()

def flag_on(fn):
    saved_env = os.environ.pop("JOB_STATUS_WRITES_ENABLED", None)
    saved_sb = H.supabase
    stub = StubSupabase()
    os.environ["JOB_STATUS_WRITES_ENABLED"] = "1"
    H.supabase = stub
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            out = fn(stub)
    finally:
        H.supabase = saved_sb
        os.environ.pop("JOB_STATUS_WRITES_ENABLED", None)
        if saved_env is not None:
            os.environ["JOB_STATUS_WRITES_ENABLED"] = saved_env
    return out, stub, buf.getvalue()

print("=== W1: terminal failed write lands (flag on) ===")
_, stub, _ = flag_on(lambda s: H.write_job_status(
    "j1", status="failed", phase="Something went wrong",
    result={"error_code": "UNKNOWN", "user_message": "x", "retryable": True}))
check("one patch recorded", len(stub.patches) == 1, str(stub.patches))
t, p, jid = stub.patches[0] if stub.patches else ("", {}, "")
check("targets video_jobs-configured table via env or default", t in ("jobs", "video_jobs"))
check("status=failed + result carried", p.get("status") == "failed"
      and p.get("result", {}).get("error_code") == "UNKNOWN" and jid == "j1")

print("\n=== W2: flag OFF -> zero writes (byte-identical default) ===")
saved_sb = H.supabase
stub2 = StubSupabase()
H.supabase = stub2
saved_env = os.environ.pop("JOB_STATUS_WRITES_ENABLED", None)
try:
    H.write_job_status("j1", status="failed", phase="x")
finally:
    H.supabase = saved_sb
    if saved_env is not None:
        os.environ["JOB_STATUS_WRITES_ENABLED"] = saved_env
check("zero patches with flag off", len(stub2.patches) == 0)

print("\n=== W3: fail-open — supabase raise never propagates ===")
def _w3(stub):
    stub.raise_next = True
    H.write_job_status("j1", status="failed", phase="x")
    return True
out, stub, o = flag_on(_w3)
check("no raise, fail-open log", out is True and "write failed job=j1" in o)

print("\n=== W4: handler MISSING_FIELDS path writes failed (job_id present) ===")
def _w4(stub):
    return H.handler({"input": {"job_id": "j-mf", "vibe": "v"}})  # missing video_url etc.
out, stub, _ = flag_on(_w4)
check("error envelope returned", isinstance(out, dict) and "Missing required" in str(out.get("error")), str(out))
fails = [p for (t, p, j) in stub.patches if p.get("status") == "failed" and j == "j-mf"]
check("terminal failed write fired", len(fails) == 1, str(stub.patches))
check("MISSING_FIELDS code carried", fails and fails[0]["result"]["error_code"] == "MISSING_FIELDS")

print("\n=== W5: handler outer-except path writes failed AFTER the rescue declines ===")
def _w5(stub):
    saved = H.fetch_user_tier
    H.fetch_user_tier = lambda uid: (_ for _ in ()).throw(RuntimeError("boom before pipeline"))
    try:
        return H.handler({"input": {"job_id": "j-exc", "video_url": "u", "vibe": "v",
                                    "user_id": "u1", "upload_url": "up"}})
    finally:
        H.fetch_user_tier = saved
out, stub, o = flag_on(_w5)
check("error envelope returned", isinstance(out, dict) and out.get("error_code"), str(out)[:120])
fails = [p for (t, p, j) in stub.patches if p.get("status") == "failed" and j == "j-exc"]
check("terminal failed write fired on the except path", len(fails) == 1, str(stub.patches))
check("rescue declined quietly (not ready), no engaged line",
      "engaged reason=outer" not in o)

print("\n=== W6: rescue-success path — terminal write comes from the INNER run ===")
def _w6(stub):
    job = {"input": {"job_id": "j-resc", "video_url": "u", "vibe": "v",
                     "user_id": "u1", "upload_url": "up"}}
    def fake_inner(j):
        H.write_job_status(j["input"]["job_id"], status="completed", phase="Done",
                           progress=100, result={"video_url": "https://cdn/v.mp4"})
        return {"status": "success", "video_url": "https://cdn/v.mp4"}
    import time as _t
    state = {"ready": True, "mode": "full", "dur": 30.0, "t0": _t.time()}
    return H._outer_safe_rescue(job, job["input"],
                                {"error_code": "UNKNOWN"}, state, run_fn=fake_inner)
out, stub, o = flag_on(_w6)
check("rescued payload returned", isinstance(out, dict) and out.get("status") == "success", str(out))
comp = [p for (t, p, j) in stub.patches if p.get("status") == "completed" and j == "j-resc"]
check("complete write landed via the inner run", len(comp) == 1, str(stub.patches))

print("\n=== W7: source pins — every early return is write-covered ===")
src = open("handler.py").read()
for _code, _n in (("MISSING_FIELDS", 2), ("TIER_CONCURRENCY", 1)):
    check(f"{_code} write present x{_n}", src.count(f'"error_code": "{_code}"') == _n)
_exc = src.find("classified = classify_error(e)")
_resc = src.find("_outer_safe_rescue(job, input_data, classified, _rescue_state)", _exc)
_failw = src.find('status="failed"', _resc)
check("except path: rescue precedes the failed write", -1 < _exc < _resc < _failw)


print("\n=== T-GUARD: first-terminal-wins — late async 'processing' cannot regress a terminal row ===")
def _guard_case(stub):
    H._JOB_TERMINAL_SEEN.discard("j-guard")
    H.write_job_status("j-guard", status="completed", phase="Done", progress=100, result={"ok": True})
    H.write_job_status("j-guard", status="processing", phase="Finalizing", progress=99)
    term = [p for (t_, p, j) in stub.patches if j == "j-guard"]
    check("terminal write landed", any(p.get("status") == "completed" for p in term))
    check("late processing write dropped entirely",
          not any(p.get("status") == "processing" for p in term) and len(term) == 1)
    H.write_job_status("j-guard", status="failed", phase="Something went wrong", progress=100)
    term2 = [p for (t_, p, j) in stub.patches if j == "j-guard"]
    check("a terminal RE-write still lands (needs_input->resume->terminal class)",
          any(p.get("status") == "failed" for p in term2))
flag_on(_guard_case)

print("=== F1: CANCEL FENCE — terminal write DECLINES on a canceled row ===")
def _fence_terminal(stub):
    stub.row_status = "canceled"
    H.write_job_status("j-fence1", status="completed", phase="Done", progress=100,
                       result={"video_url": "x", "vocab": {}})
_, stub, logs = flag_on(_fence_terminal)
check("no patch landed on the canceled row", len(stub.patches) == 0, str(stub.patches))
check("fence decline logged with matched=0",
      "fence declined job=j-fence1" in logs and "matched=0" in logs, logs[-200:])

print("\n=== F2: CANCEL FENCE — heartbeat tick (the RUN-3 resurrector) DECLINES ===")
def _fence_tick(stub):
    stub.row_status = "canceled"
    H.write_job_status("j-fence2", status="processing",
                       phase="Cutting your timeline", progress=72)
_, stub, logs = flag_on(_fence_tick)
check("tick did not land on the canceled row", len(stub.patches) == 0, str(stub.patches))

print("\n=== F3: CANCEL FENCE — failed rows equally fenced ===")
def _fence_failed(stub):
    stub.row_status = "failed"
    H.write_job_status("j-fence3", status="completed", phase="Done", progress=100,
                       result={"video_url": "x"})
_, stub, logs = flag_on(_fence_failed)
check("no resurrection of a failed row", len(stub.patches) == 0, str(stub.patches))

print("\n=== F4: SOFT TERMINAL — needs_input stays OPEN for the resume rail ===")
def _fence_soft(stub):
    stub.row_status = "needs_input"
    H.write_job_status("j-fence4", status="completed", phase="Done", progress=100,
                       result={"video_url": "x"})
_, stub, _ = flag_on(_fence_soft)
check("resume terminal lands over needs_input", len(stub.patches) == 1
      and stub.patches[0][1].get("status") == "completed", str(stub.patches))

print("\n=== F5: no write rides the UNFENCED legacy chain ===")
def _fence_chain(stub):
    H.write_job_status("j-fence5", status="processing", phase="x", progress=10)
_, stub, _ = flag_on(_fence_chain)
check("every write carries the predicate",
      all(len(p) == 3 for p in stub.patches), str(stub.patches))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL STATUS-WRITE CASES PASS")
