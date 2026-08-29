"""DELIVERED DENSITY, BY FAMILY, PER 25s OF OUTPUT — std-editorial cohort.

Read from result.edit_recipe (the DELIVERED recipe, post-cull), which is what a
viewer actually sees — not plan emission. Cut BY ROUTE per Rule 5: a blended
number over moodreel + minimal + std-editorial is not a product metric.

DENOMINATOR IS OUTPUT SECONDS, derived from the recipe's kept cuts. Source
seconds would inflate it by exactly the silence the cut pass removed and
understate density.

FAMILIES, and where each lives in the recipe (the recipe is FLAT for
std-editorial — 77% of output — and the nested `{plan:...}` shape belongs to
diverted routes; both are handled because reading one shape from one sample is
a documented way to be wrong here):
  emphasis    cuts[]._zoom_effect          (the zoom-per-emphasis instrument)
  mg          motion_graphics[]
  overlay     text_overlays[]
  transition  cuts[].transition_out != none
  sfx         sound_effects[]
  broll       broll_clips[]

  ./run_modal.sh probe_density_by_family_app.py --since 2026-08-27
"""
import os
import statistics as st
from collections import Counter

import modal

app = modal.App("probe-density-family")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 500
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,created_at,result,demo")
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


def _flat(rec):
    if not isinstance(rec, dict):
        return None
    return rec.get("plan") if isinstance(rec.get("plan"), dict) else rec


def _measure(rec):
    r = _flat(rec)
    if not isinstance(r, dict):
        return None
    cuts = [c for c in (r.get("cuts") or []) if isinstance(c, dict)
            and isinstance(c.get("source_start"), (int, float))
            and isinstance(c.get("source_end"), (int, float))
            and c["source_end"] > c["source_start"]]
    if not cuts:
        return None
    out = sum((c["source_end"] - c["source_start"]) / (c.get("speed") or 1) for c in cuts)
    if out <= 0:
        return None
    return {
        "out_s": out,
        "emphasis": sum(1 for c in cuts if c.get("_zoom_effect")),
        "transition": sum(1 for c in cuts
                          if c.get("transition_out") and c["transition_out"] != "none"),
        "mg": len(r.get("motion_graphics") or []),
        "overlay": len(r.get("text_overlays") or []),
        "sfx": len(r.get("sound_effects") or []),
        "broll": len(r.get("broll_clips") or []),
        # tight_cut_overlays was MISSING from this query while emitting at
        # 0.25/25s — a family nobody counted. It is the DESIGNED substitute for
        # transitions on tight footage (compute_transition_slot_frames: "on tight
        # footage they go extinct and tight-cut overlays + bare cuts own the
        # seams"), so whether it DELIVERS is the load-bearing question, not an
        # afterthought. Emission without delivery here would mean the substitute
        # is failing silently and seams are simply undressed.
        "tight_ovl": len(r.get("tight_cut_overlays") or []),
        "cuts": len(cuts),
    }


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    d = scan.remote(since)
    rows = [r for r in d["rows"] if not r.get("demo")]
    FAM = ("emphasis", "mg", "overlay", "transition", "tight_ovl", "sfx", "broll")

    buckets = {}
    norec = 0
    for r in rows:
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        route = str(res.get("route") or "std-editorial")
        m = _measure(res.get("edit_recipe"))
        if not m:
            norec += 1
            continue
        buckets.setdefault(route, []).append(m)

    print(f"\n=== DELIVERED DENSITY per 25s of OUTPUT — since {d['since']} ===")
    print(f"  {len(rows)} organic completions; {norec} without a readable recipe "
          f"(reported, not silently dropped)")

    for route, ms in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        tot_out = sum(m["out_s"] for m in ms)
        print(f"\n  ── {route}: {len(ms)} jobs, {tot_out/60:.1f} min of output ──")
        print(f"     {'family':>11} {'per 25s (p50)':>14} {'mean':>7} "
              f"{'total':>7} {'jobs w/ 0':>10}")
        allsum = 0.0
        for f in FAM:
            per = [25.0 * m[f] / m["out_s"] for m in ms]
            zero = sum(1 for m in ms if m[f] == 0)
            allsum += st.mean(per)
            print(f"     {f:>11} {st.median(per):>14.2f} {st.mean(per):>7.2f} "
                  f"{sum(m[f] for m in ms):>7} {zero:>7} ({100.0*zero/len(ms):.0f}%)")
        print(f"     {'ALL':>11} {'':>14} {allsum:>7.2f}  <- mean events/25s, all families")
        _mg = [25.0 * m["mg"] / m["out_s"] for m in ms]
        print(f"\n     MG-only per 25s: p50 {st.median(_mg):.2f}  mean {st.mean(_mg):.2f}"
              f"   (the 7.76 / 12.5 ceiling / 16.7 reference are MG-family numbers)")
