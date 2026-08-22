#!/usr/bin/env python3
"""read_chunk_split.py — PER-CHUNK STARTUP vs PER-FRAME RASTERISATION.

v568 (8d14590) puts a `remotion:<label>` span on every overlay and micro chunk.
Before it, render_remotion reported unaccounted == dur with zero children on
every job — 80-85% of the render, entirely blind.

THE FORK, pre-registered, because the two need OPPOSITE fixes:
  * FIXED per chunk (~10s each, flat regardless of frames) -> the cost is
    PROCESS STARTUP. Fix = fewer chunks, not less work per chunk. Splitting
    harder makes it WORSE.
  * SCALES with frames -> the cost is RASTERISATION. Fix = paint fewer frames
    (empty-canvas skip, occupied-span-only overlay, cheaper alpha codec), and
    more chunks genuinely helps.
  * BOTH -> there is a floor (startup) and a slope (frames); the empty-canvas
    skip removes the slope but leaves N x startup, which caps the win.

    python3 read_chunk_split.py
"""
import json, os, statistics as st, sys, urllib.parse, urllib.request, collections
import promptly_read as P

V568 = "2026-08-22T21:12:00Z"


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


url, key = _creds()
r = urllib.request.Request(
    url + "/rest/v1/video_jobs?select=id,created_at,stage_timings,result"
    "&status=eq.completed&created_at=gte." + urllib.parse.quote(V568)
    + "&order=created_at.desc&limit=1000",
    headers={"apikey": key, "Authorization": f"Bearer {key}"})
rows = json.loads(urllib.request.urlopen(r, timeout=90).read())

def _find(n, nm):
    if not isinstance(n, dict): return None
    if n.get("name") == nm: return n
    for c in n.get("children") or []:
        f = _find(c, nm)
        if f: return f
    return None

data = []
for x in rows:
    if P.route(x) != "EDITORIAL": continue
    tl = P.timeline(x)
    if tl is P.MISSING: continue
    rr = _find(tl, "render_remotion")
    if not rr: continue
    kids = rr.get("children") or []
    rec = P.edit_plan(x)
    cuts = (rec or {}).get("cuts") or [] if rec is not P.MISSING else []
    out = sum(max(0.0, float(c.get("source_end", 0) or 0) - float(c.get("source_start", 0) or 0))
              for c in cuts)
    data.append({"id": str(x["id"])[:8], "dur": float(rr.get("dur") or 0),
                 "unacc": float(rr.get("unaccounted") or 0),
                 "kids": [(c["name"], float(c.get("dur") or 0)) for c in kids],
                 "out": out})

print(f"  ── remotion CHUNK SPLIT · since v568 ({V568}) ──")
if not data:
    print("  NO editorial renders yet — EMPTY, not answered.")
    sys.exit(2)
lit = [d for d in data if d["kids"]]
print(f"  editorial renders: {len(data)}   with chunk spans: {len(lit)}")
if not lit:
    print("  render_remotion STILL has no children — the v568 wrapper did not "
          "fire. NOT confirmed.")
    sys.exit(1)

allk = []
for d in lit:
    print(f"\n  {d['id']}  render_remotion {d['dur']:.1f}s  output {d['out']:.1f}s  "
          f"unaccounted {d['unacc']:.1f}s  chunks={len(d['kids'])}")
    for nm, v in sorted(d["kids"], key=lambda kv: -kv[1]):
        print(f"      {nm:<28}{v:>8.1f}s")
        allk.append((nm, v, d["out"], len(d["kids"])))
if not allk:
    sys.exit(1)

ov = [k for k in allk if "overlay" in k[0]]
mi = [k for k in allk if "micro" in k[0]]
print(f"\n  overlay chunks n={len(ov)}  p50={st.median([k[1] for k in ov]):.1f}s"
      if ov else "\n  overlay chunks: none")
if mi:
    print(f"  micro chunks   n={len(mi)}  p50={st.median([k[1] for k in mi]):.1f}s")

print("\n  ── VERDICT ──")
if ov and len(set(round(k[2]) for k in ov)) > 1:
    import math
    pts = [(k[2], k[1]) for k in ov]          # output seconds vs chunk seconds
    n = len(pts); mx = sum(p[0] for p in pts)/n; my = sum(p[1] for p in pts)/n
    den = sum((p[0]-mx)**2 for p in pts)
    if den:
        b = sum((p[0]-mx)*(p[1]-my) for p in pts)/den
        a = my - b*mx
        print(f"  overlay chunk ~= {a:.1f}s fixed + {b:.2f}s per output-second")
        if a > 0 and b*st.median([k[2] for k in ov]) < a:
            print("  STARTUP-DOMINATED: the fixed term exceeds the frame term at "
                  "typical length.\n  Fix = FEWER chunks. An empty-canvas skip "
                  "removes the slope but leaves N x startup.")
        else:
            print("  RASTERISATION-DOMINATED: the frame term dominates.\n"
                  "  Fix = paint fewer frames; the empty-canvas skip is the lever.")
else:
    print("  Too few distinct output lengths to separate fixed from per-frame.\n"
          "  n>=3 jobs of differing length needed — this is UNRESOLVED, not resolved.")
