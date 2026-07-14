"""STAGEDPUSH NATURAL TEST (Zac 2026-07-13). Zac's real source with a stat/number reveal.
Run it through the FULL pipeline on a viral/punchy vibe — NO injection — and see whether
Gemini fires StagedPush NATURALLY on the building phrase. Taps the transcript (to see the
phrase), the emphases + zoom types, and (if it fired) the stages ON THE CLIP + the words.
If it does NOT fire, that's diagnostic: report the transcript + emphases so we can see why.

  modal run staged_push_real.py
"""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-stagedpush-real",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
SRC_KEY="sources/seam-tests/stagedpush-real/IMG_5260-1783994675.mov"


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_real(vibe, tag):
    import io,os,time,contextlib,boto3,json
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":SRC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/stagedpush-real/out-{tag}-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={}
    _orig=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        try:
            _dg=edit_plan.get("_deepgram_words") or []
            tap["transcript"]=" ".join(str(w.get("word") or "") for w in _dg)
            _em=edit_plan.get("emphasis_moments") or []
            _zooms=[]; _staged=[]
            for m in _em:
                _ze=(m.get("zoom_effect") or {}); _zt=_ze.get("type")
                if _zt: _zooms.append(_zt)
                if _zt=="StagedPush":
                    _wis=m.get("word_indices") or []
                    _staged.append({"word_indices":_wis,
                                    "words":[(_dg[i].get("word") if 0<=i<len(_dg) else "?") for i in _wis],
                                    "onsets_s":[round(H._audible_word_onset_s(_dg,i),3) for i in _wis if 0<=i<len(_dg)]})
            # clip-level: what actually renders
            _clip_staged=[]
            for _ci,_c in enumerate(cuts or []):
                _cze=(_c.get("_zoom_effect") or _c.get("zoom_effect") or {})
                if _cze.get("type")=="StagedPush":
                    _ev=(_cze.get("events") or [{}])[0]
                    _clip_staged.append({"clip":_ci,"stages":_ev.get("stages"),"cutTerminated":_ev.get("cutTerminated")})
            from collections import Counter
            tap["zoom_distribution"]=dict(Counter(_zooms))
            tap["staged_push_emphases"]=_staged
            tap["staged_push_on_clip"]=_clip_staged
            tap["n_emphasis"]=len(_em)
        except Exception as e: tap["tap_err"]=str(e)[:200]
        return _orig(source_path,cuts,edit_plan,*a,**k)
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"spreal-{tag}-{ts}","video_url":src,
                "vibe":vibe,"user_id":"stagedpush-real",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:400]}"
    _log=buf.getvalue()
    import re as _re
    _zl=[l.strip()[:200] for l in _log.splitlines() if _re.search(r"StagedPush|zoom-event",l)][:8]
    return json.dumps({"tag":tag,"vibe":vibe,"err":err,"url":CF+okey,"tap":tap,"zoom_lines":_zl},default=str)


@app.local_entrypoint()
def main():
    import json
    out=json.loads(render_real.remote("high energy, punchy, viral — really sell the big number", "viral"))
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
         "0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad/staged_real.json","w").write(json.dumps(out,indent=1))
    print("\nSTAGEDPUSH_REAL_DONE")
    k=out.get("tap",{})
    print(f"  err: {out.get('err')}")
    print(f"  url: {out.get('url')}")
    print(f"  TRANSCRIPT: {k.get('transcript')}")
    print(f"  zoom distribution: {k.get('zoom_distribution')}  (of {k.get('n_emphasis')} emphases)")
    print(f"  StagedPush FIRED (emphasis): {k.get('staged_push_emphases')}")
    print(f"  StagedPush ON CLIP (renders): {k.get('staged_push_on_clip')}")
    for l in out.get('zoom_lines',[]): print(f"    · {l}")
