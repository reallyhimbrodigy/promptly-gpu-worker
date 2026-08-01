"""Verify (Zac 2026-08-01 ⚠️) the DEPLOYED per-stage cpu sampler reads CGROUP (not
psutil=0) on a REAL editorial render. Replicates run_pipeline_bg's cgroup reader +
per-stage bucketing around H.handler on a short coverage-passing clip. Non-zero
per-stage peaks = instrument good; zeros = still blind."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cgroup-verify", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"
@app.function(secrets=SECRETS, cpu=16.0, memory=131072, region="us", timeout=1800)
def run():
    import time, uuid, threading
    os.environ["APP_URL"]=""; os.environ["JOB_STATUS_WRITES_ENABLED"]=""
    sys.path.insert(0,"/"); import handler as H
    def rd():
        try:
            with open("/sys/fs/cgroup/cpu.stat") as f:
                for ln in f:
                    if ln.startswith("usage_usec"): return int(ln.split()[1])
        except Exception: pass
        for p in ("/sys/fs/cgroup/cpuacct/cpuacct.usage","/sys/fs/cgroup/cpu,cpuacct/cpuacct.usage","/sys/fs/cgroup/cpuacct.usage"):
            try:
                with open(p) as f: return int(f.read().strip())//1000
            except Exception: continue
        return None
    cg_ok = rd() is not None
    by={}; stop=threading.Event()
    def samp():
        lu=rd(); lt=time.monotonic()
        while not stop.wait(3.0):
            nt=time.monotonic(); nu=rd()
            if nu is None or lu is None or nt<=lt: lu,lt=nu,nt; continue
            cores=(nu-lu)/((nt-lt)*1e6); lu,lt=nu,nt
            try: stg=H._CPU_STAGE[0]
            except Exception: stg="?"
            by.setdefault(stg,[]).append(cores)
    th=threading.Thread(target=samp,daemon=True); th.start()
    jid=str(uuid.uuid4())
    body={"job_id":jid,"video_url":SRC,"vibe":"Clean engaging edit","user_id":"ec702499-ca10-49e6-8850-df8f99840904",
          "upload_url":f"https://thisismybucketagainwooo.s3.amazonaws.com/cgv/{jid}.mp4","public_url":f"https://thisismybucketagainwooo.s3.amazonaws.com/cgv/{jid}.mp4",
          "model":"flare","supports_progressive":False,"premium_pipeline_enabled":False}
    try: res=H.handler({"input":body})
    except Exception as e: res={"error":str(e)[:150]}
    stop.set()
    per={s:{"peak":round(max(v),1),"mean":round(sum(v)/len(v),1),"n":len(v)} for s,v in by.items() if v}
    return {"cgroup_readable":cg_ok,"per_stage_cores":per,"status":(res or {}).get("status"),"route":(res or {}).get("route")}
@app.local_entrypoint()
def main():
    print("CGVERIFY "+json.dumps(run.remote(),default=str))
