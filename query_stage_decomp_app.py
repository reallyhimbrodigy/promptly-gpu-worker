"""edit_plan DECOMPOSITION — where do the ~130 unnamed seconds go? (Zac 2026-08-02)

gemini_call is 60.4s (TTFB 45.9 + generation 14.5). edit_plan is 189s. Mining my
own 48 PLAN_ONLY runs accounted for only 72.7s, and that mining has two defects
that make it the WRONG source:
  1. CONTAMINATED — that run fired 48 concurrent jobs and drew 26 Vertex 429s,
     giving 1.40 post-cuts calls/job. That retry rate is MY load, not production.
  2. INCOMPLETE — several stages do not log an "in Xs" line at all, so they are
     invisible to log mining regardless.

handler already persists `result.stage_timings` per job. That is the real
decomposition, on real traffic, and nobody has read it. CPU-only DB read, ~$0.01.

Cut BY ROUTE (Rule 5): a caption-less route skips planning entirely and would
drag every median toward zero.
"""
import os
from collections import defaultdict

import modal

app = modal.App("query-stage-decomp")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=SECRETS, timeout=900)
def query(hours: int = 48) -> dict:
    from datetime import datetime, timedelta, timezone
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY"))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    per_stage = defaultdict(list)
    per_route = defaultdict(int)
    n = 0
    for off in range(0, 20000, 1000):
        try:
            r = (sb.table("video_jobs").select("result,status,created_at")
                 .gte("created_at", since).range(off, off + 999).execute())
        except Exception as e:  # noqa: BLE001
            print(f"[query] page {off}: {e}", flush=True)
            break
        rows = r.data or []
        if not rows:
            break
        for row in rows:
            res = row.get("result")
            if not isinstance(res, dict):
                continue
            st_ = res.get("stage_timings")
            if not isinstance(st_, dict):
                continue
            route = res.get("route") or "standard"
            per_route[route] += 1
            if route != "standard":
                continue          # planning stages only exist on the standard route
            n += 1
            for k, v in st_.items():
                if isinstance(v, (int, float)) and v >= 0:
                    per_stage[k].append(float(v))
    return {"n_standard": n, "per_route": dict(per_route),
            "stages": {k: v for k, v in per_stage.items()}}


@app.local_entrypoint()
def main(hours: int = 48):
    import statistics as st
    d = query.remote(hours)
    print(f"\nedit_plan DECOMPOSITION — {d['n_standard']:,} standard-route jobs, last {hours}h")
    print(f"route mix: {d['per_route']}\n")
    rows = []
    for k, v in d["stages"].items():
        if not v:
            continue
        v = sorted(v)
        rows.append((st.median(v), k, len(v), v[int(0.9 * len(v)) - 1] if len(v) > 1 else v[0], v[-1]))
    rows.sort(reverse=True)
    print(f"  {'stage':<30} {'n':>5} {'median':>9} {'p90':>9} {'max':>9}")
    print("  " + "-" * 66)
    for med, k, cnt, p90, mx in rows:
        print(f"  {k:<30} {cnt:>5} {med:>9.1f} {p90:>9.1f} {mx:>9.1f}")
    # NOT every key in stage_timings is a DURATION, and the durations NEST.
    # Summing them all (as this tool first did) produced 592.1s against a 360.4s
    # total — a nonsense "-231.7s unnamed". Both classes are excluded explicitly
    # rather than by guessing at names.
    VALUES = {"target_fps", "source_fps", "source_duration_s", "shake_score",
              "cpu_by_stage", "mem_by_stage"}
    TOP = ("normalize_transcribe_upload", "edit_plan", "render", "upload_export")
    NESTED = {"gemini_call": "edit_plan", "gemini_wasted_degen": "edit_plan",
              "fps_normalize": "normalize_transcribe_upload",
              "download": "normalize_transcribe_upload",
              "source_poll": "normalize_transcribe_upload"}
    med = {k: m for m, k, _, _, _ in rows}
    print("\n  TOP-LEVEL stages (these partition `total`):")
    s = 0.0
    for k in TOP:
        if k in med:
            s += med[k]
            print(f"    {k:<30} {med[k]:>8.1f}s")
    print(f"    {'sum of top-level':<30} {s:>8.1f}s   vs total median "
          f"{med.get('total', float('nan')):.1f}s")
    print("\n  NESTED inside a parent (do NOT add these to the sum):")
    for k, parent in NESTED.items():
        if k in med:
            pv = med.get(parent)
            share = f"{100*med[k]/pv:.0f}% of {parent}" if pv else ""
            print(f"    {k:<30} {med[k]:>8.1f}s   {share}")
    print(f"\n  excluded as NON-DURATIONS: {sorted(VALUES & set(med))}")
