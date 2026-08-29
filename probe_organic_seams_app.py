"""ORGANIC SEAM DISTRIBUTION — how much of the 3.37x is reachable on real uploads?

THE QUESTION. The seam-candidate widening measured 3.37x more overlay
transitions (0.33 -> 1.12 per 25s) on THREE staged talking heads chosen for
being seam-poor: shot=0-1, broll=0-4, and 4 of 6 runs skipped the sub-call
entirely for want of any candidate. Real uploads are not those three. If organic
jobs already carry plenty of shot changes and b-roll edges, the widening buys
little; if they look like the fixtures, it buys a lot.

WHY NOT READ THE [seam-candidates] INSTRUMENT. It prints to container stdout,
which is not queryable across jobs. Everything needed is already persisted:

  OFFERED TODAY  = seam_bare_choice (ledger) + tight_cut_overlays + transitions
                   (delivered recipe). Every offered seam resolves to exactly one
                   of those three — bare, overlay, or transition — so the sum IS
                   the count that was offered.
  MECHANICAL     = len(cuts) - 1 from the delivered recipe. Every adjacent pair
                   of kept cuts is a splice the cutter made.

The widening's reach is the mechanical count MINUS what is already offered, and
that difference is what the 3.37x would act on.

STATED LIMIT: `_subcall_seam_awis` is underscore-prefixed and stripped by the
persist sanitiser, so the exact offered set cannot be recovered per job — only
its size, via the three-way resolution above. Overlap between mechanical splices
and existing shot/broll seams is therefore an UPPER BOUND on the delta, not an
exact new-candidate count.

  ./run_modal.sh probe_organic_seams_app.py --since 2026-08-27
"""
import os
import statistics as st
from collections import Counter

import modal

app = modal.App("probe-organic-seams")
image = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=1800)
def run(since: str) -> list:
    import json
    import boto3
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    r = (sb.table("video_jobs").select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True).limit(600).execute())
    out = []
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        if str(res.get("route") or "std-editorial") != "std-editorial":
            continue
        rc = res.get("edit_recipe")
        rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
        if not isinstance(rc, dict):
            continue
        cuts = [c for c in (rc.get("cuts") or []) if isinstance(c, dict)
                and isinstance(c.get("source_start"), (int, float))
                and isinstance(c.get("source_end"), (int, float))
                and c["source_end"] > c["source_start"]]
        if not cuts:
            continue
        out_s = sum((c["source_end"] - c["source_start"]) / (c.get("speed") or 1)
                    for c in cuts)
        if out_s <= 0:
            continue
        rec = {"id": x["id"], "out_s": out_s, "n_cuts": len(cuts),
               "mechanical": max(0, len(cuts) - 1),
               "tight_ovl": len(rc.get("tight_cut_overlays") or []),
               "trans": sum(1 for c in cuts if c.get("transition_out")
                            and c["transition_out"] != "none"),
               "broll": len(rc.get("broll_clips") or []),
               "bare": 0, "ledger": False}
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{x['id']}.jsonl")["Body"].read()
            rec["ledger"] = True
            for line in body.decode("utf-8", "replace").split("\n"):
                if line.strip():
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("action") == "seam_bare_choice":
                        rec["bare"] += 1
        except Exception:
            pass
        out.append(rec)
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    rows = [r for r in run.remote(since) if r["ledger"]]
    if not rows:
        print("\n  NO LEDGERS — absent read, not a zero.")
        return
    for r in rows:
        r["offered"] = r["bare"] + r["tight_ovl"] + r["trans"]
        r["delta"] = max(0, r["mechanical"] - r["offered"])

    def p(vals, q):
        v = sorted(vals)
        return v[min(len(v) - 1, int(len(v) * q))]

    off = [r["offered"] for r in rows]
    mech = [r["mechanical"] for r in rows]
    dlt = [r["delta"] for r in rows]
    print(f"\n=== ORGANIC SEAM DISTRIBUTION — {len(rows)} std-editorial jobs "
          f"with ledgers ===")
    print(f"\n  {'':>26} {'p10':>5} {'p50':>5} {'p90':>5} {'mean':>6}")
    for lbl, v in (("seams OFFERED today", off),
                   ("mechanical splices", mech),
                   ("would-be NEW (upper bd)", dlt)):
        print(f"  {lbl:>26} {p(v,0.1):>5} {p(v,0.5):>5} {p(v,0.9):>5} "
              f"{st.mean(v):>6.1f}")

    zero = sum(1 for r in rows if r["offered"] == 0)
    print(f"\n  jobs offered ZERO seams today: {zero}/{len(rows)} "
          f"({100.0*zero/len(rows):.0f}%)  <- the sub-call is skipped entirely")
    print(f"  jobs where widening adds >=1:   "
          f"{sum(1 for r in rows if r['delta'] > 0)}/{len(rows)}")
    _ratio = [r["mechanical"] / r["offered"] for r in rows if r["offered"] > 0]
    if _ratio:
        print(f"  mechanical / offered ratio (jobs with >0 offered): "
              f"p50 {st.median(_ratio):.1f}x")

    print(f"\n  FIXTURE COMPARISON — the three staged talking heads measured:")
    print(f"      625dfdc5-73s  offered 0   mechanical_new 34")
    print(f"      3b2e5346-35s  offered 4   mechanical_new 6")
    print(f"      0c17b20b-35s  offered 1   mechanical_new 6")
    print(f"  If organic p50 offered is near 0-1 the fixtures are representative")
    print(f"  and the 3.37x carries. If organic already offers many, it does not.")

    print(f"\n  per 25s of output:")
    for lbl, key in (("offered", "offered"), ("mechanical", "mechanical")):
        v = [25.0 * r[key] / r["out_s"] for r in rows]
        print(f"      {lbl:>12}: p50 {st.median(v):.2f}  mean {st.mean(v):.2f}")
