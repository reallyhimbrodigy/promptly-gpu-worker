"""WATCH: the first ORGANIC job to land on v586, and what the __round__ class did.

The open Rule 2 leg. v586 (3e64ac8) fixed the shot_changes seam, is cert-green
and gate-green, and has been observed by NOBODY on real traffic — the organic
denominator since 2026-08-29T01:00Z is zero. `0 hits / 0 jobs` is not a green;
it is an absent measurement, and this exits non-zero until a REAL denominator
exists so a caller cannot mistake quiet traffic for a working fix.

EXIT CODES are the contract (an `until` loop reads them):
    0  organic jobs exist in the window — the verdict below is REAL
    9  no organic jobs yet — keep waiting, conclude nothing
    2  the read itself failed — NOT the same as "no jobs" (probe-collapse law:
       a failed measurement must never be reported as a confident zero)

  ./run_modal.sh watch_v586_first_job_app.py
"""
import os

import modal

app = modal.App("watch-v586-first-job")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

# v586 deployed 2026-08-28 18:00 PDT.
SINCE = "2026-08-29T01:00:00+00:00"


@app.function(image=image, secrets=S, timeout=300)
def look(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = (sb.table("video_jobs")
         .select("id,user_id,status,created_at,error_message,result,demo")
         .gte("created_at", since).order("created_at", desc=True)
         .limit(500).execute())
    rows = [x for x in (r.data or []) if not x.get("demo")]

    def _res(x):
        v = x.get("result")
        return v if isinstance(v, dict) else {}

    hits = [x for x in rows
            if "__round__" in (str(_res(x).get("error_detail") or "")
                               + str(x.get("error_message") or ""))]
    done = [x for x in rows if str(x.get("status")) == "completed"]
    failed = [x for x in rows if str(x.get("status")) in ("failed", "error")]
    return {
        "organic": len(rows),
        "users": len({x.get("user_id") for x in rows}),
        "completed": len(done),
        "failed": len(failed),
        "round_hits": len(hits),
        "round_users": len({x.get("user_id") for x in hits}),
        "round_frames": sorted({str(_res(h).get("error_where")) for h in hits}),
        "codes": sorted({str(_res(x).get("error_code")) for x in failed}),
        "first_at": (rows[-1].get("created_at") if rows else None),
    }


@app.local_entrypoint()
def main(since: str = SINCE, min_resolved: int = 8):
    """min_resolved: RESOLVED jobs (completed+failed) needed before the zero is
    worth reporting. A queued job carries no verdict — the first organic job on
    v586 landed at 06:44Z with status neither completed nor failed, and counting
    it as evidence would be the clean-zero trap with extra steps. v584 hit ~67%
    of organic jobs, so 8 resolved jobs make a clean run ~0.996 unlikely by
    chance; 1 makes it meaningless.
    """
    import sys
    try:
        d = look.remote(since)
    except Exception as e:
        print(f"WATCH: READ FAILED ({type(e).__name__}: {str(e)[:140]}) — "
              f"this is NOT 'no jobs'.")
        sys.exit(2)

    n = d["organic"]
    _resolved = d["completed"] + d["failed"]

    # A RECURRENCE OUTRANKS THE THRESHOLD. If the class is back, say so on the
    # first sighting — never wait for a denominator to report a regression.
    if d["round_hits"]:
        print(f"\n  ⚠️  __round__ RECURRED: {d['round_hits']} jobs / "
              f"{d['round_users']} users out of {n} organic")
        print(f"      frames: {d['round_frames']}")
        print("      THE FIX DID NOT HOLD — read the frame; it may be a "
              "DIFFERENT site than handler.py:7506.")
        sys.exit(0)

    if not n:
        print(f"WATCH: organic=0 since {since} — still waiting, concluding nothing.")
        sys.exit(9)
    if _resolved < min_resolved:
        print(f"WATCH: {n} organic job(s), only {_resolved}/{min_resolved} "
              f"RESOLVED (queued jobs carry no verdict) — still waiting.")
        sys.exit(9)

    print(f"\n  ══ FIRST ORGANIC TRAFFIC ON v586 ══")
    print(f"  window      : {since} onward (first job {d['first_at']})")
    print(f"  denominator : {n} organic jobs / {d['users']} users")
    print(f"  outcome     : {d['completed']} completed, {d['failed']} failed")
    if d["codes"]:
        print(f"  fail codes  : {', '.join(d['codes'])}")
    print(f"\n  __round__   : 0 jobs / 0 users OUT OF {_resolved} RESOLVED "
          f"({n} seen)")
    # v584's rate was ~67%. P(all clean | still broken) ~= 0.33**resolved.
    _p = 0.33 ** _resolved
    print(f"  >>> ZERO over a REAL denominator. If the fix had NOT held, a run "
          f"this clean has probability ~{_p:.1e}.")
    print("      This is evidence the seam fix holds on organic traffic. It is "
          "NOT proof the burst path is healthy — that is still unmeasured.")
    sys.exit(0)
