"""4/2/1 MICRO-CONCURRENCY SWEEP — ON THE BURST PATH. ~$1.50, 12 renders.

WHY THIS DISPATCHES INSTEAD OF IMPORTING. Every prior batch did
`import handler; handler.handler(...)` inside an ephemeral `modal run`, so
`_render_burst_enabled` was ALWAYS False (it is deployed-app-only) and every
number described the LOCAL path. Production bursts. This calls the DEPLOYED
`run_pipeline_bg` with `.remote()`, so the job takes the real path — burst
container, real concurrency, real contention.

THE QUESTION. Micro frames cost 775-1,797 ms/frame in production against
108-110 ms/frame measured ISOLATED at concurrency 1 (micro-seek-cost.mjs, which
also refuted decode-once-per-segment at ~1%). A 7-16x gap on the same primitive.
Hypothesis: CONTENTION — several Chromium pages behind one lazy Rust compositor.
Never tested on the path production uses.

CAPTURED PER ARM, all four in one run so no arm needs a second spend:
  ms/frame PER COMPOSITION — PromptlyMicroSegments vs PromptlyOverlay. The gap
      is on MICRO specifically (overlay measured 17-75 ms/frame, micro 775-1797
      on the same job), so a blended ms/frame would hide the whole effect.
  core count and concurrent page count — so contention is answerable from data
      rather than argument.
  cost per job — because a speed win that raises cost is a RULING, not a ship.

DECISION RULE, fixed before the run so it cannot be fitted after:
  lower concurrency wins on BOTH speed and cost -> ship flag-gated, byte-identity
      verified (renders are byte-deterministic on a fixed plan: pass/fail, not
      "within noise").
  it TRADES on either axis -> STOP and report. Zac's ruling, not an autonomous flip.

  ./run_modal.sh sweep_micro_concurrency_app.py                    # dry
  ./run_modal.sh sweep_micro_concurrency_app.py --no-dry --confirm-only
  ./run_modal.sh sweep_micro_concurrency_app.py --no-dry
"""
import json
import sys
import uuid

import modal

app = modal.App("sweep-micro-concurrency")

BUCKET = "thisismybucketagainwooo"
PREFIX = "batch-corpus"
# 59.5s owner-selected reference — long enough to clear the 45s burst floor
# (PROMPTLY_BURST_MIN_OUTPUT_S), which is what makes the job take the BURST path
# at all. A 20s source would silently stay local and measure the wrong thing.
CLIP = "v24044gl0000d2rj4k7og65tcgn43lr0.mp4"
ARMS = [4, 2, 1]


def _url(key):
    return f"https://{BUCKET}.s3.amazonaws.com/{key}"


def _dispatch(conc, rep):
    """One job through the DEPLOYED worker. Returns (call_id, body)."""
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    jid = str(uuid.uuid4())
    out = _url(f"{PREFIX}/_sweep/out_{conc}_{rep}_{jid[:8]}.mp4")
    body = {"job_id": jid, "video_url": _url(f"{PREFIX}/{CLIP}"), "vibe": "viral",
            "user_id": str(uuid.uuid4()), "upload_url": out, "public_url": out,
            "micro_concurrency_test": str(conc)}
    return fn.spawn(body).object_id, body


@app.local_entrypoint()
def main(dry: bool = True, confirm_only: bool = False, repeats: int = 2):
    cells = [(c, r) for c in ARMS for r in range(repeats)]
    if confirm_only:
        cells = [(4, 0)]
    print(f"  PLAN: {'CONFIRMATION (1 job)' if confirm_only else f'{len(ARMS)} arms x {repeats} reps'}"
          f" = {len(cells)} renders on the DEPLOYED worker (burst path)")
    print(f"  source: {CLIP} (59.5s — above the 45s burst floor, so it BURSTS)")
    print(f"  arms: {ARMS}   priced ~$0.10-0.13 each -> ~${0.10*len(cells):.2f}-${0.13*len(cells):.2f}")
    if dry:
        print("\n  DRY RUN — nothing dispatched. Pass --no-dry to fire.")
        return

    ids = []
    for (c, r) in cells:
        cid, _ = _dispatch(c, r)
        ids.append({"conc": c, "rep": r, "call_id": cid})
        print(f"  → conc={c} r{r}  {cid}")
    with open("/tmp/sweep_ids.json", "w") as fh:
        json.dump(ids, fh, indent=1)
    print(f"\n  call ids -> /tmp/sweep_ids.json (recoverable if this process dies)")

    rows = []
    for it in ids:
        try:
            res = modal.FunctionCall.from_id(it["call_id"]).get(timeout=2400)
        except Exception as e:
            print(f"  ✗ conc={it['conc']} r{it['rep']}: {type(e).__name__}")
            continue
        st = (res or {}).get("stage_timings") or {}
        legs = st.get("render_legs") or []
        rows.append({**it, "render_s": st.get("render"), "total_s": st.get("total"),
                     "legs": legs, "conc_reported": st.get("render_concurrency")})
        print(f"  ✓ conc={it['conc']} r{it['rep']}  render={st.get('render')}s "
              f"legs={len(legs)}  conc_seen={st.get('render_concurrency')}")
    with open("/tmp/sweep_rows.json", "w") as fh:
        json.dump(rows, fh, indent=1, default=str)
    _report(rows, confirm_only)


def _report(rows, confirm_only):
    ok = [r for r in rows if r.get("legs")]
    print(f"\n  ════ {len(ok)}/{len(rows)} cells returned RENDERCLOCK legs ════")
    if not ok:
        print("  NO LEGS — an EMPTY READ, not a zero. Either the job did not take")
        print("  the burst path, or the instrument is still not crossing. Do NOT")
        print("  read this as 'concurrency has no effect'.")
        return
    if confirm_only:
        print("  CONFIRMATION PASSED: the burst path returns legs. Sweep is unblocked.")
        for lg in ok[0]["legs"][:6]:
            print(f"    {str(lg.get('leg'))[:38]:>38}  frames={lg.get('frames')} "
                  f"ms/frame={lg.get('ms_per_frame')}")
        return
    agg = {}
    for r in ok:
        for lg in r["legs"]:
            comp = "micro" if "Micro" in str(lg.get("leg")) else "overlay"
            a = agg.setdefault((r["conc"], comp), {"mspf": [], "frames": 0, "legs": 0})
            a["mspf"].append(lg.get("ms_per_frame") or 0)
            a["frames"] += lg.get("frames") or 0
            a["legs"] += 1
    import statistics as st_
    print(f"\n  {'conc':>5} {'composition':>12} {'ms/frame p50':>13} {'legs':>5} {'frames':>7}")
    for (c, comp), a in sorted(agg.items()):
        print(f"  {c:>5} {comp:>12} {st_.median(a['mspf']):>13.1f} {a['legs']:>5} {a['frames']:>7}")
    print(f"\n  {'conc':>5} {'render_s p50':>13} {'cost/job est':>13}")
    for c in ARMS:
        rs = [r["render_s"] for r in ok if r["conc"] == c and r.get("render_s")]
        if rs:
            med = st_.median(rs)
            # cpu=32 burst; cost tracks CORE-SECONDS, which is what a concurrency
            # change actually moves. Rate is indicative — the RATIO is the result.
            print(f"  {c:>5} {med:>13.1f} {32*med/3600*0.55:>13.4f}")
    print("\n  DECISION: lower conc must win on BOTH ms/frame and cost/job to ship.")
    print("  A trade on either axis stops here and goes to Zac.")
