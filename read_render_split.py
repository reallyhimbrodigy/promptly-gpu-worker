#!/usr/bin/env python3
"""read_render_split.py — WHERE THE RENDER SECONDS ACTUALLY GO.

The render is ~57% of the editorial wall and was the largest unknown on the
board. `stage_timings.timeline` carries the tree; this reads it off real jobs.

WHY THE POPULATION MATTERS MORE THAN THE PERCENTAGE. Before v564 the burst
container never created a timeline (`_TL` is made at handler() entry; the burst
calls render_stage directly), so 6 of 21 renders had a `render` span with ZERO
children — and they were EXACTLY the six slowest. Any split computed then was
computed on the FAST HALF and silently reported as the whole. This tool always
prints the opaque count next to the split, so a partial answer can never again
be mistaken for a complete one.

    python3 read_render_split.py --since 2026-08-21T22:53:00Z   # post-v564
    python3 read_render_split.py --compare 2026-08-21T22:53:00Z # before/after
"""
import argparse
import collections
import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

GRAFT_UTC = "2026-08-21T22:53:00Z"   # v564 @ 4ae2896


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


def _j(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return v if isinstance(v, dict) else None


def _find(node, name):
    if node.get("name") == name:
        return node
    for c in node.get("children") or []:
        f = _find(c, name)
        if f:
            return f
    return None


def analyse(rows, label):
    kids = collections.defaultdict(list)
    lit, blind, unacc = [], [], []
    for row in rows:
        res = _j(row.get("result")) or {}
        s = _j(row.get("stage_timings")) or _j(res.get("stage_timings")) or {}
        tl = s.get("timeline")
        if not tl:
            continue
        rn = _find(tl, "render")
        if not rn:
            continue
        jid, dur = str(row["id"])[:8], float(rn.get("dur") or 0.0)
        src = s.get("source_duration_s") or 0
        ch = rn.get("children") or []
        if not ch:
            blind.append((jid, dur, src))
            continue
        lit.append((jid, dur, src))
        for c in ch:
            kids[c["name"]].append(float(c.get("dur") or 0.0))
        if dur:
            unacc.append(float(rn.get("unaccounted") or 0.0) / dur * 100)

    n = len(lit) + len(blind)
    print(f"\n  ══ {label} ══")
    if n == 0:
        print("  no renders with a timeline in this window — UNMEASURED, not zero")
        return None
    print(f"  renders: {n}   lit={len(lit)}   OPAQUE={len(blind)}"
          + ("" if not blind else "   ** the split below EXCLUDES these **"))
    if blind:
        b = sorted(blind, key=lambda x: -x[1])
        print(f"    opaque renders: " + ", ".join(f"{j}({d:.0f}s)" for j, d, _ in b[:8]))
        lit_d = [d for _, d, _ in lit]
        bl_d = [d for _, d, _ in blind]
        if lit_d and bl_d:
            print(f"    opaque p50 render={st.median(bl_d):.1f}s vs lit p50="
                  f"{st.median(lit_d):.1f}s  <- if opaque is SLOWER, the split is "
                  f"computed on the fast half")
    if not lit:
        return None

    tot = st.median([d for _, d, _ in lit])
    print(f"\n  {'render child':<24}{'n':>4}{'p50':>9}{'max':>9}{'share of render p50':>22}")
    for k, v in sorted(kids.items(), key=lambda kv: -st.median(kv[1])):
        m = st.median(v)
        print(f"  {k:<24}{len(v):>4}{m:>9.1f}{max(v):>9.1f}{m/tot*100:>21.1f}%")
    if unacc:
        print(f"  {'unaccounted':<24}{len(unacc):>4}{'':>18}{st.median(unacc):>21.1f}%")
    print(f"  render span p50 = {tot:.1f}s   (n={len(lit)})")
    return {"n": n, "lit": len(lit), "blind": len(blind), "kids": kids,
            "render_p50": tot}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=GRAFT_UTC)
    ap.add_argument("--compare", default=None,
                    help="split the window at this UTC instant (before/after)")
    a = ap.parse_args()
    url, key = _creds()
    since = a.compare or a.since
    rows = _q(url, key,
              "video_jobs?select=id,created_at,stage_timings,result"
              "&status=eq.completed&created_at=gte."
              + urllib.parse.quote("2026-08-21T18:47:00Z")
              + "&order=created_at.asc&limit=400")
    if a.compare:
        before = [r for r in rows if str(r["created_at"]) < a.compare]
        after = [r for r in rows if str(r["created_at"]) >= a.compare]
        analyse(before, f"BEFORE the graft (< {a.compare})")
        r2 = analyse(after, f"AFTER the graft (>= {a.compare})")
        if r2 and r2["blind"] == 0 and r2["n"]:
            print(f"\n  GRAFT CONFIRMED ON REAL TRAFFIC: {r2['n']}/{r2['n']} renders "
                  f"have children; 0 opaque.")
        elif r2:
            print(f"\n  NOT YET CONFIRMED: {r2['blind']} of {r2['n']} still opaque. "
                  f"A burst job needs >45s OUTPUT — if none has run since the "
                  f"deploy, this is an EMPTY TEST, not a failed one.")
        return 0
    analyse([r for r in rows if str(r["created_at"]) >= since], f"since {since}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
