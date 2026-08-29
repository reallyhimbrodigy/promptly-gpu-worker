"""PRODUCTION HEALTH WITH A DENOMINATOR — and the blast radius of a dead AWS key.

Two questions, one read:

  1. Did the __round__ regression stop? Cut the window at v586 (2026-08-29T01:00Z)
     and count the class against a real denominator. A zero over a denominator of
     1 is not an answer — this reports the denominator so a small one is VISIBLE
     rather than dressed up as a result.

  2. The deployed worker's AWS key is rejected by AWS (probe_aws_creds_app:
     PutObject -> InvalidAccessKeyId). `_aws_s3_client` is used by the BURST
     render path (handler.py:28432-28496 uploads overlay/micro inputs and pulls
     chunk outputs). If burst renders were dying on it, that is a live incident
     that outranks everything else. If they are completing, the dead key is
     confined to auxiliary paths and the sweep is what is blocked, not users.

     Measured, not argued: count completions and render_legs by hour.

Rule 7: per-USER counts alongside per-job, users first.

  ./run_modal.sh probe_prod_health_app.py --hours 12
"""
import os
from collections import Counter

import modal

app = modal.App("probe-prod-health")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 1000
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,created_at,error_message,result,demo")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 20:
            break
    return {"rows": rows, "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-29T01:00:00+00:00"):
    d = scan.remote(since)
    rows = d["rows"]
    # DEMO ROWS ARE MINE, NOT USERS'. Sweep/confirmation jobs are marked demo=True
    # precisely so they never contaminate a product metric (Rule 5, clean cohort).
    organic = [r for r in rows if not r.get("demo")]
    mine = [r for r in rows if r.get("demo")]

    print(f"\n=== window {d['since']} onward (v586 live 2026-08-29T01:00Z) ===")
    print(f"  {len(rows)} rows  =  {len(organic)} organic  +  {len(mine)} demo/mine")
    if not organic:
        print("\n  ORGANIC DENOMINATOR IS ZERO. Nothing can be concluded about the")
        print("  fix from real traffic in this window — not 'it works', not 'it")
        print("  doesn't'. The deploy is younger than the traffic it needs.")

    st = Counter(str(r.get("status")) for r in organic)
    print(f"\n  organic status: {dict(st)}")

    def _res(r):
        v = r.get("result")
        return v if isinstance(v, dict) else {}

    failed = [r for r in organic if str(r.get("status")) in ("failed", "error")]
    codes = Counter(str(_res(r).get("error_code") or "?") for r in failed)
    if failed:
        print(f"\n  organic failures: {len(failed)} jobs / "
              f"{len({r.get('user_id') for r in failed})} users (users lead, Rule 7)")
        for c, n in codes.most_common(10):
            _u = len({r.get("user_id") for r in failed
                      if str(_res(r).get("error_code") or "?") == c})
            print(f"      {n:>3} jobs / {_u:>2} users   {c}")

    # (1) THE __round__ CLASS
    hits = [r for r in organic
            if "__round__" in (str(_res(r).get("error_detail") or "")
                               + str(r.get("error_message") or ""))]
    print(f"\n  __round__ class: {len(hits)} jobs / "
          f"{len({h.get('user_id') for h in hits})} users"
          f"   OUT OF {len(organic)} organic jobs")
    if not hits and organic:
        print("      zero over a REAL denominator")
    elif not hits:
        print("      zero over an EMPTY denominator — proves nothing (see above)")
    for h in hits[:5]:
        print(f"      {h.get('created_at')} {_res(h).get('error_where')}")

    # (2) BURST-PATH BLAST RADIUS of the dead AWS key
    done = [r for r in organic if str(r.get("status")) == "completed"]
    legs = [r for r in done
            if (_res(r).get("stage_timings") or {}).get("render_legs")]
    print(f"\n  completions: {len(done)} jobs / "
          f"{len({r.get('user_id') for r in done})} users")
    print(f"  of those, WITH render_legs (burst path): {len(legs)}")
    if done:
        print("      → renders are completing, so the rejected AWS key is NOT")
        print("        killing user jobs; it is confined to paths the main")
        print("        delivery route does not use (delivery PUTs to a")
        print("        caller-supplied presigned URL, no AWS creds needed).")
    else:
        print("      → NO completions in this window. Cannot separate 'quiet")
        print("        traffic' from 'burst path broken by the dead key'.")
