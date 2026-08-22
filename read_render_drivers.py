#!/usr/bin/env python3
"""read_render_drivers.py — WHAT ACTUALLY DRIVES RENDER TIME.

THE MODEL THIS REPLACES. On n=19 I fitted `wall ~= 85s + 1.9 x source_seconds`
and reported it. At n=70 the correlation between source length and render time
is r=0.163 — the duration term was a small-sample artifact. Render p50 is
roughly FLAT across source buckets (95s at <20s, 233s at 20-40s, 216s at 40-80s,
211s at >80s) while the RATIO runs inverse, so short sources look worst: 24% of
editorial renders take >=10x their source, topping out at 30.5x.

So duration does not drive the render. This tests the hypothesis the duration
model vacated: COMPONENT COUNT.

LEDGER SHAPE, which is why the first read reported '?' on every job:
    component_ledger = {kind: {requested, dropped_by_us, survived_derived,
                               drop_reasons}}
`requested` is nested PER KIND. The first reader did cl.get('requested') and
summed its .values() — but there is no top-level 'requested' key, so every job
silently scored 0 and the hypothesis could not be tested at all. Same
wrong-shape class as edit_plan-vs-edit_recipe and result['timeline'].

SURVIVED, NOT REQUESTED, is the render-cost variable: a component the ladder
dropped never reached Remotion, so it cost nothing to draw. Both are reported —
if requested correlates and survived does not, the cost is in the PLANNING, not
the drawing, and that is a different fix.

    python3 read_render_drivers.py
"""
import json
import math
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

SINCE = "2026-08-21T18:47:00Z"


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


def _ledger(cl):
    """Sum a component_ledger. Returns (requested, survived, per_kind_survived)."""
    req = surv = 0
    per = {}
    if not isinstance(cl, dict):
        return 0, 0, per
    for kind, d in cl.items():
        if not isinstance(d, dict):
            continue
        r = d.get("requested")
        s = d.get("survived_derived")
        if isinstance(r, int):
            req += r
        if isinstance(s, int):
            surv += s
            per[kind] = s
    return req, surv, per


def _r(pts):
    n = len(pts)
    if n < 3:
        return float("nan")
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = math.sqrt(sum((p[0] - mx) ** 2 for p in pts)
                    * sum((p[1] - my) ** 2 for p in pts))
    return num / den if den else float("nan")


def main():
    url, key = _creds()
    rows = _q(url, key,
              "video_jobs?select=id,stage_timings,result&status=eq.completed"
              f"&created_at=gte.{urllib.parse.quote(SINCE)}&limit=300")
    data = []
    no_ledger = 0
    for row in rows:
        res = _j(row.get("result")) or {}
        s = _j(row.get("stage_timings")) or _j(res.get("stage_timings")) or {}
        if not any(k in s for k in ("gemini_call", "edit_plan")):
            continue
        if res.get("route") in ("hype", "moodreel"):
            continue
        rn, src = s.get("render"), s.get("source_duration_s")
        if not isinstance(rn, (int, float)) or not rn:
            continue
        cl = res.get("component_ledger")
        if not cl:
            no_ledger += 1
            continue
        req, surv, per = _ledger(cl)
        data.append({"id": str(row["id"])[:8], "render": float(rn),
                     "src": float(src or 0), "req": req, "surv": surv, "per": per})

    print(f"  editorial renders with a ledger: {len(data)}   "
          f"without (excluded): {no_ledger}")
    if len(data) < 5:
        print("  TOO FEW to test anything. Not a null result — an unmeasured one.")
        return 2

    print(f"\n  {'variable':<28}{'r vs render':>13}{'n':>6}")
    for lbl, f in (("source_duration_s", lambda d: d["src"]),
                   ("components REQUESTED", lambda d: d["req"]),
                   ("components SURVIVED", lambda d: d["surv"])):
        pts = [(f(d), d["render"]) for d in data if f(d) or f(d) == 0]
        print(f"  {lbl:<28}{_r(pts):>13.3f}{len(pts):>6}")

    # per-kind: which component actually costs render seconds?
    kinds = sorted({k for d in data for k in d["per"]})
    print(f"\n  {'per-kind survived':<28}{'r vs render':>13}{'p50 count':>11}"
          f"{'max':>6}")
    for k in kinds:
        pts = [(d["per"].get(k, 0), d["render"]) for d in data]
        vals = [p[0] for p in pts]
        print(f"  {k:<28}{_r(pts):>13.3f}{st.median(vals):>11.1f}"
              f"{max(vals):>6}")

    # the tail, described by components rather than by duration
    data.sort(key=lambda d: -d["render"])
    print(f"\n  SLOWEST RENDERS — is the tail component-heavy?")
    print(f"  {'job':<10}{'render':>9}{'src':>8}{'req':>6}{'surv':>6}  per-kind")
    for d in data[:8]:
        per = {k: v for k, v in d["per"].items() if v}
        print(f"  {d['id']:<10}{d['render']:>9.1f}{d['src']:>8.1f}"
              f"{d['req']:>6}{d['surv']:>6}  {per}")
    lo = sorted(data, key=lambda d: d["render"])[:8]
    print(f"\n  FASTEST RENDERS")
    for d in lo:
        per = {k: v for k, v in d["per"].items() if v}
        print(f"  {d['id']:<10}{d['render']:>9.1f}{d['src']:>8.1f}"
              f"{d['req']:>6}{d['surv']:>6}  {per}")

    top = data[:max(3, len(data) // 4)]
    bot = sorted(data, key=lambda d: d["render"])[:max(3, len(data) // 4)]
    print(f"\n  slowest quartile: p50 survived={st.median([d['surv'] for d in top]):.1f}"
          f"  p50 src={st.median([d['src'] for d in top]):.1f}s")
    print(f"  fastest quartile: p50 survived={st.median([d['surv'] for d in bot]):.1f}"
          f"  p50 src={st.median([d['src'] for d in bot]):.1f}s")
    print("\n  READ: if survived-count separates the quartiles and source does not,"
          "\n  the render is priced by COMPONENTS and the fix is component-side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
