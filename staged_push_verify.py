"""STAGEDPUSH VERIFICATION (Zac 2026-07-13, Phase 4 — the GATE). Render the same source
under several vibes and tap whether StagedPush fired, ON WHICH WORDS, and the overall zoom
distribution. The gate is RESERVED-NOT-SPRINKLED: StagedPush should fire on 0-2 genuine
2-3-word BUILDING phrases per video (never scattered), and should be SUPPRESSED entirely on
calm/corporate vibes (Fights). If it overuses or misfires, the usage guidance tightens.

  modal run staged_push_verify.py
"""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-stagedpush-verify",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"

CASES={
    "viral":     "high energy, punchy, viral — really sell the big numbers and claims",
    "corporate": "a clean, restrained, professional corporate explainer",
    "story":     "a calm, cinematic, reflective story",
}


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_case(vibe, tag):
    import io,os,time,contextlib,boto3,json
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/stagedpush-v/{tag}-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={}
    _orig=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        try:
            _dg=edit_plan.get("_deepgram_words") or edit_plan.get("_projected_words") or []
            _word=lambda i: (_dg[i].get("word") if 0<=i<len(_dg) else f"#{i}")
            _em=edit_plan.get("emphasis_moments") or edit_plan.get("_emphasis_moments") or []
            _zooms=[]; _staged=[]
            for m in _em:
                _ze=(m.get("zoom_effect") or {})
                _zt=_ze.get("type")
                if _zt: _zooms.append(_zt)
                if _zt=="StagedPush":
                    _wis=m.get("word_indices") or []
                    _stgs=(_ze.get("events") or [{}])[0].get("stages") or []
                    _staged.append({"word_indices":_wis,"words":[_word(i) for i in _wis],
                                    "n_stages":len(_stgs)})
            from collections import Counter
            tap["zoom_distribution"]=dict(Counter(_zooms))
            tap["staged_push_count"]=len(_staged)
            tap["staged_push_fired_on"]=_staged
            tap["n_emphasis"]=len(_em)
        except Exception as e: tap["tap_err"]=str(e)[:200]
        return _orig(source_path,cuts,edit_plan,*a,**k)
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"spv-{tag}-{ts}","video_url":src,
                "vibe":vibe,"user_id":"stagedpush-verify",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:300]}"
    _log=buf.getvalue()
    import re as _re
    _pick=[l.strip()[:200] for l in _log.splitlines() if _re.search(r"StagedPush|staged",l)][:8]
    return json.dumps({"tag":tag,"vibe":vibe,"err":err,"url":CF+okey,"tap":tap,"staged_lines":_pick},default=str)


@app.local_entrypoint()
def main():
    import json
    out={}
    for t,v in CASES.items():
        out[t]=json.loads(render_case.remote(v, t))
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
         "0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad/staged_verify.json","w").write(json.dumps(out,indent=1))
    print("\nSTAGEDPUSH_VERIFY_DONE")
    for t in CASES:
        r=out[t]; k=r.get("tap",{})
        print(f"\n=== {t.upper()} ({r.get('vibe')[:40]}) err={r.get('err')}")
        print(f"  url: {r.get('url')}")
        print(f"  StagedPush count: {k.get('staged_push_count')}  (RESERVED: expect 0-2; corporate/story expect 0)")
        print(f"  fired on: {k.get('staged_push_fired_on')}")
        print(f"  zoom distribution: {k.get('zoom_distribution')}  (of {k.get('n_emphasis')} emphases)")
