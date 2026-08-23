#!/usr/bin/env python3
"""read_standing_board.py — THE NUMBERS THAT MUST NEVER GO UNWATCHED AGAIN.

Each line here exists because it moved a lot while nothing was looking.

  SAFE-EDIT SHARE. Between 35.6% and 65.8% of completions were shipping a
  STRIPPED safe edit — no MG, no b-roll, no overlays — and the dashboards were
  green throughout, because completion rate and p50 wall are both blind to WHAT
  was delivered. It fell to 0.0% when PROMPTLY_EDITORIAL_LIVE=1 landed
  (2026-08-21). That was the largest quality change of the campaign and it was
  discovered four days late, by accident, while chasing a different bug.

  UPLOAD FUNNEL. 47% of users who request an upload never get a job row. The
  server-side instrument (`upload_url_requested`) has been firing since well
  before anyone read it — the class was unread, not unbuilt.

  EDITORIAL SHARE + UNKNOWN. The flip is only real while editorial keeps
  routing; a silent fall back to safe-edit would look identical on every other
  metric.

Read it, do not infer it. Every number carries its denominator [Rule 2] and the
user cut leads where a user cut exists [Rule 7].

    python3 read_standing_board.py [--days 3]
"""
import argparse, collections, json, os, statistics as st, sys, urllib.parse, urllib.request
import promptly_read as P


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


url, key = _creds()
ap = argparse.ArgumentParser(); ap.add_argument("--since", default="2026-08-20T00:00:00Z")
a = ap.parse_args()
Q = urllib.parse.quote(a.since)


def _count(path):
    r = urllib.request.Request(url + "/rest/v1/" + path,
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Prefer": "count=exact", "Range": "0-0"})
    return int(urllib.request.urlopen(r, timeout=90).headers.get("content-range", "0/0").split("/")[-1])


def _page(path, cap=20000):
    out, off = [], 0
    while off < cap:
        r = urllib.request.Request(url + "/rest/v1/" + path + f"&offset={off}&limit=1000",
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        b = json.loads(urllib.request.urlopen(r, timeout=120).read())
        out += b; off += 1000
        if len(b) < 1000:
            break
    return out


print(f"  ══ STANDING BOARD · since {a.since} ══")
# error_message IS IN THE SELECT DELIBERATELY. The first cut omitted it, so
# x.get("error_message") was None on every row and all 58 failures scored as
# UNKNOWN — a fabricated trigger on the board built to stop fabricated triggers.
# A column you did not ask for reads exactly like a column that is empty.
rows = _page(f"video_jobs?select=id,created_at,status,user_id,error_message,stage_timings,result"
             f"&created_at=gte.{Q}&order=created_at.desc")
done = [x for x in rows if str(x.get("status")) == "completed"]

# ── 1. SAFE-EDIT SHARE, by day, with its denominator ────────────────────
byday, tot = collections.Counter(), collections.Counter()
for x in done:
    d = x["created_at"][:10]; tot[d] += 1
    rec = P.edit_plan(x)
    if rec is not P.MISSING and "safe-edit" in str(rec.get("notes") or ""):
        byday[d] += 1
print("\n  SAFE-EDIT SHARE (a stripped edit delivered as if it were the product)")
for d in sorted(tot):
    pct = byday[d] / tot[d] * 100 if tot[d] else 0
    flag = "   <-- REGRESSION" if pct >= 5 else ""
    print(f"    {d}  {byday[d]:>4}/{tot[d]:<4} = {pct:5.1f}%{flag}")

# ── 2. ROUTE MIX — the flip is only real while editorial keeps routing ──
routes = collections.Counter(P.route(x) for x in done)
n = sum(routes.values())
print(f"\n  ROUTE MIX (n={n})")
for r_, c in routes.most_common():
    print(f"    {r_:<12} {c:>4}  {c/n*100 if n else 0:5.1f}%")

# ── 3. UPLOAD FUNNEL, per user ──────────────────────────────────────────
ne = _count(f"analytics_events?select=id&event=eq.upload_url_requested&created_at=gte.{Q}")
ev = _page(f"analytics_events?select=anon_user_id&event=eq.upload_url_requested&created_at=gte.{Q}")
eu = {e.get("anon_user_id") for e in ev if e.get("anon_user_id")}
ju = {x.get("user_id") for x in rows if x.get("user_id")}
print(f"\n  UPLOAD FUNNEL")
print(f"    upload requests            {ne:>6}")
print(f"    job rows                   {len(rows):>6}")
print(f"    users requesting           {len(eu):>6}")
print(f"    users who NEVER got a job  {len(eu - ju):>6}  = "
      f"{len(eu - ju)/len(eu)*100 if eu else 0:.0f}%   <-- lead with THIS [Rule 7]")

# ── 4. UNKNOWN, which must stay at zero ─────────────────────────────────
failed = [x for x in rows if str(x.get("status")) == "failed"]
unk = [x for x in failed if not str(x.get("error_message") or "").strip()]
print(f"\n  FAILURES  {len(failed)}/{len(rows)}   UNKNOWN (no message): {len(unk)}"
      + ("   <-- TRIGGER" if unk else ""))
