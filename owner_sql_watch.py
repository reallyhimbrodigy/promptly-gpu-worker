"""DETECT an owner SQL apply, flip PENDING -> APPLIED, and start the clocks.

Zac's rule (2026-08-11): `~/Desktop/Promptly Reports/` holds the SQL he runs by
hand. The `.sql` files there are PURE runnable SQL — select-all, copy, paste,
Run, zero editing — so no status text may live inside them. All status lives in
`_STATUS.md` beside them, which is what this script rewrites. He never pastes
anything back, so detection is OUR job, not his.

This probes for the actual objects. A status only flips on a PROBE — never on a
claim, never on a paste-back, never on "it looked like it worked".

It also enforces the distinction that matters: **DDL having run is not the same
as an instrument working.** For DELIVERY's column, existence flips the status,
but the 48h watch clock only starts once rows are actually FLOWING (a non-null
value observed on a real completion).

  python3 owner_sql_watch.py            # probe once, report
  python3 owner_sql_watch.py --apply    # ...and rewrite the Desktop file's status

Zero Modal spend. Read-only against Supabase.
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

DESKTOP_FILE = "/Users/zaclibman/Desktop/Promptly Reports/_STATUS.md"
ENV_FILE = "/Users/zaclibman/content-studio/.env.local"


def _creds():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return url.rstrip("/"), key
    try:
        env = {}
        with open(ENV_FILE) as fh:
            for line in fh:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'\"")
        return (env.get("SUPABASE_URL") or "").rstrip("/"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    except OSError:
        return None, None


def _get(url, key, path):
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def probe(url, key):
    """Real existence checks. A 200 means the object is there; 400/404 means it is not."""
    out = {}
    for label, path in (
        ("table  public.fulfillment_scores", "fulfillment_scores?select=job_id&limit=1"),
        ("table  public.daily_scoreboard", "daily_scoreboard?select=day&limit=1"),
        ("column video_jobs.completion_delivery", "video_jobs?select=completion_delivery&limit=1"),
        ("column video_jobs.worker_started_at", "video_jobs?select=worker_started_at&limit=1"),
    ):
        try:
            _get(url, key, path)
            out[label] = True
        except urllib.error.HTTPError:
            out[label] = False
        except Exception as e:                       # network/auth trouble is UNKNOWN, not False
            out[label] = None
            print(f"  ! {label}: probe error ({e})")
    return out


def instrument_flowing(url, key):
    """DDL ran != the instrument works. Look for a real non-null stamp."""
    try:
        rows = _get(url, key,
                    "video_jobs?select=id,completion_delivery&completion_delivery=not.is.null&limit=5")
        return len(rows), [r.get("completion_delivery") for r in rows]
    except Exception:
        return 0, []


def main():
    url, key = _creds()
    if not url or not key:
        print("OWNER-SQL WATCH: UNKNOWN — no Supabase credentials.")
        return 2

    res = probe(url, key)
    for k, v in res.items():
        print(f"  {'ok     ' if v else ('MISSING' if v is False else 'UNKNOWN')}  {k}")

    if any(v is None for v in res.values()):
        print("OWNER-SQL WATCH: UNKNOWN — at least one probe could not run. Not flipping.")
        return 2

    applied = all(res.values())
    n_flowing, sample = instrument_flowing(url, key)

    if not applied:
        print("OWNER-SQL WATCH: entry 01 still PENDING.")
        return 1

    print("OWNER-SQL WATCH: entry 01 objects ALL PRESENT -> APPLIED.")
    if n_flowing:
        print(f"  instrument FLOWING: {n_flowing} row(s) with completion_delivery set "
              f"(e.g. {sample[:3]}) -> DELIVERY's 48h watch clock STARTS NOW.")
    else:
        print("  instrument NOT yet flowing: 0 rows carry completion_delivery. The DDL is "
              "applied but the 48h clock does NOT start until a real completion stamps it.")

    if "--apply" in sys.argv:
        try:
            doc = open(DESKTOP_FILE).read()
        except OSError as e:
            print(f"  ! could not open the Desktop file ({e})")
            return 0
        today = datetime.date.today().isoformat()
        new = re.sub(r"\|\s*\*\*PENDING\*\*\s*\|",
                     f"| **APPLIED** ({today}) |", doc, count=1)
        if new != doc:
            open(DESKTOP_FILE, "w").write(new)
            print(f"  Desktop _STATUS.md: entry 01 flipped PENDING -> APPLIED ({today}).")
        else:
            print("  Desktop _STATUS.md: already APPLIED, nothing to change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
