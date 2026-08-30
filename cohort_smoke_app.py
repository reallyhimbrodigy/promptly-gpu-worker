"""COHORT SMOKE — is the armed cohort actually RECORDING? Not a result.

Deployed and armed is not working. This checks only that the instrumentation
fires: seam_arm present, both arms appearing, seams_narrow populated on rows
after v593. A broken cohort discovered on day 10 costs ten days.

Explicitly NOT a health check (that is day 3) and NOT a result (day 10).
"""
import os, modal
from collections import Counter
app = modal.App("cohort-smoke")
image = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=image, secrets=S, timeout=600)
def q(since: str) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = (sb.table("video_jobs").select("id,result,demo,created_at")
         .gte("created_at", since).eq("status","completed")
         .order("created_at", desc=True).limit(300).execute())
    arms=Counter(); narrow_present=0; offered_present=0; n=0; samples=[]
    for x in (r.data or []):
        if x.get("demo"): continue
        res=x.get("result") or {}
        if str(res.get("route") or "std-editorial") != "std-editorial": continue
        st=res.get("stage_timings") or {}
        n+=1
        arms[str(st.get("seam_arm") or "<ABSENT>")]+=1
        if st.get("seams_narrow") is not None: narrow_present+=1
        if st.get("seams_offered") is not None: offered_present+=1
        if len(samples)<5:
            samples.append({"arm":st.get("seam_arm"),"narrow":st.get("seams_narrow"),
                            "offered":st.get("seams_offered"),"at":str(x.get("created_at"))[:19]})
    return {"n":n,"arms":dict(arms),"narrow":narrow_present,"offered":offered_present,
            "samples":samples}
@app.local_entrypoint()
def main(since: str = "2026-08-30T18:38:00+00:00"):
    d=q.remote(since)
    print(f"\n  std-editorial completions since v593: {d['n']}")
    if not d["n"]:
        print("  NO TRAFFIC YET — absent read, not a broken cohort.")
        import sys; sys.exit(9)
    print(f"  seam_arm       : {d['arms']}")
    print(f"  seams_narrow   : {d['narrow']}/{d['n']} populated")
    print(f"  seams_offered  : {d['offered']}/{d['n']} populated")
    for s in d["samples"]:
        print(f"      {s['at']}  arm={s['arm']}  narrow={s['narrow']} offered={s['offered']}")
    import sys
    ok = (d["narrow"] == d["n"] and "<ABSENT>" not in d["arms"])
    print(f"\n  RECORDING: {'YES' if ok else 'NO — instrumentation is not firing'}")
    # EXIT CODE IS THE CONTRACT (an `until` loop reads it, and a pipe would
    # destroy it — that mistake ended a watch after one poll earlier today).
    #   0  recording confirmed, stop watching
    #   9  no traffic yet, keep waiting
    #   1  traffic arrived and instrumentation is NOT firing — act now
    sys.exit(0 if ok else 1)

