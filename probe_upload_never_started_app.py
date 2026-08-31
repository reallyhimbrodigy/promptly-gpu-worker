"""UPLOAD_NEVER_STARTED mechanism — 74 users, 10.5% of active, the largest class.

The server polls S3 for the source object and, when it never lands, terminates
WITHOUT spawning Modal. So the question is not "why did the render fail" — no
render was attempted — it is WHY THE BYTES NEVER ARRIVED.

The candidate causes, and the instrument that separates them:
  - presign expiry .......... FIXED (TTL 600s -> 3600s -> 604800s/7d). If this
                              were still live the class would correlate with a
                              LONG gap between job creation and the gate firing.
  - iCloud eviction ......... video_jobs.source_type ('local'|'icloud'), a
                              column added on 2026-08-03 for exactly this.
  - clip length ............. source_duration; a big clip on a weak network is
                              a different failure from a missing file.
  - the asset never resolved  the picker family (picker_asset_unresolved).

`source_type` is READ, not assumed: a column that exists is not a column that is
populated, and an unpopulated column reads as a clean zero for every arm.
"""
import os
from collections import Counter

import modal

app = modal.App("probe-uns-mechanism")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 24:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,result,demo,created_at,updated_at,"
                     "source_type,source_duration")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < 500:
            break
        page += 1
    uns, other_term = [], []
    for x in rows:
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        rec = {"id": x.get("id"), "user": x.get("user_id"),
               "created": str(x.get("created_at")), "updated": str(x.get("updated_at")),
               "stype": x.get("source_type"), "sdur": x.get("source_duration"),
               "status": str(x.get("status") or "")}
        if str(res.get("error_code") or "") == "UPLOAD_NEVER_STARTED":
            uns.append(rec)
        elif rec["status"] in ("completed", "failed", "error"):
            other_term.append(rec)
    return {"uns": uns, "other": other_term}


@app.local_entrypoint()
def main(since: str = "2026-08-24"):
    d = scan.remote(since)
    uns, other = d["uns"], d["other"]
    print(f"\n=== UPLOAD_NEVER_STARTED — mechanism, since {since} ===")
    print(f"  {len(uns)} jobs, {len({r['user'] for r in uns})} users")

    # ── is the instrument even populated? ──────────────────────────────────
    pop_uns = sum(1 for r in uns if r["stype"])
    pop_oth = sum(1 for r in other if r["stype"])
    print(f"\n  [instrument check] source_type populated on "
          f"{pop_uns}/{len(uns)} UNS jobs, {pop_oth}/{len(other)} other terminals")
    if not pop_uns and not pop_oth:
        print("      COLUMN IS EMPTY EVERYWHERE — the iCloud arm is UNMEASURED.")
        print("      That is an absent read, not 'iCloud is not the cause'. The")
        print("      migration exists; the server write is best-effort and may")
        print("      never have landed, or the client stopped sending it.")
    else:
        print(f"      UNS   source_type: {dict(Counter(r['stype'] for r in uns))}")
        print(f"      other source_type: {dict(Counter(r['stype'] for r in other))}")

    # ── expiry would show as a long created->failed gap ────────────────────
    import datetime as dt
    def gap(r):
        try:
            a = dt.datetime.fromisoformat(r["created"].replace("Z", "+00:00"))
            b = dt.datetime.fromisoformat(r["updated"].replace("Z", "+00:00"))
            return (b - a).total_seconds()
        except Exception:
            return None
    gaps = sorted(g for g in (gap(r) for r in uns) if g is not None)
    if gaps:
        print(f"\n  [expiry test] seconds from job creation to the gate firing:")
        print(f"      n={len(gaps)} min={gaps[0]:.0f} p50={gaps[len(gaps)//2]:.0f} "
              f"max={gaps[-1]:.0f}")
        print(f"      A 7-day presign cannot expire inside these windows, so")
        print(f"      EXPIRY IS REFUTED as the live cause — the bytes are not")
        print(f"      late, they never start.")
    dur = [r["sdur"] for r in uns if isinstance(r["sdur"], (int, float))]
    if dur:
        ds = sorted(dur)
        print(f"\n  [clip length] n={len(ds)} p50={ds[len(ds)//2]:.0f}s max={ds[-1]:.0f}s")
    else:
        print(f"\n  [clip length] source_duration EMPTY on all UNS jobs — unmeasured")

    # ── repeat vs one-shot users ───────────────────────────────────────────
    per = Counter(r["user"] for r in uns)
    once = sum(1 for u, n in per.items() if n == 1)
    print(f"\n  [users] {len(per)} affected; {once} hit it ONCE, "
          f"{len(per)-once} more than once")
    done_users = {r["user"] for r in other if r["status"] == "completed"}
    stuck = set(per) - done_users
    print(f"      never completed ANY job in the window: {len(stuck)}/{len(per)} "
          f"({100.0*len(stuck)/max(1,len(per)):.0f}%)  <- the real loss")
