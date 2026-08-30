"""OVERLAP ARM — CODE HALF, tested with an INJECTED plan (mode=render_only).

WHY INJECTED. The overlap drop fires only on b-roll that was authored AND
fetched, and authoring is stochastic: 7 positives in 229 organic jobs, 2 of 12
fixture runs, and all three staged renders authored NOTHING. There is no source
property to select on — the referent-density spec failed its own test ("I'm a
cowboy. Yes, sir. I am." authored b-roll with no named entity). So the model's
choice is removed from the experiment: a plan carrying a deliberate collision is
handed straight to the renderer.

THE FIXTURE PROVES ITSELF, and this is the load-bearing design decision. The
CONTROL arm must SHOW THE DROP — a b-roll clip that overlaps an MG window must
disappear and log overlay_window_conflict. If the control does NOT drop, the
fixture is wrong (bad indices, malformed plan, the clip never fetched) and the
treatment arm says nothing. A treatment-only read here would be measuring my
plan construction, not the arm.

    CONTROL   (no variant)      -> b-roll DROPPED, overlay_window_conflict fires
    TREATMENT (variant 6)       -> b-roll SURVIVES, no conflict fire

Anything else — both drop, both survive, neither fetches — is a FIXTURE
FAILURE and is reported as one, not as a result.

  ./run_modal.sh overlap_arm_injected_app.py --base-job <uuid> --no-dry
"""
import json
import os
import sys
import uuid

import modal

app = modal.App("overlap-arm-injected")
IMG = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
SRC_KEY = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"


@app.function(image=IMG, secrets=S, timeout=900)
def build(base_job: str) -> dict:
    """Take a REAL delivered recipe and inject one deliberate collision."""
    import boto3
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = sb.table("video_jobs").select("result").eq("id", base_job).limit(1).execute()
    res = (r.data or [{}])[0].get("result") or {}
    rc = res.get("edit_recipe") or {}
    rc = rc.get("plan") if isinstance(rc.get("plan"), dict) else rc
    if not isinstance(rc, dict) or not rc.get("cuts"):
        return {"ok": False, "why": "base job has no usable recipe"}
    tr = res.get("transcript") or {}
    words = tr.get("words") if isinstance(tr, dict) else None
    n_words = len(words or [])
    if n_words < 30:
        return {"ok": False, "why": f"base transcript too short ({n_words} words)"}

    # Anchor both elements to the SAME word span so their output windows must
    # overlap. Mid-transcript, well away from the first ~3s opening gate and the
    # hook, so the prompt-side exclusions cannot be what removes the clip.
    sw, ew = int(n_words * 0.45), int(n_words * 0.45) + 4
    plan = json.loads(json.dumps(rc, default=str))
    plan["broll_clips"] = [{
        "keyword": "modern city skyline aerial drone shot daytime",
        "start_word_index": sw, "end_word_index": ew,
        "reason": "overlap-arm fixture — deliberate collision with the MG below",
    }]
    plan["motion_graphics"] = [{
        "type": "StatCard",
        "anchor": {"start_word_index": sw, "end_word_index": ew},
        "props": {"value": "80", "label": "PERCENT"},
    }]
    return {"ok": True, "plan": plan, "n_words": n_words, "span": [sw, ew],
            "base_cuts": len(plan.get("cuts") or [])}


@app.function(image=IMG, secrets=S, timeout=900)
def presign_and_insert(rows: list) -> dict:
    import boto3
    from supabase import create_client
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    src = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": b, "Key": SRC_KEY},
                                    ExpiresIn=14400)
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = {"src": src, "dst": {}, "inserted": 0, "errors": []}
    for r in rows:
        out["dst"][r["arm"]] = s3.generate_presigned_url(
            "put_object", Params={"Bucket": b,
                                  "Key": f"overlap-arm/{r['job_id']}.mp4",
                                  "ContentType": "video/mp4"}, ExpiresIn=14400)
        try:
            sb.table("video_jobs").insert({
                "id": r["job_id"], "status": "queued", "video_url": SRC_KEY,
                "vibe_input": "viral", "demo": True}).execute()
            out["inserted"] += 1
        except Exception as e:
            out["errors"].append(str(e)[:150])
    return out


@app.function(image=IMG, secrets=S, timeout=1800)
def collect(pairs: list) -> list:
    import boto3
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or BUCKET
    out = []
    for p in pairs:
        rec = {"arm": p["arm"], "job_id": p["job_id"], "status": None,
               "delivered_broll": None, "conflict_fires": 0, "broll_acts": {}}
        try:
            r = (sb.table("video_jobs").select("status,result")
                 .eq("id", p["job_id"]).limit(1).execute())
            d = (r.data or [{}])[0]
            rec["status"] = d.get("status")
            res = d.get("result") if isinstance(d.get("result"), dict) else {}
            rc = res.get("edit_recipe") or {}
            rc = rc.get("plan") if isinstance(rc.get("plan"), dict) else rc
            if isinstance(rc, dict):
                rec["delivered_broll"] = len(rc.get("broll_clips") or [])
                # DID THE INJECTION TAKE AT ALL? If the MG is also absent, the
                # provided plan was not honoured and nothing about b-roll can be
                # concluded — a different failure from "b-roll specifically died".
                rec["delivered_mg"] = len(rc.get("motion_graphics") or [])
                rec["n_cuts"] = len(rc.get("cuts") or [])
        except Exception as e:
            rec["status"] = "READ FAILED %s" % type(e).__name__
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key="divergences/%s.jsonl" % p["job_id"])["Body"].read()
            from collections import Counter
            c = Counter()
            for line in body.decode("utf-8", "replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if "broll" in str(ev.get("component")) or "broll" in str(ev.get("action")):
                    c["%s:%s" % (ev.get("component"), ev.get("action"))] += 1
                if str(ev.get("reason") or "") == "overlay_window_conflict":
                    rec["conflict_fires"] += 1
            rec["broll_acts"] = dict(c)
        except Exception:
            pass
        out.append(rec)
    return out


@app.local_entrypoint()
def main(base_job: str = "f7db71b9-9013-4643-86bd-995b8cade3f0",
         dry: bool = True, read: bool = False):
    if read:
        pairs = json.load(open("/tmp/overlap_arm_pairs.json"))
        for r in collect.remote(pairs):
            print("\n  %-9s %s  status=%s  cuts=%s  broll=%s  MG=%s  conflicts=%s"
                  % (r["arm"], r["job_id"][:8], r["status"], r.get("n_cuts"),
                     r["delivered_broll"], r.get("delivered_mg"),
                     r["conflict_fires"]))
            for k, v in sorted(r["broll_acts"].items(), key=lambda z: -z[1]):
                print("      %3d  %s" % (v, k))
        print("\n  FIXTURE VALIDITY: the CONTROL arm must show delivered_broll=0")
        print("  AND conflict_fires>=1. Anything else is a fixture failure, not")
        print("  a result — read nothing from the treatment arm until it holds.")
        return

    b = build.remote(base_job)
    if not b.get("ok"):
        print("  ❌ %s" % b.get("why"))
        sys.exit(2)
    print("  base recipe: %d cuts, %d transcript words; collision anchored at "
          "words %s" % (b["base_cuts"], b["n_words"], b["span"]))
    if dry:
        print("  DRY — nothing dispatched. --no-dry to fire (2 renders, ~$0.26).")
        return

    pairs = [{"arm": "CONTROL", "job_id": str(uuid.uuid4()), "variant": None},
             {"arm": "ARM6", "job_id": str(uuid.uuid4()), "variant": 6}]
    pi = presign_and_insert.remote(pairs)
    print("  pre-inserted %d/%d rows %s" % (pi["inserted"], len(pairs),
                                            pi["errors"] or ""))
    if pi["inserted"] != len(pairs):
        print("  ❌ refusing to dispatch — a job with no row reports nowhere")
        sys.exit(2)
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    for p in pairs:
        body = {"job_id": p["job_id"], "video_url": pi["src"], "vibe": "viral",
                "user_id": str(uuid.uuid4()),
                "upload_url": pi["dst"][p["arm"]], "public_url": pi["dst"][p["arm"]],
                "mode": "render_only", "edit_plan": b["plan"]}
        if p["variant"] is not None:
            body["density_variant"] = p["variant"]
        cid = fn.spawn(body).object_id
        print("  → %-8s %s  %s" % (p["arm"], p["job_id"][:8], cid))
    with open("/tmp/overlap_arm_pairs.json", "w") as fh:
        json.dump(pairs, fh)
    print("\n  read with: ./run_modal.sh overlap_arm_injected_app.py --read")
