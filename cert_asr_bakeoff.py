#!/usr/bin/env python3
"""ASR bake-off on the 40 TRANSCRIPTION_INCOMPLETE clips (29 users, 33.2 min).

Engines normalise to [{word, start, end}] so coverage + timing are scored
identically. Gemini is COVERAGE + LANGUAGE ID only — its word-timestamp drift is
already proven (cert_gemini_vs_deepgram_timing.py) so it cannot be the cut clock.
"""
import base64, concurrent.futures as cf, json, os, sys, time, wave
import requests

AUD = "audio"
OUT = "asr_raw"
os.makedirs(OUT, exist_ok=True)

DG = os.environ.get("DEEPGRAM_API_KEY")
AAI = os.environ.get("ASSEMBLYAI_API_KEY")
GROQ = os.environ.get("GROQ_API_KEY")
EL = os.environ.get("ELEVENLABS_API_KEY")
OAI = os.environ.get("OPENAI_API_KEY")
GEM = os.environ.get("GEMINI_API_KEY")


def _norm(words):
    out = []
    for w in words or []:
        t = (w.get("word") or w.get("text") or w.get("punctuated_word") or "").strip()
        s, e = w.get("start"), w.get("end")
        if not t or s is None or e is None:
            continue
        out.append({"word": t, "start": float(s), "end": float(e)})
    return out


# ── engines ────────────────────────────────────────────────────────────────
def deepgram(p):
    r = requests.post(
        "https://api.deepgram.com/v1/listen",
        params={"model": "nova-3", "detect_language": "true", "punctuate": "true",
                "smart_format": "true"},
        headers={"Authorization": f"Token {DG}", "Content-Type": "audio/wav"},
        data=open(p, "rb").read(), timeout=300)
    r.raise_for_status()
    j = r.json()
    ch = j["results"]["channels"][0]
    lang = ch.get("detected_language") or j["results"].get("channels", [{}])[0].get("detected_language")
    return _norm(ch["alternatives"][0].get("words")), lang, j


def assemblyai(p):
    up = requests.post("https://api.assemblyai.com/v2/upload",
                       headers={"authorization": AAI},
                       data=open(p, "rb").read(), timeout=300)
    up.raise_for_status()
    url = up.json()["upload_url"]
    tr = requests.post("https://api.assemblyai.com/v2/transcript",
                       headers={"authorization": AAI},
                       json={"audio_url": url, "language_detection": True}, timeout=120)
    tr.raise_for_status()
    tid = tr.json()["id"]
    for _ in range(180):
        g = requests.get(f"https://api.assemblyai.com/v2/transcript/{tid}",
                         headers={"authorization": AAI}, timeout=60).json()
        if g.get("status") == "completed":
            return (_norm([{"word": w["text"], "start": w["start"] / 1000.0, "end": w["end"] / 1000.0}
                           for w in (g.get("words") or [])]),
                    g.get("language_code"), g)
        if g.get("status") == "error":
            raise RuntimeError(g.get("error"))
        time.sleep(2)
    raise TimeoutError("assemblyai poll timeout")


def _openai_compat(p, base, key, model):
    r = requests.post(f"{base}/audio/transcriptions",
                      headers={"Authorization": f"Bearer {key}"},
                      files={"file": (os.path.basename(p), open(p, "rb"), "audio/wav")},
                      data={"model": model, "response_format": "verbose_json",
                            "timestamp_granularities[]": "word"}, timeout=600)
    r.raise_for_status()
    j = r.json()
    return _norm(j.get("words")), j.get("language"), j


def groq_v3(p):
    return _openai_compat(p, "https://api.groq.com/openai/v1", GROQ, "whisper-large-v3")


def groq_turbo(p):
    return _openai_compat(p, "https://api.groq.com/openai/v1", GROQ, "whisper-large-v3-turbo")


def openai_whisper(p):
    return _openai_compat(p, "https://api.openai.com/v1", OAI, "whisper-1")


def elevenlabs(p):
    r = requests.post("https://api.elevenlabs.io/v1/speech-to-text",
                      headers={"xi-api-key": EL},
                      files={"file": (os.path.basename(p), open(p, "rb"), "audio/wav")},
                      data={"model_id": "scribe_v1"}, timeout=600)
    r.raise_for_status()
    j = r.json()
    ws = [w for w in (j.get("words") or []) if w.get("type", "word") == "word"]
    return _norm(ws), j.get("language_code"), j


def gemini(p):
    """COVERAGE + LANGUAGE ID ONLY — timestamps are known-drifting, not requested."""
    b = base64.b64encode(open(p, "rb").read()).decode()
    body = {"contents": [{"parts": [
        {"text": "Transcribe ALL speech in this audio verbatim. Then on the final line "
                 "output exactly: LANGUAGE=<BCP47 code>. Do not add commentary."},
        {"inline_data": {"mime_type": "audio/wav", "data": b}}]}]}
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": GEM}, json=body, timeout=600)
        if r.status_code == 200:
            txt = "".join(pt.get("text", "") for pt
                          in r.json()["candidates"][0]["content"]["parts"])
            lang = None
            for line in txt.splitlines():
                if line.strip().upper().startswith("LANGUAGE="):
                    lang = line.split("=", 1)[1].strip()
            body_txt = "\n".join(l for l in txt.splitlines()
                                 if not l.strip().upper().startswith("LANGUAGE="))
            return [], lang, {"text": body_txt, "n_words": len(body_txt.split()), "model": model}
    r.raise_for_status()


ENGINES = {
    "deepgram_nova3": (deepgram, bool(DG)),
    "assemblyai": (assemblyai, bool(AAI)),
    "groq_whisper_large_v3": (groq_v3, bool(GROQ)),
    "groq_whisper_v3_turbo": (groq_turbo, bool(GROQ)),
    "elevenlabs_scribe": (elevenlabs, bool(EL)),
    "openai_whisper1": (openai_whisper, bool(OAI)),
    "gemini_audio": (gemini, bool(GEM)),
}

clips = sorted(f[:-4] for f in os.listdir(AUD) if f.endswith(".wav"))
print(f"clips={len(clips)}  engines={[k for k,(_,ok) in ENGINES.items() if ok]}", flush=True)
missing = [k for k, (_, ok) in ENGINES.items() if not ok]
if missing:
    print(f"SKIPPING (no key): {missing}", flush=True)


def run(job):
    name, cid = job
    dst = f"{OUT}/{cid}__{name}.json"
    if os.path.exists(dst):
        return name, cid, "cached"
    fn = ENGINES[name][0]
    t0 = time.time()
    try:
        words, lang, raw = fn(f"{AUD}/{cid}.wav")
        json.dump({"words": words, "lang": lang, "elapsed": time.time() - t0,
                   "raw_keys": list(raw.keys()) if isinstance(raw, dict) else None,
                   "extra": raw if name == "gemini_audio" else None},
                  open(dst, "w"))
        return name, cid, f"ok {len(words)}w lang={lang} {time.time()-t0:.1f}s"
    except Exception as e:
        json.dump({"error": f"{type(e).__name__}: {e}"[:400]}, open(dst, "w"))
        return name, cid, f"ERR {type(e).__name__}: {str(e)[:120]}"


jobs = [(n, c) for n, (_, ok) in ENGINES.items() if ok for c in clips]
print(f"total calls: {len(jobs)}", flush=True)
done = 0
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for name, cid, st in ex.map(run, jobs):
        done += 1
        if st.startswith("ERR") or done % 25 == 0:
            print(f"  [{done}/{len(jobs)}] {name} {cid}: {st}", flush=True)
print("DONE", flush=True)
