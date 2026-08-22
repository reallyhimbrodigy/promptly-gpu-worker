#!/usr/bin/env python3
"""read_render_drivers_full.py — THE COMPONENT HYPOTHESIS, ON THE WHOLE POPULATION.

The ledger-based test could only see the fast half: 22 of 70 editorial jobs
shipped with no component_ledger and they were the SLOW ones (p50 render 247.7s
vs 153.7s), holding the entire p95 tail. The fix for that landed but is not yet
deployed, so post-fix traffic does not exist.

IT DOES NOT NEED TO. The ledger is a CONVENIENCE; `edit_recipe` is the SOURCE,
it rides the same envelope, and every job in the p95 tail carries one. Counting
components off the recipe reaches the jobs the ledger could not — today.

WHY THIS IS THE DECIDING MEASUREMENT. Duration was refuted (r=0.163 at n=70).
If components explain the tail, then every quality feature — an extra card, a
denser emphasis pass, gap-fill — stops being a taste call and becomes a PRICED
latency decision, with a number attached per component.

CLIPS ARE COUNTED SEPARATELY AND DELIBERATELY. The renderer splits work into
micro/overlay chunks, so the CUT COUNT may drive render cost independently of
anything drawn on top. A test that folds clips into "components" cannot tell a
decoration problem from a segmentation problem, and those have opposite fixes.

    python3 read_render_drivers_full.py
"""
import collections
import json
import math
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

import promptly_read as P

SINCE = "2026-08-20T00:00:00Z"

# Arrays whose length plausibly costs RENDER seconds. caption_keywords is
# excluded on purpose: captions render for every job regardless of count, so
# including it would import a term that cannot be traded away.
#
# ALIASES, NOT SEPARATE COMPONENTS. The recipe carries several lists under BOTH
# a bare and an underscore-prefixed name (`emphasis_moments` and
# `_emphasis_moments` are the same 4 items; likewise sound_effects and
# tight_cut_overlays). Summing both double-counts them, which is the bug the
# first cut of this tool shipped — it scored 40c3ddc5 at 8 drawn when the recipe
# holds 4. One canonical name per kind, resolved by preference order.
DRAWN = {
    "motion_graphics": ("motion_graphics", "_motion_graphics"),
    "text_overlays": ("text_overlays", "_text_overlays"),
    "broll_clips": ("broll_clips",),
    "transitions": ("transitions",),
    "generated_scenes": ("generated_scenes",),
    "tight_cut_overlays": ("_resolved_tight_cut_overlays", "tight_cut_overlays"),
    "emphasis_moments": ("emphasis_moments", "_emphasis_moments"),
    "sound_effects": ("_parsed_sound_effects", "sound_effects"),
}
# The cut list is `cuts`. The first cut of this tool looked for `clips`, found
# nothing, and reported 0 for every job — a silent zero that would have retired
# the segmentation hypothesis without ever testing it. Sixth wrong-key instance,
# and made inside the very tool written to end them: the accessor cannot help
# with a key nobody checked against the data.
CUTS_KEYS = ("cuts", "clips", "_cuts")


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
              f"&created_at=gte.{urllib.parse.quote(SINCE)}&order=created_at.asc&limit=400")
    data = []
    skipped = 0
    for row in rows:
        if P.route(row) != "EDITORIAL":
            continue
        st_ = P.stage_timings(row)
        rn, src = st_.get("render"), st_.get("source_duration_s")
        if not isinstance(rn, (int, float)) or not rn:
            continue
        rec = P.edit_plan(row)
        if rec is P.MISSING:
            skipped += 1
            continue
        per = {}
        for canon, aliases in DRAWN.items():
            for a in aliases:
                v = rec.get(a)
                if isinstance(v, list):
                    if v:
                        per[canon] = len(v)
                    break   # FIRST alias present wins — never sum aliases
        n_clips = 0
        for a in CUTS_KEYS:
            v = rec.get(a)
            if isinstance(v, list):
                n_clips = len(v)
                break
        data.append({
            "id": str(row["id"])[:8], "render": float(rn), "src": float(src or 0),
            "drawn": sum(per.values()), "clips": n_clips, "per": per,
            "had_ledger": P.component_ledger(row) is not P.MISSING,
        })

    n_led = sum(1 for d in data if d["had_ledger"])
    print(f"  editorial renders: {len(data)}   (recipe missing, excluded: {skipped})")
    print(f"  of these, {n_led} had a ledger and {len(data)-n_led} did NOT — the "
          f"latter were invisible to the previous test")
    if len(data) < 8:
        print("  TOO FEW. Unmeasured, not null.")
        return 2

    print(f"\n  {'variable':<26}{'r vs render':>13}{'p50':>8}{'max':>7}")
    for lbl, f in (("source_duration_s", lambda d: d["src"]),
                   ("DRAWN components", lambda d: d["drawn"]),
                   ("clips (cut count)", lambda d: d["clips"])):
        pts = [(f(d), d["render"]) for d in data]
        vals = [p[0] for p in pts]
        print(f"  {lbl:<26}{_r(pts):>13.3f}{st.median(vals):>8.1f}{max(vals):>7.0f}")

    kinds = sorted({k for d in data for k in d["per"]})
    print(f"\n  {'per-kind (recipe)':<26}{'r vs render':>13}{'p50':>8}{'max':>7}")
    for k in kinds:
        pts = [(d["per"].get(k, 0), d["render"]) for d in data]
        vals = [p[0] for p in pts]
        print(f"  {k:<26}{_r(pts):>13.3f}{st.median(vals):>8.1f}{max(vals):>7.0f}")

    data.sort(key=lambda d: -d["render"])
    print(f"\n  SLOWEST — the population the ledger could not see")
    print(f"  {'job':<10}{'render':>8}{'src':>7}{'drawn':>7}{'clips':>7}  led?  per-kind")
    for d in data[:8]:
        print(f"  {d['id']:<10}{d['render']:>8.1f}{d['src']:>7.1f}{d['drawn']:>7}"
              f"{d['clips']:>7}  {str(d['had_ledger']):<5} "
              f"{ {k: v for k, v in d['per'].items() if v} }")
    print(f"\n  FASTEST")
    for d in sorted(data, key=lambda d: d["render"])[:6]:
        print(f"  {d['id']:<10}{d['render']:>8.1f}{d['src']:>7.1f}{d['drawn']:>7}"
              f"{d['clips']:>7}  {str(d['had_ledger']):<5} "
              f"{ {k: v for k, v in d['per'].items() if v} }")

    q = max(3, len(data) // 4)
    top, bot = data[:q], sorted(data, key=lambda d: d["render"])[:q]
    print(f"\n  {'quartile':<12}{'p50 render':>12}{'p50 drawn':>11}{'p50 clips':>11}"
          f"{'p50 src':>10}")
    for lbl, s in (("slowest", top), ("fastest", bot)):
        print(f"  {lbl:<12}{st.median([d['render'] for d in s]):>12.1f}"
              f"{st.median([d['drawn'] for d in s]):>11.1f}"
              f"{st.median([d['clips'] for d in s]):>11.1f}"
              f"{st.median([d['src'] for d in s]):>10.1f}")

    # seconds per component, the number that turns a feature into a price
    pts = [(d["drawn"], d["render"]) for d in data]
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den:
        b = sum((p[0] - mx) * (p[1] - my) for p in pts) / den
        print(f"\n  FIT  render ~= {my - b*mx:.0f}s + {b:.1f}s per DRAWN component")
        print(f"       -> that slope IS the price of a quality feature, if the "
              f"correlation holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
