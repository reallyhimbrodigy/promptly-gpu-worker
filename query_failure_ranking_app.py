"""FAILURE RANKING BY USERS, WITH SUB-CODES ($0 — one CPU container).

Rule 7: a user who fails five times and gives up is ONE LOST USER, not five
failures. Per-job counting inflates every class by the retry multiplier, which
is exactly what made a one-user 100fps bug read as a 67% outage. Both numbers
are reported; the USER count leads.

WHAT THIS IS RE-RUN FOR: `ladder_exhausted` went live at v574. A ladder trying
every rung and running out is a DESIGN OUTCOME, not a crash, and it was landing
in RENDER_FATAL/unclassified — the top unnamed class by users. The question is
whether unclassified drops to residue, and whether the cause suffix
(ladder_exhausted:<Type>) keeps new shapes visible rather than absorbing them.
"""
import os
import sys
import json
import modal

app = modal.App("query-failure-ranking")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str = "", limit: int = 6000) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    rows, PAGE = [], 1000
    for off in range(0, max(PAGE, limit), PAGE):
        q = (sb.table("video_jobs")
             .select("id, user_id, created_at, status, error_message, "
                     "ec:result->error_code, es:result->error_subcode, "
                     "ed:result->error_detail, ec2:result->error_cause, "
                     "st:result->stage_timings")
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

    total_users = {r.get("user_id") for r in rows if r.get("user_id")}
    failed = [r for r in rows if (r.get("status") or "") in ("failed", "error")]
    classes, on_v574 = {}, 0
    for r in failed:
        st = r.get("st")
        if isinstance(st, dict) and "render_offthread_threads" in st:
            on_v574 += 1
        code = r.get("ec") or "UNCODED"
        sub = r.get("es") or "no_subcode"
        k = f"{code}:{sub}"
        c = classes.setdefault(k, {"jobs": 0, "users": set(), "sample": None})
        c["jobs"] += 1
        c["users"].add(r.get("user_id"))
        if c["sample"] is None:
            c["sample"] = (r.get("error_message") or "")[:150]
        # ROOT-CAUSE NEEDS THE WHOLE MESSAGE, not a 150-char sample. A truncated
        # message names the label and hides the mechanism.
        # error_message is the USER-FACING copy ("please run the job again") —
        # it names the terminal and hides the mechanism. error_detail carries the
        # technical string the sub-code was keyed on.
        c.setdefault("msgs", []).append(
            (str(r.get("ed") or "") or str(r.get("error_message") or ""))[:700])

    ranked = sorted(({"class": k, "users": len(v["users"]), "jobs": v["jobs"],
                      "jobs_per_user": round(v["jobs"] / max(1, len(v["users"])), 2),
                      "sample": v["sample"],
                      "full_messages": v.get("msgs", [])[:6]}
                     for k, v in classes.items()),
                    key=lambda d: (-d["users"], -d["jobs"]))
    return {"window_since": since or "all", "rows_scanned": len(rows),
            "total_users_in_window": len(total_users),
            "failed_jobs": len(failed),
            # NOTE: a FAILED job often never reaches the stage_timings persist
            # site, so this undercounts and must not be read as "0 jobs ran on
            # v574+". Cut the WINDOW instead — that is the honest cohort.
            "failed_jobs_with_stage_timings": on_v574,
            "failed_users": len({r.get("user_id") for r in failed if r.get("user_id")}),
            "classes": ranked}


@app.local_entrypoint()
def main(since: str = "", limit: int = 6000):
    r = query.remote(since=since, limit=limit)
    if r.get("error"):
        print(f"  ❌ {r['error']}"); sys.exit(1)
    print(f"\n  window {r['window_since']}   scanned {r['rows_scanned']}   "
          f"users in window {r['total_users_in_window']}")
    print(f"  FAILED: {r['failed_users']} users / {r['failed_jobs']} jobs "
          f"({r['failed_jobs_with_stage_timings']} wrote stage_timings — failed "
          f"jobs often never reach that write, so cut by WINDOW, not by this)")
    if not r["classes"]:
        print("\n  NO FAILURES IN WINDOW. An empty read, not a proven zero —")
        print("  state the denominator before calling this a result.")
        sys.exit(2)
    print(f"\n  {'users':>5} {'jobs':>5} {'j/u':>5}  class")
    for c in r["classes"]:
        print(f"  {c['users']:>5} {c['jobs']:>5} {c['jobs_per_user']:>5}  {c['class']}")
    # EXACT, not substring. The first cut of this line matched every class
    # containing "unclassified" — CLIP_TOO_SHORT, UNKNOWN, RECIPE_INVALID,
    # EDITOR_GENERIC — and reported 13 users where RENDER_FATAL's own share was
    # 5. A loose reader inflating the very number the change is judged by.
    unc = [c for c in r["classes"] if c["class"] == "RENDER_FATAL:unclassified"]
    lad = [c for c in r["classes"] if "ladder_exhausted" in c["class"]]
    print(f"\n  RENDER_FATAL/unclassified: "
          f"{sum(c['users'] for c in unc)} users / {sum(c['jobs'] for c in unc)} jobs")
    print(f"  ladder_exhausted:*        : "
          f"{sum(c['users'] for c in lad)} users / {sum(c['jobs'] for c in lad)} jobs")
    for c in lad:
        print(f"      {c['class']}  ({c['users']}u/{c['jobs']}j)")
    # ROOT-CAUSE DUMP: the whole message for every class asked about, because a
    # label names the terminal and hides the mechanism.
    import os as _os
    _want = (_os.environ.get("DUMP_CLASS") or "ladder_exhausted").split(",")
    for c in r["classes"]:
        if any(w.strip() and w.strip() in c["class"] for w in _want):
            print(f"\n══ {c['class']}  ({c['users']}u / {c['jobs']}j) ══")
            for i, msg in enumerate((c.get("full_messages") or [])[:4]):
                print(f"  [{i}] {(msg or '')[:600]}")
