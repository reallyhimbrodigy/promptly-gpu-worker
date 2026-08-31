"""Which of the four missing corpus sub-codes have a CAPTURED source to seed?

A seed is not a name — it is a real file that once reproduced the defect. The
manifest can only grow as the corpus captures them, so this asks the two
questions that decide whether each of frame_grid / analyze_loudness /
keyterm_limit / missing_artifact_path can be seeded TODAY:

  1. Did any job ever die with that sub-code?          (is the class real here)
  2. Is that job's source sitting in failure-corpus/?  (is there a file to run)

A sub-code with no captured source cannot be seeded, and saying so is the
result — inventing a key would make the gate green against a file that does not
exist, which is worse than the gap.
"""
import os, modal
from collections import Counter
app = modal.App("probe-corpus-seeds")
img = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S=[modal.Secret.from_name("promptly-secrets")]
WANT = ("frame_grid", "analyze_loudness", "keyterm_limit", "missing_artifact_path")

@app.function(image=img, secrets=S, timeout=900)
def scan(bucket: str):
    import boto3
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3=boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    # every object already in the failure corpus
    keys=set(); tok=None
    while True:
        kw={"Bucket":bucket,"Prefix":"failure-corpus/","MaxKeys":1000}
        if tok: kw["ContinuationToken"]=tok
        r=s3.list_objects_v2(**kw)
        for o in r.get("Contents") or []: keys.add(o["Key"])
        tok=r.get("NextContinuationToken")
        if not r.get("IsTruncated"): break
    rows=[]; page=0
    while page<12:
        r=(sb.table("video_jobs").select("id,result,created_at,status")
           .in_("status",["failed","error"]).order("created_at",desc=True)
           .range(page*500,page*500+499).execute())
        d=r.data or []; rows.extend(d)
        if len(d)<500: break
        page+=1
    out={w:{"jobs":0,"users":set(),"seedable":[]} for w in WANT}
    seen=Counter()
    for x in rows:
        res=x.get("result") if isinstance(x.get("result"),dict) else {}
        sc=str(res.get("error_subcode") or "")
        seen[sc]+=1
        if sc not in out: continue
        out[sc]["jobs"]+=1
        code=str(res.get("error_code") or "UNKNOWN")
        k=f"failure-corpus/{code}/{x['id']}.mp4"
        if k in keys: out[sc]["seedable"].append(k)
    return {"corpus_objects":len(keys),
            "per":{w:{"jobs":out[w]["jobs"],"seedable":out[w]["seedable"][:3]} for w in WANT},
            "top_subcodes":seen.most_common(12)}

@app.local_entrypoint()
def main(bucket: str = "thisismybucketagainwooo"):
    d=scan.remote(bucket)
    print(f"\n=== CORPUS 5->9: can the four be seeded? ===")
    print(f"  {d['corpus_objects']} objects already under failure-corpus/\n")
    ready=[]
    for w,v in d["per"].items():
        if v["seedable"]:
            ready.append((w,v["seedable"][0]))
            print(f"  ✅ {w:<22} {v['jobs']} failed job(s), SOURCE CAPTURED")
            print(f"       {v['seedable'][0]}")
        else:
            print(f"  ❌ {w:<22} {v['jobs']} failed job(s), no source in the corpus")
    print(f"\n  seedable now: {len(ready)}/4")
    if len(ready) < 4:
        print("  A sub-code with no captured source CANNOT be seeded. Naming it in")
        print("  the manifest would point the gate at a file that does not exist —")
        print("  green against nothing, which is worse than the gap.")
    print(f"\n  top failure sub-codes in the window (for context):")
    for sc,n in d["top_subcodes"]:
        print(f"    {n:>5}  {sc or '(none)'}")
