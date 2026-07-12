"""SFX ONSET FIXTURE — the DETERMINISTIC offline-harness input (Zac 2026-07-12).

The full-render before/after CANNOT validate SFX timing — each render re-plans
(one came back sound_effects=0). This builds a FIXED, repeatable fixture from
Zac's real source so the detector is tuned OFFLINE against ground truth, not the
ear on a re-planning render:

  1. Zac's source's REAL audio (decoded 16kHz mono f32) + REAL Deepgram words.
  2. The TRUSTED silence-based onset per word (the exact handler path:
     _compute_floor_speech_range -> proportional thresholds ->
     _detect_silence_regions_level -> _audible_word_onset_s, spectral cleared).
     On POST-SILENCE words this is ground truth.

Uploads audio.f32 + words.json + the per-word table to CloudFront; prints URLs.
Then tune _spectral_word_onset LOCALLY (pure numpy on the returned audio) until
it AGREES with the silence-based onset on post-silence words, then apply to
mid-phrase words. No render in the loop.  Run: modal run sfx_onset_fixture.py
"""
import sys, os
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import modal
try:
    from modal_app import image
except ModuleNotFoundError:
    image = None
app = modal.App("promptly-sfx-fixture", image=image,
                secrets=[modal.Secret.from_name("promptly-secrets"),
                         modal.Secret.from_name("gemini-vertex")])
CF = "https://d1iax8jos987n3.cloudfront.net/"
ZAC_KEY = "sources/ec702499-ca10-49e6-8850-df8f99840904/1783637668931-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


@app.function(timeout=900, cpu=8, memory=16384, region=["us-west", "us-east"])
def build_fixture():
    import os, sys, time, json, subprocess, requests
    import numpy as np
    import boto3
    sys.path.insert(0, "/"); import handler as H

    ts = str(int(time.time()))
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")

    # 1. source
    src = "/tmp/src.mp4"
    url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": ZAC_KEY}, ExpiresIn=3600)
    open(src, "wb").write(requests.get(url, timeout=180).content)

    # 2. real Deepgram words
    dgkey = os.environ.get("DEEPGRAM_API_KEY")
    with open(src, "rb") as f:
        r = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true&smart_format=false",
            headers={"Authorization": f"Token {dgkey}", "Content-Type": "video/mp4"},
            data=f.read(), timeout=180)
    r.raise_for_status()
    words = r.json()["results"]["channels"][0]["alternatives"][0].get("words") or []

    # 3. TRUSTED silence-based onsets — the exact handler ground-truth path
    H._WORD_ONSET_LAST.clear()  # ensure NO spectral correction contaminates the ground truth
    spans = [(float(w.get("start") or 0.0), float(w.get("end") or 0.0)) for w in words]
    floor, speech, rng = H._compute_floor_speech_range(src, spans)
    tap = {"floor": floor, "speech": speech, "range": rng,
           "between_pct": H._DEADAIR_BETWEEN_PCT, "within_pct": H._DEADAIR_WITHIN_PCT}
    if rng >= H._DEADAIR_MIN_RANGE_DB:
        between_db = floor + H._DEADAIR_BETWEEN_PCT * rng
        within_db = floor + H._DEADAIR_WITHIN_PCT * rng
        H._LEVEL_SILENCES_LAST[:] = list(H._detect_silence_regions_level(src, between_db, H._WITHIN_CLIP_TRIM_TRIGGER_S))
        H._WITHIN_WORD_SILENCES_LAST[:] = list(H._detect_silence_regions_level(src, within_db, H._WITHIN_CLIP_TRIM_TRIGGER_S))
        tap.update({"between_db": between_db, "within_db": within_db,
                    "n_level": len(H._LEVEL_SILENCES_LAST), "n_within": len(H._WITHIN_WORD_SILENCES_LAST)})
    else:
        tap["no_op"] = True

    table = []
    for i, w in enumerate(words):
        dg = float(w.get("start") or 0.0)
        sil = H._audible_word_onset_s(words, i)  # spectral registry empty -> silence-based best
        table.append({
            "i": i, "word": w.get("word", ""),
            "dg_start": round(dg, 4),
            "dg_end": round(float(w.get("end") or 0.0), 4),
            "silence_onset": round(float(sil), 4),
            "post_silence": bool(sil < dg - 1e-4),   # a silence corrected it earlier
            "correction_ms": round((dg - float(sil)) * 1000, 1),
        })

    # 4. decode the audio to 16kHz mono f32 — the same signal the detector sees
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, timeout=120).stdout

    # 5. upload the fixture
    akey = f"sources/seam-tests/onset/audio-{ts}.f32"
    wkey = f"sources/seam-tests/onset/words-{ts}.json"
    tkey = f"sources/seam-tests/onset/table-{ts}.json"
    s3.put_object(Bucket=bucket, Key=akey, Body=raw, ContentType="application/octet-stream")
    s3.put_object(Bucket=bucket, Key=wkey, Body=json.dumps(words).encode(), ContentType="application/json")
    s3.put_object(Bucket=bucket, Key=tkey, Body=json.dumps({"tap": tap, "table": table}).encode(), ContentType="application/json")

    n_post = sum(1 for t in table if t["post_silence"])
    print(f"[fixture] {len(words)} words, {n_post} post-silence (ground truth), {len(words)-n_post} mid-phrase")
    print(f"[fixture] audio {len(raw)} bytes = {len(raw)//4/16000:.1f}s @16kHz")
    return json.dumps({"audio": CF + akey, "words": CF + wkey, "table": CF + tkey,
                       "sr": 16000, "n_words": len(words), "n_post_silence": n_post, "tap": tap})


@app.local_entrypoint()
def main():
    import json
    out = build_fixture.remote()
    d = json.loads(out)
    scr = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad"
    open(f"{scr}/onset_fixture.json", "w").write(out)
    print("FIXTURE:", json.dumps(d, indent=1))
