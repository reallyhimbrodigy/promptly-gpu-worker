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
    def __init__(self):
        self.patches = []      # (table, patch, job_id)
        self.raise_next = False
    def table(self, name):
        outer = self
        class _T:
            def update(self, patch):
                class _U:
                    def eq(self, col, jid):
                        class _E:
                            def execute(_s):
                                if outer.raise_next:
                                    outer.raise_next = False
                                    raise RuntimeError("supabase down")
                                outer.patches.append((name, patch, jid))
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
        H.write_job_status(j["input"]["job_id"], status="complete", phase="Done",
                           progress=100, result={"video_url": "https://cdn/v.mp4"})
        return {"status": "success", "video_url": "https://cdn/v.mp4"}
    import time as _t
    state = {"ready": True, "mode": "full", "dur": 30.0, "t0": _t.time()}
    return H._outer_safe_rescue(job, job["input"],
                                {"error_code": "UNKNOWN"}, state, run_fn=fake_inner)
out, stub, o = flag_on(_w6)
check("rescued payload returned", isinstance(out, dict) and out.get("status") == "success", str(out))
comp = [p for (t, p, j) in stub.patches if p.get("status") == "complete" and j == "j-resc"]
check("complete write landed via the inner run", len(comp) == 1, str(stub.patches))

print("\n=== W7: source pins — every early return is write-covered ===")
src = open("handler.py").read()
for _code, _n in (("MISSING_FIELDS", 2), ("TIER_CONCURRENCY", 1)):
    check(f"{_code} write present x{_n}", src.count(f'"error_code": "{_code}"') == _n)
_exc = src.find("classified = classify_error(e)")
_resc = src.find("_outer_safe_rescue(job, input_data, classified, _rescue_state)", _exc)
_failw = src.find('status="failed"', _resc)
check("except path: rescue precedes the failed write", -1 < _exc < _resc < _failw)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL STATUS-WRITE CASES PASS")
