"""DOES UPLOAD_NEVER_STARTED FALL AS 1.3.16 ADOPTS? ($0 — one CPU container.)

THE CLASS: 11 of 16 failing users post-v574 (69%), at 1.0 jobs/user. That is
ABANDONMENT, not retry — people who fail once and never come back. It dwarfs
everything the speed work is aimed at, and it is the same door that loses users
upstream. 1.3.16 shipped the iCloud materialization fix, the resume window and
the failure notification.

CUT BY VERSION, NEVER BY CLOCK. Adoption is gradual, so a pre/post time cut
mixes adopters with non-adopters in BOTH windows and regresses toward no effect
however good the fix is — the same confound shape as the warm/cold container
mixture, one layer up. A time cut cannot answer this question at all.

STEP 0 IS A SHAPE PROBE, and it runs before any aggregation: if the client
version is not on the row, this read is IMPOSSIBLE and must say so rather than
fall back to a clock cut and report a number. That is the discipline the
falsifier work forced — establish the reading can be TAKEN before taking it.
"""
import os
import sys
import json
import modal

app = modal.App("query-upload-adoption")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# Every plausible home for a client build string, checked by NAME.
VERSION_CANDIDATES = [
    "app_version", "client_version", "build", "build_number", "ios_version",
    "version", "client_build", "app_build", "sdk_version",
]


@app.function(image=image, secrets=SECRETS, timeout=600)
def probe() -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    out = {"columns": None, "column_probe_errors": {}, "found_version_columns": [],
           "result_keys_sample": None, "metadata_sample": None}

    # 1. What TOP-LEVEL columns exist? select("*") on one row names them.
    try:
        r = sb.table("video_jobs").select("*").limit(1).execute()
        if r.data:
            out["columns"] = sorted(r.data[0].keys())
    except Exception as e:
        out["column_probe_errors"]["star"] = f"{type(e).__name__}: {e}"

    # 2. Probe each candidate BY NAME — a column absent from the sample row can
    #    still exist (it may simply be NULL there), so ask the API directly.
    for c in VERSION_CANDIDATES:
        try:
            sb.table("video_jobs").select(c).limit(1).execute()
            out["found_version_columns"].append(c)
        except Exception as e:
            out["column_probe_errors"][c] = str(e)[:80]

    # 3. Is it hiding inside a jsonb blob instead?
    try:
        r2 = (sb.table("video_jobs").select("result, metadata")
              .not_.is_("result", "null").limit(1).execute())
        if r2.data:
            _res = r2.data[0].get("result")
            out["result_keys_sample"] = (sorted(_res.keys())[:40]
                                         if isinstance(_res, dict) else str(type(_res)))
            _md = r2.data[0].get("metadata")
            out["metadata_sample"] = (json.dumps(_md)[:400] if _md else None)
    except Exception as e:
        out["column_probe_errors"]["result_metadata"] = str(e)[:120]

    return out


def _vkey(v):
    """Sortable version tuple from strings like "1.3.16 (234)".

    THE BUILD NUMBER IS IN PARENS AND BROKE THE FIRST PARSER. int("16 (234)")
    raises, the except returned (9999,), and (9999,) >= (1,3,16) is TRUE — so
    EVERY build classified as 1.3.16+ and the read announced "100% adopted"
    while the table beside it plainly showed 1.3.6, 1.3.11 and 1.3.12 users.
    A parser failing OPEN into the experimental cohort is the worst direction
    to fail in: it makes an unadopted population look fully adopted.

    Unknown now sorts to (-1,) — it can never masquerade as the newest build.
    """
    import re as _re
    m = _re.match(r"\s*(\d+)\.(\d+)\.(\d+)", str(v or ""))
    return tuple(int(g) for g in m.groups()) if m else (-1,)


@app.function(image=image, secrets=SECRETS, timeout=600)
def read(since: str = "", limit: int = 20000) -> dict:
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
             .select("id, user_id, created_at, status, app_version, error_message, "
                     "ec:result->error_code")
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

    by_v = {}
    for r in rows:
        v = r.get("app_version") or "unknown"
        uid = r.get("user_id")
        b = by_v.setdefault(v, {"jobs": 0, "users": set(), "uns_users": set(),
                                "uns_jobs": 0, "failed_users": set(), "failed_jobs": 0})
        b["jobs"] += 1
        if uid:
            b["users"].add(uid)
        failed = (r.get("status") or "") in ("failed", "error")
        code = r.get("ec") or ""
        # UPLOAD_NEVER_STARTED is the coded class; fall back to the message only
        # when the code is absent, and say so rather than silently widening.
        is_uns = (code == "UPLOAD_NEVER_STARTED") or (
            not code and "UPLOAD_NEVER_STARTED" in (r.get("error_message") or ""))
        if failed:
            b["failed_jobs"] += 1
            if uid:
                b["failed_users"].add(uid)
        if is_uns:
            b["uns_jobs"] += 1
            if uid:
                b["uns_users"].add(uid)

    out = {}
    for v, b in by_v.items():
        nu = len(b["users"])
        out[v] = {
            "users": nu, "jobs": b["jobs"],
            # THE NUMBER: share of that build's USERS who hit the class.
            "uns_users": len(b["uns_users"]),
            "uns_user_rate": round(len(b["uns_users"]) / nu, 4) if nu else None,
            "uns_jobs": b["uns_jobs"],
            "uns_jobs_per_user": (round(b["uns_jobs"] / len(b["uns_users"]), 2)
                                  if b["uns_users"] else None),
            "failed_users": len(b["failed_users"]),
            "failed_user_rate": round(len(b["failed_users"]) / nu, 4) if nu else None,
        }
    return {"window_since": since or "all", "rows_scanned": len(rows),
            "by_version": dict(sorted(out.items(), key=lambda kv: _vkey(kv[0])))}


@app.local_entrypoint()
def main(since: str = "", limit: int = 20000):
    r = probe.remote()
    print(json.dumps(r, indent=1)[:2600])
    if r.get("error"):
        print(f"\n  ❌ {r['error']}")
        sys.exit(1)
    found = r.get("found_version_columns") or []
    print(f"\n  version-bearing columns FOUND: {found or 'NONE'}")
    if not found:
        print("\n  ❌ THE READ IS NOT POSSIBLE AS SPECIFIED.")
        print("  No client build string on video_jobs, so UPLOAD_NEVER_STARTED")
        print("  cannot be cut by version. A clock cut would mix adopters and")
        print("  non-adopters in BOTH windows and regress toward no effect —")
        print("  it would answer a different question and look like an answer.")
        sys.exit(2)
    print("  -> the version cut is possible.\n")

    d = read.remote(since=since, limit=limit)
    if d.get("error"):
        print(f"  ❌ {d['error']}"); sys.exit(1)
    bv = d["by_version"]
    print(f"  window {d['window_since']}   scanned {d['rows_scanned']}\n")
    print(f"  {'version':>10} {'users':>6} {'jobs':>5} {'UNS_u':>6} {'UNS/u%':>7} "
          f"{'j/UNSu':>7} {'fail_u':>7} {'fail%':>6}")
    for v, b in bv.items():
        print(f"  {v:>10} {b['users']:>6} {b['jobs']:>5} {b['uns_users']:>6} "
              f"{(100*b['uns_user_rate'] if b['uns_user_rate'] is not None else 0):>6.1f}% "
              f"{str(b['uns_jobs_per_user']):>7} {b['failed_users']:>7} "
              f"{(100*b['failed_user_rate'] if b['failed_user_rate'] is not None else 0):>5.1f}%")
    tot_u = sum(b["users"] for b in bv.values())
    new = {v: b for v, b in bv.items() if _vkey(v) >= (1, 3, 16) and v != "unknown"}
    old = {v: b for v, b in bv.items() if _vkey(v) < (1, 3, 16)}
    nu, ou = sum(b["users"] for b in new.values()), sum(b["users"] for b in old.values())
    print(f"\n  ADOPTION: {nu} users on 1.3.16+, {ou} on older "
          f"({(100*nu/tot_u if tot_u else 0):.1f}% adopted of {tot_u} total)")
    if not nu or not ou:
        print("\n  ONLY ONE COHORT PRESENT — no concurrent comparison is possible.")
        print("  Not a result. A clock cut here would mix adopters and non-adopters.")
        sys.exit(2)
    nun = sum(b["uns_users"] for b in new.values())
    oun = sum(b["uns_users"] for b in old.values())
    print(f"  UPLOAD_NEVER_STARTED by USERS:  1.3.16+ {nun}/{nu} = "
          f"{100*nun/nu:.1f}%   older {oun}/{ou} = {100*oun/ou:.1f}%")
    print("\n  Both cohorts sit in the SAME window, so traffic conditions are")
    print("  shared and the only systematic difference is the build.")
