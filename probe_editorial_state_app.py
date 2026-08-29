"""EDITORIAL LAYER — OBSERVED STATE. Read-only, one CPU container, no renders.

Answers from the DB rather than from code defaults, because the two disagree:
handler.py's GEMINI_EDITORIAL_MODEL default is "gemini-3.1-pro-preview" but
PROMPTLY_EDITORIAL_MODEL can override it at container start, and
STAGE_DECOMPOSITION.md claims "gemini-3.7-flash". Only the rows know.

  1. Which editorial model actually ran, by job, with a denominator.
  2. Route mix (std-editorial vs the rest) — density means nothing unblended.
  3. What component-count telemetry is ACTUALLY persisted, dumped verbatim from
     a real std-editorial row, so density is read from the bucket it is measured
     in rather than a shape inferred from one sample.

  ./run_modal.sh probe_editorial_state_app.py --since 2026-08-27
"""
import os
from collections import Counter

import modal

app = modal.App("probe-editorial-state")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 1000
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,created_at,result,demo")
             .gte("created_at", since).eq("status", "completed")
             .order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 20:
            break
    return {"rows": rows, "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    import json
    d = scan.remote(since)
    rows = [r for r in d["rows"] if not r.get("demo")]

    def _res(r):
        v = r.get("result")
        return v if isinstance(v, dict) else {}

    def _st(r):
        v = _res(r).get("stage_timings")
        return v if isinstance(v, dict) else {}

    print(f"\n=== organic COMPLETIONS since {d['since']}: {len(rows)} jobs "
          f"/ {len({r.get('user_id') for r in rows})} users ===")
    if not rows:
        print("  EMPTY — nothing below is measurable.")
        return

    # 1 — WHICH MODEL ACTUALLY RAN
    em = Counter(str(_st(r).get("editorial_model") or _res(r).get("editorial_model")
                     or "<absent>") for r in rows)
    print("\n  [1] editorial_model, OBSERVED:")
    for k, n in em.most_common():
        print(f"      {n:>4}  ({100.0*n/len(rows):>5.1f}%)  {k}")
    um = Counter(str(_st(r).get("utility_model") or "<absent>") for r in rows)
    print("      utility_model: " + ", ".join(f"{k}={n}" for k, n in um.most_common(3)))

    # media resolution + proxy sample fps actually sent
    mr = Counter(str(_st(r).get("media_resolution") or "<absent>") for r in rows)
    sf = Counter(str(_st(r).get("proxy_sample_fps") or "<absent>") for r in rows)
    print(f"      media_resolution: " + ", ".join(f"{k}={n}" for k, n in mr.most_common(4)))
    print(f"      proxy_sample_fps: " + ", ".join(f"{k}={n}" for k, n in sf.most_common(4)))

    # 2 — ROUTE MIX
    rt = Counter(str(_res(r).get("route") or _st(r).get("route") or "<absent>") for r in rows)
    print("\n  [2] route mix:")
    for k, n in rt.most_common():
        print(f"      {n:>4}  ({100.0*n/len(rows):>5.1f}%)  {k}")

    # 3 — WHAT COMPONENT TELEMETRY EXISTS. Dump the union of stage_timings keys
    #     and one real row verbatim, so density is read from the actual shape.
    keys = Counter()
    for r in rows:
        for k in _st(r):
            keys[k] += 1
    print(f"\n  [3] stage_timings keys present on >=50% of rows:")
    for k, n in sorted(keys.items()):
        if n >= len(rows) * 0.5:
            print(f"      {n:>4}  {k}")

    cand = [k for k in keys if any(t in k.lower() for t in
            ("count", "mg", "overlay", "sfx", "sound", "emph", "trans", "broll",
             "density", "v2_"))]
    print(f"\n      component-ish keys: {sorted(cand)}")
    sample = next((r for r in rows if _st(r).get("v2_counts")), rows[0])
    print(f"\n      VERBATIM sample (job {sample.get('id')}):")
    for k in sorted(cand):
        print(f"        {k} = {json.dumps(_st(sample).get(k))[:220]}")
    print(f"\n      result top-level keys: {sorted(_res(sample).keys())[:30]}")
