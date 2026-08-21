#!/usr/bin/env python3
"""read_postflip_cohort.py — THE PRE-REGISTERED READ ON THE EDITORIAL FLIP.

PROMPTLY_EDITORIAL_LIVE went to "1" at v563 (2026-08-21 18:47Z). For the first
time this campaign, live traffic reaches the editorial model.

PRE-REGISTERED, so the answer cannot be chosen after seeing the data:
    completion rate · p50 wall · $/job

REVERT TRIGGERS (owner, locked BEFORE the flip):
    any UNKNOWN error class
    >10% per-user failure at n>=20 users
    p95 wall > 300s
    $/job > $0.25
~220s p50 is EXPECTED and is NOT a revert.

CLEAN COHORT (Rule 5): only jobs created AFTER the deploy. A window straddling
the flip mixes two products and can prove anything.

PER USER, NOT PER JOB (Rule 7): the trigger is per-user; both are reported.

COST IS COMPUTED, NOT GUESSED, from MODAL_COST_RECONCILIATION.md's owner-supplied
rates and the cpu=/memory= literals in modal_app.py. Two containers bill per job
whenever the render runs on the burst:
    run_pipeline_bg  cpu=16 / 12GiB   for the WHOLE wall (it idle-holds)
    render_burst     cpu=32 / 64GiB   for the render stage only
That overlap is exactly what L1/L2 propose to reclaim, so it is printed split.

WHAT THIS CANNOT SEE, stated rather than implied: non-job idle/prewarm (the
~$87/day term). This is JOB COMPUTE. `./cost_weekly.sh` is the billed truth.

    python3 read_postflip_cohort.py --since 2026-08-21T18:47:00Z
"""
import argparse
import collections
import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

FLIP_UTC = "2026-08-21T18:47:00Z"
CORE_S = 0.0000131      # $/core-second   (owner-supplied)
GIB_S = 0.00000222      # $/GiB-second    (Modal list)
ORCH = 16 * CORE_S + 12 * GIB_S     # run_pipeline_bg, held for the whole wall
BURST = 32 * CORE_S + 64 * GIB_S    # render_burst, render stage only


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


def _j(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return v if isinstance(v, dict) else None


def _classify(row):
    """Which brain produced this job? Read the ARTIFACT, not the flag."""
    res = _j(row.get("result")) or {}
    stg = _j(row.get("stage_timings")) or _j(res.get("stage_timings")) or {}
    if res.get("route") in ("hype", "moodreel"):
        return str(res["route"])
    # The editorial brain leaves fingerprints no other path writes.
    if any(k in stg for k in ("gemini_call", "edit_plan", "degen_retries")):
        rec = _j(row.get("edit_recipe")) or _j(res.get("edit_recipe")) or {}
        note = str(rec.get("notes") or "")
        return "safe-edit" if "safe-edit" in note else "EDITORIAL"
    if "plan" in stg:
        return "lean/plan"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=FLIP_UTC)
    ap.add_argument("--target", type=int, default=50)
    a = ap.parse_args()
    url, key = _creds()
    rows = _q(url, key,
              "video_jobs?select=id,user_id,status,created_at,started_at,completed_at,"
              "error_message,stage_timings,result,edit_recipe"
              f"&created_at=gte.{urllib.parse.quote(a.since)}"
              "&order=created_at.asc&limit=400")
    n = len(rows)
    print(f"  ── POST-FLIP COHORT · created >= {a.since} ──")
    if n == 0:
        print("  NO JOBS. An EMPTY WINDOW is a failed read, not a clean bill of health.")
        return 2
    print(f"  jobs: {n}/{a.target} toward the pre-registered read"
          + ("" if n >= a.target else "   ** UNDER-POWERED — provisional **"))

    by_status = collections.Counter(str(r.get("status")) for r in rows)
    done = [r for r in rows if str(r.get("status")) == "completed"]
    failed = [r for r in rows if str(r.get("status")) == "failed"]
    inflight = [r for r in rows if str(r.get("status")) in ("processing", "queued", "pending")]
    users = {r.get("user_id") for r in rows if r.get("user_id")}
    fail_users = {r.get("user_id") for r in failed if r.get("user_id")}
    print(f"  status: {dict(by_status)}")

    settled = len(done) + len(failed)
    print(f"\n  COMPLETION RATE : {len(done)}/{settled} settled = "
          f"{(len(done)/settled*100 if settled else 0):.1f}%"
          f"   ({len(inflight)} still in flight, excluded — they are not failures)")
    print(f"  users           : {len(users)}   with >=1 failure: {len(fail_users)}")
    per_user = (len(fail_users) / len(users) * 100) if users else 0.0
    print(f"  PER-USER FAILURE: {per_user:.1f}%"
          + ("   (trigger >10% at n>=20 users)" if len(users) >= 20
             else f"   (n={len(users)} users < 20 — TRIGGER NOT ARMED)"))

    # ── wall, per route (Rule: never blend routes) ──────────────────────────
    walls, per_route = [], collections.defaultdict(list)
    costs, cost_split = [], []
    for r in done:
        res = _j(r.get("result")) or {}
        stg = _j(r.get("stage_timings")) or _j(res.get("stage_timings")) or {}
        tot = stg.get("total")
        rend = stg.get("render")
        route = _classify(r)
        if isinstance(tot, (int, float)) and tot > 0:
            walls.append(float(tot))
            per_route[route].append(float(tot))
            c_o = float(tot) * ORCH
            c_b = (float(rend) * BURST) if isinstance(rend, (int, float)) else 0.0
            costs.append(c_o + c_b)
            cost_split.append((route, c_o, c_b))

    p50 = p95 = None
    if walls:
        w = sorted(walls)
        p50 = st.median(w)
        p95 = w[min(len(w) - 1, int(len(w) * 0.95))]
        print(f"\n  p50 WALL        : {p50:.1f}s   (expected ~220s — NOT a revert)")
        print(f"  p95 WALL        : {p95:.1f}s   (trigger >300s)     n={len(w)}")
        print("  by route:")
        for rt, v in sorted(per_route.items(), key=lambda kv: -len(kv[1])):
            print(f"      {rt:12} n={len(v):3}  p50={st.median(v):7.1f}s  "
                  f"max={max(v):7.1f}s")
    else:
        print("\n  WALL: no stage_timings.total on any completed job — UNMEASURED, not 0s")

    if costs:
        cm = st.median(sorted(costs))
        o_med = st.median([c[1] for c in cost_split])
        b_med = st.median([c[2] for c in cost_split])
        print(f"\n  $/JOB (compute) : ${cm:.4f}   (trigger >$0.25; cost law $0.10)")
        print(f"      orchestrator cpu=16/12GiB over the whole wall : ${o_med:.4f}")
        print(f"      render_burst cpu=32/64GiB over render only    : ${b_med:.4f}")
        print(f"      ^ both bill CONCURRENTLY during the render — that overlap is "
              f"the L1/L2 target")
        by_rt = collections.defaultdict(list)
        for rt, co, cb in cost_split:
            by_rt[rt].append(co + cb)
        for rt, v in sorted(by_rt.items(), key=lambda kv: -len(kv[1])):
            print(f"      {rt:12} n={len(v):3}  $/job median ${st.median(v):.4f}")
        print("      NOTE: JOB COMPUTE only. Non-job idle/prewarm is not visible "
              "here; ./cost_weekly.sh is the billed truth.")
    else:
        print("\n  $/JOB: UNCOMPUTABLE — no timings to price")

    # ── error classes ───────────────────────────────────────────────────────
    codes = collections.Counter()
    for r in failed:
        msg = str(r.get("error_message") or "").strip()
        codes[(msg.split(":")[0][:48] or "empty") if msg else "NO_MESSAGE"] += 1
    unknown = sum(v for k, v in codes.items()
                  if "UNKNOWN" in k.upper() or k == "NO_MESSAGE")
    print(f"\n  failure classes : {dict(codes) or 'none'}")
    print(f"  UNKNOWN class   : {unknown}   (trigger: ANY)")

    routes = collections.Counter(_classify(r) for r in done)
    print(f"\n  ROUTE MIX       : {dict(routes) or 'none'}")
    print(f"  ^ EDITORIAL>0 proves the flip reached real jobs; all safe-edit means "
          f"it did not.")

    trips = []
    if unknown:
        trips.append(f"UNKNOWN x{unknown}")
    if len(users) >= 20 and per_user > 10:
        trips.append(f"per-user failure {per_user:.0f}% > 10%")
    if p95 and p95 > 300:
        trips.append(f"p95 {p95:.0f}s > 300s")
    if costs and st.median(sorted(costs)) > 0.25:
        trips.append(f"$/job ${st.median(sorted(costs)):.3f} > $0.25")
    print(f"\n  REVERT TRIGGERS : {trips or 'NONE TRIPPED'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
