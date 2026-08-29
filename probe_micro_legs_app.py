"""WHERE DOES PromptlyMicroSegments ACTUALLY RUN? And what does it cost?

WHY THIS EXISTS. The 4/2/1 micro-concurrency sweep was about to spend ~$1.44 on
12 renders of a source that produces ZERO micro segments. The confirmation job
(~$0.13) caught it: 3 legs, all PromptlyOverlay, and `render_concurrency` null.

Micro segments come from TRANSITIONS and COMPLEX ZOOMS (handler.py:31786 —
"empty (no transitions, no complex zooms)"), and the `micro_concurrency_test`
override lives INSIDE the micro render path (handler.py:32251-32273). So on a
source with no micro work the sweep's independent variable never executes and
its dependent variable never exists. All 12 cells would have been identical
overlay renders reading as "concurrency has no effect" — an instrument failure
wearing a result's face.

So: measure the real population FIRST.
  1. What fraction of organic completions produce micro legs at all? (If micro
     is rare, the 7-16x ms/frame gap is a narrow problem, and that changes
     whether the sweep is worth running.)
  2. What is the ACTUAL ms/frame per composition on real traffic, with a
     denominator — the 775-1797 figure the sweep is premised on came from a
     small sample and has never been cut this way.
  3. Which sources produce micro, so a sweep can pick one that exercises it.

Rule 5: cut by composition, never blended. Rule 7: users beside jobs.

  ./run_modal.sh probe_micro_legs_app.py --since 2026-08-26
"""
import os
import statistics as st
from collections import Counter, defaultdict

import modal

app = modal.App("probe-micro-legs")
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
             .select("id,user_id,status,created_at,video_url,result,demo")
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
def main(since: str = "2026-08-26"):
    d = scan.remote(since)
    rows = [r for r in d["rows"] if not r.get("demo")]

    def _st(r):
        v = (r.get("result") or {})
        v = v.get("stage_timings") if isinstance(v, dict) else None
        return v if isinstance(v, dict) else {}

    withlegs = [r for r in rows if _st(r).get("render_legs")]
    per_comp = defaultdict(list)      # comp -> [ms/frame]
    frames = Counter()
    jobs_with = Counter()
    micro_sources = []

    for r in withlegs:
        seen = set()
        for lg in _st(r).get("render_legs") or []:
            name = str(lg.get("leg") or "")
            comp = ("micro" if "Micro" in name
                    else "overlay" if "Overlay" in name
                    else "other")
            mpf = lg.get("ms_per_frame")
            if isinstance(mpf, (int, float)):
                per_comp[comp].append(float(mpf))
            frames[comp] += int(lg.get("frames") or 0)
            seen.add(comp)
        for c in seen:
            jobs_with[c] += 1
        if "micro" in seen:
            micro_sources.append((r.get("created_at"), r.get("id"),
                                  str(r.get("video_url") or "")[:110]))

    print(f"\n=== organic COMPLETIONS since {d['since']} ===")
    print(f"  {len(rows)} completed jobs / {len({r.get('user_id') for r in rows})} users")
    print(f"  with RENDERCLOCK legs: {len(withlegs)}"
          + ("" if withlegs else "  <- no legs at all; nothing below is measurable"))
    if not withlegs:
        return

    print(f"\n  {'composition':>12} {'jobs':>6} {'legs':>6} {'frames':>9} "
          f"{'ms/frame p50':>13} {'p90':>8} {'max':>8}")
    for comp in ("micro", "overlay", "other"):
        v = per_comp.get(comp) or []
        if not v:
            print(f"  {comp:>12} {jobs_with[comp]:>6} {0:>6} {frames[comp]:>9}"
                  f" {'—':>13} {'—':>8} {'—':>8}")
            continue
        v_sorted = sorted(v)
        p90 = v_sorted[min(len(v_sorted) - 1, int(len(v_sorted) * 0.9))]
        print(f"  {comp:>12} {jobs_with[comp]:>6} {len(v):>6} {frames[comp]:>9} "
              f"{st.median(v):>13.1f} {p90:>8.1f} {max(v):>8.1f}")

    _m = jobs_with["micro"]
    print(f"\n  MICRO REACH: {_m}/{len(withlegs)} jobs with legs "
          f"({100.0 * _m / len(withlegs):.1f}%)")
    if per_comp.get("micro") and per_comp.get("overlay"):
        _r = st.median(per_comp["micro"]) / st.median(per_comp["overlay"])
        print(f"  MICRO/OVERLAY ms-per-frame ratio (p50): {_r:.1f}x")
        print("  The sweep is premised on a 7-16x gap. If this ratio is small,")
        print("  the premise came from a sample the population does not support.")
    else:
        print("  Cannot compute the micro/overlay ratio — one side has no legs.")

    if micro_sources:
        print(f"\n  SOURCES THAT ACTUALLY PRODUCE MICRO (pick one for the sweep):")
        for at, jid, url in micro_sources[:8]:
            print(f"    {at}  {jid}")
            print(f"       {url}")
    else:
        print("\n  NO ORGANIC JOB PRODUCED MICRO LEGS in this window.")
        print("  Then the 4/2/1 sweep has no population to generalise to, and")
        print("  the right next step is to question the premise, not to buy a")
        print("  synthetic source that exercises a path users do not hit.")
