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
        # ── 02: daily_scoreboard v2. Migration 01 created the table at JUDGE's
        # shape THAT DAY; these five landed in later JUDGE commits and were never
        # in a RUN NOW file. The cron therefore writes rows that silently lose
        # exactly the fields worth reading — outage days, the purchase funnel,
        # active Pro subs. A scoreboard that runs is not a scoreboard that
        # answers. All five verified ABSENT by probe 2026-08-12.
        ("column daily_scoreboard.active_pro_subs", "daily_scoreboard?select=active_pro_subs&limit=1"),
        ("column daily_scoreboard.outage", "daily_scoreboard?select=outage&limit=1"),
        ("column daily_scoreboard.outage_note", "daily_scoreboard?select=outage_note&limit=1"),
        ("column daily_scoreboard.sentinel", "daily_scoreboard?select=sentinel&limit=1"),
        ("column daily_scoreboard.purchase_funnel", "daily_scoreboard?select=purchase_funnel&limit=1"),
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

    # PER-ENTRY, never all-or-nothing (2026-08-12). With only entry 01 in the
    # folder, `all(res.values())` was the same thing as "01 applied". Adding 02's
    # columns made that read "01 still PENDING" while 01's four objects were
    # green — an applied migration reported as un-applied, which is the failure
    # mode this watcher exists to prevent, pointed at itself.
    entries = {
        "01": [k for k in res if not k.startswith("column daily_scoreboard.")],
        "02": [k for k in res if k.startswith("column daily_scoreboard.")],
    }
    status = {e: all(res[k] for k in keys) for e, keys in entries.items() if keys}
    n_flowing, sample = instrument_flowing(url, key)

    for e, ok in sorted(status.items()):
        missing = [k.split(".")[-1] for k in entries[e] if not res[k]]
        print(f"OWNER-SQL WATCH: entry {e} "
              + ("objects ALL PRESENT -> APPLIED." if ok
                 else f"still PENDING — missing: {', '.join(missing)}"))
    if not status.get("01"):
        return 1
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
        # Flip only the rows whose entry actually probed APPLIED. A blanket
        # first-PENDING substitution would mark 02 applied because 01 is.
        changed = []
        for _e, _ok in sorted(status.items()):
            if not _ok:
                continue
            _pat = re.compile(r"(\|\s*" + re.escape(_e) + r"\s*\|[^\n]*?\|\s*)\*\*PENDING\*\*(\s*\|)")
            doc2 = _pat.sub(rf"\g<1>**APPLIED** ({today})\g<2>", doc, count=1)
            if doc2 != doc:
                doc = doc2
                changed.append(_e)
        if changed:
            open(DESKTOP_FILE, "w").write(doc)
            print(f"  Desktop _STATUS.md: entr{'y' if len(changed)==1 else 'ies'} "
                  f"{', '.join(changed)} flipped PENDING -> APPLIED ({today}).")
        else:
            print("  Desktop _STATUS.md: nothing to flip (already APPLIED, or still pending).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
