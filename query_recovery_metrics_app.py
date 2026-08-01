"""Recovery reads (Zac 2026-07-31, post cpu=16+fanout=0 deploy): the FIRST real
numbers on the deployed config. Reports, from video_jobs:
  1. completions since the deploy — E2E distribution (stage_timings.total) + Modal
     compute-cost/job (container-seconds x rate; dashboard is authoritative).
  2. error-code distribution incl UPLOAD_STALLED / upload_failed (note only).
  3. month-to-date job count for the spend extrapolation vs the $100 alarm.
Read window = the RECOVERY window (post-deploy) — the opposite of the outage rule;
here the recent window IS the signal.
"""
import os, sys, json
import modal
from collections import Counter

app = modal.App("query-recovery-metrics")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# Modal published rates (VERIFY on dashboard — this is a computed estimate):
CPU_RATE_S = 0.0000375      # ~$0.135/physical-core/hour
MEM_RATE_S = 0.00000667     # ~$0.024/GiB/hour
CORES = 16
GIB = 128


def _p(vals):
    if not vals: return {}
    v = sorted(vals); n = len(v)
    q = lambda f: round(v[min(n-1, int(round(f*(n-1))))], 1)
    return {"n": n, "min": round(v[0],1), "p25": q(.25), "p50": q(.5), "p75": q(.75),
            "p90": q(.9), "max": round(v[-1],1), "mean": round(sum(v)/n,1)}


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    sb = create_client(url, key)
    # recent jobs since the deploy
    rows = []
    for off in range(0, 4000, 1000):
        r = (sb.table("video_jobs").select("created_at,status,st:result->stage_timings,ec:result->error_code,cd:result->code,rt:result->route")
             .gte("created_at", since).order("created_at", desc=True).range(off, off+999).execute())
        d = r.data or []
        if not d: break
        rows.extend(d)
    status_ct = Counter(r.get("status") for r in rows)
    def _err(r): return r.get("ec") or r.get("cd")
    err_ct = Counter(_err(r) for r in rows if _err(r))
    route_ct = Counter((r.get("rt") if isinstance(r.get("rt"), str) else None) for r in rows)
    e2e, costs = [], []
    for r in rows:
        if r.get("status") != "completed": continue
        st = r.get("st")
        if isinstance(st, dict) and isinstance(st.get("total"), (int, float)):
            t = float(st["total"]); e2e.append(t)
            costs.append(t * (CORES*CPU_RATE_S + GIB*MEM_RATE_S))
    # month-to-date count (Modal billing month)
    mtd = sb.table("video_jobs").select("id", count="exact").gte("created_at", "2026-07-01").execute()
    return {
        "since": since, "rows": len(rows),
        "status_counts": dict(status_ct),
        "error_code_counts": dict(err_ct),
        "route_counts": {str(k): v for k, v in route_ct.items()},
        "E2E_total_s": _p(e2e),
        "modal_cost_per_completed_job": {
            "n": len(costs), "mean_$": round(sum(costs)/max(1,len(costs)), 3),
            "p50_$": round(sorted(costs)[len(costs)//2], 3) if costs else None,
            "max_$": round(max(costs), 3) if costs else None,
            "rate_note": f"computed: E2E_s x ({CORES}core x ${CPU_RATE_S}/core-s + {GIB}GiB x ${MEM_RATE_S}/GiB-s); DASHBOARD AUTHORITATIVE",
        },
        "month_to_date_jobs_since_0701": getattr(mtd, "count", None),
        # RAW newest 40 (any status) so the post-deploy recovery cluster can be
        # isolated from the outage failures by created_at.
        "recent_40": [
            {"t": r.get("created_at"), "status": r.get("status"),
             "e2e": (r.get("st") or {}).get("total") if isinstance(r.get("st"), dict) else None,
             "err": _err(r), "route": r.get("rt")}
            for r in sorted(rows, key=lambda x: x.get("created_at") or "", reverse=True)[:40]
        ],
    }


@app.local_entrypoint()
def main():
    print("RECOVERY " + json.dumps(query.remote("2026-07-30"), indent=2, default=str))
