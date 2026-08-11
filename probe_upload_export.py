#!/usr/bin/env python3
"""Is PROMPTLY_HLS_COPY actually LIVE? Measure upload_export by deploy cohort.

WHY THIS EXISTS. The live secret reads PROMPTLY_HLS_COPY=1 [MEASURED 2026-08-11
via secret_flags_readback], but LANE4_FLIP_HLS_COPY.md filed it as "currently
off" and asked for a flip. Both cannot be true of the same moment, and a secret
value is not the question anyway: memory snapshots freeze os.environ at DEPLOY
time, so "the secret says 1" and "the running code sees 1" are different claims
(built != committed != deployed != working).

Only traffic settles it. `_hls_copy_enabled()` replaces a 4-rendition libx264
re-encode of the finished MP4 with a single-rendition `-c copy` segmentation, so
its whole signature is stage_timings.upload_export collapsing. The filed
pre-flip baseline is p50 4.4s / p90 10.4s (n=289, Aug 9-11, outage traffic);
post-flip should be ~1-2s.

COHORTS are cut at deploy boundaries read from `modal app history`, because a
flip can only take effect at a redeploy — a window straddling one is a
contaminated window, which is this codebase's most expensive recurring
measurement bug. Every cohort prints its own n; a cohort with n < 5 is reported
as too small to read rather than silently averaged into a confident number.

Read-only. No Modal spend.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

ENV_FILE = "/Users/zaclibman/content-studio/.env.local"

# Deploy boundaries (UTC) from `modal app history promptly-gpu-worker`.
# v521 was the last deploy before today's run of five.
COHORTS = [
    ("Aug 9-10 (pre-v522, live image = v521 from Aug 4)", "2026-08-09T00:00:00Z", "2026-08-11T18:01:00Z"),
    ("v522 18:01Z -> v523 18:29Z",                        "2026-08-11T18:01:00Z", "2026-08-11T18:29:00Z"),
    ("v523 18:29Z -> v526 19:32Z",                        "2026-08-11T18:29:00Z", "2026-08-11T19:32:00Z"),
    ("v526 19:32Z -> now (CURRENT IMAGE)",                "2026-08-11T19:32:00Z", "2099-01-01T00:00:00Z"),
]


def _creds():
    with open(ENV_FILE) as fh:
        env = {}
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env["SUPABASE_URL"].rstrip("/"), (
        env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _get(url, key, query):
    req = urllib.request.Request(
        f"{url}/rest/v1/video_jobs?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(round((len(s) - 1) * p)))]


def main():
    url, key = _creds()
    rows = _get(url, key,
                "select=id,created_at,updated_at,result,user_id&status=eq.completed"
                "&created_at=gte.2026-08-09T00:00:00Z&order=created_at.asc&limit=2000")
    print(f"pulled {len(rows)} completed jobs since 2026-08-09\n")

    def parse(ts):
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)

    for label, lo, hi in COHORTS:
        lo_d, hi_d = parse(lo), parse(hi)
        ue, routes, users = [], {}, set()
        for r in rows:
            t = parse(r["created_at"])
            if not (lo_d <= t < hi_d):
                continue
            res = r.get("result") or {}
            if not isinstance(res, dict):
                continue
            users.add(r.get("user_id"))
            routes[res.get("route") or "?"] = routes.get(res.get("route") or "?", 0) + 1
            st = res.get("stage_timings") or {}
            v = st.get("upload_export") if isinstance(st, dict) else None
            if isinstance(v, (int, float)):
                ue.append(float(v))

        n_jobs = sum(routes.values())
        if not ue:
            print(f"{label}\n  n={n_jobs} jobs / {len(users)} users — NO upload_export timings. "
                  f"Cannot read this cohort.\n  routes: {routes}\n")
            continue
        note = "  ⚠️  n<5 — too small to read as a rate" if len(ue) < 5 else ""
        print(f"{label}\n  n={len(ue)} timed / {n_jobs} jobs / {len(users)} users{note}\n"
              f"  upload_export  p50 {pct(ue, .5):.2f}s  p90 {pct(ue, .9):.2f}s  "
              f"max {max(ue):.2f}s  mean {sum(ue)/len(ue):.2f}s\n  routes: {routes}\n")

    print("READ: p50 collapsing toward ~1s ⇒ -c copy is LIVE. p50 near the filed "
          "4.4s baseline ⇒ the 4-rendition re-encode is still running.")


if __name__ == "__main__":
    sys.exit(main())
