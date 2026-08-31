"""MICRO CONCURRENCY 4/2/1 on an IDENTICAL PLAN — the number worth acting on.

The first sweep showed a real monotonic trend (4->1 halved ms/frame) but the
arms rendered DIFFERENT micro frame totals — 239 / 634 / 272 / 287 — because
the plan is regenerated per run and Gemini plans differently every time. A
per-frame cost compared across different frame sets is a trend, not a number.

FIX: mode=render_only with ONE harvested plan. Same source, same plan, same
cuts, same micro segments, same chunk boundaries — the ONLY variable is
concurrency. That is what makes the comparison a measurement.

The plan comes from a COMPLETED job (a job that fails at the integrity gate
persists no edit_recipe, which is why the earlier arms could not donate one).

  ./run_modal.sh micro_sweep_fixed_plan_app.py --no-dry
  ./run_modal.sh micro_sweep_fixed_plan_app.py --read-only
"""
import json
import os
import sys
import uuid

import modal

app = modal.App("micro-sweep-fixed-plan")
IMG = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
SRC_KEY = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"
ARMS = (4, 2, 1)


@app.function(image=IMG, secrets=S, timeout=600)
def presign_and_insert(rows: list) -> dict:
    import boto3
    from supabase import create_client
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    s3.head_object(Bucket=b, Key=SRC_KEY)
    src = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": b, "Key": SRC_KEY},
                                    ExpiresIn=14400)
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = {"src": src, "dst": {}, "inserted": 0, "errors": []}
    for r in rows:
        out["dst"][str(r["conc"])] = s3.generate_presigned_url(
            "put_object", Params={"Bucket": b,
                                  "Key": f"micro-sweep/{r['job_id']}.mp4",
                                  "ContentType": "video/mp4"}, ExpiresIn=14400)
        try:
            sb.table("video_jobs").insert({
                "id": r["job_id"], "status": "queued", "video_url": SRC_KEY,
                "vibe_input": "viral", "demo": True}).execute()
            out["inserted"] += 1
        except Exception as e:
            out["errors"].append(str(e)[:140])
    return out


@app.function(image=IMG, secrets=S, timeout=900)
def collect(pairs: list) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = []
    for p in pairs:
        r = (sb.table("video_jobs").select("status,result")
             .eq("id", p["job_id"]).limit(1).execute())
        d = (r.data or [{}])[0]
        res = d.get("result") if isinstance(d.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        out.append({"conc": p["conc"], "job": p["job_id"][:8],
                    "status": d.get("status"),
                    "render": stt.get("render"), "total": stt.get("total"),
                    "hls": stt.get("hls"),
                    "err": str(res.get("error_code") or "")})
    return out


@app.local_entrypoint()
def main(dry: bool = True, read_only: bool = False,
         plan_file: str = "/tmp/harvested_plan.json"):
    if read_only:
        pairs = json.load(open("/tmp/micro_sweep_pairs.json"))
        rows = collect.remote(pairs)
        print(f"\n=== MICRO SWEEP — identical plan, only concurrency varies ===")
        print(f"  {'conc':>5} {'job':<10} {'status':<11} {'render_s':>9} {'total_s':>8} {'hls':>6}")
        for r in sorted(rows, key=lambda z: -z["conc"]):
            print(f"  {r['conc']:>5} {r['job']:<10} {str(r['status']):<11} "
                  f"{str(r['render']):>9} {str(r['total']):>8} {str(r['hls']):>6}"
                  + (f"  {r['err']}" if r["err"] else ""))
        ok = [r for r in rows if r["status"] == "completed"
              and isinstance(r["render"], (int, float))]
        if len(ok) < 2:
            print("\n  fewer than 2 arms completed — NOT a comparison. Absent read.")
            return
        base = max(ok, key=lambda z: z["conc"])
        print(f"\n  render stage vs concurrency={base['conc']} baseline "
              f"({base['render']}s):")
        for r in sorted(ok, key=lambda z: -z["conc"]):
            d = r["render"] - base["render"]
            print(f"    conc={r['conc']}: {r['render']:>7.1f}s  "
                  f"{d:+7.1f}s  ({100.0*d/max(1e-9, base['render']):+.0f}%)")
        print(f"\n  IDENTICAL PLAN, so the frame set is the same in every arm and")
        print(f"  the delta is attributable to concurrency alone.")
        return

    if not os.path.exists(plan_file):
        print(f"  ❌ no harvested plan at {plan_file} — run harvest_plan_app.py first")
        sys.exit(2)
    plan = json.load(open(plan_file))
    if not plan.get("cuts"):
        print("  ❌ harvested plan has no cuts — refusing to render nothing")
        sys.exit(2)
    print(f"  plan: {len(plan.get('cuts') or [])} cuts, "
          f"{len(json.dumps(plan))} bytes — IDENTICAL across all arms")
    pairs = [{"conc": c, "job_id": str(uuid.uuid4())} for c in ARMS]
    if dry:
        print(f"  DRY — {len(ARMS)} render_only jobs (~$0.10 each). --no-dry to fire.")
        return
    pi = presign_and_insert.remote(pairs)
    print(f"  pre-inserted {pi['inserted']}/{len(pairs)} rows {pi['errors'] or ''}")
    if pi["inserted"] != len(pairs):
        print("  ❌ refusing to dispatch — a job with no row reports nowhere")
        sys.exit(2)
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    fn.hydrate()
    for p in pairs:
        dst = pi["dst"][str(p["conc"])]
        cid = fn.spawn({"job_id": p["job_id"], "video_url": pi["src"],
                        "vibe": "viral", "user_id": str(uuid.uuid4()),
                        "upload_url": dst, "public_url": dst,
                        "mode": "render_only", "edit_plan": plan,
                        "micro_concurrency_test": str(p["conc"])}).object_id
        print(f"  → conc={p['conc']}  {p['job_id'][:8]}  {cid}")
    json.dump(pairs, open("/tmp/micro_sweep_pairs.json", "w"))
    print("\n  read with: ./run_modal.sh micro_sweep_fixed_plan_app.py --read-only")
