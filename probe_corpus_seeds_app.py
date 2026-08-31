"""Which of the four missing corpus sub-codes have a CAPTURED source to seed?

A seed is not a name — it is a real file that once reproduced the defect. The
manifest can only grow as the corpus captures them, so this asks the two
questions that decide whether each of frame_grid / analyze_loudness /
keyterm_limit / missing_artifact_path can be seeded TODAY:

  1. Did any job ever die with that sub-code?          (is the class real here)
  2. Is that job's source sitting in failure-corpus/?  (is there a file to run)

THIS ANSWERS ONLY HALF THE QUESTION, and the other half is the dangerous one.
The corpus re-runs each source and asserts it NOW COMPLETES, so a seed requires
the class to be **FIXED**. A still-ACTIVE class reproduces its founding sub-code
and fails cert_regression_corpus on EVERY DEPLOY. A high "failed jobs" count
here is therefore a reason NOT to seed, not a reason to — it means the class is
alive. Read this output as "is a seed POSSIBLE", never as "should I seed".

A sub-code with no captured source cannot be seeded, and saying so is the
result — inventing a key would make the gate green against a file that does not
exist, which is worse than the gap.
"""
import os, modal
from collections import Counter
app = modal.App("probe-corpus-seeds")
img = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S=[modal.Secret.from_name("promptly-secrets")]
# The classes that ACTUALLY recur and have no seed, by live frequency — not the
# four that were queued by name, three of which have never fired. A seed only
# means something for a class that can come back.
WANT = ("freeze", "dead_moment", "black", "audio_extract_stream_map",
        "ladder_exhausted:RuntimeError", "ladder_exhausted:TypeError",
        "component_crash", "delay_render", "unclassified")

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
            # A class with recent failures is ALIVE — seeding it breaks every
            # deploy. Flag that here rather than letting a green tick imply go.
            _flag = ("  ⚠️  STILL ACTIVE — do NOT seed" if v["jobs"] > 0 else "")
            print(f"  {'⚠️ ' if v['jobs'] else '✅'} {w:<22} {v['jobs']} failed job(s), "
                  f"SOURCE CAPTURED{_flag}")
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
