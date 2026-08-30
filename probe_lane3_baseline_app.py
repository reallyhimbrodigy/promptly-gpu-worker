"""LANE 3 BASELINE — what is actually being relocated, and what does it cost today?

NOT a re-derivation of scope. The scope is settled: four closures, one unit,
cpu=8, before the plan. This measures the PRECONDITIONS and the BASELINE the
relocation will be judged against, because two of them change what the move is
worth and one of them can make it cost MORE:

  1. PROXY PATH MIX. _do_gemini_proxy_impl has THREE paths — client-provided
     proxy (download ~3-6MB), prewarm cache hit (Modal volume read), or a full
     480p encode. Only the third is real CPU. If the encode rarely fires, the
     "proxy encode" being relocated is mostly a download, and the S3 round trip
     the relocation adds is paid against a smaller saving.

  2. PREWARM HIT RATE. The cache lives on a Modal volume. The target function
     MUST mount it or every hit degrades into a re-encode — that would ADD cost.
     (Volume is mountable: modal_app.py mounts /prewarm on 9 functions already.)

  3. THE STAGE BASELINE the two verification checks compare against —
     per-stage wall for the four relocated tasks, and the completion rate that
     the 78.9%->35.7% crash shape would move.

Read from persisted stage_timings only. No renders, one CPU container.

  ./run_modal.sh probe_lane3_baseline_app.py --since 2026-08-28
"""
import os
import statistics as st
from collections import Counter

import modal

app = modal.App("probe-lane3-baseline")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

# The four relocated tasks, as named in _timings by _timed(...).
RELOCATED = ("gemini_proxy", "loudness", "shot_changes", "faces")
STAYING = ("vocal_emphasis", "shake_probe", "exposure_probe", "fps_normalize")


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 500
    while True:
        r = (sb.table("video_jobs")
             .select("id,status,result,demo,created_at")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 10:
            break
    return {"rows": [r for r in rows if not r.get("demo")], "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-28"):
    d = scan.remote(since)
    rows = d["rows"]

    def st_of(r):
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        v = res.get("stage_timings")
        return v if isinstance(v, dict) else {}

    def pool_of(r):
        # THE POOL TASKS LIVE IN stage_timings["pool_task_s"], NESTED — not as
        # top-level keys. Looking for stage_timings["gemini_proxy"] returned n=0
        # for all four relocated stages, which reads as "never persisted" and is
        # really "read the wrong key". A clean zero is guilty until proven.
        v = st_of(r).get("pool_task_s")
        return v if isinstance(v, dict) else {}

    done = [r for r in rows if str(r.get("status")) == "completed"]
    term = [r for r in rows if str(r.get("status")) in ("completed", "failed", "error")]
    print(f"\n=== LANE 3 BASELINE — since {d['since']} ===")
    print(f"  {len(rows)} jobs, {len(term)} terminal, {len(done)} completed")

    # ── 3. COMPLETION RATE — the revert trigger ─────────────────────────────
    if term:
        cr = 100.0 * len(done) / len(term)
        print(f"\n  [3] COMPLETION RATE (the revert trigger): {cr:.1f}% "
              f"({len(done)}/{len(term)})")
        print(f"      The v584-era crash shape was 78.9% -> 35.7%. ANY movement "
              f"after the relocation means immediate revert.")

    # ── 1/2. PROXY PATH MIX + PREWARM ───────────────────────────────────────
    pw = [st_of(r).get("prewarm") for r in done]
    pw = [p for p in pw if isinstance(p, dict)]
    print(f"\n  [1/2] PREWARM telemetry present on {len(pw)}/{len(done)} completions")
    if pw:
        keys = Counter()
        for p in pw:
            for k, v in p.items():
                keys[f"{k}={v}"] += 1
        for k, n in keys.most_common(10):
            print(f"      {n:>4}  {k}")
    else:
        print("      ABSENT — the proxy path mix cannot be read from the row.")
        print("      That is a MEASUREMENT GAP, not 'the encode never fires'.")

    # ── STAGE WALL for the relocated four vs the ones staying ───────────────
    print(f"\n  STAGE WALL (seconds, p50 across completions with the key):")
    print(f"      {'stage':>16} {'n':>5} {'p50':>7} {'p90':>7}   moves?")
    for stage in RELOCATED + STAYING:
        v = [pool_of(r).get(stage) for r in done]
        v = [x for x in v if isinstance(x, (int, float))]
        if not v:
            print(f"      {stage:>16} {0:>5} {'—':>7} {'—':>7}   "
                  f"{'RELOCATE' if stage in RELOCATED else 'stays'}")
            continue
        vs = sorted(v)
        p90 = vs[min(len(vs) - 1, int(len(vs) * 0.9))]
        print(f"      {stage:>16} {len(v):>5} {st.median(v):>7.1f} {p90:>7.1f}   "
              f"{'RELOCATE' if stage in RELOCATED else 'stays'}")

    _tot = [st_of(r).get("total") for r in done]
    _tot = [x for x in _tot if isinstance(x, (int, float))]
    if _tot:
        print(f"\n  job wall p50 {st.median(_tot):.1f}s — the ~450s figure the "
              f"41-53x is priced against is the PLANNER HOLD, not this.")
    print(f"\n  NOTE: a relocated stage's wall does not vanish — it moves to a "
          f"cpu=8 box and the planner stops holding cpu=16 for it. The saving is "
          f"CORE-SECONDS, not latency. Expect no p50 movement.")
