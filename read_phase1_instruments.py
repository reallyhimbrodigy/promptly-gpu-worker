#!/usr/bin/env python3
"""COMMITTED READER for the Phase 1 / delivery instruments `[Rule 2]`.

The built-not-wired sweep flagged three events as WRITTEN, NEVER READ:
`design_system_built`, `caption_modes_applied`, `burst_double_hold`. All three
are mine, all three were read ad-hoc from a shell, and the finding was fair —
**an instrument with no committed reader is one context-loss away from being
noise.** This is that reader.

It reports rates against a stated DENOMINATOR and refuses to report one below a
floor, because a small-sample zero is the class this project keeps paying for.

    python3 read_phase1_instruments.py            # last 24h
    python3 read_phase1_instruments.py 72         # last N hours
"""
import json
import os
import sys
import urllib.request
from collections import Counter

MIN_N = 30          # below this, report the count and REFUSE the rate


def _sb(path, params):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not url or not key:
        print("  SUPABASE_URL / SUPABASE_SERVICE_KEY not set — cannot read.")
        print("  This is a FAILED READ, not a zero.")
        sys.exit(2)
    q = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{url}/rest/v1/{path}?{q}",
                                 headers={"apikey": key,
                                          "Authorization": f"Bearer {key}",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _rate(label, num, den, unit="%"):
    if den < MIN_N:
        print(f"    {label:34} {num}/{den} — NO RATE (n<{MIN_N}; a small-sample "
              f"rate is not a result)")
        return
    print(f"    {label:34} {num}/{den} = {100.0 * num / den:.1f}{unit}")


def main(argv):
    hours = int(argv[1]) if len(argv) > 1 else 24
    since = f"now()-interval'{hours} hours'"
    # PostgREST cannot take now()-interval in a filter, so compute it here.
    import datetime as dt
    since_iso = (dt.datetime.utcnow() - dt.timedelta(hours=hours)).isoformat() + "Z"

    print(f"\nPHASE 1 INSTRUMENTS — last {hours}h (since {since_iso})")
    print("=" * 72)

    jobs = _sb("video_jobs", {"select": "id,status,created_at",
                              "status": "eq.completed",
                              "created_at": f"gte.{since_iso}",
                              "limit": "5000"})
    den = len(jobs)
    print(f"\n  DENOMINATOR: {den} completed jobs\n")

    ev = _sb("analytics_events", {"select": "event,props,created_at",
                                  "created_at": f"gte.{since_iso}",
                                  "event": "in.(design_system_built,"
                                           "caption_modes_applied,burst_double_hold,"
                                           "post_upload_watchdog_fired,worker_envelope_write)",
                                  "limit": "20000"})
    by = Counter(e["event"] for e in ev)

    print("  DESIGN SYSTEM [§3.1 Phase 1.1]")
    ds = [e for e in ev if e["event"] == "design_system_built"]
    ds_ok = sum(1 for e in ds if (e.get("props") or {}).get("ok"))
    _rate("attach rate (built / completed)", len(ds), den)
    _rate("build succeeded", ds_ok, len(ds))
    accents = Counter((e.get("props") or {}).get("accent") for e in ds if (e.get("props") or {}).get("accent"))
    print(f"    distinct accents extracted:        {len(accents)} "
          f"{'— a constant here would mean the palette is NOT per-video' if len(accents) <= 1 and len(ds) > 3 else ''}")

    print("\n  CAPTION MODES [§3.1 Phase 1.2]")
    cm = [e for e in ev if e["event"] == "caption_modes_applied"]
    _rate("applied (jobs / completed)", len(cm), den)
    pages = sum((e.get("props") or {}).get("pages") or 0 for e in cm)
    emph = sum((e.get("props") or {}).get("pages_with_emphasis") or 0 for e in cm)
    hero = sum((e.get("props") or {}).get("hero_number_pages") or 0 for e in cm)
    kw = sum((e.get("props") or {}).get("keyword_accent_pages") or 0 for e in cm)
    _rate("pages carrying emphasis", emph, pages)
    print(f"    hero-number pages:                 {hero}")
    print(f"    keyword-accent pages:              {kw}")
    if emph and hero == 0:
        print("    !! zero hero numbers across every emphasised page — REF-2's mode "
              "is not reaching production")

    print("\n  BURST DOUBLE-HOLD [Law 1]")
    dh = [e for e in ev if e["event"] == "burst_double_hold"]
    if not dh:
        print(f"    no burst renders in the window (n=0). Not a zero — burst fires "
              f"only above the output floor.")
    else:
        blocked = sorted((e.get("props") or {}).get("blocked_s") or 0 for e in dh)
        rep = [(e.get("props") or {}).get("burst_reported_render_s") for e in dh]
        rep = [r for r in rep if r]
        p50 = blocked[len(blocked) // 2]
        print(f"    n={len(dh)}  blocked p50={p50:.0f}s  max={blocked[-1]:.0f}s")
        if rep:
            print(f"    burst-REPORTED render p50={sorted(rep)[len(rep)//2]:.0f}s")
            print(f"    -> the gap is dispatch+queue+cold start, billed at 48 cores "
                  f"and invisible in stage_timings")
        print(f"    orchestrator idle core-s (sum):    "
              f"{sum((e.get('props') or {}).get('orchestrator_idle_core_s') or 0 for e in dh):.0f}")

    print("\n  WATCHDOG [Law 2]")
    wd = [e for e in ev if e["event"] == "post_upload_watchdog_fired"]
    print(f"    fired: {len(wd)}")
    if wd:
        # LOWER only. The upper is a BOUND and summing it counts savings that
        # would not have occurred — ~4x overstatement at 60 jobs/day.
        low = sum((e.get("props") or {}).get("recovered_lower") or 0 for e in wd)
        print(f"    recovered core-seconds (LOWER, the summable one): {low:.0f}")
        print(f"    recovered_upper is a BOUND and is deliberately NOT summed here")

    print("\n  ENVELOPE WRITE [Law 2]")
    we = [e for e in ev if e["event"] == "worker_envelope_write"]
    acc = sum(1 for e in we if (e.get("props") or {}).get("accepted"))
    rai = sum(1 for e in we if (e.get("props") or {}).get("raised"))
    pg = sum(1 for e in we if (e.get("props") or {}).get("pgrst204"))
    print(f"    n={len(we)}  accepted={acc}  raised={rai}  pgrst204={pg}")
    if len(we) < 100:
        print(f"    (bar is n>=100 before this answers overwrite-vs-never-arrived)")
    slow = [(e.get("props") or {}).get("db_write_ms") for e in we]
    slow = sorted(x for x in slow if isinstance(x, (int, float)))
    if slow:
        print(f"    db_write_ms p50={slow[len(slow)//2]:.0f} max={slow[-1]:.0f}")
    print(f"\n  events seen: {dict(by)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
