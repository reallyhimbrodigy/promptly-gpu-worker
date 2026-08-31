"""What did the FREEZE discriminator see? The [echo:] line is the diagnostic.

The gate builds `_ig_why` before raising:
    [echo: source=Y/MISSING map=<t>/UNRESOLVED downgraded=N spans=a-b->c/d]
which says, per trip: did the SOURCE echo resolve at all, did the output->source
map resolve, how many spans were DOWNGRADED (explained away), and the actual
span geometry. That is the whole decision the discriminator made, persisted on
every trip — so the mechanism is readable without adding instrumentation.
"""
import os, re
from collections import Counter
import modal
app = modal.App("probe-freeze-echo")
image = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]

@app.function(image=image, secrets=S, timeout=900)
def scan(since: str):
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows=[];page=0
    while page<20:
        r=(sb.table("video_jobs").select("id,user_id,result,created_at,error_message")
           .gte("created_at",since).order("created_at",desc=True)
           .range(page*500,page*500+499).execute())
        d=r.data or []; rows.extend(d)
        if len(d)<500: break
        page+=1
    out=[]
    for x in rows:
        res=x.get("result") if isinstance(x.get("result"),dict) else {}
        msg=str(x.get("error_message") or "")
        det=str(res.get("error_detail") or "")
        # error_message is the USER-FACING copy ("We caught a rendering defect
        # on our side…"); the machine string lives in error_detail. Matching on
        # message+where alone returned 0 of 38 — a clean zero that contradicted
        # a number measured ten minutes earlier, which is the only reason it was
        # caught rather than reported.
        blob=msg+" "+det+" "+str(res.get("error_where") or "")
        if "INTEGRITY_TRIP" not in blob: continue
        out.append({"id":x.get("id"),"user":x.get("user_id"),
                    "sub":str(res.get("error_subcode") or ""),
                    "created":str(x.get("created_at")),
                    "msg":msg[:900],
                    "detail":det[:1500]})
    return out

@app.local_entrypoint()
def main(since: str = "2026-08-10"):
    rows=scan.remote(since)
    fz=[r for r in rows if r["sub"]=="freeze"]
    print(f"\n=== FREEZE trips: what the discriminator saw ({len(fz)} of {len(rows)}) ===")
    src=Counter(); mp=Counter(); dg=Counter(); nsp=Counter(); anyecho=0
    for r in fz:
        t=r["msg"]+" "+r["detail"]
        m=re.search(r"echo: source=(\S+)\s+map=(\S+)\s+downgraded=(\d+)\s+spans=([^\]]*)", t)
        if not m:
            src["(no echo in the row)"]+=1; continue
        anyecho+=1
        src[m.group(1)]+=1; mp[m.group(2)]+=1; dg[m.group(3)]+=1
        nsp[len([s for s in m.group(4).split(",") if s.strip()])]+=1
    print(f"  rows carrying the [echo:] diagnostic: {anyecho}/{len(fz)}")
    for lbl,c in (("source= (was the source readable)",src),
                  ("map=    (did output->source resolve)",mp),
                  ("downgraded= (spans explained away)",dg),
                  ("span count",nsp)):
        print(f"\n  {lbl}")
        for k,v in c.most_common(6): print(f"      {v:>4}  {k}")
    print(f"\n  SAMPLE MESSAGES (the geometry):")
    for r in fz[:5]:
        print(f"    {r['created'][:16]} {str(r['id'])[:8]}")
        print(f"      {(r['msg'] or r['detail'])[:280]}")

