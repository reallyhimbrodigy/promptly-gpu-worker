"""Bridge-selection measurement — for the Urdu source, transcribe BOTH ways (multi vs
language=ar) and measure VAD-speech coverage of each. Answers: is the multi transcript
(the one the bridge throws away) actually better coverage? If yes, the fix is to KEEP it
(selection, not rejection) and Urdu is effectively deliverable. Report before Tier-1 scope.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-bridge-select", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
CORPORA = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/corpora.json"


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=900)
def measure(url: str) -> dict:
    import subprocess, tempfile, traceback
    sys.path.insert(0, "/")
    import handler as H
    try:
        wd = tempfile.mkdtemp(); src = os.path.join(wd, "src.mp4")
        b, k = H._parse_aws_s3_url(url)
        H._aws_s3_client.download_file(b, k, src)
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "default=nw=1:nk=1", src]).decode().strip())
        out = {"dur": round(dur, 1)}
        for lang in ("multi", "ar"):
            tx = H.transcribe_audio(src, language=lang)
            w = (tx or {}).get("words") or []
            _ok, _cov = H._transcription_coverage_check(src, w, dur)
            out[lang] = {"words": len(w), "unworded_s": _cov.get("unworded_speech_s"),
                         "frac": _cov.get("unworded_frac"), "vad_speech_s": _cov.get("vad_speech_s"),
                         "gate_would": ("REJECT" if not _ok else "pass"),
                         "script": (H._dominant_script(w) if w else "?")}
        return out
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:180]}", "tb": traceback.format_exc()[-500:]}


@app.local_entrypoint()
def main():
    items = json.load(open(CORPORA))
    seen, urls = set(), []
    for i in items:
        if i["label"] == "URDU" and i["video_url"] not in seen:
            seen.add(i["video_url"]); urls.append(i["video_url"])
    print(f"=== URDU multi-vs-ar coverage ({len(urls)} sources) ===")
    for r in measure.map(urls):
        print(json.dumps(r, indent=2))
        if not r.get("error"):
            m, a = r.get("multi", {}), r.get("ar", {})
            mu, au = m.get("unworded_s"), a.get("unworded_s")
            mu_v = mu if mu is not None else 1e9
            au_v = au if au is not None else 1e9
            better = "MULTI" if mu_v <= au_v else "AR"
            kept_gate = m.get("gate_would") if better == "MULTI" else a.get("gate_would")
            print(f"→ dur={r.get('dur')}s | multi {m.get('words')}w {mu}s ({m.get('gate_would')}) | "
                  f"ar {a.get('words')}w {au}s ({a.get('gate_would')}) → KEEP {better}; "
                  f"deliverable via kept = {kept_gate == 'pass'}")
