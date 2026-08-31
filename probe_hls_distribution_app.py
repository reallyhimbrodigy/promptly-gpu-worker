"""HLS: the SHAPE of the distribution, not p50.

Zac reports HLS is sometimes ~1s and sometimes ~80s. A p50 over a bimodal
population describes neither mode and is how this was missed before, so this
prints the full histogram and the two arms separately.

80s is almost exactly the pre-copy-mode four-rendition re-encode (~72s), which
makes "the ladder still runs sometimes" the leading hypothesis. The competing
ones, all separable here:
  - copy mode OFF on some containers (env read at import; a secret flip is not
    live until redeploy, so containers of different ages can disagree)
  - the span includes SEGMENT UPLOAD, so 80s is network, not encode
  - route: the minimal route records its own `hls` span around a different call

Cut BY ROUTE, because a blended number over a mixed route population is not a
product metric.
"""
import os
import statistics as st
from collections import Counter, defaultdict

import modal

app = modal.App("probe-hls-distribution")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 20:
        r = (sb.table("video_jobs")
             .select("id,result,demo,created_at,status")
             .gte("created_at", since).eq("status", "completed")
             .order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < 500:
            break
        page += 1
    out = []
    for x in rows:
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        if "hls" not in stt:
            continue
        out.append({
            "id": x.get("id"), "created": str(x.get("created_at"))[:16],
            "hls": stt.get("hls"),
            "route": str(res.get("route") or "std-editorial"),
            "render": stt.get("render"), "upload": stt.get("upload"),
            "total": stt.get("total"),
            "src_s": stt.get("source_duration_s"),
            "fps": stt.get("target_fps"),
        })
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-10"):
    rows = scan.remote(since)
    vals = [r["hls"] for r in rows if isinstance(r["hls"], (int, float))]
    print(f"\n=== HLS DISTRIBUTION — {len(rows)} completions carrying stage_timings.hls ===")
    if not vals:
        print("  NO JOBS RECORD stage_timings.hls. That is an ABSENT read, not")
        print("  'HLS is fast' — the span may only be recorded on some routes.")
        return
    vs = sorted(vals)
    print(f"  n={len(vs)}  min={vs[0]:.1f}  p50={st.median(vs):.1f}  "
          f"p90={vs[int(len(vs)*0.9)]:.1f}  max={vs[-1]:.1f}")

    print(f"\n  HISTOGRAM (the point — p50 describes neither arm of a bimodal set)")
    buckets = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 40), (40, 60),
               (60, 75), (75, 90), (90, 120), (120, 1e9)]
    for lo, hi in buckets:
        n = sum(1 for v in vs if lo <= v < hi)
        if n:
            bar = "█" * max(1, int(40 * n / len(vs)))
            label = f"{lo}-{hi}s" if hi < 1e9 else f"{lo}s+"
            print(f"    {label:>10} {n:>4}  {bar}")

    fast = [r for r in rows if isinstance(r["hls"], (int, float)) and r["hls"] < 10]
    slow = [r for r in rows if isinstance(r["hls"], (int, float)) and r["hls"] >= 40]
    print(f"\n  TWO ARMS: fast(<10s)={len(fast)}  slow(>=40s)={len(slow)}  "
          f"middle={len(vs)-len(fast)-len(slow)}")
    if not slow:
        print("  NO SLOW ARM in this window — the ~80s reports are not reproduced")
        print("  here. Either the window is wrong or the number came from logs, not rows.")
    for name, grp in (("fast", fast), ("slow", slow)):
        if not grp:
            continue
        hv = sorted(r["hls"] for r in grp)
        print(f"\n  --- {name} arm (n={len(grp)}) hls p50 {st.median(hv):.1f}s ---")
        print(f"      routes: {dict(Counter(r['route'] for r in grp).most_common(4))}")
        for k in ("render", "upload", "total", "src_s", "fps"):
            g = [r[k] for r in grp if isinstance(r[k], (int, float))]
            if g:
                print(f"      {k:>8} p50 {st.median(g):>7.1f}   (n={len(g)})")
    if slow:
        print(f"\n  SLOWEST 6 (id / date / hls / route / render / src_s):")
        for r in sorted(slow, key=lambda z: -z["hls"])[:6]:
            print(f"    {str(r['id'])[:8]} {r['created']} hls={r['hls']:>6.1f} "
                  f"{r['route']:<22} render={r['render']} src={r['src_s']}")
