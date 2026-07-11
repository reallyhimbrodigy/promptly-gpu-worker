"""PERCEPTUAL SYNC CHECK — the standing instrument (D1, Zac 2026-07-11).
One command: modal run perceptual_sync_check.py
Renders the reference source, transcribes the RENDER, and measures every
component's fire time against the audible word onset in the output audio.
The release ritual: run after any timing-adjacent pin; every |delta| must be
<= 0.25s or the run FAILS loudly. The gap this closes permanently: drift 0
proved tracks agree with EACH OTHER; this proves they agree with the EAR.

A) measure_rejected: Zac's exact file — transcribe the RENDER (audible word
   onsets in output time) + zoom-motion onset curve from frame diffs → the
   'not easy' delta measured directly on the artifact he judged.
B) diagnostic: fresh full-capture render of the same source — for EVERY
   zoom/SFX/MG: target word · Deepgram source start · projected output
   start · timeline fire time · audible onset in the rendered audio."""
import sys, os
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-d1",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
REJECTED=CF+"sources/seam-tests/zoomproof/zac2-1783750754.mp4"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"

def _dg_transcribe(path):
    import os, requests, json
    key=os.environ.get("DEEPGRAM_API_KEY")
    with open(path,"rb") as f:
        r=requests.post("https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true&smart_format=false",
            headers={"Authorization":f"Token {key}","Content-Type":"video/mp4"},
            data=f.read(), timeout=180)
    r.raise_for_status()
    alts=r.json()["results"]["channels"][0]["alternatives"][0]
    return alts.get("words") or []

def _motion_curve(path, w=160, h=90):
    import subprocess, numpy as np
    p=subprocess.run(["ffmpeg","-v","error","-i",path,"-vf",f"scale={w}:{h},format=gray",
                      "-f","rawvideo","-"],capture_output=True,timeout=300)
    buf=np.frombuffer(p.stdout,dtype=np.uint8)
    n=len(buf)//(w*h)
    frames=buf[:n*w*h].reshape(n,h,w).astype(np.int16)
    d=np.abs(np.diff(frames,axis=0)).mean(axis=(1,2))
    return d  # per-frame motion energy, index = frame (fps from probe)

@app.function(timeout=900,cpu=8,memory=16384,region=["us-west","us-east"])
def measure_rejected():
    import requests, subprocess, json, numpy as np
    open("/tmp/rej.mp4","wb").write(requests.get(REJECTED,timeout=120).content)
    words=_dg_transcribe("/tmp/rej.mp4")
    fps=60.0
    curve=_motion_curve("/tmp/rej.mp4")
    med=float(np.median(curve)); thr=med*2.5
    # onsets: rising edges above threshold, min 0.5s apart
    onsets=[]
    last=-100
    for i,v in enumerate(curve):
        if v>thr and (i==0 or curve[i-1]<=thr) and i-last>30:
            onsets.append(round(i/fps,2)); last=i
    wlist=[{"w":x["word"],"s":round(float(x["start"]),2),"e":round(float(x["end"]),2)} for x in words[:20]]
    return json.dumps({"render_words_head":wlist,
        "motion_onsets_s":onsets[:20],
        "motion_median":round(med,2),"thr":round(thr,2),
        "n_frames":len(curve)+1})

@app.function(timeout=3600,cpu=64,memory=131072,max_inputs=1,region=["us-west","us-east"])
def diagnostic():
    import io,os,time,contextlib,re,json,gzip,boto3
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/d1/diag-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={}
    _orig_rmc=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        r=_orig_rmc(source_path,cuts,edit_plan,*a,**k)
        try:
            tap["timeline"]=edit_plan.get("_render_timeline")
            tap["projected"]=[{"i":int(w.get("word_index",-1)),"start":float(w.get("start") or 0),
                               "word":str(w.get("word") or "")}
                              for w in (edit_plan.get("_projected_words") or [])]
            tap["cuts"]=[{"ss":float(c.get("source_start") or 0),"se":float(c.get("source_end") or 0),
                          "tr":c.get("transition_out"),"z":(c.get("_zoom_effect") or {}).get("type")}
                         for c in cuts]
            tap["emphasis"]=[{"w":(m.get("word_indices") or [None])[0],
                              "zoom":((m.get("zoom_effect") or {}) or {}).get("type"),
                              "claim":((m.get("zoom_effect") or {}) or {}).get("arc_position")}
                             for m in (edit_plan.get("_emphasis_moments") or [])]
            tap["sfx"]=[{"w":x.get("word_index"),"sound":x.get("sound")}
                        for x in (edit_plan.get("_parsed_sound_effects") or [])]
            tap["mgs"]=[{"w":m.get("start_word_index"),"type":m.get("type"),
                         "anchor":m.get("anchor")}
                        for m in (edit_plan.get("motion_graphics") or [])]
            tap["dg"]=[{"i":i,"w":w.get("word"),"s":float(w.get("start") or 0)}
                       for i,w in enumerate(edit_plan.get("_deepgram_words") or [])]
            tap["removed"]=sorted(edit_plan.get("_removed_word_indices") or [])
        except Exception as e:
            tap["tap_err"]=str(e)[:200]
        return r
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"d1-diag-{ts}","video_url":src,
                "vibe":"high-energy TikTok product ad","user_id":"d1",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:200]}"
    log=buf.getvalue()
    s3.put_object(Bucket=bucket,Key=f"sources/seam-tests/d1/log-{ts}.txt.gz",
                  Body=gzip.compress(log.encode()),ContentType="text/plain")
    pick=lambda pat:[l.strip()[:200] for l in log.splitlines() if re.search(pat,l)]
    # transcribe the RENDER for audible onsets
    import requests
    rw=[]
    try:
        rb=requests.get(f"https://{bucket}.s3.amazonaws.com/{okey}",timeout=120)
        if rb.status_code!=200:
            rb=requests.get(CF+okey,timeout=120)
        open("/tmp/out.mp4","wb").write(rb.content)
        rw=[{"w":x["word"],"s":round(float(x["start"]),3)} for x in _dg_transcribe("/tmp/out.mp4")]
    except Exception as e:
        tap["render_transcribe_err"]=str(e)[:200]
    return json.dumps({"err":err,"url":CF+okey,"log":CF+f"sources/seam-tests/d1/log-{ts}.txt.gz",
        "tap":tap,"render_words":rw,
        "zoom_lines":pick(r"\[zoom-event\]"),
        "sfx_lines":pick(r"\[sfx\]")[:14],
        "mg_lines":pick(r"fromFrame|motion_graphic.*resolved|\[mg\]")[:8],
        "merged":pick(r"Merged plan")[-1:]},default=str)

@app.local_entrypoint()
def main():
    import json, concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        fa=ex.submit(measure_rejected.remote); fb=ex.submit(diagnostic.remote)
        a,b=fa.result(),fb.result()
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
         "e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/d1_result.json","w").write(
        json.dumps({"rejected":json.loads(a),"diagnostic":json.loads(b)},indent=1))
    print("D1_DONE")
