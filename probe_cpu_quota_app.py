"""PROBE: what does cpu= actually buy? Quota-only, no rendering.

MEASURED: arms requesting cpu=8/16/32 delivered 2.81/12.84/2.84 effective cores.
cpu=32 bought nothing over cpu=8. Three explanations, and they need separating
because they imply opposite things:

  (a) the benchmark misreads the quota            -> instrument bug, fix it
  (b) Modal sets the quota but does not schedule  -> cores exist, contended
  (c) cpu= is a RESERVATION, not a limit          -> the number means something
                                                     else than assumed

This reads the raw cgroup files alongside the benchmark, so the quota Modal
actually set is visible rather than inferred. No render, so it costs seconds.
"""
import json
import os

import modal

from agentic_editor_app import IMG, container_benchmark, cgroup_cpu_quota

PROBE_IMG = IMG.add_local_python_source("agentic_editor_app")
app = modal.App("probe-cpu-quota")

_CGROUP_FILES = [
    "/sys/fs/cgroup/cpu.max",
    "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
    "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
    "/sys/fs/cgroup/cpu.weight",
    "/sys/fs/cgroup/cpuset.cpus",
    "/sys/fs/cgroup/cpuset.cpus.effective",
]


def _probe(requested):
    raw = {}
    for f in _CGROUP_FILES:
        try:
            with open(f) as fh:
                raw[f] = fh.read().strip()[:120]
        except Exception as e:
            # ABSENT is a fact worth printing — it is how we tell cgroup v1 from
            # v2 from "Modal does not expose this at all".
            raw[f] = f"ABSENT ({type(e).__name__})"
    out = {
        "requested_cpu": requested,
        "cgroup_quota": cgroup_cpu_quota(),
        "os_cpu_count": os.cpu_count(),
        "sched_affinity": (len(os.sched_getaffinity(0))
                           if hasattr(os, "sched_getaffinity") else None),
        "bench": container_benchmark(),
        "cgroup_raw": raw,
    }
    print(f"[cpu{requested}] {json.dumps(out)}", flush=True)
    return out


@app.function(image=PROBE_IMG, timeout=300, cpu=2)
def q2():
    return _probe(2)


@app.function(image=PROBE_IMG, timeout=300, cpu=8)
def q8():
    return _probe(8)


@app.function(image=PROBE_IMG, timeout=300, cpu=16)
def q16():
    return _probe(16)


@app.function(image=PROBE_IMG, timeout=300, cpu=32)
def q32():
    return _probe(32)


@app.function(image=PROBE_IMG, timeout=300, cpu=64)
def q64():
    return _probe(64)


@app.local_entrypoint()
def main():
    rows = []
    for name, fn in (("2", q2), ("8", q8), ("16", q16), ("32", q32), ("64", q64)):
        try:
            rows.append(fn.remote())
        except Exception as e:
            rows.append({"requested_cpu": name, "error": str(e)[:200]})
    print("\n" + "=" * 92)
    print("CPU QUOTA PROBE — what cpu= actually provisions")
    print("=" * 92)
    print(f"  {'cpu=':>6}{'cgroup_quota':>14}{'affinity':>10}{'os_count':>10}"
          f"{'eff_cores':>11}{'single_ms':>11}{'basis':>22}")
    for r in rows:
        if r.get("error"):
            print(f"  {r['requested_cpu']:>6}  FAILED {r['error'][:60]}")
            continue
        b = r.get("bench") or {}
        print(f"  {r['requested_cpu']:>6}{str(r.get('cgroup_quota')):>14}"
              f"{str(r.get('sched_affinity')):>10}{str(r.get('os_cpu_count')):>10}"
              f"{str(b.get('effective_cores')):>11}{str(b.get('single_ms')):>11}"
              f"{str(b.get('cpu_basis')):>22}")
    print("\n  RAW CGROUP (first arm that read anything):")
    for r in rows:
        if r.get("cgroup_raw") and any(not v.startswith("ABSENT")
                                       for v in r["cgroup_raw"].values()):
            for k, v in r["cgroup_raw"].items():
                print(f"    {k:44} {v}")
            break
    else:
        print("    every cgroup file ABSENT in every arm — the quota is not")
        print("    readable from inside a Modal container, so effective_cores")
        print("    is the ONLY evidence of what was provisioned.")
    print("\n  READ: quota == cpu= means Modal set a limit and any shortfall is")
    print("  SCHEDULING. quota absent/unequal means cpu= is a reservation and")
    print("  effective_cores is the only number that describes reality.")
