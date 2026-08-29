"""MG EMITTED vs SURVIVING, BY LEAN ARM — the cull counted inside each job.

WHY THIS AND NOT MORE REPS. The PLAN_ONLY read found MG emission IDENTICAL
between arms (0.83/plan both sides) against a delivered gap of 0.45 vs 0.27.
That points gate-side — but MG counts are 0-2 per plan, so a 41% relative
difference is ~0.34 counts and n=6 per arm cannot resolve it either way. More
reps buys power slowly and expensively.

The divergence ledger already carries the cull. Counting emitted-vs-survived
INSIDE each job makes the comparison paired within the job, so between-job
variance stops mattering and the whole 123-job std-editorial population is
usable at zero render cost.

    emitted ≈ delivered + dropped

TWO NUMBERS, KEPT APART, because they answer different questions:
  • RAW COUNTS — does lean deliver fewer MGs? (already known: yes, 0.59x)
  • GROUNDING-FAILURE RATE — of the MGs the model DID author, what fraction were
    culled for failing the grounding predicate? If lean's cull rate is higher on
    the same emission, the lean arm is producing MGs that cannot survive the
    gate, which is a different defect from producing fewer.

ALSO RESOLVES THE OVERLAY CONTRADICTION: emitted text_overlays read LOWER under
lean in the PLAN_ONLY run (7 vs 4) while delivered organic read HIGHER (1.19x).
One of those is wrong. The same ledger carries overlay drops, so the same read
settles it.

  ./run_modal.sh probe_mg_cull_by_arm_app.py --since 2026-08-27
"""
import os
import statistics as st
from collections import Counter, defaultdict

import modal

app = modal.App("probe-mg-cull-by-arm")
image = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=1800)
def scan(since: str) -> list:
    import json
    import boto3
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"

    r = (sb.table("video_jobs")
         .select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True)
         .limit(600).execute())
    out = []
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        arm = str(stt.get("lean_arm") or "")
        if arm not in ("lean", "control"):
            continue                      # scoped: only jobs that ran the A/B
        rec = {"id": x.get("id"), "arm": arm, "acts": Counter()}
        rc = res.get("edit_recipe")
        rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
        if isinstance(rc, dict):
            cuts = [c for c in (rc.get("cuts") or []) if isinstance(c, dict)
                    and isinstance(c.get("source_start"), (int, float))
                    and isinstance(c.get("source_end"), (int, float))
                    and c["source_end"] > c["source_start"]]
            rec["out_s"] = sum((c["source_end"] - c["source_start"]) / (c.get("speed") or 1)
                               for c in cuts) or None
            rec["mg_delivered"] = len(rc.get("motion_graphics") or [])
            rec["ovl_delivered"] = len(rc.get("text_overlays") or [])
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{rec['id']}.jsonl")["Body"].read()
            for line in body.decode("utf-8", "replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                rec["acts"][f"{ev.get('component')}:{ev.get('action')}"] += 1
            rec["ledger"] = True
        except Exception:
            rec["ledger"] = False
        rec["acts"] = dict(rec["acts"])
        out.append(rec)
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    rows = [r for r in scan.remote(since) if r.get("ledger")]
    L = [r for r in rows if r["arm"] == "lean"]
    C = [r for r in rows if r["arm"] == "control"]
    print(f"\n=== MG CULL BY ARM — {len(rows)} std-editorial jobs with ledgers "
          f"(lean {len(L)} / control {len(C)}) ===")
    if not L or not C:
        print("  one arm empty — no comparison.")
        return

    MG_DROPS = ("motion_graphic:drop_ungrounded_text",)

    def agg(rs, keys):
        return sum(sum(r["acts"].get(k, 0) for k in keys) for r in rs)

    print(f"\n  [1] RAW COUNTS (per job)")
    print(f"      {'':>22} {'LEAN':>8} {'CONTROL':>8} {'ratio':>7}")
    for lbl, fn in (
            ("mg delivered/job", lambda rs: st.mean([r.get("mg_delivered", 0) for r in rs])),
            ("mg dropped/job", lambda rs: agg(rs, MG_DROPS) / len(rs)),
    ):
        a, b = fn(L), fn(C)
        print(f"      {lbl:>22} {a:>8.2f} {b:>8.2f} {(a/b if b else float('inf')):>7.2f}x")

    _le = st.mean([r.get("mg_delivered", 0) for r in L]) + agg(L, MG_DROPS) / len(L)
    _ce = st.mean([r.get("mg_delivered", 0) for r in C]) + agg(C, MG_DROPS) / len(C)
    print(f"      {'mg EMITTED/job (d+drop)':>22} {_le:>8.2f} {_ce:>8.2f} "
          f"{(_le/_ce if _ce else float('inf')):>7.2f}x")

    print(f"\n  [2] GROUNDING-FAILURE RATE — of what was authored, what was culled")
    for nm, rs in (("lean", L), ("control", C)):
        d = st.mean([r.get("mg_delivered", 0) for r in rs])
        dr = agg(rs, MG_DROPS) / len(rs)
        em = d + dr
        print(f"      {nm:>8}: emitted {em:.2f}  delivered {d:.2f}  culled {dr:.2f}"
              f"  -> cull rate {(100.0*dr/em if em else 0):.1f}%")
    print(f"\n      If EMISSION matches and CULL RATE differs, the lean arm authors")
    print(f"      MGs that cannot survive the grounding predicate — a different")
    print(f"      defect from authoring fewer, and fixed in a different place.")

    print(f"\n  [3] OVERLAY DIRECTION — settling the contradiction")
    print(f"      PLAN_ONLY emission read overlays LOWER under lean (7 vs 4);")
    print(f"      delivered organic read them HIGHER (1.19x). Same ledger, same jobs:")
    _lo = st.mean([r.get("ovl_delivered", 0) for r in L])
    _co = st.mean([r.get("ovl_delivered", 0) for r in C])
    print(f"      overlays delivered/job: lean {_lo:.2f}  control {_co:.2f}  "
          f"{(_lo/_co if _co else float('inf')):.2f}x")

    print(f"\n  [4] ALL component:action deltas (per job, lean - control)")
    keys = set()
    for r in rows:
        keys |= set(r["acts"].keys())
    deltas = []
    for k in keys:
        a = agg(L, (k,)) / len(L)
        b = agg(C, (k,)) / len(C)
        if a + b >= 0.15:
            deltas.append((a - b, k, a, b))
    for dlt, k, a, b in sorted(deltas, key=lambda t: -abs(t[0]))[:14]:
        print(f"      {dlt:>+7.2f}  {k:<44} lean {a:.2f} ctrl {b:.2f}")
