import os, modal
app = modal.App("dbg-trip3")
image = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]

@app.function(image=image, secrets=S, timeout=900)
def go():
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out=[]; page=0
    while page<20 and len(out)<3:
        r=(sb.table("video_jobs").select("id,result,error_message,created_at")
           .gte("created_at","2026-08-10").order("created_at",desc=True)
           .range(page*500,page*500+499).execute())
        d=r.data or []
        for x in d:
            res=x.get("result") if isinstance(x.get("result"),dict) else {}
            if str(res.get("error_subcode") or "") != "freeze": continue
            out.append({"id":x["id"][:8],"created":str(x.get("created_at"))[:16],
                        "all_keys":sorted(res.keys())[:40],
                        "err_keys":{k:str(res[k])[:600] for k in res
                                    if "err" in k.lower() or "integ" in k.lower()
                                    or "ig_" in k.lower() or k in ("freeze","spans")}})
            if len(out)>=3: break
        if len(d)<500: break
        page+=1
    return out

@app.local_entrypoint()
def main():
    rows=go.remote()
    print(f"\n=== {len(rows)} freeze trips, FULL error surface as persisted ===")
    for r in rows:
        print(f"\n== {r['id']}  {r['created']}")
        print(f"   result keys: {r['all_keys']}")
        for k,v in sorted(r["err_keys"].items()):
            print(f"   {k} = {v}")
