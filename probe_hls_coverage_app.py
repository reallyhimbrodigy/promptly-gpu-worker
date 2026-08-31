"""Does the MAIN route even record stage_timings.hls?

The distribution above came entirely from diverted routes (moodreel, minimal,
minimal_speech_uncut, hype). If std-editorial — the majority of output — never
records `hls`, then that distribution describes the minority and says NOTHING
about the ~80s Zac reports. Measure the bucket you intend to measure.
"""
import os
from collections import Counter

import modal

app = modal.App("probe-hls-coverage")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 20:
        r = (sb.table("video_jobs").select("id,result,demo,status,created_at")
             .gte("created_at", since).eq("status", "completed")
             .order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < 500:
            break
        page += 1
    per = {}
    keysets = Counter()
    for x in rows:
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        rt = str(res.get("route") or "std-editorial")
        d = per.setdefault(rt, {"n": 0, "with_hls": 0, "hls_vals": []})
        d["n"] += 1
        if "hls" in stt:
            d["with_hls"] += 1
            if isinstance(stt["hls"], (int, float)):
                d["hls_vals"].append(stt["hls"])
        if rt == "std-editorial":
            keysets[",".join(sorted(k for k in stt if "hls" in k.lower()
                                    or k in ("render", "upload", "total")))] += 1
    return {"per": {k: {"n": v["n"], "with_hls": v["with_hls"],
                        "hls_p50": (sorted(v["hls_vals"])[len(v["hls_vals"])//2]
                                    if v["hls_vals"] else None)}
                    for k, v in per.items()},
            "std_keysets": keysets.most_common(6)}


@app.local_entrypoint()
def main(since: str = "2026-08-10"):
    d = scan.remote(since)
    print(f"\n=== stage_timings.hls COVERAGE BY ROUTE — since {since} ===")
    print(f"    {'route':<24} {'completions':>12} {'with hls':>9} {'cover':>7}  hls p50")
    tot = totc = 0
    for rt, v in sorted(d["per"].items(), key=lambda kv: -kv[1]["n"]):
        tot += v["n"]; totc += v["with_hls"]
        p = 100.0 * v["with_hls"] / max(1, v["n"])
        print(f"    {rt:<24} {v['n']:>12} {v['with_hls']:>9} {p:>6.1f}%  "
              f"{v['hls_p50'] if v['hls_p50'] is not None else '—'}")
    print(f"    {'TOTAL':<24} {tot:>12} {totc:>9} {100.0*totc/max(1,tot):>6.1f}%")
    print(f"\n  std-editorial timing keys seen (hls/render/upload/total only):")
    for ks, n in d["std_keysets"]:
        print(f"    {n:>5}  [{ks}]")
