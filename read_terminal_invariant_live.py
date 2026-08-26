#!/usr/bin/env python3
"""DID THE DELIVERABLE GUARD ACTUALLY EXECUTE? — the production counter. `[Rule 2, Rule 5, Rule 7]`

THE STANDARD THIS ANSWERS TO (owner, 2026-08-18): "a fix isn't reportable as
shipped until a production counter proves it executed." The guard is deployed
(content-studio d121eba, live in rev 1e4b59f). Deployed is not executed.

═══ THE COUNTER IS AMBIGUOUS UNLESS IT IS CUT ═══

`completion_delivery='invariant_heal'` is stamped by TWO different writers:

    heal_terminal_invariant.py   MY manual back-heal of the 124-row cohort
    lib/terminal-invariant.js    THE GUARD, at failure time, in production

Reporting their sum as "the guard fired N times" would be a lie of exactly the
kind Rule 5 exists to prevent — a contaminated window. So they are separated by
the CLEAN COHORT BOUNDARY: the manual heal only ever touched rows created BEFORE
the guard shipped, so a row created at-or-after the boundary carrying the stamp
can only have come from the guard.

═══ AND A ZERO HERE IS NOT AN ANSWER BY ITSELF ═══

The guard only fires when a job would have been terminal-failed WHILE HOLDING A
RENDERED VIDEO. If no job hit that shape in the window, the correct report is
"0 out of N failures had a deliverable" — a real result — and NOT "the guard
works". The two are distinguished by printing the denominator every time, and by
refusing to speak at all when the window holds no rows (a vacuous probe).

    python3 read_terminal_invariant_live.py [--since 2026-08-18T15:07:53Z]
"""
import argparse
import collections
import json
import sys
import urllib.parse
import urllib.request

ENV = "/Users/zaclibman/content-studio/.env.local"
# content-studio d121eba on main 14:54:52Z; rev 1e4b59f gate-stamped 15:07:53Z.
# Take the LATER — a job created before the deploy completed cannot be protected.
GUARD_LIVE = "2026-08-18T15:07:53Z"


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _get(url, key, path):
    req = urllib.request.Request(f"{url}/rest/v1/{path}",
                                 headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def _deliverable(row):
    d = row.get("rendered_video_url") or row.get("result_url") or row.get("hls_manifest_url")
    if d:
        return d
    res = row.get("result")
    if isinstance(res, dict):
        return res.get("video_url") or res.get("rendered_video_url")
    return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=GUARD_LIVE)
    a = ap.parse_args(argv)
    url, key = _creds()
    since = urllib.parse.quote(a.since)

    sel = ("id,user_id,status,created_at,completion_delivery,error_message,"
           "rendered_video_url,result_url,hls_manifest_url,result")
    rows = _get(url, key, f"video_jobs?select={sel}&created_at=gte.{since}"
                          f"&order=created_at.asc&limit=2000")

    print(f"  WINDOW: created_at >= {a.since}  (content-studio rev 1e4b59f, the")
    print(f"  first deploy carrying the guard — jobs before it CANNOT be protected,")
    print(f"  which is why the window starts here and not 24h back.)")
    if not rows:
        # NON-VACUITY. No rows means "not observed yet", never "no violations".
        print(f"\n  0 jobs in the window. This is NOT a result — the probe has")
        print(f"  nothing to see. Re-run when traffic lands.")
        return 0

    by_status = collections.Counter(r["status"] for r in rows)
    users = {r["user_id"] for r in rows}
    terminal_fail = [r for r in rows if r["status"] == "failed"]
    fail_users = {r["user_id"] for r in terminal_fail}

    print(f"\n  DENOMINATOR: {len(rows)} jobs / {len(users)} users")
    print(f"  status: {dict(by_status)}")
    print(f"\n  FAILURE RATE  {len(terminal_fail)}/{len(rows)} jobs "
          f"({100.0*len(terminal_fail)/len(rows):.1f}%)"
          f"   —   {len(fail_users)}/{len(users)} USERS "
          f"({100.0*len(fail_users)/len(users):.1f}%)  [Rule 7: lead with users]")

    # THE COUNTER. In-window stamps can only be the guard: the manual heal ran
    # once, before the boundary, against rows created before the boundary.
    fired = [r for r in rows if r.get("completion_delivery") == "invariant_heal"]
    fired_users = {r["user_id"] for r in fired}
    print(f"\n  GUARD EXECUTIONS IN-WINDOW: {len(fired)} jobs / {len(fired_users)} users")
    for r in fired[:10]:
        print(f"     {r['id'][:8]}  {r['created_at'][:19]}  status={r['status']}  "
              f"video={'yes' if _deliverable(r) else 'NO'}")
    if not fired:
        print(f"     none — and that is a RESULT, not a failure of the guard: it")
        print(f"     fires only when a job would have been terminal-failed WHILE")
        print(f"     HOLDING A VIDEO. {len(terminal_fail)} failures occurred and")
        print(f"     none carried a deliverable, which is the outcome we wanted.")

    # THE INVARIANT ITSELF — the thing the guard exists to make impossible.
    violations = [r for r in terminal_fail if _deliverable(r)]
    print(f"\n  INVARIANT (a failed row holding a video): {len(violations)} "
          f"violation(s) in-window, out of {len(terminal_fail)} failure(s)")
    if violations:
        print(f"  *** THE GUARD IS NOT HOLDING — these rows have a playable video")
        print(f"      and told their user it failed:")
        for r in violations[:10]:
            print(f"     {r['id'][:8]}  {r['created_at'][:19]}  "
                  f"{(r.get('error_message') or '')[:60]}")
        return 1

    # CONTAMINATION CHECK, stated rather than assumed: how many pre-window rows
    # carry the same stamp, so the two populations are never read as one.
    pre = _get(url, key, f"video_jobs?select=id&completion_delivery=eq.invariant_heal"
                         f"&created_at=lt.{since}&limit=2000")
    print(f"\n  (pre-window rows carrying the same stamp: {len(pre)} — the manual")
    print(f"   back-heal. Deliberately EXCLUDED above; summing them would report")
    print(f"   my own repair as the guard's production count.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
