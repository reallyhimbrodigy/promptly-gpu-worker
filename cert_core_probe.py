"""Ground-truth core-count probe (Zac 2026-08-03): the concurrency clamp fell
back to os.cpu_count() if Modal limits cores via cpuset rather than a cpu.max
quota. This prints, on a REAL cpu=8 container, every core-count source so the
forward fix uses the ONE that matches what Remotion/Node sees (which reported 8).
Ephemeral `modal run` — ~$0.001, ~20s. No render, no synthetic pipeline spend."""
import modal

app = modal.App("promptly-core-probe")


@app.function(cpu=8, memory=1024, region="us")
def probe():
    import os
    out = {}
    try:
        out["sched_getaffinity_len"] = len(os.sched_getaffinity(0))
    except Exception as e:
        out["sched_getaffinity_len"] = f"ERR {type(e).__name__}: {e}"
    out["os_cpu_count"] = os.cpu_count()
    for p in ("/sys/fs/cgroup/cpu.max",
              "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
              "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
              "/sys/fs/cgroup/cpu.weight"):
        try:
            with open(p) as f:
                out[p] = f.read().strip()
        except Exception as e:
            out[p] = f"ERR {type(e).__name__}"
    print("CORE_PROBE_RESULT", out, flush=True)
    return out


@app.local_entrypoint()
def main():
    print("PROBE_RETURN", probe.remote())
