"""Did the new diagnostic actually emit? Read error_detail on one job."""
import json, os, modal
app = modal.App("check-trip-echo")
image = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]

@app.function(image=image, secrets=S, timeout=600)
def go(jid: str):
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r=sb.table("video_jobs").select("status,result").eq("id",jid).limit(1).execute()
    x=(r.data or [{}])[0]
    res=x.get("result") if isinstance(x.get("result"),dict) else {}
    return {"status":x.get("status"),
            "code":str(res.get("error_code") or ""),
            "sub":str(res.get("error_subcode") or ""),
            "detail":str(res.get("error_detail") or "")}

@app.local_entrypoint()
def main(job: str = ""):
    jid = job or json.load(open("/tmp/arm_confirm_job.json"))["job_id"]
    d=go.remote(jid)
    print(f"\n  job {jid[:8]}  status={d['status']}  {d['code']}:{d['sub']}")
    print(f"  error_detail: {d['detail']}")
    if d["code"] == "INTEGRITY_TRIP":
        if "[echo:" in d["detail"]:
            print("\n  ✅ THE DIAGNOSTIC EMITTED. Before this fix, a freeze trip")
            print("     persisted with an EMPTY gap here — 0 of 22 carried one.")
        else:
            print("\n  ❌ still no echo — the fix did not reach this path")
    elif d["status"] == "completed":
        print("\n  completed, no trip. ABSENT read for the echo — the trip is not")
        print("  deterministic on this source, so this run cannot show the fix.")
