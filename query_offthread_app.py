"""READ offthreadVideoThreads OFF REAL JOBS ($0 — one CPU container, no render).

The lever shipped at v573 and was unproven for one reason only: render-full.mjs
prints the value it used INSIDE the burst container, while the orchestrator's tee
captures the orchestrator. Twice the instrument was aimed at the wrong process
and twice "no evidence" was indistinguishable from "no effect".

It is a COLUMN now (v574+). This reads it.

WHAT A VALUE MEANS
  2        Remotion's DEFAULT_RENDER_FRAMES_OFFTHREAD_VIDEO_THREADS. The lever is
           NOT in force, whatever the source says.
  == concurrency   matched extractor — the intended state.
  None     no render leg reported. UNMEASURED, not zero, and NOT "the lever is
           off": a job that never rendered says nothing about the lever.

Cut BY ROUTE (Rule 5). A blended render number over a mixed route population is
not a product metric — std-editorial and premium differ by ~4.5x in wall clock.
"""
import os
import sys
import json
import modal

app = modal.App("query-offthread")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]


def _pct(v, q):
    if not v:
        return None
    s = sorted(v)
    return round(s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))], 1)


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str = "", limit: int = 4000) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    rows, PAGE = [], 1000
    for off in range(0, max(PAGE, limit), PAGE):
        q = (sb.table("video_jobs")
             .select("id, user_id, created_at, status, st:result->stage_timings, "
                     "rt:result->route, oa:result->stage_timings->offthread_arm, "
                     "rl:result->stage_timings->render_legs")
             .order("created_at", desc=True).range(off, off + PAGE - 1))
        if since:
            q = q.gte("created_at", since)
        try:
            r = q.execute()
        except Exception as e:
            return {"error": f"QUERY FAILED: {type(e).__name__}: {e}"}
        if not r.data:
            break
        rows.extend(r.data)
        if len(r.data) < PAGE:
            break

    # SHAPE PROBE: what does timeline ACTUALLY contain? Guessing key names is
    # how a confident zero gets reported for a stage that was simply read wrong.
    shape = {"stage_timings_keys": None, "timeline_keys": None, "timeline_sample": None}
    # THE ARM + THE DECOMPOSITION. "2" = extractor pinned to Remotion's default;
    # None = control. legs carry frames/elapsed/fps so 110s becomes two terms.
    arms = {}
    by_route, unmeasured, no_field, seen_vals = {}, 0, 0, {}
    for r in rows:
        st = r.get("st") or {}
        if not isinstance(st, dict):
            continue
        if "render_offthread_threads" not in st:
            no_field += 1                     # pre-v574 build
            continue
        ot = st.get("render_offthread_threads")
        cc = st.get("render_concurrency")
        legs = st.get("render_legs_reporting") or 0
        if not ot:
            unmeasured += 1                   # no render leg reported — NOT zero
            continue
        if shape["stage_timings_keys"] is None:
            shape["stage_timings_keys"] = sorted(st.keys())
            _tl = st.get("timeline")
            shape["timeline_keys"] = (sorted(_tl.keys()) if isinstance(_tl, dict)
                                      else f"NOT-A-DICT:{type(_tl).__name__}")
            shape["timeline_sample"] = None
            # ITEM (2): does normalize_transcribe_upload have CHILDREN, or is it
            # 49.5s of unattributed wall? Find the node and report its shape.
            def _find(n, want):
                if isinstance(n, dict):
                    if n.get("name") == want:
                        return n
                    for c in (n.get("children") or []):
                        f = _find(c, want)
                        if f:
                            return f
                return None
            _nz = _find(_tl, "normalize_transcribe_upload")
            shape["normalize_node"] = (
                {"dur": _nz.get("dur"), "unaccounted": _nz.get("unaccounted"),
                 "n_children": len(_nz.get("children") or []),
                 "children": [(c.get("name"), c.get("dur")) for c in (_nz.get("children") or [])]}
                if _nz else "NODE ABSENT FROM TIMELINE ENTIRELY")
        _arm = str(r.get("oa"))
        _a = arms.setdefault(_arm, {"jobs": 0, "users": set(), "render_s": [],
                                    "frames": [], "fps": [], "legs": 0})
        _a["jobs"] += 1
        _a["users"].add(r.get("user_id"))
        if isinstance(st.get("render"), (int, float)):
            _a["render_s"].append(float(st["render"]))
        for _l in (r.get("rl") or []):
            if isinstance(_l, dict) and _l.get("frames"):
                _a["legs"] += 1
                _a["frames"].append(float(_l["frames"]))
                _a["fps"].append(float(_l.get("fps") or 0))
        route = (r.get("rt") or "std-editorial")
        b = by_route.setdefault(route, {"jobs": 0, "users": set(), "legs": [],
                                        "offthread": {}, "concurrency": {},
                                        "total_s": [], "render_s": [],
                                        "norm_s": [], "by_ot": {}, "spans": {}})
        b["jobs"] += 1
        b["users"].add(r.get("user_id"))
        b["legs"].append(legs)
        for v in (ot or []):
            b["offthread"][str(v)] = b["offthread"].get(str(v), 0) + 1
            seen_vals[str(v)] = seen_vals.get(str(v), 0) + 1
        for v in (cc or []):
            b["concurrency"][str(v)] = b["concurrency"].get(str(v), 0) + 1
        if isinstance(st.get("total"), (int, float)):
            b["total_s"].append(float(st["total"]))
        # FLAT KEYS, not timeline children. The first cut of this read looked in
        # timeline["render"] and returned n=0 — a WRONG READER reporting a
        # confident absence. Caught by probing the shape instead of believing it.
        if isinstance(st.get("render"), (int, float)):
            b["render_s"].append(float(st["render"]))
        if isinstance(st.get("normalize_transcribe_upload"), (int, float)):
            b["norm_s"].append(float(st["normalize_transcribe_upload"]))
        # PER-VALUE, so render time can be cut by the offthread value in force.
        _k = ",".join(str(v) for v in (ot or []))
        b["by_ot"].setdefault(_k, []).append(float(st.get("render") or 0) or None)
        # What does the render span actually contain? Item (2)'s question, for
        # normalize_transcribe_upload, asked of the timeline tree.
        def _walk(n, depth=0):
            if not isinstance(n, dict):
                return
            nm, du = n.get("name"), n.get("dur")
            if nm and isinstance(du, (int, float)):
                b["spans"][nm] = b["spans"].get(nm, [])
                b["spans"][nm].append(float(du))
            for c in (n.get("children") or []):
                _walk(c, depth + 1)
        _walk(st.get("timeline") or {})

    out = {}
    for route, b in by_route.items():
        out[route] = {
            "jobs": b["jobs"], "users": len(b["users"]),
            "offthread_values": b["offthread"],
            "concurrency_values": b["concurrency"],
            "median_legs_reporting": _pct(b["legs"], .5),
            "total_s_p50": _pct(b["total_s"], .5), "total_s_p90": _pct(b["total_s"], .9),
            "render_s_p50": _pct(b["render_s"], .5), "render_s_p90": _pct(b["render_s"], .9),
            "n_render_timed": len(b["render_s"]),
            "norm_s_p50": _pct(b["norm_s"], .5), "norm_s_p90": _pct(b["norm_s"], .9),
            "n_norm_timed": len(b["norm_s"]),
            "render_s_p50_by_offthread": {k: _pct([x for x in v if x], .5)
                                          for k, v in b["by_ot"].items()},
            "render_n_by_offthread": {k: len([x for x in v if x]) for k, v in b["by_ot"].items()},
            "timeline_spans_p50": dict(sorted(
                ((k, _pct(v, .5)) for k, v in b["spans"].items()),
                key=lambda kv: -(kv[1] or 0))),
            "n_spans_seen": len(b["spans"]),
        }
    return {"window_since": since or "all", "rows_scanned": len(rows),
            "excluded_pre_v574_no_field": no_field,
            "render_leg_unmeasured": unmeasured,
            "offthread_values_seen": seen_vals, "shape": shape,
            "by_route": out,
            "by_arm": {k: {"jobs": v["jobs"], "users": len(v["users"]),
                           "render_s_p50": _pct(v["render_s"], .5),
                           "legs_with_stats": v["legs"],
                           "frames_p50": _pct(v["frames"], .5),
                           "fps_p50": _pct(v["fps"], .5)}
                       for k, v in arms.items()}}


@app.local_entrypoint()
def main(since: str = "", limit: int = 4000):
    r = query.remote(since=since, limit=limit)
    print(json.dumps(r, indent=1))
    if r.get("error"):
        print(f"\n  ❌ {r['error']}")
        sys.exit(1)
    seen = r.get("offthread_values_seen") or {}
    print(f"\n  window {r['window_since']}   scanned {r['rows_scanned']}   "
          f"pre-v574 {r['excluded_pre_v574_no_field']}   "
          f"render-leg UNMEASURED {r['render_leg_unmeasured']}")
    if not seen:
        print("\n  NO VALUE OBSERVED. This is an EMPTY READ, not 'the lever is off'.")
        print("  Either no job has rendered on v574+ or no leg reported a value.")
        sys.exit(2)
    print(f"\n  offthreadVideoThreads observed across all routes: {seen}")
    print("  (2 = Remotion's default => the lever is NOT in force)")
    ba = r.get("by_arm") or {}
    print(f"\n  ── OFFTHREAD ARM ('2' = pinned to Remotion default, 'None' = control)")
    print(f"  {'arm':>6} {'jobs':>5} {'users':>6} {'render_p50':>11} {'legs':>5} "
          f"{'frames_p50':>11} {'fps_p50':>8}")
    for a, v in sorted(ba.items()):
        print(f"  {a:>6} {v['jobs']:>5} {v['users']:>6} {str(v['render_s_p50']):>11} "
              f"{v['legs_with_stats']:>5} {str(v['frames_p50']):>11} {str(v['fps_p50']):>8}")
    if len(ba) < 2:
        print("  ONE ARM ONLY — not a comparison. Needs post-v577 traffic.")
    _anylegs = sum(v['legs_with_stats'] for v in ba.values())
    if not _anylegs:
        print("  NO LEGSTAT YET — empty read, not 'the renderer reported nothing'.")
    for route, b in sorted(r["by_route"].items()):
        print(f"\n  ── {route}: {b['jobs']} jobs / {b['users']} users")
        print(f"     offthread {b['offthread_values']}   concurrency {b['concurrency_values']}")
        print(f"     total p50 {b['total_s_p50']}s p90 {b['total_s_p90']}s")
        print(f"     render p50 {b['render_s_p50']}s p90 {b['render_s_p90']}s "
              f"(n={b['n_render_timed']})")
        print(f"     normalize_transcribe_upload p50 {b['norm_s_p50']}s "
              f"p90 {b['norm_s_p90']}s (n={b['n_norm_timed']})")
        print(f"     render p50 BY offthread value: {b['render_s_p50_by_offthread']}")
        print(f"                            n each: {b['render_n_by_offthread']}")
        print(f"     top timeline spans p50: {b['timeline_spans_p50']}")
