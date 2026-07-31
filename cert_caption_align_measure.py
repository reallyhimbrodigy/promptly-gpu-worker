"""MEASURE the caption sequence-aligner on Hindi/Punjabi (Zac 2026-07-28 ship gate).

Runs the REAL handler production functions (_gemini_correct_transcript +
_corrected_text_by_index) on real clips, reconstructs the corrected caption STRING,
and has Gemini INDEPENDENTLY rate raw-Deepgram vs corrected caption fidelity against
the audio. Also verifies the two safety behaviours on real data: the Hindi-30s-drop
is OMITTED (not fabricated) and the Punjabi song (align 0.0) is REFUSED. Ship if
corrected fidelity >> raw AND the safety behaviours hold.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-caption-align-measure", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("gemini-vertex")]

CLIPS = [
    {"label": "hindi-drop(omit-tail)", "url": "https://d1iax8jos987n3.cloudfront.net/sources/15c392d6-26bf-4838-92c4-40afe386b9e0/1785208983103-930A4D00-CF5D-4337-BB24-0F65D408538F_L0_001.mp4"},
    {"label": "punjabi-heavy", "url": "https://d1iax8jos987n3.cloudfront.net/sources/8ebdc64d-909c-49a8-83b3-e5d3b20b7d29/1784617018415-186FADA5-12F0-4F7A-BCCB-08DB4C4F3ECA_L0_001.mp4"},
    {"label": "punjabi-song(refuse)", "url": "https://d1iax8jos987n3.cloudfront.net/sources/5bc48531-f774-40e8-b092-1c25c8548486/1784678176285-8111F14B-06DF-4C5E-8691-FDCEDCD783D6_L0_001.mp4"},
    {"label": "english(skip)", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"},
]


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=1800)
def run() -> dict:
    import uuid, urllib.request, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    out = {"clips": []}
    for clip in CLIPS:
        rec = {"label": clip["label"]}
        try:
            path = f"/tmp/{uuid.uuid4()}.mp4"
            urllib.request.urlretrieve(clip["url"], path)
            dg = H.transcribe_audio(path, language="multi")
            dgw = dg.get("words") or []
            audio = H.prepare_audio_for_deepgram(path)
            # REAL production functions
            gm = H._gemini_correct_transcript(audio)
            mp, meta = H._corrected_text_by_index(dgw, gm)
            rec["align_rate"] = meta["align_rate"]; rec["refused"] = meta["refused"]
            rec["corrected_slots"] = meta["corrected_slots"]
            rec["dropped_spans"] = meta["dropped_spans"]
            rec["dg_words"] = len(dgw); rec["gemini_words"] = len(gm)

            # reconstruct the caption STRING the builder would emit
            raw_txt = " ".join((w.get("punctuated_word") or w.get("word") or "") for w in dgw).strip()
            corr_parts = []
            for i, w in enumerate(dgw):
                t = mp[i] if i in mp else (w.get("punctuated_word") or w.get("word") or "")
                if str(t).strip():
                    corr_parts.append(str(t))
            corr_txt = " ".join(corr_parts).strip()
            rec["raw_sample"] = raw_txt[:150]
            rec["corrected_sample"] = corr_txt[:150]
            rec["changed"] = (corr_txt != raw_txt)

            # Gemini INDEPENDENT fidelity judge (raw vs corrected), blind to which is which
            try:
                jp = ("Two automatic transcripts of this audio, A and B. Rate each 1-5 for how "
                      "accurately it captures the SPOKEN WORDS (not translation).\n\nA: \""
                      + raw_txt[:1200] + "\"\n\nB: \"" + corr_txt[:1200] + "\"\n\n"
                      'Return JSON {"A_fidelity":<int>,"B_fidelity":<int>,"better":"A"|"B"|"same"}.')
                jr = H._get_genai_client().models.generate_content(
                    model=H.GEMINI_MODEL,
                    contents=[H.genai_types.Part.from_bytes(data=audio, mime_type="audio/flac"), jp],
                    config=H.genai_types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"))
                j = json.loads(jr.text or "{}")
                rec["raw_fidelity"] = j.get("A_fidelity"); rec["corrected_fidelity"] = j.get("B_fidelity")
                rec["judge_better"] = j.get("better")
            except Exception as _je:
                rec["judge_error"] = str(_je)[:120]
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"; rec["tb"] = traceback.format_exc()[-500:]
        out["clips"].append(rec)
    return out


@app.local_entrypoint()
def main():
    print("=== CAPTION-ALIGNER MEASUREMENT (real handler fns, Hindi/Punjabi) ===")
    o = run.remote()
    for c in o.get("clips", []):
        print("\n" + "=" * 60)
        if c.get("error"):
            print(f"  {c['label']}: ERROR {c['error']}"); continue
        print(f"  {c['label']}: align_rate={c.get('align_rate')} refused={c.get('refused')} "
              f"corrected_slots={c.get('corrected_slots')} dropped_spans={c.get('dropped_spans')}")
        print(f"    raw fidelity={c.get('raw_fidelity')}/5  ->  corrected fidelity={c.get('corrected_fidelity')}/5  "
              f"(judge: {c.get('judge_better')})   changed={c.get('changed')}")
        print(f"    RAW : {c.get('raw_sample')!r}")
        print(f"    CORR: {c.get('corrected_sample')!r}")
    print("\nRAW:", json.dumps(o)[:1600])
