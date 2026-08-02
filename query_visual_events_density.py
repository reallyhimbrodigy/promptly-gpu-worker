"""VISUAL EVENTS PER 25s, cut BY ROUTE — the pace metric (Zac 2026-08-01).

A FREE Supabase read of stored plans. NOT Modal spend: it touches no container,
starts no render, and costs nothing. (I once declined this as "Modal spend" —
wrong, and the correction is recorded here so it is not repeated.)

    export $(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' \
        ~/content-studio/.env.local | xargs)
    python3 query_visual_events_density.py [limit]

SHAPE TRAPS that silently collapse the cohort if you miss them:
  • `video_jobs.edit_recipe` is SOMETIMES {plan, reason, route} and sometimes the
    plan itself. Unwrap both or you read zero.
  • standard-editorial plans carry `cuts` (source_start/source_end); the light
    routes (minimal / minimal_speech_uncut / moodreel / hype) carry `clips` with
    `start_s`/`end_s`. Handle both or every light route reads as "no timeline".
  • `video_jobs.user_id` is NULL on every row, so a per-USER cut (Rule 7) is NOT
    computable from this table. Do not report an apparent user count off it.

Events counted: cut BOUNDARIES (clips-1, the visible changes) + zooms + motion
graphics + text overlays + transitions. Caption-keyword pops are reported
SEPARATELY because whether an emphasised caption word counts as "something
happening" is a taste call, and it moves the median by ~2x.
"""
import json
import os
import statistics as st
import sys
import urllib.request
from collections import Counter, defaultdict

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 400
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TARGET_LO, TARGET_HI = 16, 25          # Zac: something every 1.0-1.5s


def fetch():
    q = ("/rest/v1/video_jobs?select=id,created_at,edit_recipe,result"
         "&status=eq.completed&edit_recipe=not.is.null"
         f"&order=created_at.desc&limit={LIMIT}")
    r = urllib.request.Request(URL + q, headers={
        "apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)


def unwrap(job):
    er = job.get("edit_recipe") or {}
    plan = er.get("plan") if isinstance(er.get("plan"), dict) else er
    plan = plan if isinstance(plan, dict) else {}
    route = er.get("route") or (job.get("result") or {}).get("route")
    if not route:
        route = "standard_editorial" if plan.get("cuts") else "unrecorded"
    return plan, route


def out_duration_s(plan):
    total = 0.0
    for c in plan.get("cuts") or []:
        try:
            s, e = float(c["source_start"]), float(c["source_end"])
            sp = float(c.get("speed") or 1) or 1
            if e > s:
                total += (e - s) / sp
        except Exception:
            pass
    if total:
        return total
    for c in plan.get("clips") or []:
        try:
            s, e = float(c.get("start_s", 0)), float(c.get("end_s", 0))
            sp = float(c.get("speed") or 1) or 1
            if e > s:
                total += (e - s) / sp
        except Exception:
            pass
    return total


def main():
    by = defaultdict(list)
    for job in fetch():
        plan, route = unwrap(job)
        dur = out_duration_s(plan)
        if dur < 5:                     # no timeline -> no rate to form
            continue
        ems = plan.get("_emphasis_moments") or plan.get("emphasis_moments") or []
        by[route].append(dict(
            dur=dur,
            cut=max(0, len(plan.get("cuts") or plan.get("clips") or []) - 1),
            zoom=sum(1 for e in ems if isinstance(e, dict) and e.get("zoom_effect")),
            mg=len(plan.get("motion_graphics") or []),
            to=len(plan.get("text_overlays") or []),
            tr=len(plan.get("transitions") or []),
            cap=len(plan.get("caption_keywords") or []),
        ))

    ev = lambda r: r["cut"] + r["zoom"] + r["mg"] + r["to"] + r["tr"]
    rate = lambda rows, f: sorted(f(r) / r["dur"] * 25 for r in rows)
    hdr = (f"{'route':<22}{'n':>4}{'cuts':>7}{'zoom':>6}{'MG':>6}{'txt':>6}"
           f"{'trans':>7}{'EVENTS':>8}{'+caps':>7}")
    print(f"VISUAL EVENTS / 25s — target {TARGET_LO}-{TARGET_HI}\n")
    print(hdr)
    print("-" * len(hdr))
    for route, rows in sorted(by.items(), key=lambda x: -len(x[1])):
        m = lambda f: st.median(rate(rows, f))
        print(f"{route:<22}{len(rows):>4}{m(lambda r: r['cut']):>7.2f}"
              f"{m(lambda r: r['zoom']):>6.2f}{m(lambda r: r['mg']):>6.2f}"
              f"{m(lambda r: r['to']):>6.2f}{m(lambda r: r['tr']):>7.2f}"
              f"{m(ev):>8.2f}{m(lambda r: ev(r) + r['cap']):>7.2f}")

    se = by.get("standard_editorial") or []
    if se:
        v = rate(se, ev)
        hit = sum(1 for x in v if x >= TARGET_LO)
        print(f"\nSTANDARD EDITORIAL (the product), n={len(se)}")
        print(f"  events/25s  p10={v[len(v)//10]:.1f}  median={st.median(v):.1f}"
              f"  p90={v[int(len(v)*.9)]:.1f}")
        print(f"  at/above {TARGET_LO}: {hit}/{len(v)} ({hit*100//len(v)}%)")
        print(f"  median gap between events: {25/st.median(v):.2f}s")
        vc = rate(se, lambda r: ev(r) + r["cap"])
        print(f"  incl. caption pops: median={st.median(vc):.1f}"
              f"  gap={25/st.median(vc):.2f}s")


if __name__ == "__main__":
    main()
