import os, json, modal
app = modal.App("harvest-plan")
img = modal.Image.debian_slim().pip_install(["supabase","boto3"])
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=img, secrets=S, timeout=600)
def go(jid: str):
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r=sb.table("video_jobs").select("id,status,result").eq("id",jid).limit(1).execute()
    x=(r.data or [{}])[0]
    res=x.get("result") if isinstance(x.get("result"),dict) else {}
    stt=res.get("stage_timings") or {}
    rc=res.get("edit_recipe") or {}
    rc=rc.get("plan") if isinstance(rc,dict) and isinstance(rc.get("plan"),dict) else rc
    return {"hls":stt.get("hls"),"render":stt.get("render"),"total":stt.get("total"),
            "route":res.get("route"),"pool":stt.get("pool_task_s") or {},
            "plan":rc if isinstance(rc,dict) else None,
            "cuts":len(rc.get("cuts") or []) if isinstance(rc,dict) else 0,
            "zooms":len(rc.get("zoom") or []) if isinstance(rc,dict) else 0}
@app.local_entrypoint()
def main(jid: str = ""):
    d=go.remote(jid)
    print(f"\n  route={d['route']}  total={d['total']}s  render={d['render']}s")
    print(f"  *** stage_timings.hls (STD-EDITORIAL, first ever recorded) = {d['hls']}s ***")
    print(f"  pool_task_s: {d['pool']}")
    print(f"  plan: cuts={d['cuts']} zooms={d['zooms']}")
    if d["plan"]:
        json.dump(d["plan"], open("/tmp/harvested_plan.json","w"))
        print(f"  plan saved -> /tmp/harvested_plan.json ({len(json.dumps(d['plan']))} bytes)")
