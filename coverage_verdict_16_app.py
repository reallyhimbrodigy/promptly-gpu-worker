"""Caveat-2 check (Zac 2026-07-31): how many of the 16 plan-decision-A/B clips would
PASS the REAL coverage gate? Coverage-off forced them onto the editorial path; if
several would REJECT in production, the A/B sample isn't representative of the
talking-head traffic the lean/DWELL changes actually affect. Transcribe + the real
_transcription_coverage_check only — no render, no editorial Gemini."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("coverage-verdict-16", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

CF = "https://d1iax8jos987n3.cloudfront.net/sources/"
CLIPS = [
    ("clean_93s", CF + "watched-clean/goodEN_93s.mp4"),
    ("goodEN_7513987a", CF + "ec702499-ca10-49e6-8850-df8f99840904/1782599246881-AB653DB0-BCCF-4C67-9910-0355686EC183_L0_001.mp4"),
    ("goodEN_233ef734", CF + "ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"),
    ("bg_0909a327", CF + "3a0fe91b-2e6a-4f9a-861d-7d1f60343589/1784898556353-01872AE4-1423-4D62-8E8A-E1B6D5DDEF80_L0_001.mp4"),
    ("bg_b6ca5284", CF + "670ba2a1-c1d3-4f83-a1d1-88a9b029404a/1784679626911-B73364F3-9C55-47E6-8AB6-4082B866A83E_L0_001.mp4"),
    ("bg_e4fddb37", CF + "1eea8ab0-d365-4ff2-9eab-289194932e39/1784925058383-FAAD6F24-94E6-439F-81BE-25E1B87854E6_L0_001.mp4"),
    ("bg_febe1098", CF + "4326653f-927b-4caa-bb51-927a9baffb8e/1784286698284-0093D893-F594-4FBB-900B-4EB519CCF002_L0_001.mp4"),
    ("bg_3045ef1c", CF + "d26f9f96-f38b-486c-99ae-8502030d7ad9/1784274080968-9383B9FD-1F75-4FFC-9689-898BB7B2D3D8_L0_001.mp4"),
    ("bg_de548e46", CF + "ac984a64-b7a4-4362-b60d-ce11714a2b67/1784296682758-C2A2D859-49D2-4238-84B9-04439A4B21E4_L0_001.mp4"),
    ("bg_8b2aed41", CF + "a0290ba1-1bc8-4a6a-ac26-fd33c8d97546/1784271717407-EAF477DD-1BB7-4AFB-913D-41AC99166FC0_L0_001.mp4"),
    ("bg_fede192a", CF + "429257b9-8670-4901-b579-524e37ca465b/1783522440664-EE72C8FD-0F01-40E3-9A8D-7D33004CF570_L0_001.mp4"),
    ("bg_5f2e913f", CF + "618e81dd-a88c-490f-b451-453e8c2cf173/1784564569682-118511E9-FDAE-47FA-A3CD-2447578051BC_L0_001.mp4"),
    ("bg_2b2b93e0", CF + "2460c4ef-4e7a-4533-b4f8-6981b9ae0b11/1784708798937-F540C0F7-92B9-40A9-8536-74AA15320280_L0_001.mp4"),
    ("bg_edc99dda", CF + "59327a64-221a-4539-b37d-eb26ed386f74/1784306340933-C6C6B976-0366-4348-8135-58FCF7C68B97_L0_001.mp4"),
    ("bg_2844f6f7", CF + "7c0278a3-ba9f-4619-9c71-8d5432c28869/1784298291335-849A1595-1E17-46AA-8333-A97708F046E6_L0_001.mp4"),
    ("bg_de52fa48", CF + "51667d23-3916-4552-934d-423d098f1f29/1784282952043-85FAA299-CB11-4A3A-8506-2397205AD640_L0_001.mp4"),
]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1200)
def check(item: dict) -> dict:
    import time, tempfile, subprocess, urllib.request
    sys.path.insert(0, "/")
    import handler as H
    name, url = item["name"], item["url"]
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "src.mp4")
        urllib.request.urlretrieve(url, src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        tr = H.transcribe_audio(src, language="multi"); words = (tr or {}).get("words") or []
        ok, st = H._transcription_coverage_check(src, words, dur)
        return {"name": name, "dur": round(dur, 1), "words": len(words),
                "verdict": "PASS" if ok else "REJECT",
                "unworded_s": st.get("unworded_speech_s"), "frac": st.get("unworded_frac")}
    except Exception as e:
        return {"name": name, "error": f"{type(e).__name__}: {str(e)[:150]}"}


@app.local_entrypoint()
def main():
    print(f"=== REAL coverage-gate verdict on the {len(CLIPS)} A/B clips (caveat 2) ===")
    items = [{"name": n, "url": u} for n, u in CLIPS]
    out = list(check.map(items))
    npass = sum(1 for r in out if r.get("verdict") == "PASS")
    nrej = sum(1 for r in out if r.get("verdict") == "REJECT")
    nerr = sum(1 for r in out if r.get("error"))
    for r in sorted(out, key=lambda x: x.get("name", "")):
        print(f"  {r.get('verdict', 'ERR'):7} {r.get('name'):18} words={r.get('words')} "
              f"unworded={r.get('unworded_s')}s frac={r.get('frac')} {r.get('error','')}")
    print(f"\n  PASS={npass}  REJECT={nrej}  ERR={nerr}  of {len(CLIPS)}")
    print(f"  => {npass} clips are representative (production would run the editorial path); "
          f"{nrej} would route to minimal (unrepresentative of lean/DWELL traffic).")
