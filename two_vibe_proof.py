"""TWO-VIBE PROOF (Part 2, Zac 2026-07-12). ONE source, rendered twice under two
vibes — corporate vs viral — to prove the palette split lands: does corporate come
back genuinely restrained (QUIET SFX / CleanCut captions / structural MGs) and
viral genuinely punchy (booms+dings / kinetic captions), from IDENTICAL input?

  modal run two_vibe_proof.py

Captures each render's tonal fingerprint (SFX sounds, caption styles, MG types,
classified family) so the split is auditable in numbers, not just to the eye —
then leaves two output URLs for Zac to judge."""
import sys, os
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-two-vibe",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"

CORPORATE="a clean, restrained corporate product explainer"
VIRAL="a high-energy viral TikTok hype reel"


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_vibe(vibe, tag):
    import io,os,time,contextlib,re,json,gzip,boto3
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/vibe/{tag}-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={"vibe":vibe}
    _orig_rmc=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        r=_orig_rmc(source_path,cuts,edit_plan,*a,**k)
        try:
            # tonal fingerprint — what the palette actually produced
            tap["sfx"]=sorted([x.get("sound") for x in (edit_plan.get("_parsed_sound_effects") or []) if x.get("sound")])
            tap["emphasis_sounds"]=sorted([m.get("sound") for m in (edit_plan.get("_emphasis_moments") or []) if m.get("sound") and m.get("sound")!="voice"])
            tap["caption_styles"]=sorted({(c.get("caption_style") or "?") for c in cuts})
            tap["mg_types"]=sorted([m.get("type") for m in (edit_plan.get("motion_graphics") or []) if m.get("type")])
            tap["n_cuts"]=len(cuts)
            tap["transitions"]=sorted({(c.get("transition_out") or "cut") for c in cuts})
        except Exception as e:
            tap["tap_err"]=str(e)[:200]
        return r
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"vibe-{tag}-{ts}","video_url":src,
                "vibe":vibe,"user_id":"vibe-proof",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:300]}"
    log=buf.getvalue()
    s3.put_object(Bucket=bucket,Key=f"sources/seam-tests/vibe/log-{tag}-{ts}.txt.gz",
                  Body=gzip.compress(log.encode()),ContentType="text/plain")
    pick=lambda pat,n:[l.strip()[:220] for l in log.splitlines() if re.search(pat,l)][:n]
    return json.dumps({"tag":tag,"vibe":vibe,"err":err,"url":CF+okey,
        "log":CF+f"sources/seam-tests/vibe/log-{tag}-{ts}.txt.gz","tap":tap,
        "palette_lines":pick(r"\[obedience\]|palette|vibe.*famil|classif",6),
        "merged":pick(r"Merged plan",1)},default=str)


@app.local_entrypoint()
def main():
    import json, concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        fc=ex.submit(render_vibe.remote, CORPORATE, "corporate")
        fv=ex.submit(render_vibe.remote, VIRAL, "viral")
        c,v=fc.result(),fv.result()
    out={"corporate":json.loads(c),"viral":json.loads(v)}
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
         "0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad/two_vibe_result.json","w").write(json.dumps(out,indent=1))
    print("TWO_VIBE_DONE")
    for k in ("corporate","viral"):
        r=out[k]; t=r.get("tap",{})
        print(f"\n=== {k.upper()} ({r.get('vibe')}) family={t.get('family')} err={r.get('err')}")
        print(f"  url: {r.get('url')}")
        print(f"  sfx: {t.get('sfx')}")
        print(f"  emphasis_sounds: {t.get('emphasis_sounds')}")
        print(f"  caption_styles: {t.get('caption_styles')}")
        print(f"  mg_types: {t.get('mg_types')}")
        print(f"  transitions: {t.get('transitions')}  n_cuts={t.get('n_cuts')}")
