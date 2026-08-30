"""Is INTEGRITY_TRIP a NEW failure or a standing class? Free, no renders.

One armed-path job tripped the render integrity gate. Attributing that to the
Lane 3 arm from n=1 would be exactly the mistake this codebase keeps paying for
— a single sampled instance read as a universal shape. The gate lives far
downstream of the ingest pool, and the ingest outputs were already proven
byte-identical across the boundary, so the prior is weak either way.

So ask the cheap question before spending on a control render: does
INTEGRITY_TRIP appear in the PRE-ARM window? If it is a standing class, this
job is one more instance of it and the arm is not implicated by it. If it has
never appeared before the arm, that is a signal and step 1 reverts.

Cut PER USER as well as per job — a user who retries five times is one lost
user, not five failures.

  ./run_modal.sh probe_integrity_trip_history_app.py --since 2026-08-20
"""
import os
from collections import Counter

import modal

app = modal.App("probe-integrity-trip-history")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]
ARM_CUT = "2026-08-30T20:07:00+00:00"


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 500
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,result,demo,created_at,error_message")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 20:
            break
    out = []
    for x in rows:
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        blob = " ".join([
            str(x.get("error_message") or ""),
            str(res.get("error_where") or ""),
            str(res.get("error_code") or ""),
            str(res.get("error_subcode") or ""),
            str(res.get("error_detail") or ""),
        ])
        out.append({"id": x.get("id"), "user": x.get("user_id"),
                    "status": x.get("status"), "demo": bool(x.get("demo")),
                    "created": str(x.get("created_at")),
                    "trip": "INTEGRITY_TRIP" in blob,
                    "where": str(res.get("error_where") or "")[:70]})
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-20"):
    rows = scan.remote(since)
    trips = [r for r in rows if r["trip"]]
    pre = [r for r in trips if r["created"] < ARM_CUT]
    post = [r for r in trips if r["created"] >= ARM_CUT]
    term = [r for r in rows if r["status"] in ("completed", "failed", "error")]
    pre_term = [r for r in term if r["created"] < ARM_CUT]

    print(f"\n=== INTEGRITY_TRIP — standing class, or new with the arm? ===")
    print(f"  window since {since}: {len(rows)} jobs, {len(term)} terminal")
    print(f"  arm cut: {ARM_CUT}\n")
    print(f"  INTEGRITY_TRIP total          : {len(trips)}")
    print(f"    BEFORE the arm              : {len(pre)}   "
          f"({100.0*len(pre)/max(1,len(pre_term)):.2f}% of {len(pre_term)} pre-arm terminal)")
    print(f"    AFTER the arm               : {len(post)}")
    print(f"    of those, demo/synthetic    : {sum(1 for r in post if r['demo'])}")

    if pre:
        print(f"\n  ✅ INTEGRITY_TRIP IS A STANDING CLASS — it predates the arm by")
        print(f"     {len(pre)} occurrence(s) across "
              f"{len({r['user'] for r in pre})} user(s). The armed job is one more")
        print(f"     instance, NOT evidence the relocation caused it.")
        print(f"\n  pre-arm occurrences (most recent first):")
        for r in pre[:8]:
            print(f"    {r['created'][:19]}  {str(r['id'])[:8]}  "
                  f"demo={r['demo']}  {r['where']}")
    else:
        print(f"\n  ❌ NO PRE-ARM OCCURRENCE in this window. INTEGRITY_TRIP appears")
        print(f"     only AFTER the arm. That is a signal — revert step 1 and")
        print(f"     re-test, rather than explaining it away.")

    if trips:
        print(f"\n  frames:")
        for w, n in Counter(r["where"] for r in trips).most_common(5):
            print(f"    {n:>3}  {w}")
