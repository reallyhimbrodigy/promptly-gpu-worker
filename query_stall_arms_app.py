"""THE STALL EXPERIMENT READ ($0 — one tiny container, no render, no Gemini).

Reports located -> offered -> preserved PER ARM, cut by the value the job
ACTUALLY RAN WITH (result.stage_timings.midsentence_stall_s), never by clock.

THE ARMS ARE CONCURRENT BY DESIGN, not by accident. A per-job 50/50 split on
sha256(job_id) puts both values on the same traffic in the same hours, so this
is not a before/after. Reading the env var directly would have given ONE value
per container — 100% of traffic on the arm — and the only concurrency that
yields is the warm/cold container mixture after a flip, where container age
correlates with load and time of day. That is the confound that made the
proxy-fps read AGREE with its own prediction (-34.3% vs -36%) while being noise.

WHY NOT BY TIMESTAMP ANYWAY. During the deploy window, containers still warm
from before it have no env value and contribute CONTROL jobs only. Cutting by
clock would fold those in as if they were assigned; cutting by the PERSISTED arm
does not. The arm-invariance check below is what proves the two cohorts are
comparable despite that transition.

THE PRE-REGISTERED READINGS (NEXT_TWO_ITEMS.md item 1):

  `located` is ARM-INVARIANT. It is counted after the silence bar and BEFORE
  the linguistic gate, so the constant cannot touch it. If located differs
  between arms by more than sampling noise, the cut is contaminated and NO
  other number here is readable — that is the self-check, and it is reported
  first for that reason.

  FALSIFIER, stated in advance: if `preserved` rises in LOCKSTEP with
  `offered`, the model is being handed spans it does not want and the constant
  is not the lever. The rate that matters is preserved/offered — if it holds
  flat while offered rises, the extra spans are being accepted; if it climbs,
  they are being refused.

Reports per-USER counts beside per-job ones (Rule 7) and states its window.
"""
import os
import sys
import json
import modal

app = modal.App("query-stall-arms")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]


def _median(v):
    if not v:
        return None
    s = sorted(v)
    return round(s[len(s) // 2], 2)


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str = "", limit: int = 6000) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — this is a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    rows, PAGE = [], 1000
    for off in range(0, max(PAGE, limit), PAGE):
        q = (sb.table("video_jobs")
             .select("id, user_id, created_at, status, st:result->stage_timings")
             .order("created_at", desc=True).range(off, off + PAGE - 1))
        if since:
            q = q.gte("created_at", since)
        try:
            r = q.execute()
        except Exception as e:
            return {"error": f"QUERY FAILED: {type(e).__name__}: {e}"}
        if not r.data:
            break
        rows.extend(r.data)
        if len(r.data) < PAGE:
            break

    # ARM = the value the job ran with. A row with no value did not run this
    # code (pre-deploy) and is EXCLUDED — it is not a control, it is a
    # different build, and mixing it in is exactly the contamination Rule 5
    # exists to prevent.
    arms, no_field, no_dead_air = {}, 0, 0
    for r in rows:
        st = r.get("st") or {}
        if not isinstance(st, dict):
            continue
        arm = st.get("midsentence_stall_s")
        if arm is None:
            no_field += 1
            continue
        loc = st.get("dead_air_spans_located")
        off_ = st.get("dead_air_spans_offered")
        pres = st.get("dead_air_spans_preserved")
        if loc is None:
            no_dead_air += 1
            continue
        a = arms.setdefault(str(arm), {
            "jobs": 0, "users": set(), "located": [], "offered": [], "preserved": [],
            "jobs_with_located": 0})
        a["jobs"] += 1
        a["users"].add(r.get("user_id"))
        a["located"].append(loc or 0)
        a["offered"].append(off_ or 0)
        a["preserved"].append(pres or 0)
        if (loc or 0) > 0:
            a["jobs_with_located"] += 1

    out = {}
    for arm, a in sorted(arms.items()):
        L, O, P = sum(a["located"]), sum(a["offered"]), sum(a["preserved"])
        out[arm] = {
            "jobs": a["jobs"],
            "users": len(a["users"]),
            "jobs_with_a_located_span": a["jobs_with_located"],
            # THE THREE NUMBERS, as totals with their denominator.
            "located_total": L,
            "offered_total": O,
            "preserved_total": P,
            # THE GATE: what fraction of located spans survived to the model.
            "offered_per_located": round(O / L, 3) if L else None,
            # THE FALSIFIER: of what it was offered, what did the model KEEP?
            # Flat while offered rises  -> the extra spans are accepted.
            # Rising with offered       -> handed spans it does not want.
            "preserved_per_offered": round(P / O, 3) if O else None,
            "median_located_per_job": _median(a["located"]),
            "median_offered_per_job": _median(a["offered"]),
        }

    return {"window_since": since or "all", "rows_scanned": len(rows),
            "excluded_no_arm_field_predeploy": no_field,
            "excluded_no_dead_air_measurement": no_dead_air,
            "arms": out}


@app.local_entrypoint()
def main(since: str = "", limit: int = 6000):
    r = query.remote(since=since, limit=limit)
    print(json.dumps(r, indent=1))
    if r.get("error"):
        print(f"\n  ❌ {r['error']}")
        sys.exit(1)
    arms = r.get("arms") or {}
    print(f"\n  window: {r['window_since']}   rows scanned: {r['rows_scanned']}")
    print(f"  excluded: {r['excluded_no_arm_field_predeploy']} pre-deploy (no arm field), "
          f"{r['excluded_no_dead_air_measurement']} with no dead-air measurement")
    if not arms:
        print("\n  NO ARMS FOUND. This is an EMPTY READ, not a zero: either the")
        print("  build is not live yet or no job reached the dead-air stage.")
        sys.exit(2)
    print(f"\n  {'arm':>7} {'jobs':>5} {'users':>6} {'located':>8} {'offered':>8} "
          f"{'presvd':>7} {'off/loc':>8} {'pres/off':>9}")
    for arm, a in sorted(arms.items(), key=lambda kv: float(kv[0]), reverse=True):
        print(f"  {arm:>7} {a['jobs']:>5} {a['users']:>6} {a['located_total']:>8} "
              f"{a['offered_total']:>8} {a['preserved_total']:>7} "
              f"{str(a['offered_per_located']):>8} {str(a['preserved_per_offered']):>9}")
    if len(arms) < 2:
        print("\n  ONE ARM ONLY — no comparison is possible yet. Not a result.")
        sys.exit(2)
    # THE SELF-CHECK, reported before any conclusion.
    med = {k: v["median_located_per_job"] for k, v in arms.items()}
    print(f"\n  ARM-INVARIANCE CHECK (located must NOT move): median located/job = {med}")
    print("  If these differ materially the cohorts are not comparable and")
    print("  nothing below the line is readable.")
