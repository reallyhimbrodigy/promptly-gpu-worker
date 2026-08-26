#!/usr/bin/env python3
"""read_outer_unknown_cohort.py — WHO did outer:UNKNOWN happen to, and did they
already have a real plan when it fired?

TWO QUESTIONS THE PER-JOB NUMBER CANNOT ANSWER.

  PER USER (Rule 7). 128 of 781 jobs is a JOB rate, and a user who fails five
  times and gives up is ONE LOST USER, NOT FIVE FAILURES. Per-job counting
  inflates every class by the retry multiplier — exactly what once made a
  one-user 100fps bug read as a 67% outage. The divergence ledger cannot answer
  this: its key is a job id and it carries no user. So this joins the ledger's
  job ids against video_jobs.

  DID A PLAN EXIST. `edit_recipe` is the durable plan the editorial call
  produced. If it is populated on these jobs, the pipeline HAD a real edit and
  the orchestration failed AFTER planning — the user was handed a bare
  mechanical cut while a good plan sat right there, which is a different and
  much worse defect than failing before the brain ran.

READ-ONLY. S3 ledgers + one REST read. No Modal spend, no new cells.

    python3 read_outer_unknown_cohort.py --since 2026-08-16 --until 2026-08-18
"""
import argparse
import collections
import concurrent.futures
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

ENV = os.path.expanduser("~/content-studio/.env.local")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-16")
    ap.add_argument("--until", default="2026-08-18")
    a = ap.parse_args()
    import read_divergence_rates as R

    s3 = R._client()
    keys = R._list(s3, dt.date.fromisoformat(a.since), dt.date.fromisoformat(a.until))
    print(f"  window {a.since}..{a.until}   ledgers: {len(keys)}")

    hit, all_jobs = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for k, rows in ex.map(lambda k: R._fetch(s3, k), keys):
            jid = os.path.basename(k).replace(".jsonl", "")
            all_jobs.append(jid)
            for r in rows:
                if r.get("component") != "recipe" or r.get("action") != "safe_edit_fallback":
                    continue
                why = str((r.get("original") or {}).get("reason") or "")
                if why.startswith("outer:"):
                    hit[jid] = why
    print(f"  jobs with an outer:* forced safe edit: {len(hit)} "
          f"({len(hit) / max(1, len(all_jobs)) * 100:.1f}% of jobs)")
    by_code = collections.Counter(hit.values())
    for code, n in by_code.most_common():
        print(f"      {code:24} {n}")
    if not hit:
        print("  NOTHING TO CUT — no outer:* in this window. That is a window "
              "result, not a clean bill of health.")
        return 0

    # ── the join: job -> user, and did a plan exist ─────────────────────────
    url, key = _creds()
    ids = list(hit)
    rows, CH = [], 25
    # `edit_recipe` is a large jsonb column; ask for a BOOLEAN of it rather than
    # the body. The question is "did a plan exist", not "what was it", and
    # pulling 128 full recipes is a slow query that times out before it answers.
    SEL = "id,user_id,status,created_at,edit_recipe"
    for i in range(0, len(ids), CH):
        inlist = ",".join(ids[i:i + CH])
        q = f"video_jobs?select={SEL}&id=in.({urllib.parse.quote(inlist, safe=',')})"
        try:
            rows.extend(_get(url, key, q))
        except Exception as e:
            # NAME THE FAILURE. "HTTPError" alone sent me hunting the wrong
            # cause; PostgREST puts the offending column in the response body.
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            print(f"  DB read FAILED for chunk {i // CH} "
                  f"({type(e).__name__}: {str(e)[:60]}) {body} — "
                  f"reporting the PARTIAL join, never a zero")
    found = {r["id"]: r for r in rows}
    missing = [j for j in ids if j not in found]

    # A FAILED JOIN IS NOT A FINDING. The first run of this tool joined 0 of 128
    # jobs (every chunk 400'd) and then printed "no job carried a plan: the
    # failure is BEFORE/AT planning" — a confident causal claim derived from an
    # empty result set. That is the probe-collapse class, in the very instrument
    # written to investigate a probe-collapse-shaped defect. Refuse to continue
    # instead of concluding from nothing.
    if not found:
        print(f"\n  NO EVIDENCE — joined 0 of {len(ids)} jobs. Every conclusion "
              f"below would be derived from an empty result set, so none are "
              f"printed. This says the DB read failed; it says NOTHING about "
              f"whether a plan existed or how many users were affected.")
        return 2

    users = collections.Counter()
    plan_yes = plan_no = 0
    status_ct = collections.Counter()
    for jid in ids:
        r = found.get(jid)
        if not r:
            continue
        users[r.get("user_id")] += 1
        status_ct[r.get("status")] += 1
        rec = r.get("edit_recipe")
        # SHAPE, NOT PRESENCE. `edit_recipe` is read at COMPLETION, which on a
        # rescued job is AFTER the safe edit re-ran and wrote its own recipe.
        # Testing presence returned "127 of 127 had a plan" — a false causal
        # claim; all 20 sampled carried notes == 'safe-edit fallback', the
        # literal marker build_safe_recipe emits, alongside its signature shape
        # (motion_graphics [], broll_clips [], 0-3 deterministic peak zooms).
        # A populated column here is the RESCUE's output, not evidence that an
        # editorial plan survived.
        rec = rec if isinstance(rec, dict) else {}
        is_safe = (str(rec.get("notes") or "") == "safe-edit fallback"
                   or (not rec.get("motion_graphics")
                       and not rec.get("broll_clips")
                       and not rec.get("text_overlays")))
        plan_no += 1 if is_safe else 0
        plan_yes += 0 if is_safe else 1

    print(f"\n  joined {len(found)}/{len(ids)} job(s)"
          + (f"   ({len(missing)} not in video_jobs — NOT counted as anything)"
             if missing else ""))

    print(f"\n  ── PER USER (Rule 7) ──────────────────────────────────────")
    print(f"  distinct users affected : {len(users)}")
    print(f"  jobs                    : {sum(users.values())}")
    if users:
        print(f"  retry multiplier        : "
              f"{sum(users.values()) / len(users):.1f} jobs per affected user")
        print(f"  worst offenders (jobs per user):")
        for u, n in users.most_common(6):
            print(f"      {str(u)[:8]:10} {n}")
        top = users.most_common(1)[0][1]
        print(f"  the single worst user accounts for {top}/{sum(users.values())} "
              f"({top / sum(users.values()) * 100:.0f}%) of these jobs")

    print(f"\n  ── DID A PLAN EXIST WHEN THE RESCUE FIRED ─────────────────")
    print(f"  denominator             : {len(found)} joined job(s) — every count "
          f"below is out of THIS, not out of {len(ids)}")
    print(f"  edit_recipe populated   : {plan_yes}")
    print(f"  edit_recipe empty/null  : {plan_no}")
    # THE HONEST LIMIT OF THIS COLUMN — stated here because I got it wrong in
    # BOTH directions before stating it. First pass tested PRESENCE and
    # concluded "127 of 127 had a real plan". Second pass tested SHAPE and was
    # about to conclude "no job carried a plan, so the failure is before
    # planning". Both are unsound for the same reason: `edit_recipe` is read at
    # COMPLETION, and on a rescued job the safe edit re-ran and OVERWROTE it.
    # Whatever the pre-rescue plan was, this column no longer holds it — a
    # safe-edit shape here is the rescue's own output, not evidence about what
    # came before.
    print(f"  -> UNANSWERABLE FROM THIS COLUMN. edit_recipe is post-rescue: the "
          f"safe edit overwrote whatever planning produced, so a safe-edit shape "
          f"here is the RESCUE's output and proves nothing about the failed "
          f"attempt. {plan_no}/{len(found)} carry build_safe_recipe's signature "
          f"(notes == 'safe-edit fallback', no MG/broll/overlays) — which is "
          f"what a rescued job must look like either way.")
    print(f"     WHAT WILL ANSWER IT: the rescue now ledgers exc_type + the "
          f"innermost frame (handler.py, 2026-08-19). The frame names the stage "
          f"that raised, which places the failure before or after planning "
          f"DIRECTLY. Re-run this after the next occurrence.")
    print(f"\n  terminal status of these jobs: {dict(status_ct)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
