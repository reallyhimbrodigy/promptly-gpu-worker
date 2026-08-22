#!/usr/bin/env python3
"""read_ledger_coverage.py — DID THE LEDGER FIX ACTUALLY EXECUTE?

v565 (c890235) moved _component_ledger_reset() out of _asr_diag_set — a setter
that ran repeatedly per job and erased the ledger. Before the fix, 22 of 70
editorial jobs shipped uninstrumented, and they were the SLOW ones (p50 render
247.7s vs 153.7s), holding the entire p95 tail.

THE PRE-REGISTERED PROOF, so it cannot be chosen after the fact:
  * coverage goes to 100% of editorial jobs, AND
  * the slow jobs in particular are covered — the old failure was BIASED, so
    "95% covered" while the 5% missing are still the slowest is NOT a fix, it
    is the same bug with a better headline.

Both halves are printed. A coverage number without the slow-job cut is the
kind of green that hid this for a day.

    python3 read_ledger_coverage.py
"""
import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

import promptly_read as P

V565_UTC = "2026-08-22T19:30:00Z"


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _q(url, key, path, t=120):
    r = urllib.request.Request(f"{url}/rest/v1/{path}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


def _cut(rows, label):
    ed = []
    for row in rows:
        if P.route(row) != "EDITORIAL":
            continue
        st_ = P.stage_timings(row)
        rn = st_.get("render")
        if not isinstance(rn, (int, float)) or not rn:
            continue
        ed.append((str(row["id"])[:8], float(rn),
                   P.component_ledger(row) is not P.MISSING))
    if not ed:
        print(f"\n  {label}: NO editorial renders yet — an EMPTY window, "
              f"not a passing one.")
        return None
    have = [e for e in ed if e[2]]
    miss = [e for e in ed if not e[2]]
    print(f"\n  {label}")
    print(f"    coverage: {len(have)}/{len(ed)} = {len(have)/len(ed)*100:.0f}%")
    if have:
        print(f"    covered   p50 render {st.median([e[1] for e in have]):7.1f}s "
              f"max {max(e[1] for e in have):7.1f}s")
    if miss:
        print(f"    UNCOVERED p50 render {st.median([e[1] for e in miss]):7.1f}s "
              f"max {max(e[1] for e in miss):7.1f}s   {[e[0] for e in miss][:6]}")
        if have and st.median([e[1] for e in miss]) > st.median([e[1] for e in have]):
            print(f"    ** STILL BIASED: the uncovered jobs are SLOWER than the "
                  f"covered ones. **")
    else:
        print(f"    uncovered: none")
    return len(have), len(ed)


def main():
    url, key = _creds()
    rows = _q(url, key,
              "video_jobs?select=id,created_at,stage_timings,result&status=eq.completed"
              "&created_at=gte." + urllib.parse.quote("2026-08-20T00:00:00Z")
              + "&order=created_at.asc&limit=400")
    before = [r for r in rows if str(r["created_at"]) < V565_UTC]
    after = [r for r in rows if str(r["created_at"]) >= V565_UTC]
    print(f"  ── COMPONENT LEDGER COVERAGE · v565 @ {V565_UTC} ──")
    _cut(before, f"BEFORE the fix (< {V565_UTC})")
    res = _cut(after, f"AFTER the fix  (>= {V565_UTC})")
    if res and res[0] == res[1]:
        print(f"\n  FIX CONFIRMED ON REAL TRAFFIC: {res[0]}/{res[1]} editorial "
              f"renders instrumented, 0 uncovered.")
    elif res:
        print(f"\n  NOT CONFIRMED: {res[1]-res[0]} of {res[1]} still uncovered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
