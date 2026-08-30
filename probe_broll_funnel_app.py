"""B-ROLL FUNNEL — where does 3.32/25s become 0.04/25s?

Reference edits carry cutaways at 3.32 per 25s; we deliver 0.04, on 3% of jobs.
80x, the largest and least ambiguous gap in the reference comparison. Mechanism
before rules.

THE FUNNEL, read from the code:
    authorable    PostCutPlan.broll_clips is in the schema
    keyword       "[broll] Missing keyword on broll_entry — skipping"
    PEXELS        "[broll] PEXELS_API_KEY not set — skipping"   <- a HARD STOP
    content gate  broll_content_reject (dark unless PROMPTLY_BROLL_GATE)
    timing        removed-words skip
    overlap       B-roll overlapping an MG or overlay window is dropped
    prompt gate   nothing in the first ~3s or inside the hook segment

The KEY is checked FIRST because it is a hard stop: with no key every fetch is
skipped and every number downstream of it is meaningless. It is one env read on
the deployed secret set, not an inference.

  ./run_modal.sh probe_broll_funnel_app.py --since 2026-08-27
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-broll-funnel", image=image)
SEC = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]


@app.function(secrets=SEC, cpu=4.0, memory=8192, timeout=1800)
def run(since: str) -> dict:
    import json
    from collections import Counter
    import boto3
    from supabase import create_client

    out = {"pexels_present": bool(os.environ.get("PEXELS_API_KEY")),
           "pexels_prefix": (os.environ.get("PEXELS_API_KEY") or "")[:6] or None,
           "broll_gate_flag": os.environ.get("PROMPTLY_BROLL_GATE", "<unset>")}
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    r = (sb.table("video_jobs").select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True).limit(600).execute())

    acts = Counter()
    jobs = delivered = jobs_with = 0
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
        jobs += 1
        n = len(rc.get("broll_clips") or [])
        delivered += n
        if n:
            jobs_with += 1
        key = "divergences/" + str(x.get("id")) + ".jsonl"
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        except Exception:
            continue
        for line in body.decode("utf-8", "replace").split("\n"):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            comp = str(ev.get("component") or "")
            act = str(ev.get("action") or "")
            if "broll" in comp or "broll" in act:
                acts[comp + ":" + act] += 1
    out["acts"] = dict(acts)
    out["jobs"] = jobs
    out["delivered"] = delivered
    out["jobs_with"] = jobs_with
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    d = run.remote(since)
    print("\n=== B-ROLL FUNNEL — %d std-editorial jobs ===" % d["jobs"])
    print("\n  [1] THE HARD STOP")
    print("      PEXELS_API_KEY present : %s  (%s)"
          % (d["pexels_present"], d["pexels_prefix"]))
    print("      PROMPTLY_BROLL_GATE    : %s" % d["broll_gate_flag"])
    if not d["pexels_present"]:
        print("      >>> NO KEY IN THE DEPLOYED SECRET SET. Every b-roll fetch")
        print("          is skipped at source. Nothing downstream is meaningful —")
        print("          that alone IS the 80x, and it is a credential, not a rule.")
    else:
        print("      key present — the gap is downstream of the fetch")
    print("\n  [2] DELIVERED: %d clips across %d jobs (%d jobs carry >=1, %.0f%%)"
          % (d["delivered"], d["jobs"], d["jobs_with"],
             100.0 * d["jobs_with"] / max(1, d["jobs"])))
    print("\n  [3] B-ROLL LEDGER ACTIONS")
    if not d["acts"]:
        print("      NONE — no broll divergence recorded at all. Either b-roll is")
        print("      never authored, or its drops are not ledgered. Both are")
        print("      findings; they are not the same finding.")
    for k, v in sorted(d["acts"].items(), key=lambda z: -z[1]):
        print("      %5d  %s" % (v, k))
