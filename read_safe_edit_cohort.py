#!/usr/bin/env python3
"""read_safe_edit_cohort.py — WHY did the safe edit fire, and to HOW MANY USERS?

THE QUESTION THIS ANSWERS, and why it is first: 46.7% of recent completed jobs
shipped a deterministic safe edit. ONE CAUSE OR MANY decides everything after
it — a single dominant cause is a fix, a long tail is an architecture problem.

TWO SOURCES, JOINED, because neither alone can answer it:
  video_jobs        has user_id (the ledger does not) and the recipe shape
  divergence ledger has the REASON (`recipe:safe_edit_fallback` ->
                    original.reason), which the DB row does not carry

PER USER, NOT PER JOB (Rule 7). A user who fails five times and gives up is ONE
LOST USER, NOT FIVE FAILURES. Per-job counting inflates every class by the retry
multiplier. Both numbers are printed; the USER count leads.

FAILED LOOKUPS ARE NOT ZEROS. A job whose ledger is missing is counted as
`reason: <no ledger>` and reported separately — never folded into a named cause,
and never silently dropped from the denominator.

    python3 read_safe_edit_cohort.py --limit 400
"""
import argparse
import collections
import concurrent.futures
import json
import os
import sys
import urllib.request


def _q(url, key, path, t=180):
    r = urllib.request.Request(f"{url}/rest/v1/{path}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


def _is_safe(rec):
    """The safe edit's own signature. `edit_recipe` has TWO shapes in this
    column — a {plan,route,reason} wrapper for routed jobs and a FLAT plan
    otherwise — and reading the wrong one returns a confident false zero (it
    did, on the first pass of this investigation). Unwrap, then test."""
    if isinstance(rec, str):
        try:
            rec = json.loads(rec)
        except Exception:
            return None, None
    if not isinstance(rec, dict):
        return None, None
    route = None
    if isinstance(rec.get("plan"), dict):
        route, rec = rec.get("route"), rec["plan"]
    return (str(rec.get("notes") or "") == "safe-edit fallback"), route


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400)
    a = ap.parse_args()
    import read_outer_unknown_cohort as C
    import read_divergence_rates as R
    url, key = C._creds()

    rows = _q(url, key,
              "video_jobs?select=id,user_id,created_at,edit_recipe,status"
              f"&status=eq.completed&edit_recipe=not.is.null"
              f"&order=created_at.desc&limit={a.limit}")
    safe = {}
    routes = collections.Counter()
    for r in rows:
        is_safe, route = _is_safe(r.get("edit_recipe"))
        if is_safe is None:
            continue
        routes[route or ("SAFE" if is_safe else "flat-editorial")] += 1
        if is_safe:
            safe[r["id"]] = r.get("user_id")
    if not rows:
        print("  NO ROWS — empty window, NOT a zero rate.")
        return 2
    print(f"  scanned {len(rows)} completed recipes "
          f"({rows[-1].get('created_at','?')[:16]} -> {rows[0].get('created_at','?')[:16]})")
    print(f"  safe edits: {len(safe)} ({len(safe)/len(rows)*100:.1f}% of completions)")

    # ── the reason, from each job's own ledger ──────────────────────────────
    s3 = R._client()
    def fetch(jid):
        try:
            _k, rws = R._fetch(s3, f"divergences/{jid}.jsonl")
        except Exception:
            return jid, None
        for w in rws:
            if w.get("component") == "recipe" and w.get("action") == "safe_edit_fallback":
                return jid, str((w.get("original") or {}).get("reason") or "unnamed")
        return jid, None

    by_reason_jobs = collections.Counter()
    by_reason_users = collections.defaultdict(set)
    per_user = collections.Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for jid, why in ex.map(fetch, list(safe)):
            why = why or "<no ledger — NOT a cause>"
            by_reason_jobs[why] += 1
            by_reason_users[why].add(safe.get(jid))
            per_user[safe.get(jid)] += 1

    print(f"\n  ── BY REASON ─────────────────────────────────────────")
    print(f"  {'reason':34} {'jobs':>6} {'users':>7} {'j/user':>7}")
    for why, n in by_reason_jobs.most_common():
        u = len(by_reason_users[why])
        print(f"  {why[:34]:34} {n:6} {u:7} {n/max(1,u):7.1f}")

    print(f"\n  ── PER USER (Rule 7) ─────────────────────────────────")
    print(f"  distinct users receiving a safe edit : {len(per_user)}")
    print(f"  jobs                                 : {sum(per_user.values())}")
    if per_user:
        print(f"  retry multiplier                     : "
              f"{sum(per_user.values())/len(per_user):.1f} jobs/user")
        top = per_user.most_common(5)
        print(f"  heaviest users (jobs): "
              f"{', '.join(f'{str(u)[:8]}={n}' for u, n in top)}")
        worst = top[0][1]
        print(f"  worst single user accounts for {worst}/{sum(per_user.values())} "
              f"({worst/sum(per_user.values())*100:.0f}%)")
    named = sum(n for w, n in by_reason_jobs.items() if not w.startswith("<no ledger"))
    print(f"\n  ONE CAUSE OR MANY: {len(by_reason_jobs)} distinct reason(s); "
          f"{named}/{len(safe)} jobs have a named cause.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
