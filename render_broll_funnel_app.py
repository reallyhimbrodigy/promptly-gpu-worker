"""RENDER the three staged sources to exercise the B-ROLL ASSET FUNNEL.

WHY RENDERS AND NOT PLAN_ONLY. The Pexels fetch, the match floor, the content
gate and the overlay-overlap drop all live in the RENDER path. PLAN_ONLY exits
before every one of them — my arm logs show "[broll] Gemini requested 2 B-roll
clip(s)" with full keywords and then NOTHING, because the fetch never runs.
The funnel is per-clip mechanics, so three controlled sources answer it better
than waiting for a population rate.

WHAT THIS READS. v591 ledgers every b-roll drop cause, so the funnel is now
visible from the divergence rows rather than from container stdout:
    no_portrait_candidate            Pexels returned nothing usable
    below_match_score_floor          best score < 60
    asset_over_byte_cap              >30MB
    anchor_words_all_removed_by_cut  the cut pass ate the anchor
    index_out_of_kept_range          two-pass translation
    overlay_window_conflict          an overlay won the window
    broll_content_reject             the frame-level gate (LIVE: PROMPTLY_BROLL_GATE=1)

Pre-inserts the video_jobs row before dispatch — write_job_status UPDATEs and
never INSERTs, so a synthetic job_id reports nowhere and reads as a confident
null. demo=True keeps these out of product metrics.

  ./run_modal.sh render_broll_funnel_app.py --no-dry
"""
import json
import os
import sys
import uuid

import modal

app = modal.App("render-broll-funnel")
IMG = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]

CLIPS = [
    "ab-sources/talking-head-v1/625dfdc5-73s.mp4",
    "ab-sources/talking-head-v1/3b2e5346-35s.mp4",
    "ab-sources/talking-head-v1/0c17b20b-35s.mp4",
]
BUCKET = "thisismybucketagainwooo"


@app.function(image=IMG, secrets=S, timeout=900)
def presign(keys: list) -> dict:
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    out = {}
    for k in keys:
        s3.head_object(Bucket=b, Key=k)      # non-vacuity before any spend
        out[k] = {
            "src": s3.generate_presigned_url("get_object",
                                             Params={"Bucket": b, "Key": k},
                                             ExpiresIn=14400),
            "dst": s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": b, "Key": f"broll-funnel/{uuid.uuid4()}.mp4",
                        "ContentType": "video/mp4"}, ExpiresIn=14400),
        }
    return out


@app.function(image=IMG, secrets=S, timeout=900)
def preinsert(rows: list) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    ok, errs = 0, []
    for r in rows:
        try:
            sb.table("video_jobs").insert({
                "id": r["job_id"], "status": "queued", "video_url": r["key"],
                "vibe_input": "viral", "demo": True}).execute()
            ok += 1
        except Exception as e:
            errs.append(str(e)[:160])
    return {"inserted": ok, "errors": errs}


@app.function(image=IMG, secrets=S, timeout=1800)
def collect(job_ids: list) -> list:
    import boto3
    from collections import Counter
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or BUCKET
    out = []
    for jid in job_ids:
        rec = {"job_id": jid, "acts": {}, "reasons": [], "delivered": None,
               "status": None}
        try:
            r = (sb.table("video_jobs").select("status,result")
                 .eq("id", jid).limit(1).execute())
            d = (r.data or [{}])[0]
            rec["status"] = d.get("status")
            res = d.get("result") if isinstance(d.get("result"), dict) else {}
            rc = res.get("edit_recipe")
            rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
            if isinstance(rc, dict):
                rec["delivered"] = len(rc.get("broll_clips") or [])
        except Exception as e:
            rec["status"] = "READ FAILED: %s" % type(e).__name__
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key="divergences/%s.jsonl" % jid)["Body"].read()
            c = Counter()
            for line in body.decode("utf-8", "replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                comp, act = str(ev.get("component")), str(ev.get("action"))
                if "broll" in comp or "broll" in act:
                    c["%s:%s" % (comp, act)] += 1
                    rsn = str(ev.get("reason") or "")[:60]
                    if rsn:
                        rec["reasons"].append(rsn)
            rec["acts"] = dict(c)
        except Exception:
            pass
        out.append(rec)
    return out


@app.local_entrypoint()
def main(dry: bool = True, read: bool = False):
    # ONE entrypoint. Modal binds a single local_entrypoint per app;
    # a second decorator silently shadows the first.
    if read:
        ids = json.load(open("/tmp/broll_funnel_ids.json"))
        rows = collect.remote(ids)
        print("\n=== B-ROLL ASSET FUNNEL — %d rendered jobs ===" % len(rows))
        for r in rows:
            print("\n  %s  status=%s  delivered=%s"
                  % (r["job_id"][:8], r["status"], r["delivered"]))
            if not r["acts"]:
                print("      no b-roll ledger rows")
            for k, v in sorted(r["acts"].items(), key=lambda z: -z[1]):
                print("      %3d  %s" % (v, k))
            for rs in r["reasons"][:6]:
                print("           reason: %s" % rs)
        return

    urls = presign.remote(CLIPS)
    print("  %d source(s) presigned and HEADed" % len(urls))
    if dry:
        print("  DRY — nothing dispatched. --no-dry to fire (~$0.13 each).")
        return
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    pend = []
    for k in CLIPS:
        jid = str(uuid.uuid4())
        pend.append({"job_id": jid, "key": k, "body": {
            "job_id": jid, "video_url": urls[k]["src"], "vibe": "viral",
            "user_id": str(uuid.uuid4()),
            "upload_url": urls[k]["dst"], "public_url": urls[k]["dst"]}})
    pre = preinsert.remote([{"job_id": p["job_id"], "key": p["key"]} for p in pend])
    print("  pre-inserted %s/%d rows %s"
          % (pre.get("inserted"), len(pend), pre.get("errors") or ""))
    if pre.get("inserted", 0) != len(pend):
        print("  ❌ not all rows exist — refusing to dispatch (a job with no row "
              "reports nowhere and returns a confident null)")
        sys.exit(2)
    ids = []
    for p in pend:
        cid = fn.spawn(p["body"]).object_id
        ids.append(p["job_id"])
        print("  → %s  %s  %s" % (p["key"].split("/")[-1], p["job_id"][:8], cid))
        try:
            modal.FunctionCall.from_id(cid)
        except Exception:
            pass
    with open("/tmp/broll_funnel_ids.json", "w") as fh:
        json.dump(ids, fh)
    print("\n  ids -> /tmp/broll_funnel_ids.json")
    print("  read with: ./run_modal.sh render_broll_funnel_app.py::collect")


