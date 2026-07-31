"""B-ROLL GATE CERT (Flare quality campaign): run _verify_broll_content against
REAL clips — Zac's two reported-bad examples (must REJECT) + clean object/
environment clips (must KEEP). Ephemeral (`modal run`), never deployed."""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-broll-gate", image=image)
SECRETS=[modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("gemini-vertex")]

CASES = [
  # Zac's reported-bad examples — expect REJECT
  {"label":"ZAC phone-scrolling (record 10 videos)","expect":"REJECT","keyword":"person holding smartphone tapping screen to upload files","intent":"someone recording videos on their phone","url":"https://videos.pexels.com/video-files/9785305/9785305-hd_1080_2048_25fps.mp4"},
  {"label":"ZAC creepy-man (editing)","expect":"REJECT","keyword":"frustrated creator editing video on laptop late at night moody","intent":"editing a video","url":"https://videos.pexels.com/video-files/33812577/14351086_1080_1920_60fps.mp4"},
  {"label":"editing-timeline (stranger back + screen)","expect":"REJECT","keyword":"complex video editing timeline software interface on computer monitor","intent":"video editing software","url":"https://videos.pexels.com/video-files/8100345/8100345-hd_1080_2048_25fps.mp4"},
  # clean object/environment controls — expect KEEP
  {"label":"CTRL camping tent nature","expect":"KEEP","keyword":"morning camping trip campsite tent nature outdoor","intent":"a campsite in nature","url":"https://videos.pexels.com/video-files/5993978/5993978-hd_1080_2048_25fps.mp4"},
]

@app.function(secrets=SECRETS, timeout=1200, cpu=8.0, memory=16384)
def run() -> dict:
    import subprocess, urllib.request, traceback, uuid
    os.environ["APP_URL"]=""
    import handler as H
    out={"cases":[]}
    for i,c in enumerate(CASES):
        work=f"/tmp/bg/{uuid.uuid4().hex[:8]}"; os.makedirs(work,exist_ok=True)
        path=os.path.join(work,f"clip_{i}.mp4")
        try:
            _req=urllib.request.Request(c["url"],headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"})
            with urllib.request.urlopen(_req,timeout=90) as r, open(path,"wb") as f: f.write(r.read())
            import time as _t; _t0=_t.time()
            keep,reason,is_err = H._verify_broll_content(path, c["keyword"], c["intent"], i, input_data={"broll_gate_test":True})
            _dt=round(_t.time()-_t0,1)
            verdict = ("ERROR" if is_err else ("KEEP" if keep else "REJECT"))
            out["cases"].append({"label":c["label"],"expect":c["expect"],"got":verdict,"ok":verdict==c["expect"],"call_s":_dt,"reason":reason[:140]})
        except Exception as e:
            out["cases"].append({"label":c["label"],"expect":c["expect"],"got":"ERROR","ok":False,"reason":f"{type(e).__name__}: {str(e)[:120]}"})
    out["pass"]=sum(1 for x in out["cases"] if x["ok"]); out["n"]=len(out["cases"])
    return out

@app.local_entrypoint()
def main():
    import json
    r=run.remote()
    print("\n===== B-ROLL GATE CERT =====")
    for c in r["cases"]: print(f"  [{'OK' if c['ok'] else 'XX'}] expect={c['expect']} got={c['got']} call={c.get('call_s','?')}s — {c['label']}: {c['reason']}")
    _times=[c.get('call_s') for c in r['cases'] if isinstance(c.get('call_s'),(int,float))]
    if _times: print(f"per-call vision latency: min={min(_times)}s max={max(_times)}s (CONCURRENT across N candidates ≈ max; $ ≈ N × one flash-vision call)")
    print(f"VERDICT: {r['pass']}/{r['n']} correct")
