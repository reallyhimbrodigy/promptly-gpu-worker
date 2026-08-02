"""SILENT-FAILURE DETECTOR — `completed AND events == 0` (Zac 2026-08-02).

THE CLASS THIS EXISTS FOR
  `minimal_speech_uncut` jobs COMPLETE. Status success, no error_code, no refund
  trigger, no alert — and the user gets her own clip back uncut with no captions
  (handler.py: "speech present but could not be fully transcribed — clip
  delivered complete/uncut, no captions" / "no editorial plan on this route").
  A job that succeeds and delivers NOTHING is invisible to error-rate monitoring
  BY CONSTRUCTION. That is how 195 accumulated unnoticed. This is the check that
  makes the class visible.

DESIGN NOTE THAT MATTERS — DO NOT COUNT VIA `cuts`
  The obvious implementation (sum `edit_recipe.cuts`, divide by duration) is
  BLIND to the exact failure it is hunting: caption-less recipes are
  `{route, reason, plan}` with NO `cuts` key at all, so every silent job would be
  silently skipped rather than flagged. Both recipe shapes are counted here:
    standard     -> cuts + zooms + MGs + caption emphases + transitions + overlays
    caption-less -> the HypePlan's clips + transitions
  and the CLIP COUNT is tracked separately from editorial work, because one
  uncut clip is a passthrough, not an edit.
  A job that yields no countable events under EITHER shape is the signal.

CUTS (Rule 5 + Rule 7)
  By ROUTE, because a caption-less route delivering little is a different
  product fact from standard-editorial delivering nothing.
  By USER, and the USER COUNT LEADS: five failures from one person who gave up
  is one lost user, not five failures.

COST: one CPU-only debian_slim container, no GPU / Gemini / render. ~$0.01.
Append to MODAL_SPEND_LEDGER.md before running (Rule 8).

    modal run query_silent_failures_app.py            # last 24h
    modal run query_silent_failures_app.py --hours 168
"""
import os
from collections import Counter, defaultdict

import modal

app = modal.App("query-silent-failures")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# WHY A BARE `events == 0` TEST DOES NOT WORK (found on the first live run):
# an uncut passthrough delivers ONE clip. That clip counts as an event, so the
# job scores 1 and escapes a `== 0` test — the detector reported 0 silent
# failures on a day when 82 of 180 completions were minimal_speech_uncut, the
# exact class it was built for. Second blindness, same shape as the first.
#
# The honest predicate separates the CLIP LIST from EDITORIAL WORK:
#   silent  iff  editorial_events == 0  AND  clips <= 1
# A standard job with 8 cuts and nothing else is NOT silent — the cutting IS the
# edit. A single clip spanning the source with no captions, no zooms, no
# transitions IS the source handed back, whatever the route calls itself.
SILENT_THRESHOLD = 0


def count_events(rec):
    """(clips, editorial_events) across BOTH recipe shapes. None = unreadable."""
    if not isinstance(rec, dict):
        return None
    n = 0
    clips = len(rec.get("cuts") or rec.get("clips") or [])
    for em in (rec.get("emphasis_moments") or []):
        if not isinstance(em, dict):
            continue
        if (em.get("zoom_effect") or {}).get("type"):
            n += 1
        if em.get("motion_graphic"):
            n += 1
    n += len(rec.get("motion_graphics") or [])
    n += len(rec.get("caption_keywords") or [])
    n += len(rec.get("transitions") or [])
    n += len(rec.get("tight_cut_overlays") or [])
    n += len(rec.get("text_overlays") or [])
    n += len(rec.get("broll_clips") or [])
    # ── caption-less shape: {route, reason, plan} where plan is a HypePlan ──
    plan = rec.get("plan")
    if isinstance(plan, dict):
        clips += len(plan.get("clips") or [])
        n += len(plan.get("transitions") or [])
    return clips, n


@app.function(image=image, secrets=SECRETS, timeout=900)
def query(hours: int = 24) -> dict:
    from datetime import datetime, timedelta, timezone
    from supabase import create_client

    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY"))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    per_route = defaultdict(lambda: {"done": 0, "silent": 0})
    per_user = defaultdict(lambda: {"done": 0, "silent": 0})
    silent_rows, unreadable = [], 0

    for off in range(0, 20000, 1000):
        try:
            r = (sb.table("video_jobs")
                 .select("id,user_id,status,created_at,result")
                 .gte("created_at", since)
                 .range(off, off + 999).execute())
        except Exception as e:  # noqa: BLE001
            print(f"[query] page {off} failed: {e}", flush=True)
            break
        rows = r.data or []
        if not rows:
            break
        for row in rows:
            if str(row.get("status") or "").lower() not in ("completed", "complete", "success"):
                continue
            res = row.get("result")
            if not isinstance(res, dict):
                continue
            # route: only the caption-less routes stamp result.route; absent =
            # standard editorial (verified in handler.py — the standard payload
            # carries no route key).
            route = res.get("route") or "standard"
            _r = count_events(res.get("edit_recipe"))
            if _r is None:
                unreadable += 1
                continue
            clips, n = _r
            uid = row.get("user_id") or "?"
            per_route[route]["done"] += 1
            per_user[uid]["done"] += 1
            if n <= SILENT_THRESHOLD and clips <= 1:
                per_route[route]["silent"] += 1
                per_user[uid]["silent"] += 1
                silent_rows.append({"job": row.get("id"), "user": uid, "route": route,
                                    "at": row.get("created_at")})
    return {"hours": hours, "unreadable": unreadable,
            "per_route": {k: dict(v) for k, v in per_route.items()},
            "per_user": {k: dict(v) for k, v in per_user.items()},
            "silent_rows": silent_rows[:200]}


@app.local_entrypoint()
def main(hours: int = 24):
    d = query.remote(hours)
    pr, pu = d["per_route"], d["per_user"]
    done = sum(v["done"] for v in pr.values())
    silent = sum(v["silent"] for v in pr.values())
    users_any = [u for u, v in pu.items() if v["silent"] > 0]
    users_all = [u for u, v in pu.items() if v["done"] and v["silent"] == v["done"]]

    # ── the one line for the daily report ────────────────────────────────
    print(f"\n[SILENT] {len(users_all)} users got NOTHING on every attempt "
          f"({len(users_any)} users hit it at least once) | "
          f"{silent}/{done} completed jobs delivered 0 events | last {d['hours']}h")

    print("\nBY USER (Rule 7 — the user count leads; a user who fails five times "
          "and gives up is ONE lost user, not five failures)")
    print(f"  users with a completed job      : {len(pu):>5}")
    print(f"  users hit at least once         : {len(users_any):>5} "
          f"({100.0*len(users_any)/max(1,len(pu)):.1f}%)")
    print(f"  users who NEVER got a real edit : {len(users_all):>5} "
          f"({100.0*len(users_all)/max(1,len(pu)):.1f}%)  <- these are lost users")

    print("\nBY ROUTE (Rule 5 — a caption-less route delivering little is a "
          "different product fact from standard delivering nothing)")
    print(f"  {'route':<24} {'silent':>7} {'done':>7} {'rate':>7}")
    for route, v in sorted(pr.items(), key=lambda kv: -kv[1]["silent"]):
        rate = 100.0 * v["silent"] / max(1, v["done"])
        flag = "  <-- SILENT FAILURE CLASS" if rate >= 50 and v["silent"] else ""
        print(f"  {route[:23]:<24} {v['silent']:>7,} {v['done']:>7,} {rate:>6.1f}%{flag}")

    if d["unreadable"]:
        print(f"\n  ({d['unreadable']} completed jobs had an unreadable recipe — "
              f"not counted either way)")
    worst = sorted(((v["silent"], u) for u, v in pu.items() if v["silent"] > 1), reverse=True)[:10]
    if worst:
        print("\nMOST-AFFECTED USERS (retry count is the give-up signal):")
        for cnt, u in worst:
            print(f"  {u}  {cnt} silent of {pu[u]['done']} completed")


# ── self-test: the counter must see BOTH shapes, or it is blind to the class ──
if __name__ == "__main__":
    std_ok = {"cuts": [{}, {}], "emphasis_moments": [{"zoom_effect": {"type": "SmoothPush"}}],
              "caption_keywords": ["a"]}
    capless_silent = {"route": "minimal_speech_uncut", "reason": "x", "plan": {"clips": []}}
    capless_ok = {"route": "hype", "reason": "x",
                  "plan": {"clips": [{}, {}], "transitions": [{}]}}
    passthrough = {"route": "minimal_speech_uncut", "reason": "x",
                   "plan": {"clips": [{"start": 0, "end": 41.2}], "transitions": []}}
    cuts_only = {"cuts": [{}, {}, {}, {}, {}, {}, {}, {}]}
    cases = [("standard with events", std_ok, (2, 2)),
             ("caption-less, no clips at all", capless_silent, (0, 0)),
             ("caption-less ONE UNCUT CLIP <- the class", passthrough, (1, 0)),
             ("caption-less hype with clips", capless_ok, (2, 1)),
             ("standard, 8 cuts and nothing else", cuts_only, (8, 0)),
             ("empty recipe", {}, (0, 0)),
             ("unreadable", None, None)]
    bad = 0
    for name, rec, want in cases:
        got = count_events(rec)
        ok = got == want
        bad += not ok
        verdict = ""
        if got and got is not None:
            verdict = "  -> SILENT" if (got[1] <= 0 and got[0] <= 1) else "  -> ok"
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<40} (clips,editorial)={got}{verdict}")
    print(f"\n{'SELF-TEST OK' if not bad else f'{bad} FAILED'} — one uncut clip now reads SILENT; "
          f"8 cuts with no decoration does NOT")
