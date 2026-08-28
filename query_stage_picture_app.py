"""THE CURRENT PICTURE — all four reads in ONE container ($0.005, no renders).

Every number on the board is weeks old. This answers, from TODAY's organic
traffic, in one pass because they are all the same read:

  1. WHICH MODEL the editorial call actually used, and gemini_call p50. If it
     has not moved off ~82s the flags are INERT IN THE RUNNING IMAGE whatever the
     secret says — secret-set is not path-taken, and that gap has cost this
     project a full flip before.
  2. HLS: is copy-mode actually executing? Code is wired (-c copy at 36416,
     gated on PROMPTLY_HLS_COPY which reads '1' live), and it runs in a
     ThreadPoolExecutor whose `with` block JOINS ALL THREE futures — so HLS
     still gates the terminal write even though it is parallel to the upload.
     Copy ~1s vs re-encode ~72s is the discriminator.
  3. The ~29s FIXED term in normalize_transcribe_upload. Its five waits are all
     ZERO and the pool sums to ~32s serial / ~10s wall, so neither owns it.
     Name the synchronous work by differencing the stage against its parts.
  4. The full stage decomposition, p50, by route.

CUT BY ROUTE (Rule 5) and reported with n, because a blended p50 over a mixed
route population is not a product metric.
"""
import json
import os
import statistics as st
import sys

import modal

app = modal.App("query-stage-picture")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

STAGES = ["download", "normalize_transcribe_upload", "edit_plan", "gemini_call",
          "render", "upload_export", "hls", "source_poll", "fps_normalize",
          "broll", "edit_recipe_faces", "total"]


def _p(v, q=0.5):
    if not v:
        return None
    s = sorted(v)
    return round(s[min(len(s) - 1, int(round(q * (len(s) - 1))))], 1)


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str = "", limit: int = 4000) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    rows, PAGE = [], 500
    for off in range(0, max(PAGE, limit), PAGE):
        q = (sb.table("video_jobs")
             .select("id, st:result->stage_timings, rt:result->route")
             .eq("status", "completed")
             .order("created_at", desc=True).range(off, off + PAGE - 1))
        if since:
            q = q.gte("created_at", since)
        try:
            r = q.execute()
        except Exception as e:
            return {"error": f"QUERY FAILED: {type(e).__name__}: {e}"}
        if not r.data:
            break
        rows.extend(r.data)
        if len(r.data) < PAGE:
            break

    acc, models, pool, n = {}, {}, {}, 0
    by_route = {}
    for r in rows:
        stt = r.get("st")
        if not isinstance(stt, dict):
            continue
        n += 1
        rt = r.get("rt") or "std-editorial"
        by_route[rt] = by_route.get(rt, 0) + 1
        m = stt.get("editorial_model")
        if m:
            models[str(m)] = models.get(str(m), 0) + 1
        for k in STAGES:
            v = stt.get(k)
            if isinstance(v, (int, float)):
                acc.setdefault(k, []).append(float(v))
        pt = stt.get("pool_task_s")
        if isinstance(pt, dict):
            for k, v in pt.items():
                if isinstance(v, (int, float)):
                    pool.setdefault(k, []).append(float(v))

    out = {"rows": len(rows), "with_stage_timings": n,
           "routes": dict(sorted(by_route.items(), key=lambda kv: -kv[1])),
           "editorial_models": dict(sorted(models.items(), key=lambda kv: -kv[1])),
           "stage_p50": {k: _p(v) for k, v in acc.items()},
           "stage_p90": {k: _p(v, 0.9) for k, v in acc.items()},
           "stage_n": {k: len(v) for k, v in acc.items()},
           "pool_p50": {k: _p(v) for k, v in pool.items()},
           "pool_n": {k: len(v) for k, v in pool.items()}}

    # (3) NAME THE FIXED TERM by differencing, not by assertion.
    nz = acc.get("normalize_transcribe_upload") or []
    ep = acc.get("edit_plan") or []
    if nz:
        out["normalize_p50"] = _p(nz)
        out["edit_plan_p50"] = _p(ep) if ep else None
        # edit_plan is NESTED INSIDE normalize (measured: t=40546..43390 contains
        # _mega_t0=42636..42731), so the residual is normalize MINUS edit_plan —
        # the synchronous work that is neither the Gemini wait nor the pool.
        if ep:
            out["normalize_minus_edit_plan_p50"] = round((_p(nz) or 0) - (_p(ep) or 0), 1)
        out["pool_wall_est_p50"] = max([v for v in (out["pool_p50"] or {}).values()
                                        if v is not None] or [0])
    return out


@app.local_entrypoint()
def main(since: str = "", limit: int = 4000):
    r = query.remote(since=since, limit=limit)
    if r.get("error"):
        print(f"  ❌ {r['error']}"); sys.exit(1)
    if not r.get("with_stage_timings"):
        print("  NO ROWS WITH stage_timings — an EMPTY READ, not a zero."); sys.exit(2)
    print(f"  rows {r['rows']}   with stage_timings {r['with_stage_timings']}")
    print(f"  routes: {r['routes']}")
    print(f"\n  (1) EDITORIAL MODEL ACTUALLY USED: {r['editorial_models'] or 'NOT RECORDED'}")
    p50, p90, nn = r["stage_p50"], r["stage_p90"], r["stage_n"]
    print(f"      gemini_call p50 {p50.get('gemini_call')}s  p90 {p90.get('gemini_call')}s  "
          f"(n={nn.get('gemini_call')})   baseline was 82s")
    print(f"\n  (2) HLS p50 {p50.get('hls')}s  p90 {p90.get('hls')}s (n={nn.get('hls')})")
    print(f"      ~1s => copy-mode LIVE.  ~72s => re-encode, flag inert in image.")
    print(f"\n  (3) normalize p50 {r.get('normalize_p50')}s   "
          f"edit_plan p50 {r.get('edit_plan_p50')}s (NESTED inside it)")
    print(f"      residual (normalize - edit_plan) = "
          f"{r.get('normalize_minus_edit_plan_p50')}s  <- the fixed term")
    print(f"      pool wall est (max task p50) = {r.get('pool_wall_est_p50')}s")
    print(f"      pool tasks p50: {r.get('pool_p50')}")
    print(f"\n  (4) FULL STAGE DECOMPOSITION (p50 / p90 / n)")
    for k in STAGES:
        if p50.get(k) is not None:
            print(f"      {k:>28} {str(p50[k]):>8} {str(p90.get(k)):>8}  n={nn.get(k)}")
