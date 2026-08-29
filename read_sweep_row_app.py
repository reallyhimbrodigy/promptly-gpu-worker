"""Read a dispatched sweep/confirmation job's ROW — the durable record.

WHY THIS EXISTS SEPARATELY FROM THE SWEEP. `run_pipeline_bg` is spawned, so the
job outlives the local orchestrator (standing rule: a batch is dead only when
`modal app list` shows 0 tasks — NOT when the harness exits). On 2026-08-28 the
confirmation run's ephemeral app was stopped while waiting on
FunctionCall.get(), and modal raised FAILED_PRECONDITION. The JOB was unaffected.
Reading the row is the only way to learn what it did; treating the harness's
exit code as the job's outcome is how a completed render gets reported as a
failure.

  ./run_modal.sh read_sweep_row_app.py --jids <uuid>[,<uuid>...]
"""
import os

import modal

app = modal.App("read-sweep-row")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=600)
def read(jids: list) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = []
    for jid in jids:
        r = (sb.table("video_jobs")
             .select("id,status,error_message,created_at,result")
             .eq("id", jid).limit(1).execute())
        d = (r.data or [{}])[0]
        res = d.get("result") or {}
        if not isinstance(res, dict):
            res = {}
        st = res.get("stage_timings") or {}
        if not isinstance(st, dict):
            st = {}
        out.append({
            "job_id": jid,
            "found": bool(d),
            "status": d.get("status"),
            "error_code": res.get("error_code"),
            "error_cause": res.get("error_cause"),
            "error_class": res.get("error_class"),
            "error_where": res.get("error_where", "<KEY-ABSENT>"),
            "error_detail": str(res.get("error_detail")
                                or d.get("error_message") or "")[:300],
            "stages": sorted(st.keys()),
            "render_s": st.get("render"),
            "total_s": st.get("total"),
            "conc": st.get("render_concurrency"),
            "legs": st.get("render_legs") or [],
        })
    return out


@app.local_entrypoint()
def main(jids: str = ""):
    ids = [j.strip() for j in jids.split(",") if j.strip()]
    rows = read.remote(ids)
    for d in rows:
        print(f"\n=== {d['job_id']}")
        if not d["found"]:
            print("    ROW NOT FOUND — not a zero, an absent read.")
            continue
        print(f"    status      : {d['status']}")
        print(f"    error       : {d['error_code']} / {d['error_cause']}"
              f" / {d['error_class']}")
        if d["error_detail"]:
            print(f"    detail      : {d['error_detail']}")
            print(f"    where       : {d['error_where']}")
        print(f"    render_s    : {d['render_s']}   total_s: {d['total_s']}")
        print(f"    concurrency : {d['conc']}")
        print(f"    stages      : {d['stages']}")
        legs = d["legs"]
        print(f"    RENDER LEGS : {len(legs)}")
        for lg in legs[:10]:
            print(f"        {str(lg.get('leg'))[:40]:>40}  "
                  f"frames={lg.get('frames')}  ms/frame={lg.get('ms_per_frame')}")
        # THE VERDICT THE CONFIRMATION EXISTS TO PRODUCE.
        _reached = bool(legs) or d["status"] == "completed"
        print(f"    >>> REACHED THE RENDERER: {'YES' if _reached else 'NO'}")
