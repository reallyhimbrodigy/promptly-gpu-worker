#!/usr/bin/env python3
"""read_divergence_rates.py — WHAT ARE WE DROPPING, ON REAL TRAFFIC, WITH A DENOMINATOR?

Every job persists its divergence ledger to s3://<bucket>/divergences/<job>.jsonl
at teardown. That is REAL TRAFFIC, already recorded — so a per-component drop
rate does not need a single new Modal cell. No spend, read-only.

WHY THIS EXISTS. `drop_ungrounded_text` became the top delivery blocker the
moment `empty_props` was fixed (props required-to-decode, 2026-08-19: 41.7% ->
0). The only measurement of it was 3 cells on ONE source, where the SAME Arabic
label failed all three times — a per-source artifact until proven otherwise. One
label on one video is not a rate.

CLEAN COHORT (Rule 5). --since/--until bound the window by the ledger object's
S3 LastModified. Default window ENDS BEFORE the harness runs of 2026-08-19, so
agent cells cannot contaminate a production rate. State the window in any number
you quote from this.

DENOMINATORS, PLAINLY LABELLED. The ledger records DIVERGENCES, not requests —
so a per-request rate is not derivable from it alone. What IS derivable, and what
this reports:

    jobs_with(action) / jobs_in_window      the honest per-job rate
    count(action) / jobs_in_window          events per job (a retry multiplier
                                            lives here — see Rule 7)

Per USER is not derivable here either: the ledger key is a job id and carries no
user. A job rate is not a user rate; do not promote one to the other.

    python3 read_divergence_rates.py --since 2026-08-16 --until 2026-08-18
    python3 read_divergence_rates.py --since 2026-08-19 --grep maxitems_violation
"""
import argparse
import collections
import concurrent.futures
import datetime as dt
import json
import os
import sys

BUCKET = os.environ.get("PROMPTLY_BUCKET", "thisismybucketagainwooo")
PREFIX = "divergences/"


def _client():
    import boto3
    return boto3.client("s3")


def _list(s3, since, until):
    out, token = [], None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": PREFIX}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents") or []:
            d = o["LastModified"].date()
            if since <= d <= until:
                out.append(o["Key"])
        if not r.get("IsTruncated"):
            return out
        token = r.get("NextContinuationToken")


def _fetch(s3, key):
    try:
        body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8", "replace")
    except Exception:
        return key, []
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return key, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-16")
    ap.add_argument("--until", default="2026-08-18",
                    help="inclusive; default ends BEFORE the 08-19 harness runs")
    ap.add_argument("--grep", default=None,
                    help="report only actions containing this substring")
    ap.add_argument("--top", type=int, default=18)
    a = ap.parse_args()
    since = dt.date.fromisoformat(a.since)
    until = dt.date.fromisoformat(a.until)

    s3 = _client()
    keys = _list(s3, since, until)
    if not keys:
        print(f"  NO LEDGERS in {since}..{until} — this is NOT a zero drop rate, "
              f"it is an empty window.")
        return 2
    print(f"  window {since}..{until}   jobs (ledger objects): {len(keys)}")

    per_action_jobs = collections.Counter()
    per_action_events = collections.Counter()
    reasons = collections.defaultdict(collections.Counter)
    n_rows = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for _key, rows in ex.map(lambda k: _fetch(s3, k), keys):
            n_rows += len(rows)
            seen = set()
            for r in rows:
                act = f"{r.get('component')}:{r.get('action')}"
                if a.grep and a.grep not in act:
                    continue
                per_action_events[act] += 1
                seen.add(act)
                rsn = str(r.get("reason") or "")[:70]
                reasons[act][rsn] += 1
            for act in seen:
                per_action_jobs[act] += 1

    print(f"  divergence rows read: {n_rows:,}\n")
    print(f"  {'component:action':46} {'jobs':>6} {'job%':>7} {'events':>7} {'ev/job':>7}")
    for act, n in per_action_events.most_common(a.top):
        j = per_action_jobs[act]
        print(f"  {act:46} {j:6} {j / len(keys) * 100:6.1f}% {n:7} "
              f"{n / len(keys):7.2f}")

    # The two this was built for, always shown even at zero — an absent line and
    # a zero line are different facts.
    print()
    for act in ("motion_graphic:drop_ungrounded_text",
                "motion_graphic:drop_empty_props",
                "recipe_transport:maxitems_violation",
                "recipe_transport:degen_retry"):
        j, n = per_action_jobs.get(act, 0), per_action_events.get(act, 0)
        # A FILTERED action is NOT a zero. --grep excludes rows before
        # counting, so without this the always-shown block reports
        # "NEVER FIRED" for actions the filter simply hid — the same
        # false-zero shape this tool exists to prevent.
        if a.grep and a.grep not in act:
            state = "NOT MEASURED (excluded by --grep)"
        else:
            state = "NEVER FIRED in this window" if not n else ""
        print(f"  {act:46} jobs={j} ({j / len(keys) * 100:.1f}%)  events={n}  {state}")
        for rsn, c in (reasons.get(act) or collections.Counter()).most_common(4):
            print(f"        {c:4}x  {rsn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
