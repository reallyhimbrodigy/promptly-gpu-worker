"""Transcription-coverage cert — measure VAD-speech time that carries NO transcript
word (the content-destruction signal). Per advisor: use Silero VAD *speech* coverage,
not energy (music beds read as non-speech → no false-positive). Runs on 3 corpora:
URDU (must reject), GOODEN known-good English (must pass), BIGGAP sample (measure the
reject fraction). The threshold falls out of the data — it should be near-binary.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-coverage", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront")]
CORPORA = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/corpora.json"


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=900)
def measure(item: dict) -> dict:
    import subprocess, tempfile, time, traceback
    sys.path.insert(0, "/")
    import handler as H
    label, jid, vurl, words = item["label"], item["job_id"], item["video_url"], item["words"]
    t0 = time.time()
    try:
        wd = tempfile.mkdtemp(); src = os.path.join(wd, "src.mp4")
        b, k = H._parse_aws_s3_url(vurl)
        if b and k and getattr(H, "_aws_s3_client", None) is not None:
            H._aws_s3_client.download_file(b, k, src)
        else:
            import requests
            r = requests.get(vurl, timeout=180); r.raise_for_status()
            open(src, "wb").write(r.content)
        dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
                    "-of","default=nw=1:nk=1", src]).decode().strip())
        silence = H._detect_silence_regions_vad(src, min_silence_s=0.30)
    except Exception as e:
        return {"label": label, "job_id": jid[:8], "error": f"{type(e).__name__}: {str(e)[:180]}",
                "tb": traceback.format_exc()[-500:]}
    sil = sorted((float(a), float(b)) for a, b in silence)
    wrd = sorted((w["start"], max(w["end"], w["start"])) for w in words if str(w.get("word","")).strip())
    def iniv(iv, t):
        for a, b in iv:
            if a - 1e-6 <= t <= b + 1e-6: return True
            if a > t: break
        return False
    BIN = 0.1; nb = int(dur / BIN) + 1
    speech = unwd = 0.0; spans = []; cur = None
    for i in range(nb):
        t = i * BIN + BIN / 2
        if iniv(sil, t):
            if cur: spans.append(cur); cur = None
            continue
        speech += BIN
        if iniv(wrd, t):
            if cur: spans.append(cur); cur = None
        else:
            unwd += BIN
            if cur is None: cur = [round(t,1), round(t,1)]
            else: cur[1] = round(t,1)
    if cur: spans.append(cur)
    return {"label": label, "job_id": jid[:8], "src_dur": round(dur,1),
            "vad_speech_s": round(speech,1), "unworded_speech_s": round(unwd,1),
            "unworded_frac": round(unwd/speech,3) if speech else 0.0,
            "n_words": len(wrd), "big_unworded_spans": [f"{a}-{b}" for a,b in spans if b-a>=1.0][:8],
            "wall_s": round(time.time()-t0,1)}


@app.local_entrypoint()
def main():
    items = json.load(open(CORPORA))
    print(f"=== COVERAGE CERT: {len(items)} jobs ===")
    out = [r for r in measure.map(items)]
    errs = [r for r in out if r.get("error")]
    ok = [r for r in out if not r.get("error")]
    def show(lbl):
        rows = [r for r in ok if r["label"] == lbl]
        print(f"\n===== {lbl} (n={len(rows)}) =====")
        for r in sorted(rows, key=lambda x: -x["unworded_speech_s"]):
            print(f"  {r['job_id']} src={r['src_dur']}s vad_speech={r['vad_speech_s']}s "
                  f"UNWORDED={r['unworded_speech_s']}s frac={r['unworded_frac']} nwords={r['n_words']} spans={r['big_unworded_spans']}")
    for lbl in ("URDU","GOODEN","BIGGAP"):
        show(lbl)
    if errs:
        print(f"\n=== ERRORS ({len(errs)}) ===")
        for e in errs: print(f"  {e['label']} {e['job_id']}: {e['error']}")
    # separation summary
    def stat(lbl, key):
        v = sorted(r[key] for r in ok if r["label"]==lbl)
        return f"min={v[0] if v else '-'} med={v[len(v)//2] if v else '-'} max={v[-1] if v else '-'}"
    print("\n===== SEPARATION (unworded_speech_s) =====")
    for lbl in ("GOODEN","BIGGAP","URDU"): print(f"  {lbl}: {stat(lbl,'unworded_speech_s')}")
    print("===== SEPARATION (unworded_frac) =====")
    for lbl in ("GOODEN","BIGGAP","URDU"): print(f"  {lbl}: {stat(lbl,'unworded_frac')}")
