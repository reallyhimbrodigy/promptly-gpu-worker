import os, modal, json
app=modal.App("probe-cost"); img=modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=img,secrets=S,timeout=600)
def go(ids):
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
      os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out=[]
    for j in ids:
        r=sb.table("video_jobs").select("result").eq("id",j).limit(1).execute()
        res=(r.data or [{}])[0].get("result") or {}
        out.append({"j":j[:8],"cost":{k:v for k,v in res.items() if "cost" in k.lower()},
                    "stt_cost":{k:v for k,v in (res.get("stage_timings") or {}).items() if "cost" in k.lower()}})
    return out
@app.local_entrypoint()
def main():
    p=json.load(open("/tmp/micro_sweep_pairs.json"))
    for r in go.remote([x["job_id"] for x in p]):
        print(f"  {r['j']}  cost keys={r['cost']}  stage_timings cost={r['stt_cost']}")
