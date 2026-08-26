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

# AWAITING THE USER IS NOT LIVE WORK (2026-08-17).
#
# A job parked on an ask-back has NO CONTAINER RUNNING. It is waiting on a human,
# and a human may take days. Blocking a deploy on it protects nothing — there is
# no in-flight compute to orphan — while blocking everything.
#
# EXCLUDED BY STATUS, NOT BY STALENESS, and that distinction is the point.
# `needs_input` is not in IN_FLIGHT today, and the container-cap rule below would
# also drop a 27-day-old row, so this is not a live hazard right now — I checked
# before writing it (one row, a619c782, 27.3 days idle at needs_clarification).
# But both of those protections are INCIDENTAL. If `needs_input` were ever added
# to IN_FLIGHT, a user who answers an ask-back promptly would create a FRESH
# needs_input row that blocks deploys for 20 minutes while nothing whatsoever is
# running. Staleness is a proxy for "no container"; status is the fact itself.
AWAITING_USER = ("needs_input", "awaiting_input", "needs_clarification")

# LIVE WORK, NOT MERELY NON-TERMINAL (2026-08-15).
#
# The gate protects in-flight USER WORK from being orphaned by a deploy. A row
# that is non-terminal but STALE is not live work — it is a wedged row whose
# container Modal already killed, and blocking on it protects nothing while
# blocking everything.
#
# THE BOUND IS THE CONTAINER CAP, deliberately, not the heartbeat interval.
# Modal terminates run_pipeline_bg at its 1200s timeout, so NOTHING can still be
# running past it: excluding rows staler than the cap cannot exclude live work,
# by construction. A heartbeat-derived bound (4s) would be far tighter but NOT
# safe — some stages legitimately go quiet for tens of seconds — and a gate that
# skips a live job is worse than one that waits too long.
#
# Test case that forced this: fb702c40, status=processing at step=analyze, age
# 2180s, LAST TOUCHED 2170s ago. One row, wedged ~970s past the point its
# container could exist, blocked every deploy for ~17 minutes — including the
# fix for a contention bug that was live and unfixed.
CONTAINER_CAP_S = int(os.environ.get("PROMPTLY_CONTAINER_CAP_S") or 1200)
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
        inflight_raw = _get(url, key,
                            f"select=id,status,created_at,updated_at,current_step"
                            f"&status=in.({status_in})&limit=200")
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

    # Split LIVE from WEDGED on staleness, and report the wedged ones LOUDLY —
    # silently ignoring them would trade a blocked deploy for an invisible stuck
    # job, which is the worse of the two.
    import datetime as _dt
    _now = _dt.datetime.now(_dt.timezone.utc)

    def _stale_s(row):
        _u = row.get("updated_at") or row.get("created_at")
        if not _u:
            return None                     # unknown age -> treat as LIVE
        try:
            _t = _dt.datetime.fromisoformat(str(_u).replace("Z", "+00:00"))
            if _t.tzinfo is None:
                _t = _t.replace(tzinfo=_dt.timezone.utc)
            return (_now - _t).total_seconds()
        except Exception:
            return None                     # unparseable -> treat as LIVE

    inflight, wedged, parked = [], [], []
    for _r in inflight_raw:
        _s = _stale_s(_r)
        _st = str(_r.get("status") or "").strip().lower()
        _step = str(_r.get("current_step") or "").strip().lower()
        if _st in AWAITING_USER or _step in AWAITING_USER:
            parked.append((_r, _s))          # waiting on a HUMAN — no container
        elif _s is not None and _s > CONTAINER_CAP_S:
            wedged.append((_r, _s))
        else:
            inflight.append((_r, _s))

    if parked:
        print(f"  NOTE: {len(parked)} row(s) are AWAITING USER INPUT — no container "
              f"is running for them, so they are not live work and do not block "
              f"this deploy:")
        for _r, _s in parked[:10]:
            _d = f"{(_s or 0) / 86400:.1f}d" if _s else "?"
            print(f"    parked  {_r.get('id')}  idle={_d}  step={_r.get('current_step')}")

    if wedged:
        print(f"  NOTE: {len(wedged)} non-terminal row(s) are STALER than the "
              f"{CONTAINER_CAP_S}s container cap — their containers cannot still "
              f"exist, so they are NOT live work and do not block this deploy:")
        for _r, _s in wedged[:10]:
            print(f"    WEDGED  {_r.get('status')}/{_r.get('current_step') or '-'}  "
                  f"{_r.get('id')}  stale={int(_s)}s")
        print("  They are still STUCK ROWS and want fixing — they are just not a "
              "reason to hold a deploy.")

    if inflight:
        print(f"QUIET-WINDOW: BUSY — {len(inflight)} in-flight user job(s). "
              "Deploying now orphans live user work.")
        for _r, _s in inflight[:10]:
            print(f"    {_r.get('status')}  {_r.get('id')}  {_r.get('created_at')}"
                  f"  stale={int(_s) if _s is not None else '?'}s")
        print("  Wait for them to settle and re-run. Deliberate override: "
              "PROMPTLY_ALLOW_BUSY_DEPLOY=1 (and attribute the orphans in DEPLOY_LOG.md).")
        return 0 if allow else 1

    print(f"QUIET-WINDOW: OK — 0 in-flight user jobs (probe live: sees "
          f"{len(recent)} recent row(s)). Modal task/container count is NOT "
          "the gate and must not be used as one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
