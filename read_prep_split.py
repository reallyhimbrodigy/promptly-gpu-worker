#!/usr/bin/env python3
"""read_prep_split.py — WHERE THE DARK RENDER SECONDS WENT.

v566 (8e466c5) added four children to the `render` span: render_prep (a
catch-all from render_multi_clip entry to the Remotion spawn),
render_zoom_pre_extract, render_transition_pre_extract, and a per-attempt
render_attempt_rung<N>, plus a persisted `render_attempts` counter.

WHAT WAS ALREADY ELIMINATED, so this read is a fork and not a fishing trip:
    render unaccounted   p50  17.1s    max 499.0s   <- the tail IS the dark time
    upload_export        p50   4.5s    max  21.0s   <- explains 1% of it
    source duration      r = 0.132
    drawn components     r = 0.224
    cut count            r = 0.064
Everything the planner controls is ruled out, and so is the post-render fan-out.

THE FORK THIS READ RESOLVES, stated before the data arrives so the answer cannot
be chosen afterwards:
  * prep LARGE  -> the dark seconds are ffmpeg prep (staging + pre-extracts).
                   That is the answer, and the fix is prep-side.
  * prep SMALL  -> prep is bounded and innocent; the seconds are inside
                   Remotion's own spawn, between the process starting and
                   render_remotion's clock. The search moves there, NARROWED.
  * attempts>1  -> the render ran more than once and the wall is a retry, not a
                   slow render. Different fix entirely.

    python3 read_prep_split.py
"""
import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

import promptly_read as P

V566_UTC = "2026-08-22T19:57:00Z"
KIDS = ("render_prep", "render_zoom_pre_extract", "render_transition_pre_extract",
        "render_remotion", "render_audio", "render_composite")


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


def main():
    url, key = _creds()
    rows = _q(url, key,
              "video_jobs?select=id,created_at,stage_timings,result&status=eq.completed"
              f"&created_at=gte.{urllib.parse.quote(V566_UTC)}"
              "&order=created_at.desc&limit=1000")
    data = []
    for row in rows:
        if P.route(row) != "EDITORIAL":
            continue
        node = P.render_span(row)
        if node is P.MISSING:
            continue
        st_ = P.stage_timings(row)
        kids = {}
        for c in node.get("children") or []:
            kids[c["name"]] = kids.get(c["name"], 0.0) + float(c.get("dur") or 0.0)
        data.append({
            "id": str(row["id"])[:8], "render": float(node.get("dur") or 0.0),
            "unacc": float(node.get("unaccounted") or 0.0), "kids": kids,
            "src": st_.get("source_duration_s"),
            "attempts": st_.get("render_attempts"),
        })

    print(f"  ── PREP SPLIT · editorial renders since v566 ({V566_UTC}) ──")
    if not data:
        print("  NO editorial renders yet. EMPTY, not answered — the fork below "
              "stays open.")
        return 2
    print(f"  n={len(data)}")
    print(f"\n  {'job':<10}{'render':>9}{'prep':>9}{'zoomPE':>9}{'transPE':>9}"
          f"{'remotion':>10}{'compos':>9}{'UNACC':>9}{'att':>5}")
    for d in sorted(data, key=lambda x: -x["render"]):
        k = d["kids"]
        print(f"  {d['id']:<10}{d['render']:>9.1f}"
              f"{k.get('render_prep', 0):>9.1f}"
              f"{k.get('render_zoom_pre_extract', 0):>9.1f}"
              f"{k.get('render_transition_pre_extract', 0):>9.1f}"
              f"{k.get('render_remotion', 0):>10.1f}"
              f"{k.get('render_composite', 0):>9.1f}"
              f"{d['unacc']:>9.1f}{str(d['attempts']):>5}")

    tot = st.median([d["render"] for d in data])
    prep = st.median([d["kids"].get("render_prep", 0.0) for d in data])
    unacc = st.median([d["unacc"] for d in data])
    print(f"\n  p50 render {tot:.1f}s   prep {prep:.1f}s "
          f"({prep/tot*100 if tot else 0:.0f}%)   unaccounted {unacc:.1f}s "
          f"({unacc/tot*100 if tot else 0:.0f}%)")

    # the slowest job is the one that matters — the tail is the whole question
    slow = max(data, key=lambda d: d["render"])
    k = slow["kids"]
    p = k.get("render_prep", 0.0)
    print(f"\n  SLOWEST: {slow['id']}  render {slow['render']:.1f}s  "
          f"source {slow['src']}s  attempts={slow['attempts']}")
    print(f"    prep {p:.1f}s = {p/slow['render']*100 if slow['render'] else 0:.0f}% "
          f"of it   (zoom {k.get('render_zoom_pre_extract', 0):.1f}s, "
          f"transition {k.get('render_transition_pre_extract', 0):.1f}s)")
    print(f"    remotion {k.get('render_remotion', 0):.1f}s   "
          f"unaccounted {slow['unacc']:.1f}s")

    print("\n  ── VERDICT ──")
    if slow["attempts"] and int(slow["attempts"]) > 1:
        print(f"  RETRY: the slowest render ran {slow['attempts']} times. Its wall "
              f"is a LADDER cost, not a slow render — fix the failure, not the "
              f"renderer.")
    frac = (p / slow["render"] * 100) if slow["render"] else 0
    if frac >= 40:
        print(f"  PREP IS THE ANSWER: {frac:.0f}% of the slowest render is prep "
              f"(staging + ffmpeg pre-extracts). The fix is prep-side — these are "
              f"source-resolution-bound decodes, which is why a short 4K source "
              f"renders slower than a long 1080p one.")
    elif slow["unacc"] > 0.4 * slow["render"]:
        print(f"  PREP IS INNOCENT ({frac:.0f}%) and {slow['unacc']:.0f}s is STILL "
              f"unaccounted. The seconds are inside the Remotion spawn itself — "
              f"between process start and render_remotion's clock. Search moves "
              f"there, and it is now NARROWED rather than guessed.")
    else:
        print(f"  ACCOUNTED: prep {frac:.0f}%, unaccounted "
              f"{slow['unacc']/slow['render']*100 if slow['render'] else 0:.0f}%. "
              f"The render span now explains itself; read the largest child.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
