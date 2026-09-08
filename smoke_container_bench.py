#!/usr/bin/env python3
"""SMOKE: the container benchmark is comparable across runs, or says it is not.

WHY IT EXISTS. Identical bytes (mount f40873429cfa84a6) painted 443 caption
frames at 49.0 ms/frame and, six hours later, 134.2. A 2.7x spread with no code
difference. On the 49.0 a concurrency fix was reported as 6.1x (it is ~2.3x),
and a regression was later reported against the same 49.0 and refuted. Nothing
measured the machine.

WHAT MAKES THIS FIRE:
  - a silently CHANGED workload. Then old numbers and new numbers are not the
    same measurement, while the output still looks like a benchmark. The digest
    pin is the only thing standing between that and a year of bad comparisons.
  - a FAILED benchmark returning a number anyway. Normalising by a made-up
    single_ms is worse than refusing to normalise.
"""
import sys, types

_m = types.ModuleType("modal")
class _S:
    def __init__(s,*a,**k): pass
    def __getattr__(s,n): return _S()
    def __call__(s,*a,**k): return _S()
    def function(s,*a,**k): return lambda f: f
    def local_entrypoint(s,*a,**k): return lambda f: f
for _n in ("App","Image","Secret","Volume","Cls","Function"): setattr(_m,_n,_S())
_m.is_local=lambda: True; _m.enable_output=_S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A

fails=[]
def ok(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

b = A.container_benchmark()

ok("the benchmark runs", b.get("ok") is True, str(b.get("error")))
ok("it reports a NON-ZERO single-thread time", (b.get("single_ms") or 0) > 0,
   "a zero would normalise every stage to infinity")
ok("it reports a non-zero parallel time", (b.get("par_ms") or 0) > 0)
ok("it reports cpu_count", (b.get("cpu_count") or 0) >= 1)
ok("effective_cores is computed", b.get("effective_cores") is not None)
ok("effective_cores is at least 1", (b.get("effective_cores") or 0) >= 1.0,
   f"got {b.get('effective_cores')} — the parallel arm did no better than one core")

# ── THE PIN. This is the check that protects every historical comparison. ──
ok("the workload matches its pinned digest", b.get("digest_ok") is True,
   f"BENCH_DIGEST={A.BENCH_DIGEST} but the workload produced {b.get('digest')} — "
   "the benchmark changed, so numbers from before this change are NOT comparable "
   "to numbers after it, and nothing in the output would have said so")

# ── determinism: two calls, same digest ───────────────────────────────────
b2 = A.container_benchmark()
ok("the workload is deterministic across calls", b2.get("digest") == b.get("digest"),
   "a workload that varies run to run cannot normalise anything")

# ── a FAILED benchmark must not yield a usable number ─────────────────────
_real = A._bench_once
try:
    A._bench_once = lambda buf: (_ for _ in ()).throw(RuntimeError("boom"))
    bad = A.container_benchmark()
    ok("a failed benchmark reports ok=False", bad.get("ok") is False)
    ok("a failed benchmark yields NO single_ms", bad.get("single_ms") is None,
       "a failure that still returns a time gets used as one — absence must "
       "never render as a measurement")
finally:
    A._bench_once = _real

# ── it must be CHEAP enough to run on every job ───────────────────────────
ok("the benchmark costs under 2s", (b["single_ms"] + b["par_ms"]) < 2000,
   f"{b['single_ms']+b['par_ms']:.0f}ms — too expensive to run on every job")

if fails:
    print(f"CONTAINER-BENCH: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print(f"CONTAINER-BENCH: PASS  (single {b['single_ms']:.0f}ms, par {b['par_ms']:.0f}ms "
      f"over {b['par_workers']}w, effective_cores {b['effective_cores']})")
