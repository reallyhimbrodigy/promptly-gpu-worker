"""COMPONENT USAGE AUDIT (Zac 2026-08-01): does the catalogue actually TEACH SELECTION?

82% of the cached prefix is reference data whose whole job is making component
choice unmistakable. This measures whether it works, on real stored plans:

  • NEVER FIRES  -> badly described, or unnecessary. An unused component is a
                   REAL deletion: its catalogue entry, its Props line, and its
                   enum slot all go. This is the deletion lever Zac asked for,
                   and unlike compression it is not capped at 1.29x.
  • OVER-FIRES   -> vague or overlapping FITS/FIGHTS. The prompt is failing to
                   discriminate it from its neighbours.

Expected vocabularies are DERIVED from type_registries.py (hand-written counts
are gate-banned), so a component added tomorrow shows up here as never-fired
instead of being silently absent from the audit.

Reads video_jobs.result.edit_recipe. CPU-only debian_slim container, no GPU, no
Gemini, no render. COST: one CPU container for <10 min ~= $0.01.
"""
import os
import sys
from collections import Counter

import modal

app = modal.App("query-component-usage")
image = (modal.Image.debian_slim()
         .pip_install("supabase")
         .add_local_file("type_registries.py", "/type_registries.py"))
SECRETS = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=SECRETS, timeout=900)
def query() -> dict:
    sys.path.insert(0, "/")
    import type_registries as TR
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    sb = create_client(url, key)

    mg, cap, zoom, sfx, trans, tco, ovl = (Counter() for _ in range(7))
    n_recipes = 0
    n_rows = 0
    # EVENTS/25s (Zac 2026-08-01): the pace metric — cuts + zooms + MGs +
    # caption emphases + transitions, all counted, per 25s of OUTPUT. Target
    # ~16-25. Reported per route so a light route cannot mask the product.
    ev_rows = []
    recipe_keys = Counter()
    # per-recipe presence, so we can report "of N plans, X used this"
    mg_plans, sfx_plans = Counter(), Counter()

    for off in range(0, 12000, 1000):
        try:
            r = (sb.table("video_jobs").select("result")
                 .not_.is_("result", "null")
                 .range(off, off + 999).execute())
        except Exception as e:  # noqa: BLE001
            print(f"[query] page {off} failed: {e}", flush=True)
            break
        rows = r.data or []
        if not rows:
            break
        n_rows += len(rows)
        for row in rows:
            res = row.get("result")
            if not isinstance(res, dict):
                continue
            rec = res.get("edit_recipe")
            if not isinstance(rec, dict):
                continue
            n_recipes += 1

            seen_mg, seen_sfx = set(), set()
            for m in (rec.get("motion_graphics") or []):
                if isinstance(m, dict) and m.get("type"):
                    mg[m["type"]] += 1
                    seen_mg.add(m["type"])
            # MGs also ride inside emphasis_moments
            for em in (rec.get("emphasis_moments") or []):
                if not isinstance(em, dict):
                    continue
                g = em.get("motion_graphic")
                if isinstance(g, dict) and g.get("type"):
                    mg[g["type"]] += 1
                    seen_mg.add(g["type"])
                z = em.get("zoom_effect")
                if isinstance(z, dict) and z.get("type"):
                    zoom[z["type"]] += 1
                s = em.get("sound")
                if s:
                    sfx[s] += 1
                    seen_sfx.add(s)
            for t in (rec.get("transitions") or []):
                if isinstance(t, dict) and t.get("type"):
                    trans[t["type"]] += 1
            for t in (rec.get("tight_cut_overlays") or []):
                if isinstance(t, dict) and t.get("type"):
                    tco[t["type"]] += 1
            for o in (rec.get("text_overlays") or []):
                if isinstance(o, dict):
                    ovl[o.get("variant") or o.get("type") or "?"] += 1
            for s in (rec.get("sound_effects") or []):
                if isinstance(s, dict) and s.get("sound"):
                    sfx[s["sound"]] += 1
                    seen_sfx.add(s["sound"])
            for k in rec.keys():
                recipe_keys[k] += 1
            # duration of the OUTPUT, not the source
            dur = None
            for src_key in ("output_duration_s", "final_duration_s", "duration_s",
                            "total_duration_s"):
                v = res.get(src_key) or rec.get(src_key)
                if isinstance(v, (int, float)) and v > 0:
                    dur = float(v); break
            if dur is None:
                cl = rec.get("cuts") or rec.get("clips") or []
                if isinstance(cl, list) and cl:
                    tot = 0.0
                    for c in cl:
                        if isinstance(c, dict):
                            s = c.get("start", c.get("source_start", c.get("start_time")))
                            e = c.get("end", c.get("source_end", c.get("end_time")))
                            if isinstance(s, (int, float)) and isinstance(e, (int, float)) and e > s:
                                tot += (e - s)
                    dur = tot or None
            n_cuts = len(rec.get("cuts") or rec.get("clips") or []) or None
            if dur and dur > 0:
                n_ev = ((n_cuts or 0)
                        + sum(1 for m in (rec.get("emphasis_moments") or [])
                              if isinstance(m, dict) and (m.get("zoom_effect") or {}).get("type"))
                        + len(rec.get("motion_graphics") or [])
                        + sum(1 for m in (rec.get("emphasis_moments") or [])
                              if isinstance(m, dict) and m.get("motion_graphic"))
                        + len(rec.get("caption_keywords") or [])
                        + len(rec.get("transitions") or [])
                        + len(rec.get("tight_cut_overlays") or []))
                # DENOMINATOR VALIDATION (Rule 5): an events/25s figure is only
                # as good as the duration under it. Record how many cuts actually
                # yielded parseable bounds, plus the source duration, so an
                # under-counted denominator shows up as inflation instead of
                # being reported as pace.
                _parsed = 0
                for c in (cl if isinstance(cl, list) else []):
                    if isinstance(c, dict):
                        _s = c.get("start", c.get("source_start", c.get("start_time")))
                        _e = c.get("end", c.get("source_end", c.get("end_time")))
                        if isinstance(_s, (int, float)) and isinstance(_e, (int, float)) and _e > _s:
                            _parsed += 1
                ev_rows.append({"route": res.get("route") or "standard",
                                "dur": dur, "ev": n_ev,
                                "n_cuts": n_cuts or 0, "parsed_cuts": _parsed,
                                "src_dur": res.get("source_duration_s"),
                                "per25": round(25.0 * n_ev / dur, 2)})
            cs = rec.get("caption_style")
            if cs:
                cap[cs] += 1
            for t in seen_mg:
                mg_plans[t] += 1
            for t in seen_sfx:
                sfx_plans[t] += 1

    return {
        "n_rows": n_rows, "n_recipes": n_recipes,
        "mg": dict(mg), "mg_plans": dict(mg_plans),
        "caption": dict(cap), "zoom": dict(zoom),
        "sfx": dict(sfx), "sfx_plans": dict(sfx_plans),
        "transitions": dict(trans), "tight_cut_overlays": dict(tco),
        "overlays": dict(ovl),
        "events": ev_rows, "recipe_keys": dict(recipe_keys.most_common(30)),
        "registry": {
            "mg": sorted(TR.VALID_MG_TYPES),
            "caption": sorted(TR.VALID_CAPTION_STYLES),
            "zoom": sorted(TR.VALID_ZOOM_TYPES),
            "transitions": sorted(TR.VALID_TRANSITION_TYPES),
            "tight_cut_overlays": sorted(TR.VALID_TIGHT_CUT_OVERLAYS),
        },
    }


def _report(fam, used, registry, n, plans=None):
    print(f"\n=== {fam}  (registry = {len(registry)} types; {n:,} plans) ===")
    total = sum(used.get(t, 0) for t in registry)
    never = [t for t in registry if not used.get(t)]
    for t in sorted(registry, key=lambda x: -used.get(x, 0)):
        c = used.get(t, 0)
        share = (100.0 * c / total) if total else 0.0
        pl = f"  in {plans.get(t,0):>4} plans ({100.0*plans.get(t,0)/max(1,n):>4.1f}%)" if plans else ""
        flag = "   <-- NEVER FIRES" if c == 0 else ("   <-- dominates" if share >= 35 else "")
        print(f"  {t:<22} {c:>6,}  {share:>5.1f}%{pl}{flag}")
    off_registry = {k: v for k, v in used.items() if k not in registry}
    if off_registry:
        print(f"  OFF-REGISTRY EMITTED: {off_registry}")
    print(f"  never fires: {len(never)}/{len(registry)}  {never}")


@app.local_entrypoint()
def main():
    d = query.remote()
    print(f"\nCOMPONENT USAGE AUDIT — {d['n_recipes']:,} stored edit_recipes "
          f"of {d['n_rows']:,} job rows scanned")
    R = d["registry"]
    _report("MOTION GRAPHICS", d["mg"], R["mg"], d["n_recipes"], d["mg_plans"])
    _report("ZOOM", d["zoom"], R["zoom"], d["n_recipes"])
    _report("CAPTION STYLE", d["caption"], R["caption"], d["n_recipes"])
    _report("TRANSITIONS", d["transitions"], R["transitions"], d["n_recipes"])
    _report("TIGHT-CUT OVERLAYS", d["tight_cut_overlays"], R["tight_cut_overlays"], d["n_recipes"])
    print(f"\n=== SOUND EFFECTS (no registry export; observed) ===")
    tot = sum(d["sfx"].values())
    for k, v in sorted(d["sfx"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<22} {v:>6,}  {100.0*v/max(1,tot):>5.1f}%")
    print(f"\n=== TEXT OVERLAY VARIANTS (observed) ===")
    for k, v in sorted(d["overlays"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<22} {v:>6,}")

    ev = d.get("events") or []
    print(f"\n=== PACE — VISUAL EVENTS PER 25s (Zac's metric; target ~16-25) ===")
    if not ev:
        print("  NO DURATION FIELD FOUND on stored recipes — cannot compute.")
        print(f"  observed recipe keys: {list((d.get('recipe_keys') or {}).keys())[:24]}")
    else:
        import statistics as st
        by = {}
        for r in ev:
            by.setdefault(r["route"], []).append(r)
        print(f"  {'route':<16} {'n':>5} {'median':>8} {'mean':>7} {'p25':>7} {'p75':>7} {'med dur':>8}")
        for route, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
            v = sorted(x["per25"] for x in rs)
            q = lambda f: v[min(len(v) - 1, int(f * len(v)))]
            print(f"  {route[:15]:<16} {len(rs):>5} {st.median(v):>8.1f} "
                  f"{sum(v)/len(v):>7.1f} {q(0.25):>7.1f} {q(0.75):>7.1f} "
                  f"{st.median([x['dur'] for x in rs]):>8.1f}s")
        _full = [x for x in ev if x["n_cuts"] and x["parsed_cuts"] == x["n_cuts"]]
        _part = [x for x in ev if x["n_cuts"] and x["parsed_cuts"] < x["n_cuts"]]
        print(f"\n  DENOMINATOR VALIDATION:")
        print(f"    all cuts parsed : {len(_full):>4} plans"
              + (f"  median {st.median([x['per25'] for x in _full]):.1f} ev/25s"
                 f"  median dur {st.median([x['dur'] for x in _full]):.1f}s" if _full else ""))
        print(f"    SOME cuts lost  : {len(_part):>4} plans"
              + (f"  median {st.median([x['per25'] for x in _part]):.1f} ev/25s  <- INFLATED" if _part else ""))
        _sd = [x for x in ev if isinstance(x.get("src_dur"), (int, float)) and x["src_dur"] > 0]
        if _sd:
            print(f"    vs source_duration_s: median source {st.median([x['src_dur'] for x in _sd]):.1f}s, "
                  f"median output {st.median([x['dur'] for x in _sd]):.1f}s, "
                  f"keep-ratio {st.median([x['dur']/x['src_dur'] for x in _sd]):.2f}  (n={len(_sd)})")
        allv = sorted(x["per25"] for x in ev)
        print(f"  {'ALL':<16} {len(allv):>5} {st.median(allv):>8.1f} {sum(allv)/len(allv):>7.1f}")
        print(f"  -> at/above 16 events/25s: {100.0*sum(1 for x in allv if x>=16)/len(allv):.0f}% of plans")
