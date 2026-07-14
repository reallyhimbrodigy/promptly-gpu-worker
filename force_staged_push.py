"""FORCE-INJECT StagedPush (Zac 2026-07-13, Phase 4 render-path proof). The verification
source has no genuine building phrase, so Gemini (correctly) never fired StagedPush. To
prove the FULL render path end-to-end on real footage, monkeypatch generate_edit_gemini to
convert the strongest emphasis into a StagedPush over 3 CONSECUTIVE kept words at mid_peak,
render, and report the injected words + their audible onsets + the render URL. Then frame-
check the peaks land on those words on the actual source.

  modal run force_staged_push.py
"""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-force-staged",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_forced():
    import io,os,time,contextlib,boto3,json
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/stagedpush-forced/forced-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={}

    # ── force-inject: convert the strongest emphasis to StagedPush over 3 consecutive words ──
    _orig_gen=H.generate_edit_gemini
    def _gen(*a,**k):
        _plan=_orig_gen(*a,**k)
        try:
            _ems=_plan.get("emphasis_moments") or []
            # pick the emphasis with a word_indices[0] that has room for +1,+2 consecutive
            for _m in sorted(_ems, key=lambda m: 0 if str(m.get("intensity"))=="high" else 1):
                _w0=(_m.get("word_indices") or [None])[0]
                if isinstance(_w0,int):
                    _m["word_indices"]=[_w0,_w0+1,_w0+2]      # 3 consecutive (talking-head speech is dense)
                    _m["type"]="revelation"; _m["intensity"]="high"
                    _m["zoom_effect"]={"type":"StagedPush","arc_position":"mid_peak"}
                    _m["motion_graphic"]=None
                    tap["injected_word_indices"]=[_w0,_w0+1,_w0+2]
                    break
        except Exception as e:
            tap["inject_err"]=str(e)[:200]
        return _plan
    H.generate_edit_gemini=_gen

    _orig_rmc=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        try:
            _dg=edit_plan.get("_deepgram_words") or []
            # read the CLIP's merged _zoom_effect (what actually renders), not the plan emphasis
            for _ci,_c in enumerate(cuts or []):
                _ze=(_c.get("_zoom_effect") or _c.get("zoom_effect") or {})
                if _ze.get("type")=="StagedPush":
                    _stgs=(_ze.get("events") or [{}])[0].get("stages") or []
                    tap.setdefault("staged_clips",[]).append({
                        "clip":_ci,"stages_absMs":[s.get("atMs") for s in _stgs],
                        "stage_scales":[s.get("scale") for s in _stgs],
                        "cutTerminated":(_ze.get("events") or [{}])[0].get("cutTerminated")})
            for _m in (edit_plan.get("emphasis_moments") or []):
                if (_m.get("zoom_effect") or {}).get("type")=="StagedPush":
                    _wis=_m.get("word_indices") or []
                    tap["staged"]={"word_indices":_wis,
                                   "words":[(_dg[i].get("word") if 0<=i<len(_dg) else "?") for i in _wis],
                                   "word_onsets_s":[round(H._audible_word_onset_s(_dg,i),3) for i in _wis if 0<=i<len(_dg)]}
        except Exception as e: tap["tap_err"]=str(e)[:200]
        return _orig_rmc(source_path,cuts,edit_plan,*a,**k)
    H.render_multi_clip=_rmc

    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"forcestaged-{ts}","video_url":src,
                "vibe":"high energy and punchy","user_id":"force-staged",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:400]}"
    _log=buf.getvalue()
    import re as _re
    _zl=[l.strip()[:200] for l in _log.splitlines() if _re.search(r"zoom-event.*StagedPush|StagedPush",l)][:6]
    return json.dumps({"err":err,"url":CF+okey,"tap":tap,"zoom_lines":_zl},default=str)


@app.local_entrypoint()
def main():
    import json
    r=json.loads(render_forced.remote())
    print("\nFORCE_STAGED_DONE")
    print(f"  err: {r.get('err')}")
    print(f"  url: {r.get('url')}")
    print(f"  injected_word_indices: {r.get('tap',{}).get('injected_word_indices')}")
    _s=r.get('tap',{}).get('staged')
    if _s:
        print(f"  StagedPush fired on words: {_s['words']}")
        print(f"  word audible onsets (s): {_s['word_onsets_s']}   <-- the stage PEAKS must land here")
    print(f"  CLIP staged zoom (what renders): {r.get('tap',{}).get('staged_clips')}")
    print(f"  tap_err: {r.get('tap',{}).get('tap_err')}  inject_err: {r.get('tap',{}).get('inject_err')}")
    for l in r.get('zoom_lines',[]): print(f"    · {l}")
