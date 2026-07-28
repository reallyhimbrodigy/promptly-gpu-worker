"""TIER-1 STAGE A cert: does _probe_best_language RECOVER the failing clips? For each, run
multi (fails coverage) → _probe_best_language → report recovered language, native script,
font-render eligibility, and coverage before/after. Env set to production multilingual state."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-tier1-stagea", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1500)
def run_arm(arm: dict) -> dict:
    import time, tempfile, subprocess, traceback, urllib.request
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    # production multilingual state
    os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"
    os.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
    os.environ["PROMPTLY_LANG_ROUTING"] = "1"
    os.environ["PROMPTLY_COVERAGE_GATE"] = "1"
    sys.path.insert(0, "/")
    import handler as H
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "s.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        tr = H.transcribe_audio(src, language="multi")
        w = (tr or {}).get("words") or []
        ok0, cov0 = H._transcription_coverage_check(src, w, dur)
        out = {"id": arm["id"], "dur": round(dur, 1), "multi_words": len(w),
               "multi_pass": ok0, "multi_unworded": cov0.get("unworded_speech_s")}
        if ok0:
            out["note"] = "multi already passes — not a Stage-A case"; return out
        lang, tx, u = H._probe_best_language(src, H._LANG_ROUTING_CANDIDATES, dur)
        if tx is None:
            out["recovered"] = False; out["note"] = "no candidate recovered — needs Stage B (Gemini)"; return out
        rw = tx.get("words") or []
        sc = H._dominant_script(rw)
        ok1, cov1 = H._transcription_coverage_check(src, rw, dur)
        out.update({"recovered": True, "routed_lang": lang, "routed_words": len(rw),
                    "routed_script": sc, "font_renders": H._script_reaches_render(sc),
                    "routed_pass": ok1, "routed_unworded": cov1.get("unworded_speech_s")})
        return out
    except Exception as e:
        return {"id": arm["id"], "error": f"{type(e).__name__}: {str(e)[:180]}", "tb": traceback.format_exc()[-300:]}


@app.local_entrypoint()
def main():
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
    urls = json.load(open(SCR + "/tier1_trip_urls.json"))
    arms = [{**u, "stagger_s": i * 12} for i, u in enumerate(urls)]
    print(f"=== TIER-1 STAGE A RECOVERY CERT ({len(arms)} clips) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement"
    rec = 0; native = 0
    for r in out:
        if r.get("error"):
            print(f"  {r['id']}: ERROR {r['error']}"); continue
        if r.get("note") and not r.get("recovered"):
            print(f"  {r['id']}: {r['note']} (multi_unworded={r.get('multi_unworded')})"); continue
        if r.get("recovered"):
            rec += 1
            if r.get("font_renders") and r.get("routed_pass"): native += 1
            print(f"  {r['id']} dur={r['dur']}s: multi FAIL ({r['multi_unworded']}s) → "
                  f"RECOVERED lang={r['routed_lang']} words={r['routed_words']} script={r['routed_script']} "
                  f"font_renders={r['font_renders']} pass={r['routed_pass']} unworded={r['routed_unworded']}s")
        else:
            print(f"  {r['id']}: {r.get('note')}")
    print(f"\n=== STAGE A: {rec}/{len(out)} recovered by monolingual routing; {native} render natively (font-backed + pass) ===")
