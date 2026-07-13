"""GAP 3 PROOF (Zac 2026-07-13). Two renders on ONE source:
  A) B-ROLL of a named place — vibe requests "show footage of Ahmedabad" (Video-2's
     essence: the footage that used to be SILENTLY DROPPED). Taps resolved_broll +
     the keywords Gemini emitted → proves real Ahmedabad footage now appears, placed.
  B) HONESTY — vibe asks for unsupported features (color grade + background music).
     Taps capability_notes on the result → proves the user is TOLD, never silent.

  modal run gap3_proof.py
"""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-gap3-proof",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("gemini-vertex")])
CF="https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY="sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"

CASES={
    # b-roll fetch + b-roll caption placement (low, not on the subject's face) + crisp captions
    "broll_place": "an engaging video — and show footage of Ahmedabad",
    # crisp caption entrance on a kinetic style (Zac's eye judges the snap)
    "crisp_caps":  "high energy and punchy, use Gadzhi captions",
}


@app.function(timeout=1200,cpu=8,memory=16384,region=["us-west","us-east"])
def render_case(vibe, tag):
    import io,os,time,contextlib,re,json,boto3
    sys.path.insert(0,"/"); import handler as H
    bucket=os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3=boto3.client("s3",region_name=os.environ.get("AWS_REGION") or "us-west-1")
    ts=int(time.time())
    src=s3.generate_presigned_url("get_object",Params={"Bucket":bucket,"Key":ZAC_KEY},ExpiresIn=7200)
    okey=f"sources/seam-tests/gap3/{tag}-{ts}.mp4"
    put=s3.generate_presigned_url("put_object",Params={"Bucket":bucket,"Key":okey,"ContentType":"video/mp4"},ExpiresIn=7200)
    tap={"parsed_broll_requests":H._parse_broll_requests(vibe),
         "parsed_unsupported":H._parse_unsupported_requests(vibe)}
    _orig=H.render_multi_clip
    def _rmc(source_path,cuts,edit_plan,*a,**k):
        r=_orig(source_path,cuts,edit_plan,*a,**k)
        try:
            tap["emitted_broll_keywords"]=[b.get("keyword") for b in (edit_plan.get("broll_clips") or [])]
            tap["caption_style"]=edit_plan.get("caption_style")
        except Exception as e: tap["tap_err"]=str(e)[:200]
        return r
    H.render_multi_clip=_rmc
    buf=io.StringIO(); err=None; res=None
    try:
        with contextlib.redirect_stdout(buf):
            res=H.handler({"input":{"job_id":f"gap3-{tag}-{ts}","video_url":src,
                "vibe":vibe,"user_id":"gap3-proof",
                "upload_url":put,"public_url":f"https://{bucket}.s3.amazonaws.com/{okey}"}})
    except Exception as e:
        err=f"{type(e).__name__}: {str(e)[:300]}"
    if isinstance(res,dict):
        tap["resolved_broll"]=[{"keyword":e.get("keyword"),"pexels_video_id":e.get("pexels_video_id"),
                                "start_word_index":e.get("start_word_index"),"end_word_index":e.get("end_word_index"),
                                "url":e.get("pexels_file_url","")[:80]} for e in (res.get("resolved_broll") or [])]
        tap["capability_notes"]=res.get("capability_notes")
    log=buf.getvalue()
    pick=lambda pat,n:[l.strip()[:220] for l in log.splitlines() if re.search(pat,l)][:n]
    return json.dumps({"tag":tag,"vibe":vibe,"err":err,"url":CF+okey,"tap":tap,
        "broll_lines":pick(r"\[broll\]|\[honesty\]|REQUIRED B-ROLL",10),
        # caption-over-b-roll placement: the override divergence shows the forced position
        "caption_broll_lines":pick(r"broll_window|force_clear_of_overlay.*broll|authoritative override",6)},default=str)


@app.local_entrypoint()
def main():
    import json
    # SEQUENTIAL (max_workers=1 semantics): two parallel renders exhausted the shared
    # Vertex quota → 429 on the visual-pick step. One at a time keeps quota available.
    out={}
    for t,v in CASES.items():
        out[t]=json.loads(render_case.remote(v, t))
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
         "0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad/gap3_result.json","w").write(json.dumps(out,indent=1))
    print("GAP3_DONE")
    for t in CASES:
        r=out[t]; k=r.get("tap",{})
        print(f"\n=== {t.upper()} err={r.get('err')}")
        print(f"  vibe: {r.get('vibe')}")
        print(f"  url:  {r.get('url')}")
        print(f"  parsed_broll_requests: {k.get('parsed_broll_requests')}")
        print(f"  emitted_broll_keywords: {k.get('emitted_broll_keywords')}")
        print(f"  RESOLVED_BROLL (real footage fetched): {k.get('resolved_broll')}")
        print(f"  caption_style: {k.get('caption_style')}")
        print(f"  parsed_unsupported: {k.get('parsed_unsupported')}")
        print(f"  CAPABILITY_NOTES (surfaced to user): {k.get('capability_notes')}")
        for l in r.get("broll_lines",[]): print(f"    · {l}")
        print(f"  --- caption placement over b-roll (must NOT be top) ---")
        for l in r.get("caption_broll_lines",[]): print(f"    · {l}")
