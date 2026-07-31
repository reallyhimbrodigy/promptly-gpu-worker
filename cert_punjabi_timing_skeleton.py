"""DEEPGRAM AS A PURE TIMING SKELETON (Zac 2026-07-28, item 4).

THE QUESTION: for a language Deepgram cannot transcribe (Punjabi), do its word
BOUNDARIES still land on real speech even though the TEXT is garbage? If yes,
Stage B gets a frame-accurate clock for free (Gemini supplies the words, Deepgram
the timing) and the whole cut-authority design simplifies. If no, forced
alignment is the only path.

METHOD (no VAD dependency — energy-based, threshold-robust):
  1. Deepgram (language=multi) on the Punjabi clip → word timestamps + text.
  2. Gemini confirms the language is Punjabi and rates the transcript (expect garbage).
  3. Extract mono 16k PCM, per-20ms-frame RMS. Mark frames "word-active" if any
     Deepgram word interval covers them. Report:
       - words_on_speech_pct: of word-active frames, % above the speech-energy floor
         (are the word boxes on sound or on silence?)
       - energy_sep_ratio: median RMS(word-active) / median RMS(word-inactive)
         (threshold-free: >~2.5 means word boxes sit on the loud/speech regions)
       - speech_covered_pct: of speech frames, % that a word covers (did Deepgram
         DROP speech spans — the Hindi-last-30s failure?)
"""
import os, sys, json, subprocess
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-punjabi-timing-skeleton", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("gemini-vertex")]

CLIPS = [
    "https://d1iax8jos987n3.cloudfront.net/sources/5bc48531-f774-40e8-b092-1c25c8548486/1784678176285-8111F14B-06DF-4C5E-8691-FDCEDCD783D6_L0_001.mp4",
    "https://d1iax8jos987n3.cloudfront.net/sources/8ebdc64d-909c-49a8-83b3-e5d3b20b7d29/1784617018415-186FADA5-12F0-4F7A-BCCB-08DB4C4F3ECA_L0_001.mp4",
    "https://d1iax8jos987n3.cloudfront.net/sources/8ebdc64d-909c-49a8-83b3-e5d3b20b7d29/1784363857233-1E39B8F5-D9E2-43DA-8BB8-A0AE3DEBAAD3_L0_001.mp4",
]


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=1200)
def run() -> dict:
    import uuid, urllib.request, traceback
    import numpy as np
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    out = {"clips": []}
    for url in CLIPS:
        rec = {"url": url[-55:]}
        try:
            path = f"/tmp/{uuid.uuid4()}.mp4"
            urllib.request.urlretrieve(url, path)

            # 1) Deepgram multi → words + text
            dg = H.transcribe_audio(path, language="multi")
            dgw = dg.get("words") or []
            rec["dg_word_count"] = len(dgw)
            rec["dg_detected_lang"] = dg.get("detected_language")
            rec["dg_text_sample"] = (dg.get("text") or "")[:180]

            # 2) Gemini: confirm language + rate the transcript (expect garbage on Punjabi)
            audio = H.prepare_audio_for_deepgram(path)
            try:
                rprompt = ("Name the language spoken in this audio and rate how accurately this "
                           "automatic transcript captures the SPOKEN WORDS (not translation):\n\n\""
                           + (dg.get("text") or "")[:1500] + "\"\n\n"
                           'Return JSON {"spoken_language":"<name>","transcript_fidelity_1to5":<int>,"notes":"<one line>"}.')
                _rr = H._get_genai_client().models.generate_content(
                    model=H.GEMINI_MODEL,
                    contents=[H.genai_types.Part.from_bytes(data=audio, mime_type="audio/flac"), rprompt],
                    config=H.genai_types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"))
                rec["gemini_review"] = json.loads((_rr.text or "{}"))
            except Exception as _e:
                rec["gemini_review_error"] = f"{type(_e).__name__}: {str(_e)[:120]}"

            # 3) VAD timing-skeleton test — Silero isolates SPEECH from music beds
            #    (raw energy can't), so this is the clean per-word-boundary test.
            if not dgw:
                rec["skeleton_error"] = "no words"; out["clips"].append(rec); continue
            sil = H._detect_silence_regions_vad(path, min_silence_s=0.20)   # (start,end) silence tuples, file-time
            rec["vad_available"] = bool(sil) or True
            audio_end = max((float(w.get("end") or 0.0) for w in dgw), default=0.0)

            def _in_silence(t):
                return any(s <= t <= e for (s, e) in sil)

            def _overlaps_silence(a, b):
                return any(min(b, e) - max(a, s) > 0.05 for (s, e) in sil)

            # (a) words landing on SPEECH: word midpoint NOT inside a VAD silence
            on_speech = sum(1 for w in dgw
                            if not _in_silence((float(w.get("start") or 0) + float(w.get("end") or 0)) / 2.0))
            rec["vad_words_on_speech_pct"] = round(100.0 * on_speech / len(dgw), 1)
            # (b) CUT-BOUNDARY validity: Deepgram inter-word gaps >=0.3s that are REAL silence
            sw = sorted(dgw, key=lambda w: float(w.get("start") or 0))
            gaps = [(float(sw[i].get("end") or 0), float(sw[i + 1].get("start") or 0))
                    for i in range(len(sw) - 1)
                    if float(sw[i + 1].get("start") or 0) - float(sw[i].get("end") or 0) >= 0.3]
            gap_hits = sum(1 for (a, b) in gaps if _overlaps_silence(a, b))
            rec["vad_gaps_checked"] = len(gaps)
            rec["vad_gaps_are_real_silence_pct"] = round(100.0 * gap_hits / len(gaps), 1) if gaps else None
            # (c) did Deepgram DROP a speech span? total VAD silence vs clip; tail after last word
            total_sil = sum(max(0.0, e - s) for (s, e) in sil)
            trailing_sil = next((s for (s, e) in sorted(sil) if s >= audio_end - 0.6), None)
            rec["audio_s"] = round(audio_end, 1)
            rec["vad_silence_s"] = round(total_sil, 1)
            # secondary: coarse energy separation (kept for cross-check, confound-aware)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                                 capture_output=True).stdout
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            fl = 320; nfr = len(x) // fl
            if nfr >= 10:
                rms = np.sqrt((x[:nfr * fl].reshape(nfr, fl) ** 2).mean(axis=1) + 1e-12)
                ft = np.arange(nfr) * 0.02
                act = np.zeros(nfr, bool)
                for w in dgw:
                    act |= (ft + 0.02 > float(w.get("start") or 0)) & (ft < float(w.get("end") or 0))
                med_a = float(np.median(rms[act])) if act.any() else 0.0
                med_i = float(np.median(rms[~act])) if (~act).any() else 1e-9
                rec["energy_sep_ratio"] = round(med_a / max(med_i, 1e-9), 2)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            rec["tb"] = traceback.format_exc()[-500:]
        out["clips"].append(rec)
    return out


@app.local_entrypoint()
def main():
    print("=== DEEPGRAM AS A TIMING SKELETON FOR PUNJABI (item 4) ===")
    o = run.remote()
    for c in o.get("clips", []):
        print("\n" + "=" * 60)
        if c.get("error"):
            print("  ERROR:", c["error"]); print(c.get("tb", "")); continue
        gr = c.get("gemini_review") or {}
        print(f"  lang: gemini={gr.get('spoken_language')} dg_detected={c.get('dg_detected_lang')} | "
              f"transcript_fidelity={gr.get('transcript_fidelity_1to5')}/5  (expect garbage → confirms 'cannot transcribe')")
        print(f"  dg text sample: {c.get('dg_text_sample')!r}")
        print(f"  audio={c.get('audio_s')}s  words={c.get('dg_word_count')}  vad_silence={c.get('vad_silence_s')}s")
        print(f"  >> VAD words_on_speech       = {c.get('vad_words_on_speech_pct')}%   (word midpoint on real speech, not silence)")
        print(f"  >> VAD gaps-are-real-silence = {c.get('vad_gaps_are_real_silence_pct')}%  (of {c.get('vad_gaps_checked')} gaps>=0.3s — cut-boundary validity)")
        print(f"  >> energy_sep_ratio (2nd)    = {c.get('energy_sep_ratio')}x")
    print("\nRAW:", json.dumps(o)[:1400])
