"""COMPOSITE vs SCALE-ONLY on ORGANIC plans — does Tier 2 matter in aggregate?

Tier 1 measured, on an identical 271-frame set:
    StepZoom      (scale-only)   785 ms/frame
    FocusWindow   (composite)   1164
    LetterboxPush (composite)   1796      <- 2.3x StepZoom

That per-frame ratio is real. Whether it MATTERS depends entirely on the mix:
if organic plans are overwhelmingly scale-only, optimising LetterboxPush buys
almost nothing, and Tier 2 is not worth its cost.

WHAT IS COUNTED, and the distinction is the whole point:
  - CLIPS carrying each zoom type (how often the model reaches for it), and
  - FRAMES those clips render (what it actually costs), because a type used
    rarely but on long clips can dominate the bill while looking rare.

READ FROM cuts[]._zoom_effect on delivered plans — the SAME field the ablation
mutated, and the one categorize_clip() actually consults. NOT emphasis_moments:
that is a planning input, inert in the rendered plan, and reading it would count
a field that does not drive the render (the mistake the first ablation made).

COMPLEX_ZOOM_TYPES is the set that routes to Remotion. SIMPLE_ZOOM_TYPES is
EMPTY, so every zoom paints in the composition — "scale-only" here means the
component is a pure scale, not that it goes to FFmpeg.
"""
import os
from collections import Counter

import modal

app = modal.App("probe-zoom-mix")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

SCALE_ONLY = {"SmoothPush", "SnapReframe", "StepZoom", "StagedPush"}
COMPOSITE = {"FocusWindow", "LetterboxPush", "DepthPull"}
# Measured ms/frame from the Tier 1 ablation; StagedPush/DepthPull/SmoothPush
# were NOT measured and are marked so rather than assumed.
MEASURED = {"StepZoom": 785, "SnapReframe": 785, "FocusWindow": 1164,
            "LetterboxPush": 1796}


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 20:
        r = (sb.table("video_jobs").select("id,result,demo,created_at")
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
        rc = res.get("edit_recipe") or {}
        rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
        if not isinstance(rc, dict):
            continue
        cuts = rc.get("cuts") or []
        if not cuts:
            continue
        fps = float((res.get("stage_timings") or {}).get("target_fps") or 30) or 30
        per = []
        for c in cuts:
            if not isinstance(c, dict):
                continue
            ze = c.get("_zoom_effect")
            if not isinstance(ze, dict):
                continue
            t = str(ze.get("type") or "?")
            try:
                dur = float(c.get("source_end", 0)) - float(c.get("source_start", 0))
            except Exception:
                dur = 0.0
            per.append((t, max(0.0, dur) * fps))
        out.append({"id": x.get("id"), "n_cuts": len(cuts), "zooms": per})
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-20"):
    rows = scan.remote(since)
    print(f"\n=== ZOOM MIX ON ORGANIC PLANS — since {since} ===")
    print(f"  {len(rows)} completed std plans with cuts")
    if not rows:
        print("  NO PLANS — absent read, not 'no zooms'.")
        return
    clips = Counter()
    frames = Counter()
    with_any = 0
    for r in rows:
        if r["zooms"]:
            with_any += 1
        for t, f in r["zooms"]:
            clips[t] += 1
            frames[t] += f
    tot_c = sum(clips.values())
    tot_f = sum(frames.values())
    print(f"  {with_any}/{len(rows)} plans carry at least one zoom "
          f"({100.0*with_any/len(rows):.0f}%)")
    print(f"  {tot_c} zoomed clips total, {tot_f:,.0f} micro frames\n")
    print(f"  {'type':<16} {'kind':<12} {'clips':>6} {'clip%':>7} {'frames':>10} {'frame%':>7}")
    for t, n in clips.most_common():
        kind = ("scale-only" if t in SCALE_ONLY
                else "composite" if t in COMPOSITE else "unknown")
        print(f"  {t:<16} {kind:<12} {n:>6} {100.0*n/max(1,tot_c):>6.1f}% "
              f"{frames[t]:>10,.0f} {100.0*frames[t]/max(1,tot_f):>6.1f}%")

    sc_f = sum(frames[t] for t in frames if t in SCALE_ONLY)
    co_f = sum(frames[t] for t in frames if t in COMPOSITE)
    print(f"\n  BY FRAMES — scale-only {100.0*sc_f/max(1,tot_f):.1f}%  "
          f"composite {100.0*co_f/max(1,tot_f):.1f}%")

    # What a Tier 2 win would actually buy, priced with the MEASURED numbers.
    print(f"\n  --- what Tier 2 could buy, at the measured ms/frame ---")
    unmeasured = sorted(t for t in frames if t not in MEASURED)
    cur = sum(frames[t] * MEASURED.get(t, 0) for t in frames if t in MEASURED)
    best = sum(frames[t] * 785 for t in frames if t in MEASURED)
    meas_f = sum(frames[t] for t in frames if t in MEASURED)
    print(f"  measured-type frames: {meas_f:,.0f} of {tot_f:,.0f} "
          f"({100.0*meas_f/max(1,tot_f):.0f}%)")
    if meas_f:
        print(f"  current  : {cur/1000:>9,.0f}s of micro paint")
        print(f"  if every composite cost what StepZoom costs: {best/1000:>9,.0f}s")
        print(f"  CEILING ON A PERFECT TIER 2 FIX: {(cur-best)/1000:,.0f}s "
              f"({100.0*(cur-best)/max(1,cur):.1f}% of measured micro paint)")
    if unmeasured:
        print(f"\n  UNMEASURED types present in the mix: {unmeasured}")
        print(f"  Their cost is unknown — not assumed equal to anything.")
