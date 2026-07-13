"""CAPTION ENTRANCE PROOF (Zac 2026-07-13, 4th pass). Same source under FOUR forced
caption styles — the ones that had the most entrance motion — so the frame-1-is-final
fix is judgeable across styles, not one. Every caption should POP into final position
instantly: zero float-up, zero slide, zero grow-in, zero ghost.

  modal run caption_proof.py

SEQUENTIAL (Vertex quota — parallel renders 429 the b-roll visual pick)."""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-caption-proof",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"

# the 4 styles that had the most entrance motion (best proof they're now instant)
STYLES=["Gadzhi", "TwoTone", "Prime", "CleanCut"]


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_style(style):
    import io,os,time,contextlib,boto3,json
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/caption/{style}-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    _tap={}
    _orig=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        try: _tap["caption_style"]=edit_plan.get("caption_style")
        except Exception: pass
        return _orig(source_path,cuts,edit_plan,*a,**k)
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None
    try:
        with contextlib.redirect_stdout(buf):
            H.handler({"input":{"job_id":f"cap-{style}-{ts}","video_url":src,
                "vibe":f"fast-paced and punchy, use {style} captions","user_id":"caption-proof",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:300]}"
    return json.dumps({"style":style,"rendered_style":_tap.get("caption_style"),"err":err,"url":CF+okey})


@app.local_entrypoint()
def main():
    import json
    out=[]
    for st in STYLES:
        out.append(json.loads(render_style.remote(st)))
    print("\nCAPTION_PROOF_DONE")
    for r in out:
        print(f"  {r['style']:<10} (rendered: {r.get('rendered_style')})  err={r.get('err')}")
        print(f"     {r['url']}")
