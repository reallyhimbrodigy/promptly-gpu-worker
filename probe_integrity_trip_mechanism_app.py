"""INTEGRITY_TRIP — MECHANISM. Which discriminator is failing, on whose video?

The denominator is settled (28/1,585 = 1.77%, 20 users) and is NOT re-derived.
This asks the three questions that name the mechanism:

  1. WHICH SUB-CLASS trips? The gate checks freeze, black, dead_moment and
     others independently, each with its own discriminator. Prior art in
     handler.py (_ig_source_echo_black) says 23 of 25 trips were BLACK at the
     tail and built a source-echo to stop faithful renders of black-tailed
     sources from false-failing. If black is now small and freeze is large,
     that fix worked and the class MOVED — a different mechanism.

  2. IS IT ONE SITE OR FOUR? The clustered frames (38914/38176/37367/38617)
     come from DIFFERENT DEPLOYS, and handler.py grows constantly, so the same
     assertion drifts line numbers over time. There is exactly ONE
     `raise RuntimeError(f"INTEGRITY_TRIP:...")` in the file today. Reading
     today's file at a line number recorded weeks ago would name the wrong
     function — so this reports frame WITH the job date, and the mapping is
     resolved against the commit that was live then, not against HEAD.

  3. PER USER, and is it RETRY-INFLATED? A user who trips five times is one
     lost user. Also: do trippers RECOVER (a later completed job)?

Free. Reads persisted rows only.
"""
import os
from collections import Counter, defaultdict

import modal

app = modal.App("probe-integrity-trip-mechanism")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 20:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,result,demo,created_at,error_message")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < 500:
            break
        page += 1
    out = []
    for x in rows:
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        blob = " ".join([str(x.get("error_message") or ""),
                         str(res.get("error_where") or ""),
                         str(res.get("error_detail") or "")])
        out.append({
            "id": x.get("id"), "user": x.get("user_id"),
            "status": x.get("status"), "created": str(x.get("created_at")),
            "trip": "INTEGRITY_TRIP" in blob,
            "subcode": str(res.get("error_subcode") or ""),
            "where": str(res.get("error_where") or "")[:80],
            "detail": str(res.get("error_detail") or "")[:400],
            "msg": str(x.get("error_message") or "")[:300],
            "route": str(res.get("route") or ""),
        })
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-10"):
    rows = scan.remote(since)
    trips = [r for r in rows if r["trip"]]
    term = [r for r in rows if r["status"] in ("completed", "failed", "error")]
    done_users = {r["user"] for r in rows if r["status"] == "completed"}
    print(f"\n=== INTEGRITY_TRIP MECHANISM — since {since} ===")
    print(f"  {len(rows)} non-demo jobs, {len(term)} terminal, {len(trips)} trips")

    print(f"\n  [1] WHICH SUB-CLASS trips (this is the mechanism question)")
    for sc, n in Counter(r["subcode"] or "(none)" for r in trips).most_common(10):
        print(f"      {n:>4}  {sc}")
    print(f"      prior art in handler.py: 23 of 25 trips were BLACK at the tail,")
    print(f"      and _ig_source_echo_black was built for exactly that. If black")
    print(f"      is now small, that fix HELD and the class moved elsewhere.")

    print(f"\n  [2] FRAME vs DATE — one drifting site, or several?")
    byframe = defaultdict(list)
    for r in trips:
        byframe[r["where"]].append(r["created"][:10])
    for w, ds in sorted(byframe.items(), key=lambda kv: -len(kv[1])):
        print(f"      {len(ds):>3}  {w}")
        print(f"           dates {sorted(set(ds))[:6]}")
    print(f"      handler.py has exactly ONE `raise RuntimeError(INTEGRITY_TRIP:)`")
    print(f"      today. Distinct line numbers on distinct DATES = one assertion")
    print(f"      drifting as the file grew, not distinct sites.")

    print(f"\n  [3] PER USER — retry inflation and recovery")
    byuser = Counter(r["user"] for r in trips)
    print(f"      {len(trips)} trips across {len(byuser)} distinct users "
          f"({len(trips)/max(1,len(byuser)):.1f} per user)")
    print(f"      users tripping >1x: {sum(1 for u,n in byuser.items() if n>1)}")
    rec = {u for u in byuser if u in done_users}
    print(f"      trippers who ALSO have a completed job: {len(rec)}/{len(byuser)} "
          f"({100.0*len(rec)/max(1,len(byuser)):.0f}%)")
    print(f"      never completed anything (the real loss): "
          f"{len(set(byuser) - done_users)}")

    print(f"\n  [4] the detail line — what the gate actually saw")
    for r in trips[:6]:
        print(f"      {r['created'][:16]} {str(r['id'])[:8]} {r['subcode']}")
        print(f"        {r['detail'][:200] or r['msg'][:200]}")
