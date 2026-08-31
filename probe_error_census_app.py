"""ERROR CENSUS — ranked by AFFECTED USERS, not job count.

Per-job counting inflates every class by the retry multiplier: a user who fails
five times and gives up is ONE LOST USER, not five failures. That is exactly
what made a one-user 100fps bug read as a 67% outage. Both numbers are reported;
the ranking leads with users.

THE SPLIT THAT DECIDES THE FIX, and the two are not the same defect:

  unclassified — the error REACHED the classifier and no signature matched.
                 Fix = add a signature. The traceback is usually present.
  no_subcode   — the error never produced a subcode at all: it escaped the
                 classifier, or a hand-built terminal envelope was written that
                 never passed through it. Fix = route it through the chokepoint.
                 These look identical in a naive count and need opposite work.

Also separates DESIGNED REJECTIONS (the product saying no — too short, no
speech) from DEFECTS (we broke), because a rejection is not a failure to fix.
"""
import os
from collections import Counter, defaultdict

import modal

app = modal.App("probe-error-census")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 24:
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
        out.append({
            "user": x.get("user_id"), "status": str(x.get("status") or ""),
            "code": str(res.get("error_code") or ""),
            "sub": str(res.get("error_subcode") or ""),
            "designed": bool(res.get("designed_rejection")),
            "where": str(res.get("error_where") or "")[:60],
            "msg": str(x.get("error_message") or "")[:90],
        })
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-24"):
    rows = scan.remote(since)
    term = [r for r in rows if r["status"] in ("completed", "failed", "error")]
    fails = [r for r in term if r["status"] != "completed"]
    all_users = {r["user"] for r in term if r["user"]}
    print(f"\n=== ERROR CENSUS — since {since} ===")
    print(f"  WINDOW NOTE: '1.3.21' has no timestamp I can read from the job")
    print(f"  rows, so this is a clean recent window, stated rather than assumed.")
    print(f"  {len(term)} terminal jobs, {len(all_users)} users, "
          f"{len(fails)} failures ({100.0*len(fails)/max(1,len(term)):.1f}%)")

    # ── the split ───────────────────────────────────────────────────────────
    unclass = [r for r in fails if r["sub"] == "unclassified"]
    nosub = [r for r in fails if not r["sub"]]
    coded = [r for r in fails if r["sub"] and r["sub"] != "unclassified"]
    print(f"\n  THE SPLIT (different defects, different fixes):")
    for lbl, grp, fix in (
            ("coded (signature matched)", coded, "class-specific"),
            ("unclassified (reached _e, no signature)", unclass, "add a signature"),
            ("no_subcode (escaped _e entirely)", nosub, "route through the chokepoint")):
        u = {r["user"] for r in grp if r["user"]}
        print(f"    {len(grp):>5} jobs / {len(u):>4} users   {lbl:<42} -> {fix}")

    # ── ranking BY USER ─────────────────────────────────────────────────────
    byclass = defaultdict(lambda: {"jobs": 0, "users": set(), "designed": 0})
    for r in fails:
        key = f"{r['code'] or '(no code)'}:{r['sub'] or '(no subcode)'}"
        d = byclass[key]
        d["jobs"] += 1
        if r["user"]:
            d["users"].add(r["user"])
        d["designed"] += 1 if r["designed"] else 0
    print(f"\n  RANKED BY AFFECTED USERS (jobs shown too — the ratio is the retry"
          f" multiplier):")
    print(f"    {'users':>6} {'jobs':>6} {'j/u':>5}  {'designed':>8}  class")
    ranked = sorted(byclass.items(), key=lambda kv: -len(kv[1]["users"]))
    for key, d in ranked[:14]:
        n = len(d["users"])
        print(f"    {n:>6} {d['jobs']:>6} {d['jobs']/max(1,n):>5.1f}  "
              f"{d['designed']:>8}  {key}")

    top = [k for k, d in ranked if d["designed"] == 0][:1]
    if top:
        k = top[0]
        d = byclass[k]
        print(f"\n  LARGEST NON-DESIGNED CLASS: {k}")
        print(f"    {len(d['users'])} users, {d['jobs']} jobs "
              f"({100.0*len(d['users'])/max(1,len(all_users)):.1f}% of active users)")
        ex = [r for r in fails
              if f"{r['code'] or '(no code)'}:{r['sub'] or '(no subcode)'}" == k]
        print(f"    frames:")
        for w, n in Counter(r["where"] for r in ex).most_common(4):
            print(f"      {n:>4}  {w or '(none)'}")
        print(f"    messages:")
        for m, n in Counter(r["msg"] for r in ex).most_common(3):
            print(f"      {n:>4}  {m[:80]}")
