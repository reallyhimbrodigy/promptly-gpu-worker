"""Decor b-roll re-run (Zac 2026-08-01): does naming b-roll in decor_ground recover
broll_clips density (0.33 control -> 0.0 lean -> 0.07 old-decor)? control + decor(v2)
arms only, 16 real TH clips, PLAN_ONLY no render."""
import os,sys,json
from collections import Counter
sys.path.insert(0,"/")
import modal,modal_app
image=modal_app.image.add_local_file("modal_app.py","/modal_app.py")
app=modal.App("decor-reroll",image=image)
SECRETS=[modal.Secret.from_name("promptly-secrets"),modal.Secret.from_name("promptly-cloudfront"),modal.Secret.from_name("gemini-vertex"),modal.Secret.from_name("promptly-lang-flags")]
CLIPS=[
    ("c0", 'https://d1iax8jos987n3.cloudfront.net/sources/11d10886-8e7d-479d-b313-3007b22004d0/1785553314588-B557ABA6-09CD-47B4-BB56-7D3A59BFADF0_L0_001.mp4'),
    ("c1", 'https://d1iax8jos987n3.cloudfront.net/sources/e3756671-202d-4c67-9a33-97086f759ecc/1785551975768-6D051B2A-ED19-4778-AE4B-2671904314F6_L0_001.mp4'),
    ("c2", 'https://d1iax8jos987n3.cloudfront.net/sources/fc60800e-548c-4d5e-a800-c1092592aff9/1785551189136-95E88B2F-ACED-4D4A-B833-A9B5C44068FE_L0_001.mp4'),
    ("c3", 'https://d1iax8jos987n3.cloudfront.net/sources/63c1b134-0328-40ca-b949-639f5f74d552/1785395111241-D4F29537-8279-477A-948C-63019ACCEB53_L0_001.mp4'),
    ("c4", 'https://d1iax8jos987n3.cloudfront.net/sources/44606c90-6e94-4af3-bdab-473209819d0f/1785394115287-97EA5BBD-DA8E-4953-B2DC-351AC2EB16B7_L0_001.mp4'),
    ("c5", 'https://d1iax8jos987n3.cloudfront.net/sources/f563c015-6ac5-48c8-bf37-32f465706efc/1785393525407-EAB8E057-BE45-438B-9210-9E6003179BE5_L0_001.mp4'),
    ("c6", 'https://d1iax8jos987n3.cloudfront.net/sources/d95a3e0c-b3d8-4232-92c7-fe34c9b14c20/1785393819055-4F11ED19-D6A2-478E-9FEC-247319F3D749_L0_001.mp4'),
    ("c7", 'https://d1iax8jos987n3.cloudfront.net/sources/16eeba22-ac1d-4c83-8fdc-555fd2799a9d/1785393441656-4CD89C65-57DF-48D7-8B30-9C164F061946_L0_001.mp4'),
    ("c8", 'https://d1iax8jos987n3.cloudfront.net/sources/40ead0cd-86c1-4a1f-aee5-5dc308b671c8/1785393377104-417AB7BA-3F72-43B3-82AF-04B0A94C8ADF_L0_001.mp4'),
    ("c9", 'https://d1iax8jos987n3.cloudfront.net/sources/3322e884-af62-4c44-af32-3914e853ed11/1785393253461-28594D0D-DA73-4F5B-B4F5-ADADFAB1380A_L0_001.mp4'),
    ("c10", 'https://d1iax8jos987n3.cloudfront.net/sources/aec9efcb-af3d-4ca0-b950-c5143336e062/1785393091559-C2C582C6-75F2-47C2-97AC-25492477DE48_L0_001.mp4'),
    ("c11", 'https://d1iax8jos987n3.cloudfront.net/sources/01c2fd4c-4921-4e11-8c84-6448229a7961/1785393191173-0319E30A-84A6-4032-977D-900867540EFC_L0_001.mp4'),
    ("c12", 'https://d1iax8jos987n3.cloudfront.net/sources/76b86e26-6721-4899-bb6d-09ced35e6521/1785392878774-C8F5476D-65B5-4939-BFCD-A9965E03D5E1_L0_001.mp4'),
    ("c13", 'https://d1iax8jos987n3.cloudfront.net/sources/a8aa0e76-8d6c-4837-ac32-4e07a8aeccfd/1785392896448-E0388336-1C07-4413-A06C-3699B1E75861_L0_001.mp4'),
    ("c14", 'https://d1iax8jos987n3.cloudfront.net/sources/2e9459fe-91a4-4a6c-89f2-580d0abeb75c/1785392757711-51E40A81-2750-4D25-A350-BBF90BEC1D66_L0_001.mp4'),
    ("c15", 'https://d1iax8jos987n3.cloudfront.net/sources/e14a48db-c40e-432b-9b6e-ed378868b48d/1785392555090-2F75E901-08CF-4C4B-A7BA-6F4F0631B819_L0_001.mp4'),
]
CK=["emphasis_moments","text_overlays","sound_effects","broll_clips","motion_graphics"]
@app.function(secrets=SECRETS,cpu=8.0,memory=32768,region="us",timeout=1800)
def plan(src,decor):
    import uuid
    os.environ["APP_URL"]="";os.environ["JOB_STATUS_WRITES_ENABLED"]=""
    os.environ["PROMPTLY_PLAN_ONLY"]="1"
    os.environ["PROMPTLY_LEAN_SCHEMA"]="1" if decor else ""
    os.environ["PROMPTLY_LEAN_DECOR_GROUND"]="1" if decor else ""
    sys.path.insert(0,"/");import handler as H
    jid=str(uuid.uuid4())
    body={"job_id":jid,"video_url":src,"vibe":"Clean engaging edit","user_id":"ec702499-ca10-49e6-8850-df8f99840904","upload_url":f"https://thisismybucketagainwooo.s3.amazonaws.com/dr/{jid}.mp4","public_url":f"https://thisismybucketagainwooo.s3.amazonaws.com/dr/{jid}.mp4","model":"flare","supports_progressive":False,"premium_pipeline_enabled":False}
    try:r=H.handler({"input":body})
    except Exception as e:return {"error":str(e)[:120]}
    p=(r or {}).get("edit_plan")
    if not isinstance(p,dict):return {"error":"no-plan"}
    return {k:len(p.get(k) or []) for k in CK}
@app.local_entrypoint()
def main():
    h={n:{"ctrl":plan.spawn(s,0),"decor":plan.spawn(s,1)} for n,s in CLIPS}
    R={n:{k:v.get() for k,v in hs.items()} for n,hs in h.items()}
    def mean(arm,k):
        vs=[R[n][arm][k] for n in R if isinstance(R[n][arm],dict) and k in R[n][arm]]
        return round(sum(vs)/max(1,len(vs)),2)
    print("=== decor b-roll re-run: control vs decor(v2, b-roll named) ===")
    print(f"  {'family':16} {'control':>8} {'decor_v2':>9}")
    for k in CK:
        print(f"  {k:16} {mean('ctrl',k):>8} {mean('decor',k):>9}")
    print("  (was: broll 0.33 ctrl -> 0.07 decor_v1; target = recover toward 0.33)")
    open("/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/decor_reroll.json","w").write(json.dumps(R,default=str))
