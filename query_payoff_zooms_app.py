"""Q1(b) (Zac 2026-07-31): has a PUNCHY payoff zoom (SnapReframe/StepZoom/StagedPush)
EVER been emitted in production? The schema (ZOOM_ARC_HOMES['payoff'] =
LetterboxPush/SmoothPush) says no — this confirms empirically + rules out a bypass.
Reads video_jobs.result.edit_recipe.emphasis_moments, tallies the payoff zoom type
across the corpus. $0 read, pre-outage window. No render, no Gemini."""
import os, sys, json
import modal
from collections import Counter

app = modal.App("query-payoff-zooms")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]
SLOW = {"DepthPull", "LetterboxPush", "SmoothPush"}
PUNCHY = {"SnapReframe", "StepZoom", "StagedPush"}


@app.function(image=image, secrets=SECRETS, timeout=600)
def query() -> dict:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    sb = create_client(url, key)
    payoff_types = Counter()
    all_zoom_types = Counter()
    n_recipes = 0
    n_with_payoff = 0
    rows = 0
    for off in range(0, 8000, 1000):
        try:
            r = (sb.table("video_jobs").select("er:result->edit_recipe")
                 .lt("created_at", "2026-07-30").order("created_at", desc=True)
                 .range(off, off + 999).execute())
        except Exception:
            r = (sb.table("video_jobs").select("result")
                 .lt("created_at", "2026-07-30").order("created_at", desc=True)
                 .range(off, off + 999).execute())
        data = r.data or []
        if not data:
            break
        rows += len(data)
        for row in data:
            er = row.get("er")
            if er is None and isinstance(row.get("result"), dict):
                er = row["result"].get("edit_recipe")
            if not isinstance(er, dict):
                continue
            ems = er.get("emphasis_moments") or []
            if not isinstance(ems, list):
                continue
            n_recipes += 1
            had_payoff = False
            for em in ems:
                if not isinstance(em, dict):
                    continue
                ze = em.get("zoom_effect") or {}
                t = ze.get("type")
                if t:
                    all_zoom_types[t] += 1
                if ze.get("arc_position") == "payoff" and t:
                    payoff_types[t] += 1
                    had_payoff = True
            if had_payoff:
                n_with_payoff += 1
    punchy_payoffs = sum(payoff_types[t] for t in PUNCHY)
    slow_payoffs = sum(payoff_types[t] for t in SLOW)
    return {
        "rows_scanned": rows,
        "recipes_with_emphasis": n_recipes,
        "recipes_with_a_payoff_zoom": n_with_payoff,
        "payoff_zoom_type_distribution": dict(payoff_types),
        "payoff_PUNCHY_count": punchy_payoffs,
        "payoff_SLOW_count": slow_payoffs,
        "ALL_zoom_type_distribution": dict(all_zoom_types),
        "window": "created_at < 2026-07-30",
    }


@app.local_entrypoint()
def main():
    print("QUERY " + json.dumps(query.remote(), indent=2, default=str))
