"""BROAD HYBRID-GATE validation — REAL _transcription_coverage_check across corpus + 5 trips.
Reports edge vs interior_reject split. REJECT = large EDGE (deleted) or large contiguous INTERIOR
(bad edit); scattered breaths excluded."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-coverage-hybrid", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
CASES = [
    {
        "label": "URDU_f709170e",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/6a8b3e8f-b783-474e-8a43-b784424b2250/1784738583393-DCD4C5CF-97A5-4D61-8040-5B6C198CDCB9_L0_001.mp4"
    },
    {
        "label": "URDU_e46e84c2",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/5a694fb1-1c31-4121-922a-504fdc08179e/1784903305356-DBD6ABC5-4F8E-4F99-BCA7-A199BC118D8D_L0_001.mp4"
    },
    {
        "label": "URDU_16b4bdd2",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/78539429-5428-4123-b5a6-f3fa844ecd19/1785184730836-78331DDF-AE11-462D-A0FE-43D600039A66_L0_001.mp4"
    },
    {
        "label": "URDU_c7d00839",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785187249173-02906184-D44C-4F1F-B086-89503819CFDE_L0_001.mp4"
    },
    {
        "label": "BIGGAP_0909a327",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/3a0fe91b-2e6a-4f9a-861d-7d1f60343589/1784898556353-01872AE4-1423-4D62-8E8A-E1B6D5DDEF80_L0_001.mp4"
    },
    {
        "label": "BIGGAP_b6ca5284",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/670ba2a1-c1d3-4f83-a1d1-88a9b029404a/1784679626911-B73364F3-9C55-47E6-8AB6-4082B866A83E_L0_001.mp4"
    },
    {
        "label": "BIGGAP_e4fddb37",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/1eea8ab0-d365-4ff2-9eab-289194932e39/1784925058383-FAAD6F24-94E6-439F-81BE-25E1B87854E6_L0_001.mp4"
    },
    {
        "label": "BIGGAP_febe1098",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/4326653f-927b-4caa-bb51-927a9baffb8e/1784286698284-0093D893-F594-4FBB-900B-4EB519CCF002_L0_001.mp4"
    },
    {
        "label": "BIGGAP_3045ef1c",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/d26f9f96-f38b-486c-99ae-8502030d7ad9/1784274080968-9383B9FD-1F75-4FFC-9689-898BB7B2D3D8_L0_001.mp4"
    },
    {
        "label": "BIGGAP_de548e46",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/ac984a64-b7a4-4362-b60d-ce11714a2b67/1784296682758-C2A2D859-49D2-4238-84B9-04439A4B21E4_L0_001.mp4"
    },
    {
        "label": "BIGGAP_8b2aed41",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/a0290ba1-1bc8-4a6a-ac26-fd33c8d97546/1784271717407-EAF477DD-1BB7-4AFB-913D-41AC99166FC0_L0_001.mp4"
    },
    {
        "label": "BIGGAP_de52fa48",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/51667d23-3916-4552-934d-423d098f1f29/1784282952043-85FAA299-CB11-4A3A-8506-2397205AD640_L0_001.mp4"
    },
    {
        "label": "BIGGAP_fede192a",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/429257b9-8670-4901-b579-524e37ca465b/1783522440664-EE72C8FD-0F01-40E3-9A8D-7D33004CF570_L0_001.mp4"
    },
    {
        "label": "BIGGAP_5f2e913f",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/618e81dd-a88c-490f-b451-453e8c2cf173/1784564569682-118511E9-FDAE-47FA-A3CD-2447578051BC_L0_001.mp4"
    },
    {
        "label": "BIGGAP_2b2b93e0",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/2460c4ef-4e7a-4533-b4f8-6981b9ae0b11/1784708798937-F540C0F7-92B9-40A9-8536-74AA15320280_L0_001.mp4"
    },
    {
        "label": "BIGGAP_edc99dda",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/59327a64-221a-4539-b37d-eb26ed386f74/1784306340933-C6C6B976-0366-4348-8135-58FCF7C68B97_L0_001.mp4"
    },
    {
        "label": "BIGGAP_2844f6f7",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/7c0278a3-ba9f-4619-9c71-8d5432c28869/1784298291335-849A1595-1E17-46AA-8333-A97708F046E6_L0_001.mp4"
    },
    {
        "label": "BIGGAP_302e6854",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/02b3c741-e34e-427e-b924-a585a360e0bf/1784674125091-F5F0A7AE-620B-45AB-83C4-1BC329310A7A_L0_001.mp4"
    },
    {
        "label": "TRIP62pct_09c4fdd4",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/400e9c2f-83da-43fa-a299-00b3fb51475e/1785192532742-5706C3FE-1AD9-45D6-8011-C44F877454B9_L0_001.mp4"
    },
    {
        "label": "TRIP59pct_a5240ea7",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/d88a30b3-5db8-45b4-901e-370c337027b0/1785194050289-23A76720-4133-445E-99E3-59DD1C6A6409_L0_001.mp4"
    },
    {
        "label": "TRIP10pct_67c7c9f0",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/0b958738-3378-4d11-bc80-f921a774b54b/1785196596030-0D2D6E0A-EB8A-42A5-AB5F-8E77DB1F8051_L0_001.mp4"
    },
    {
        "label": "TRIP44pct_edea9617",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/704d811f-9f6b-45c6-a31b-573f9a6bac3b/1785196608786-2878098A-526B-4D2A-81A8-BF83FF3DBF1F_L0_001.mp4"
    },
    {
        "label": "TRIP10pct_4b1d4161",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/0b958738-3378-4d11-bc80-f921a774b54b/1785196976349-0D2D6E0A-EB8A-42A5-AB5F-8E77DB1F8051_L0_001.mp4"
    },
    {
        "label": "GOODEN_7513987a",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782599246881-AB653DB0-BCCF-4C67-9910-0355686EC183_L0_001.mp4"
    },
    {
        "label": "GOODEN_233ef734",
        "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"
    }
]
@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1200)
def run_arm(arm: dict) -> dict:
    import time, tempfile, subprocess, urllib.request
    if arm.get("stagger_s"): time.sleep(float(arm["stagger_s"]))
    sys.path.insert(0, "/")
    import handler as H
    t0 = time.time()
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "src.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",src], capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        tr = H.transcribe_audio(src, language="multi"); words = (tr or {}).get("words") or []
        ok, st = H._transcription_coverage_check(src, words, dur)
        return {"label": arm["label"], "dur": round(dur,1), "words": len(words),
                "verdict": "PASS" if ok else "REJECT", "st": st, "wall": round(time.time()-t0,1)}
    except Exception as e:
        return {"label": arm["label"], "error": f"{type(e).__name__}: {str(e)[:150]}"}
@app.local_entrypoint()
def main():
    arms = [{**c, "stagger_s": i*7} for i, c in enumerate(CASES)]
    print(f"=== BROAD HYBRID-GATE ({len(arms)} clips) ===")
    out = list(run_arm.map(arms)); assert out
    ok = [r for r in out if not r.get("error")]; errs = [r for r in out if r.get("error")]
    rej = [r for r in ok if r["verdict"]=="REJECT"]
    print(f"measured {len(ok)}/{len(out)} ({len(errs)} err); {len(rej)} REJECT")
    print("\nlabel                          dur  words verdict reject frac  edge  int_rej int_tot")
    for r in sorted(ok, key=lambda x:(x["verdict"]!="REJECT", -(x["st"].get("unworded_speech_s") or 0))):
        s=r["st"]
        print(f"  {r['label'][:30]:30} {r['dur']:5} {r['words']:5} {r['verdict']:6} {str(s.get('unworded_speech_s')):5} {str(s.get('unworded_frac')):5} {str(s.get('edge_deletable_s')):5} {str(s.get('interior_reject_s')):6} {str(s.get('interior_total_s')):6}")
    for r in errs: print("  ERR", r["label"], r["error"])
