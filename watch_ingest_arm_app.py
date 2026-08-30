"""LANE 3 ARM WATCH — is the bundle actually running, and did completion move?

TWO QUESTIONS, and the first one is the one that gets skipped.

  1. IS IT ON? An armed flag proves nothing — the unread-flag false-green has
     happened here repeatedly (BOOLEAN preview column, unmounted moodreel_editor,
     _progressive_enabled reading a dark global). The OBSERVABLE is the pool
     task name: in-process jobs record four keys in stage_timings.pool_task_s
     (gemini_proxy / loudness / shot_changes / faces); a bundled job records ONE
     key, `ingest_bundle`, and NONE of the four. So the arm is readable off
     every organic job with no special logging, and "armed but still running
     in-process" is DISTINGUISHABLE from "armed and working" rather than being
     assumed away.

  2. DID COMPLETION MOVE? Pre-arm control: 88.4% (198/224) since 2026-08-29.
     ANY movement is the revert trigger. Reported per-JOB and per-USER, because
     per-job counting inflates every class by the retry multiplier — a user who
     fails five times is one lost user, not five failures.

CLEAN COHORT: the arm cut is a DEPLOY TIME, and every deploy orphans in-flight
jobs. Jobs created before the cut are excluded entirely rather than attributed
to the wrong arm.

  ./run_modal.sh watch_ingest_arm_app.py --cut 2026-08-30T20:07:00+00:00
"""
import os
from collections import Counter

import modal

app = modal.App("watch-ingest-arm")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

FOUR = ("gemini_proxy", "loudness", "shot_changes", "faces")
PRE_RATE, PRE_N, PRE_D = 88.4, 198, 224


@app.function(image=image, secrets=S, timeout=900)
def scan(cut: str) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 500
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,result,demo,created_at,error_message")
             .gte("created_at", cut).order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 10:
            break
    return [r for r in rows if not r.get("demo")]


@app.local_entrypoint()
def main(cut: str = "2026-08-30T20:07:00+00:00"):
    rows = scan.remote(cut)
    print(f"\n=== LANE 3 ARM WATCH — jobs created after {cut} ===")
    print(f"  {len(rows)} non-demo jobs in the post-arm cohort")
    if not rows:
        print("\n  NO TRAFFIC YET in this window. That is an ABSENT read, not a")
        print("  clean result — nothing can be concluded about the arm or about")
        print("  completion until organic jobs land. Re-run later.")
        return

    def st(r):
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        v = res.get("stage_timings")
        return v if isinstance(v, dict) else {}

    def pool(r):
        v = st(r).get("pool_task_s")
        return v if isinstance(v, dict) else {}

    done = [r for r in rows if str(r.get("status")) == "completed"]
    term = [r for r in rows if str(r.get("status")) in ("completed", "failed", "error")]

    # ── 1. IS IT ON? ───────────────────────────────────────────────────────
    bundled = [r for r in done if "ingest_bundle" in pool(r)]
    inproc = [r for r in done if any(k in pool(r) for k in FOUR)]
    both = [r for r in done if "ingest_bundle" in pool(r)
            and any(k in pool(r) for k in FOUR)]
    neither = [r for r in done if not pool(r)]
    print(f"\n  [1] IS THE BUNDLE ACTUALLY RUNNING?  (read off pool_task_s, "
          f"{len(done)} completions)")
    print(f"      bundled  (ingest_bundle key present) : {len(bundled)}")
    print(f"      in-proc  (any of the four present)   : {len(inproc)}")
    print(f"      BOTH (should be 0 — would mean the arm is partial): {len(both)}")
    print(f"      no pool_task_s at all (route-diverted / old): {len(neither)}")
    if bundled and not inproc:
        print("      ✅ ARM CONFIRMED — every completion ran the bundle path.")
    elif bundled and inproc:
        print("      ⚠️  MIXED — some jobs still in-process. Expected only if the "
              "cohort straddles the deploy; if it persists, the arm is partial.")
    elif inproc and not bundled:
        print("      ❌ ARMED BUT NOT RUNNING — the flag is set and the four "
              "tasks are STILL IN-PROCESS. This is the unread-flag false-green: "
              "a report of 'relocated' would have been wrong.")
    if bundled:
        w = [pool(r).get("ingest_bundle") for r in bundled]
        w = sorted(x for x in w if isinstance(x, (int, float)))
        if w:
            print(f"      bundle wall p50 {w[len(w)//2]:.1f}s  "
                  f"p90 {w[min(len(w)-1, int(len(w)*0.9))]:.1f}s  (n={len(w)})")

    # ── 2. DID COMPLETION MOVE? ────────────────────────────────────────────
    print(f"\n  [2] COMPLETION — the revert trigger")
    if len(term) < 30:
        print(f"      n={len(term)} terminal jobs is TOO THIN to compare against "
              f"{PRE_RATE}% ({PRE_N}/{PRE_D}). A small-sample zero or dip here is "
              f"noise, not a signal. Keep watching.")
    rate = 100.0 * len(done) / len(term) if term else 0.0
    print(f"      post-arm : {rate:.1f}% ({len(done)}/{len(term)})")
    print(f"      pre-arm  : {PRE_RATE}% ({PRE_N}/{PRE_D})")
    if term:
        delta = rate - PRE_RATE
        print(f"      delta    : {delta:+.1f} pts")

    # PER USER — a user who fails five times is one lost user, not five failures.
    fu = {r.get("user_id") for r in term if str(r.get("status")) != "completed"}
    au = {r.get("user_id") for r in term}
    print(f"      users     : {len(fu)} affected of {len(au)} in the cohort "
          f"({100.0*len(fu)/max(1,len(au)):.0f}%)")

    # ── 3. anything blaming the bundle ─────────────────────────────────────
    fails = [r for r in term if str(r.get("status")) != "completed"]
    if fails:
        print(f"\n  [3] FAILURES ({len(fails)}), and whether the bundle is named:")
        c = Counter()
        named = 0
        for r in fails:
            msg = str(r.get("error_message") or "")[:400]
            res = r.get("result") if isinstance(r.get("result"), dict) else {}
            blob = msg + " " + str(res.get("error_where") or "")[:300]
            if "ingest bundle" in blob.lower() or "ingest_bundle" in blob:
                named += 1
            c[(str(res.get("error_code") or "?"),
               str(res.get("error_subcode") or "?"))] += 1
        for (code, sub), n in c.most_common(8):
            print(f"        {n:>3}  {code}:{sub}")
        print(f"      failures that NAME the ingest bundle: {named}")
        if named:
            print("      ❌ the bundle is implicated — revert step 1 now.")
    else:
        print(f"\n  [3] no terminal failures in the cohort")

    print(f"\n  VERDICT INPUTS: arm_confirmed={bool(bundled and not inproc)}  "
          f"n_terminal={len(term)}  rate={rate:.1f}%")
    print(f"  Step 2 (cpu 16->8) needs BOTH: the arm confirmed on real traffic, "
          f"and completion not moved on a cohort big enough to see it.")
