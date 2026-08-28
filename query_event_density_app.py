"""LANE 4 — EVENTS PER WINDOW, WHERE EVENTS EXIST ($0, one CPU container).

THE QUESTION THE MEAN CANNOT ANSWER. Density is reported as 7.76 events/25s
against Zac's 16.7 reference, and the doctrine caps "at most one dominant event"
per ~2s window — a CEILING of 12.5/25s, which already makes 16.7 unreachable.
But 7.76 is well UNDER that ceiling, so the cap cannot be the only governor.

A mean over all windows cannot separate the two candidate shapes:

  A. events are SPREAD THIN — most windows hold exactly 1, and the cap binds.
     Deleting the cap raises density toward 12.5.
  B. events are CLUMPED — the windows that have events often hold 1, but MANY
     WINDOWS HOLD ZERO. Then the cap never binds and the brake is elsewhere;
     deleting it changes nothing and the arm is wasted spend.

So: the distribution of events per window WHERE EVENTS EXIST, plus the share of
windows that are empty. That is the read that decides whether the delete-test is
worth firing at all — cheaper than the arm, and it can refute it.

Cut by FAMILY (emphasis / MG / overlay / transition / SFX), because a blended
event count hides which family the governor actually binds.
"""
import json
import os
import sys

import modal

app = modal.App("query-event-density")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

WINDOW_S = 2.0

# Where each family's events carry their timestamp in the stored recipe.
FAMILIES = {
    "emphasis":   ("emphasis_moments", ("start_s", "t", "time_s", "start")),
    "mg":         ("motion_graphics", ("start_s", "t", "time_s", "start")),
    "overlay":    ("text_overlays", ("start_s", "t", "time_s", "start")),
    "transition": ("transitions", ("at_s", "start_s", "t", "time_s")),
    "broll":      ("broll_clips", ("start_s", "t", "time_s", "start")),
}


def _ts(ev, keys):
    if not isinstance(ev, dict):
        return None
    for k in keys:
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


@app.function(image=image, secrets=SECRETS, timeout=600)
def query(since: str = "", limit: int = 4000) -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    if not (url and key):
        return {"error": "NO CREDENTIALS — a FAILED READ, not an empty result"}
    sb = create_client(url, key)

    rows, PAGE = [], 500
    for off in range(0, max(PAGE, limit), PAGE):
        q = (sb.table("video_jobs")
             .select("id, edit_recipe, st:result->stage_timings")
             .eq("status", "completed")
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

    shape = {"recipe_keys": None, "sample_event": None, "list_fields": None}
    jobs = 0
    win_counts = {}          # events-per-window histogram, occupied windows only
    empty_windows = 0
    total_windows = 0
    fam_events = {k: 0 for k in FAMILIES}
    fam_jobs = {k: 0 for k in FAMILIES}
    dur_total = 0.0
    no_recipe = 0

    for r in rows:
        rec = r.get("edit_recipe")
        if not isinstance(rec, dict):
            no_recipe += 1
            continue
        # THE EVENTS ARE NESTED. edit_recipe is {plan, reason, route}; the
        # component arrays live under `plan`. Reading the top level returned
        # 0.0 events/25s across 1,061 jobs and 100% empty windows — a confident
        # zero from a WRONG READER, which would have "refuted" the density cap
        # on evidence that was never measured. Probing the shape is what caught
        # it; the zero itself looked like a clean result.
        if isinstance(rec.get("plan"), dict):
            rec = rec["plan"]
        st = r.get("st") or {}
        dur = st.get("source_duration_s") if isinstance(st, dict) else None
        # OUTPUT duration is what density is measured against; fall back to
        # source only when absent, and say which was used.
        out_s = None
        for k in ("output_duration_s", "duration_s", "total"):
            if isinstance(st, dict) and isinstance(st.get(k), (int, float)):
                out_s = float(st[k]); break
        span = out_s or (float(dur) if isinstance(dur, (int, float)) else None)
        if not span or span <= 0:
            continue
        if shape["recipe_keys"] is None:
            shape["recipe_keys"] = sorted(rec.keys())[:40]
            _lf = {k: len(v) for k, v in rec.items() if isinstance(v, list) and v}
            shape["list_fields"] = _lf
            for k, v in rec.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    shape["sample_event"] = {k: sorted(v[0].keys())[:14]}
                    break
        jobs += 1
        dur_total += span
        buckets = {}
        for fam, (field, keys) in FAMILIES.items():
            evs = rec.get(field) or []
            if not isinstance(evs, list):
                continue
            n = 0
            for ev in evs:
                t = _ts(ev, keys)
                if t is None:
                    continue
                buckets[int(t // WINDOW_S)] = buckets.get(int(t // WINDOW_S), 0) + 1
                n += 1
            fam_events[fam] += n
            if n:
                fam_jobs[fam] += 1
        nwin = max(1, int(span // WINDOW_S))
        total_windows += nwin
        occupied = len(buckets)
        empty_windows += max(0, nwin - occupied)
        for _w, c in buckets.items():
            win_counts[c] = win_counts.get(c, 0) + 1

    per25 = {k: round(v / dur_total * 25.0, 2) if dur_total else None
             for k, v in fam_events.items()}
    total_ev = sum(fam_events.values())
    return {
        "window_since": since or "all", "rows_scanned": len(rows),
        "jobs_measured": jobs, "no_recipe": no_recipe,
        "total_output_s": round(dur_total, 1),
        "events_per_25s_total": round(total_ev / dur_total * 25.0, 2) if dur_total else None,
        "events_per_25s_by_family": per25,
        "family_event_counts": fam_events,
        "jobs_with_family": fam_jobs,
        "windows_total": total_windows,
        "windows_empty": empty_windows,
        "empty_window_share": round(empty_windows / total_windows, 3) if total_windows else None,
        "events_per_OCCUPIED_window": dict(sorted(win_counts.items())), "shape": shape,
    }


@app.local_entrypoint()
def main(since: str = "", limit: int = 4000):
    r = query.remote(since=since, limit=limit)
    if r.get("error"):
        print(f"  ❌ {r['error']}"); sys.exit(1)
    print(json.dumps(r, indent=1)[:1800])
    if not r.get("jobs_measured"):
        print("\n  NO JOB MEASURED — an EMPTY READ, not a density of zero.")
        sys.exit(2)
    print(f"\n  jobs {r['jobs_measured']}   output {r['total_output_s']}s   "
          f"no_recipe {r['no_recipe']}")
    print(f"  events/25s TOTAL: {r['events_per_25s_total']}   "
          f"(Zac reference 16.7, cap ceiling 12.5)")
    print(f"\n  by family (events/25s): {r['events_per_25s_by_family']}")
    print(f"\n  windows {r['windows_total']}   EMPTY {r['windows_empty']} "
          f"({100*(r['empty_window_share'] or 0):.1f}%)")
    print(f"  events per OCCUPIED window: {r['events_per_OCCUPIED_window']}")
    occ = r["events_per_OCCUPIED_window"]
    multi = sum(v for k, v in occ.items() if int(k) > 1)
    one = occ.get(1, 0) or occ.get("1", 0)
    print(f"\n  windows holding >1 event: {multi}   holding exactly 1: {one}")
    if r["empty_window_share"] and r["empty_window_share"] > 0.5:
        print("\n  => SHAPE B: most windows are EMPTY. The 'one dominant event per")
        print("     window' cap is NOT binding — it cannot be what holds density")
        print("     down, and the delete-test would change nothing. Look elsewhere.")
    elif multi == 0:
        print("\n  => SHAPE A: no window ever holds >1. The cap IS binding exactly")
        print("     as written; the delete-test is the right next spend.")
    else:
        print("\n  => MIXED: windows DO exceed 1, so the cap is already being")
        print("     violated or does not mean what the arithmetic assumed. Read the")
        print("     rule again before spending on an arm.")
