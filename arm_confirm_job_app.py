"""ARM CONFIRMATION — one real job down the PRODUCTION path, reading pool_task_s.

The watch cannot confirm the arm until organic traffic completes, and "armed"
is not "running": the unread-flag false-green has landed here repeatedly. This
settles the first half now, on the real path, without waiting.

NOT a synthetic call to ingest_bundle — that is what the boundary verification
already did. This goes through `run_pipeline_bg`, the same entrypoint every
user job uses, so it exercises the ARM ITSELF: the env write in that function's
body, read by _ingest_bundle_enabled inside handler, on the deployed image.

THE OBSERVABLE: stage_timings.pool_task_s. An in-process job records four keys
(gemini_proxy / loudness / shot_changes / faces); a bundled job records ONE,
`ingest_bundle`, and none of the four. Distinguishable, off the persisted row.

demo=True keeps it out of product metrics. The row is pre-inserted because
write_job_status UPDATEs and never INSERTs — a synthetic job_id reports nowhere
and reads as a confident null.

  ./run_modal.sh arm_confirm_job_app.py --no-dry     # ~$0.13
  ./run_modal.sh arm_confirm_job_app.py --read
"""
import json
import os
import sys
import uuid

import modal

app = modal.App("arm-confirm-job")
IMG = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
# A KNOWN std-editorial source. The first attempt used the concat fixture built
# for the BOUNDARY check and it routed to `minimal_speech_uncut` — observed off
# result.route, not guessed from the fast wall — so it short-circuited at the
# intake gates and never reached the ingest pool.
#
# DIFFERENT CHECK, DIFFERENT FIXTURE REQUIREMENT. The boundary check needed
# shot changes and faces to compare non-empty outputs. This one only needs the
# job to REACH the ingest pool and record pool_task_s, so a single-take talking
# head — no cuts, plenty of speech — is the right source and the cut-bearing
# concat is the wrong one.
SRC_KEY = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"
FOUR = ("gemini_proxy", "loudness", "shot_changes", "faces")


@app.function(image=IMG, secrets=S, timeout=600)
def presign_and_insert(job_id: str, key: str = SRC_KEY) -> dict:
    import boto3
    from supabase import create_client
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    s3.head_object(Bucket=b, Key=key)          # non-vacuity before spend
    src = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": b, "Key": key},
                                    ExpiresIn=14400)
    dst = s3.generate_presigned_url(
        "put_object", Params={"Bucket": b, "Key": f"arm-confirm/{job_id}.mp4",
                              "ContentType": "video/mp4"}, ExpiresIn=14400)
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    sb.table("video_jobs").insert({
        "id": job_id, "status": "queued", "video_url": key,
        "vibe_input": "viral", "demo": True}).execute()
    return {"src": src, "dst": dst}


@app.function(image=IMG, secrets=S, timeout=900)
def read(job_id: str) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = (sb.table("video_jobs").select("status,result,error_message")
         .eq("id", job_id).limit(1).execute())
    d = (r.data or [{}])[0]
    res = d.get("result") if isinstance(d.get("result"), dict) else {}
    stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
    pool = stt.get("pool_task_s") if isinstance(stt.get("pool_task_s"), dict) else {}
    return {"status": d.get("status"), "pool": pool,
            "err": str(d.get("error_message") or "")[:300],
            "where": str(res.get("error_where") or "")[:300],
            "total": stt.get("total"),
            # ROUTE, so "the pool never ran" is OBSERVED rather than inferred
            # from a fast wall. A diverted route (minimal/hype) short-circuits
            # at the intake gates and never reaches the ingest block at all.
            "route": str(res.get("route") or "?"),
            "st_keys": sorted(stt)[:14],
            "manifest": sorted((res.get("stage_manifest") or {}))[:14]}


@app.local_entrypoint()
def main(dry: bool = True, read_only: bool = False, job_id: str = "",
         key: str = SRC_KEY):
    if read_only:
        jid = job_id or json.load(open("/tmp/arm_confirm_job.json"))["job_id"]
        r = read.remote(jid)
        print(f"\n=== ARM CONFIRMATION — job {jid[:8]} ===")
        print(f"  status: {r['status']}   wall: {r.get('total')}s   "
              f"route: {r.get('route')}")
        print(f"  stage_timings keys: {r.get('st_keys')}")
        print(f"  stage_manifest    : {r.get('manifest')}")
        if not r["pool"]:
            print("  pool_task_s EMPTY — job not finished, or it died before the")
            print("  ingest pool. ABSENT read, not a negative result.")
            if r["err"]:
                print(f"  error: {r['err']}")
                print(f"  where: {r['where']}")
            return
        print(f"  pool_task_s keys: {sorted(r['pool'])}")
        bundled = "ingest_bundle" in r["pool"]
        inproc = [k for k in FOUR if k in r["pool"]]
        print(f"\n  bundled : {bundled}")
        print(f"  in-proc : {inproc or 'none'}")
        if bundled and not inproc:
            print(f"\n  ✅ ARM CONFIRMED ON THE PRODUCTION PATH.")
            print(f"     The four tasks ran on the cpu=8 bundle "
                  f"({r['pool']['ingest_bundle']}s), not in this container.")
        elif inproc and not bundled:
            print("\n  ❌ ARMED BUT NOT RUNNING — the flag is set and the four "
                  "tasks are STILL IN-PROCESS.")
            sys.exit(1)
        else:
            print("\n  ❌ MIXED/UNCLEAR — do not proceed to step 2.")
            sys.exit(1)
        return

    jid = str(uuid.uuid4())
    u = presign_and_insert.remote(jid, key)
    print(f"  source {key.split(chr(47))[-1]} HEADed, row pre-inserted, job {jid[:8]}")
    if dry:
        print("  DRY — nothing dispatched. --no-dry to fire (1 render, ~$0.13).")
        return
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    fn.hydrate()
    cid = fn.spawn({"job_id": jid, "video_url": u["src"], "vibe": "viral",
                    "user_id": str(uuid.uuid4()),
                    "upload_url": u["dst"], "public_url": u["dst"]}).object_id
    with open("/tmp/arm_confirm_job.json", "w") as fh:
        json.dump({"job_id": jid, "call": cid}, fh)
    print(f"  → dispatched {jid[:8]}  {cid}")
    print(f"  read with: ./run_modal.sh arm_confirm_job_app.py --read-only")
