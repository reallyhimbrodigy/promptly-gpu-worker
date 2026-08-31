import os, json, modal
app = modal.App("probe-plan-avail")
img = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=img, secrets=S, timeout=600)
def go(ids: list):
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out=[]
    for jid in ids:
        r=sb.table("video_jobs").select("id,status,result").eq("id",jid).limit(1).execute()
        x=(r.data or [{}])[0]
        res=x.get("result") if isinstance(x.get("result"),dict) else {}
        rc=res.get("edit_recipe") or {}
        rc=rc.get("plan") if isinstance(rc,dict) and isinstance(rc.get("plan"),dict) else rc
        out.append({"id":str(x.get("id"))[:8],"status":x.get("status"),
                    "has_plan":isinstance(rc,dict) and bool(rc.get("cuts")),
                    "cuts":len(rc.get("cuts") or []) if isinstance(rc,dict) else 0,
                    "zooms":len(rc.get("zoom") or []) if isinstance(rc,dict) else 0,
                    "keys":sorted(rc)[:10] if isinstance(rc,dict) else []})
    return out
@app.local_entrypoint()
def main():
    ids=["579dcbe6-5ca5-4e6f-b2f2-3c70da557358","80e7f739-0a4d-4a3d-9f6e-000000000000",
         "6dd0e91e-17d9-45a3-b45c-65c84dd7ac54","0b126e83-b56b-4047-aff6-e86da25bc8b1",
         "e2d35b3e-cfc7-4b35-be0f-9c3740a6b3fe"]
    for r in go.remote(ids):
        print(f"  {r['id']}  status={r['status']:<10} plan={r['has_plan']} "
              f"cuts={r['cuts']} zooms={r['zooms']}")
        if r['keys']: print(f"      keys: {r['keys']}")
