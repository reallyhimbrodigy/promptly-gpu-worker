"""ORGANIC stage_timings distribution ($0 read, Zac 2026-07-31): before any paid
thinking-budget sweep, read the real baseline from video_jobs.result.stage_timings
across the corpus — gemini_call (deliberation time), gemini_wasted_degen (degen
burn), edit_plan (whole editorial stage). Reports distribution + true degen rate.

Read-window discipline (Zac): created_at < 2026-07-30 (pre-outage; the outage had
~0 traffic anyway). No renders, no Gemini — one tiny container reading Supabase.
"""
import os, sys, json
import modal

app = modal.App("query-stage-timings")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]


def _pctiles(vals):
    if not vals:
        return {}
    v = sorted(vals); n = len(v)
    def p(q):
        i = min(n - 1, max(0, int(round(q * (n - 1)))))
        return round(v[i], 1)
    return {"n": n, "min": round(v[0], 1), "p10": p(.10), "p25": p(.25), "p50": p(.50),
            "p75": p(.75), "p90": p(.90), "p95": p(.95), "p99": p(.99), "max": round(v[-1], 1),
            "mean": round(sum(v) / n, 1)}


@app.function(image=image, secrets=SECRETS, timeout=600)
def query() -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    sb = create_client(url, key)

    # Page through completed jobs pre-outage, newest first, pulling only the
    # stage_timings sub-object (jsonb path select keeps the payload small).
    rows = []
    PAGE = 1000
    for off in range(0, 6000, PAGE):
        try:
            r = (sb.table("video_jobs")
                 .select("created_at, st:result->stage_timings")
                 .lt("created_at", "2026-07-30")
                 .order("created_at", desc=True)
                 .range(off, off + PAGE - 1).execute())
        except Exception as e:
            # fallback: pull whole result if the jsonb-path select is rejected
            r = (sb.table("video_jobs").select("created_at, result")
                 .lt("created_at", "2026-07-30").order("created_at", desc=True)
                 .range(off, off + PAGE - 1).execute())
        data = r.data or []
        if not data:
            break
        rows.extend(data)

    gcall, wasted, eplan, total = [], [], [], []
    n_with_st = 0
    for row in rows:
        st = row.get("st")
        if st is None and isinstance(row.get("result"), dict):
            st = row["result"].get("stage_timings")
        if not isinstance(st, dict):
            continue
        n_with_st += 1
        for key_, bucket in (("gemini_call", gcall), ("gemini_wasted_degen", wasted),
                             ("edit_plan", eplan), ("total", total)):
            v = st.get(key_)
            if isinstance(v, (int, float)):
                bucket.append(float(v))

    # degen rate: fraction of jobs whose editorial stage burned degen seconds
    wasted_all = [w for w in wasted]                 # includes 0.0 (no degen)
    degen_fired = [w for w in wasted_all if w and w > 1.0]
    degen_rate = round(100.0 * len(degen_fired) / max(1, len(wasted_all)), 1)

    return {
        "rows_scanned": len(rows),
        "jobs_with_stage_timings": n_with_st,
        "window": "created_at < 2026-07-30 (pre-outage)",
        "gemini_call_s": _pctiles(gcall),
        "edit_plan_s": _pctiles(eplan),
        "total_s": _pctiles(total),
        "gemini_wasted_degen_s_ALL": _pctiles(wasted_all),          # incl the 0s
        "gemini_wasted_degen_s_WHEN_FIRED": _pctiles(degen_fired),   # only degen jobs
        "degen_rate_pct": degen_rate,
        "n_degen_fired": len(degen_fired),
        "n_wasted_field_present": len(wasted_all),
    }


@app.local_entrypoint()
def main():
    print("QUERY_RESULT " + json.dumps(query.remote(), indent=2, default=str))
