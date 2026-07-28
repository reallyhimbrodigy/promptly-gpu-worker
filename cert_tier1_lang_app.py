"""TIER-1 §2.1 report + Stage-A proof: for each rejected clip, detect the language (Deepgram
multi) and probe whether a MONOLINGUAL model (language=xx) recovers coverage. Reports rejections
by language AND which monolingual route saves each — deciding build order (route highest-volume
arriving langs first). Coverage measured by the LIVE gate (_transcription_coverage_check)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-tier1-lang", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
# South-Asian + arriving-mix candidates to probe monolingual (beyond multi)
CANDIDATES = ["hi", "ur", "bn", "pa", "ta"]


def _cov(H, src, words, dur):
    try:
        ok, st = H._transcription_coverage_check(src, words, dur)
        return {"ok": ok, "deletable": st.get("unworded_speech_s"), "frac": st.get("unworded_frac")}
    except Exception as e:
        return {"err": str(e)[:80]}


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1500)
def run_arm(arm: dict) -> dict:
    import time, tempfile, subprocess, traceback, urllib.request
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    sys.path.insert(0, "/")
    import handler as H
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "s.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        # multi (the current fast path)
        tr = H.transcribe_audio(src, language="multi")
        w = (tr or {}).get("words") or []
        langs = {}
        for x in w:
            l = x.get("language") or x.get("lang")
            if l:
                langs[l] = langs.get(l, 0) + 1
        multi_lang = max(langs, key=langs.get) if langs else "none"
        out = {"id": arm["id"], "dur": round(dur, 1), "multi_words": len(w),
               "multi_lang": multi_lang, "multi_langs": langs, "multi_cov": _cov(H, src, w, dur)}
        # probe monolingual candidates (detected lang first, then the fixed list)
        probe = [multi_lang] + [c for c in CANDIDATES if c != multi_lang] if multi_lang not in ("none", "en") else CANDIDATES
        mono = {}
        for lg in probe[:5]:
            try:
                trx = H.transcribe_audio(src, language=lg)
                wx = (trx or {}).get("words") or []
                mono[lg] = {"words": len(wx), "cov": _cov(H, src, wx, dur)}
            except Exception as e:
                mono[lg] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
        out["monolingual"] = mono
        # best recovery = a monolingual probe whose coverage PASSES
        best = [(lg, m) for lg, m in mono.items() if isinstance(m.get("cov"), dict) and m["cov"].get("ok")]
        out["recovered_by"] = [lg for lg, _ in best]
        return out
    except Exception as e:
        return {"id": arm["id"], "error": f"{type(e).__name__}: {str(e)[:150]}", "tb": traceback.format_exc()[-300:]}


@app.local_entrypoint()
def main():
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
    urls = json.load(open(SCR + "/tier1_trip_urls.json"))
    arms = [{**u, "stagger_s": i * 10} for i, u in enumerate(urls)]
    print(f"=== TIER-1 LANGUAGE DETECTION + MONOLINGUAL RECOVERY ({len(arms)} rejected clips) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement"
    bylang = {}; recover = {"recovered": 0, "still_failing": 0}
    for r in out:
        if r.get("error"):
            print(f"  {r['id']}: ERROR {r['error']}"); continue
        ml = r["multi_lang"]; bylang[ml] = bylang.get(ml, 0) + 1
        mc = r["multi_cov"]; rec = r.get("recovered_by") or []
        if rec: recover["recovered"] += 1
        else: recover["still_failing"] += 1
        print(f"\n  {r['id']} dur={r['dur']}s | multi: lang={ml} words={r['multi_words']} cov={mc}")
        for lg, m in (r.get("monolingual") or {}).items():
            print(f"     probe {lg}: {m}")
        print(f"     → RECOVERED BY: {rec or 'NONE (needs Gemini fallback / Stage B)'}")
    print(f"\n=== BY DETECTED LANGUAGE (multi): {json.dumps(bylang)} ===")
    print(f"=== STAGE-A RECOVERY: {recover['recovered']}/{len(out)} recoverable by a Deepgram monolingual model ===")
