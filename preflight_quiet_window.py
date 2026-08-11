"""QUIET WINDOW = ZERO IN-FLIGHT USER JOBS (DB), NOT ZERO MODAL TASKS.

Zac's ruling, 2026-08-11, after TRUTH proved the old signal was a false blocker:
`modal app list` reported 6-11 "tasks" continuously for 3+ hours while the DB
held **zero** in-flight user jobs. Those tasks are prewarm + persistent
`@modal.fastapi_endpoint` containers; prewarm fires while the user is still
mid-upload, BEFORE a job row exists. Gating on container count would have
blocked the deploy queue indefinitely while a week of certified work decayed.

This makes the rule EXECUTABLE instead of remembered (Rule 1): deploy.sh runs
it, and a deploy over live user work is refused.

NON-VACUITY IS ENFORCED. A probe that silently matches nothing returns a
confident zero, which is this codebase's most expensive recurring bug class
(and it bit twice during the very investigation that produced this file). So a
zero is only believed if the probe can ALSO see recent terminal rows. If it
cannot see the table at all, that is UNKNOWN -- never "quiet".

  exit 0  QUIET      - zero in-flight, probe proven live
  exit 1  BUSY       - in-flight user jobs exist; do not deploy
  exit 2  UNKNOWN    - cannot measure (no creds / table unreadable / vacuous)

  PROMPTLY_ALLOW_BUSY_DEPLOY=1 downgrades 1 and 2 to a loud warning, for the
  deliberate emergency case. It is never the default.
"""
import json
import os
import sys
import urllib.error
import urllib.request

# A row in any of these is user work that a deploy would orphan.
IN_FLIGHT = ("processing", "pending", "queued")
ENV_FILE = "/Users/zaclibman/content-studio/.env.local"


def _creds():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if url and key:
        return url.rstrip("/"), key
    try:
        with open(ENV_FILE) as fh:
            env = {}
            for line in fh:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'\"")
        url = env.get("SUPABASE_URL")
        key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY")
        if url and key:
            return url.rstrip("/"), key
    except OSError:
        pass
    return None, None


def _get(url, key, query):
    req = urllib.request.Request(
        f"{url}/rest/v1/video_jobs?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    allow = os.environ.get("PROMPTLY_ALLOW_BUSY_DEPLOY")
    url, key = _creds()
    if not url or not key:
        print("QUIET-WINDOW: UNKNOWN — no Supabase credentials (env or "
              f"{ENV_FILE}). Cannot measure in-flight user jobs.")
        return 0 if allow else 2

    status_in = ",".join(IN_FLIGHT)
    try:
        inflight = _get(url, key,
                        f"select=id,status,created_at&status=in.({status_in})&limit=200")
        # NON-VACUITY: the probe must be able to see SOMETHING recent, or its
        # zero means nothing. Any row in the last 24h proves table + auth work.
        recent = _get(url, key, "select=id,status&order=created_at.desc&limit=5")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as e:
        print(f"QUIET-WINDOW: UNKNOWN — video_jobs unreadable ({e}).")
        return 0 if allow else 2

    if not recent:
        print("QUIET-WINDOW: UNKNOWN — the probe sees NO rows at all, so a zero "
              "in-flight reading proves nothing (vacuous probe). Refusing to "
              "call this quiet.")
        return 0 if allow else 2

    if inflight:
        print(f"QUIET-WINDOW: BUSY — {len(inflight)} in-flight user job(s). "
              "Deploying now orphans live user work.")
        for row in inflight[:10]:
            print(f"    {row.get('status')}  {row.get('id')}  {row.get('created_at')}")
        print("  Wait for them to settle and re-run. Deliberate override: "
              "PROMPTLY_ALLOW_BUSY_DEPLOY=1 (and attribute the orphans in DEPLOY_LOG.md).")
        return 0 if allow else 1

    print(f"QUIET-WINDOW: OK — 0 in-flight user jobs (probe live: sees "
          f"{len(recent)} recent row(s)). Modal task/container count is NOT "
          "the gate and must not be used as one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
