"""Beat-detection cert RE-RUN — constructed-durable synthetic corpus incl. the
busy-percussion/trap case the onset-density discriminant was least proven on.

Ephemeral, isolated R&D (modal run — no deploy, touches nothing live). Positives
are DETERMINISTICALLY SYNTHESIZED in-container (numpy click tracks — rights-free,
durable, reproducible; also mirrored to S3). Speech negatives are the durable TTS
clips. Detection ONLY — never adds music.

TWO signals reported, because they answer different questions:
  - beats>=8  -> the ROUTER signal: aubio found a usable beat grid (the router
    gates on beat_grid being non-empty; this is what actually decides hype).
  - onset density / the Brick-2 "confident" rule -> whether that discriminant
    survives busy percussion (trap = regular beat BUT dense onsets, like speech).

Run:  modal run beat_cert_app.py
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("libaubio-dev", "libsndfile1", "libsndfile1-dev", "ffmpeg")
    .pip_install("numpy")
    .pip_install("aubio", extra_options="--no-build-isolation")
    .pip_install("boto3")
)
app = modal.App("beat-cert", image=image)

BUCKET = "thisismybucketagainwooo"
NEG_LANGS = ["en", "es", "de", "fr", "hi", "id"]

MIN_BEATS = 8
BPM_LO, BPM_HI = 50.0, 200.0
MAX_CV = 0.30
MAX_ONSET_DENSITY = 0.5   # Brick-2 discriminant (music ~0.05, speech ~5-7)

# Synthesized positives: (name, bpm, subdivisions_per_beat) -> hits/sec = bpm/60*subdiv
SYNTH = [
    ("clean_kick_120", 120, 1),     # 2.0 hits/s — clean 4/4
    ("house_128", 128, 2),          # 4.3 hits/s — four-on-floor + offbeat
    ("trap_busy_140", 140, 4),      # 9.3 hits/s — DENSE hi-hats (the stress case)
    ("trap_dense_150", 150, 6),     # 15  hits/s — extreme trap roll
]


def _synth_wav(path, bpm, subdiv, dur_s=20, sr=44100):
    import numpy as np, wave
    n = int(dur_s * sr)
    audio = np.zeros(n, dtype=np.float32)
    hit_period = (60.0 / bpm) / subdiv
    length = int(0.04 * sr)
    env = np.exp(-np.linspace(0, 8, length))
    t, idx = 0.0, 0
    while t < dur_s - 0.05:
        pos = int(t * sr)
        downbeat = (idx % subdiv == 0)
        freq = 60.0 if downbeat else 8000.0      # kick vs hi-hat
        amp = 0.9 if downbeat else 0.5
        hit = (amp * np.sin(2 * np.pi * freq * np.arange(length) / sr) * env).astype(np.float32)
        end = min(pos + length, n)
        audio[pos:end] += hit[:end - pos]
        t += hit_period
        idx += 1
    audio = np.clip(audio, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((audio * 32767).astype("<i2").tobytes())


def _synth_noise(path, kind, dur_s=20, sr=44100):
    """0-word NON-music negatives: does aubio spuriously find a beat grid on
    ambient/silent audio? This is the router's real edge (speech is gated out by
    has_speech first; the beat gate only decides 0-word music vs 0-word non-music)."""
    import numpy as np, wave
    n = int(dur_s * sr)
    if kind == "white_noise":
        audio = (0.15 * np.random.default_rng(1).standard_normal(n)).astype(np.float32)
    elif kind == "quiet_ambient":
        # low broadband hum + slow swells — a silent-aesthetic-b-roll proxy
        rng = np.random.default_rng(2)
        base = 0.03 * rng.standard_normal(n)
        swell = 0.02 * np.sin(2 * np.pi * 0.15 * np.arange(n) / sr)
        audio = (base + swell).astype(np.float32)
    else:  # near_silence
        audio = (0.002 * np.random.default_rng(3).standard_normal(n)).astype(np.float32)
    audio = np.clip(audio, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((audio * 32767).astype("<i2").tobytes())


def _analyze(wavpath):
    import aubio, numpy as np
    win_s, hop_s = 1024, 512
    src = aubio.source(wavpath, 0, hop_s)
    sr = src.samplerate
    tempo = aubio.tempo("default", win_s, hop_s, sr)
    onset = aubio.onset("default", win_s, hop_s, sr)
    beats, confs, n_onsets, total, sumsq = [], [], 0, 0, 0.0
    while True:
        samples, read = src()
        if tempo(samples):
            beats.append(tempo.get_last_s())
            try:
                confs.append(float(tempo.get_confidence()))
            except Exception:
                pass
        if onset(samples):
            n_onsets += 1
        sumsq += float(np.sum(samples.astype(np.float64) ** 2))
        total += read
        if read < hop_s:
            break
    dur = total / float(sr) if sr else 0.0
    rms = (sumsq / total) ** 0.5 if total else 0.0
    rms_db = 20.0 * np.log10(rms + 1e-9)
    nb = len(beats)
    bpm, cv = 0.0, 9.99
    if nb >= 2:
        iv = np.diff(np.array(beats)); iv = iv[iv > 0]
        if len(iv):
            med = float(np.median(iv)); bpm = 60.0 / med if med > 0 else 0.0
            mean = float(np.mean(iv)); cv = float(np.std(iv) / mean) if mean > 0 else 9.99
    density = (n_onsets / dur) if dur > 0 else 0.0
    conf = float(np.mean(confs)) if confs else 0.0
    return nb, round(bpm, 1), round(cv, 3), n_onsets, round(density, 3), round(float(rms_db), 1), round(conf, 3)


def _confident(nb, bpm, cv, density):
    return (nb >= MIN_BEATS) and (BPM_LO <= bpm <= BPM_HI) and (cv <= MAX_CV) and (density <= MAX_ONSET_DENSITY)


@app.function(secrets=[modal.Secret.from_name("promptly-secrets")], timeout=900)
def run_cert():
    import boto3, subprocess, os, tempfile
    s3 = boto3.client("s3", region_name="us-west-1")
    rows = []

    # Positives — synthesized deterministically, mirrored to S3 for durability
    for name, bpm, subdiv in SYNTH:
        wav = os.path.join(tempfile.gettempdir(), f"{name}.wav")
        _synth_wav(wav, bpm, subdiv)
        try:
            s3.upload_file(wav, BUCKET, f"music-cert/synth-positives/{name}.wav")
        except Exception:
            pass
        nb, bpm_d, cv, no, dens, rms_db, conf = _analyze(wav)
        rows.append({"name": name, "kind": "pos_synth", "beats": nb, "bpm": bpm_d,
                     "cv": cv, "onsets": no, "dens": dens, "rms_db": rms_db, "conf": conf,
                     "routes": conf > 0.15, "confident": _confident(nb, bpm_d, cv, dens)})

    # Negatives (0-word, has-audio, NON-music) — the router's real edge: these
    # SHOULD NOT route (beats<8), else silent/ambient b-roll wrongly hits hype.
    for kind in ("white_noise", "quiet_ambient", "near_silence"):
        wav = os.path.join(tempfile.gettempdir(), f"amb_{kind}.wav")
        _synth_noise(wav, kind)
        nb, bpm_d, cv, no, dens, rms_db, conf = _analyze(wav)
        rows.append({"name": f"amb_{kind}", "kind": "neg_ambient", "beats": nb, "bpm": bpm_d,
                     "cv": cv, "onsets": no, "dens": dens, "rms_db": rms_db, "conf": conf,
                     "routes": conf > 0.15, "confident": _confident(nb, bpm_d, cv, dens)})

    # Negatives — TTS speech (gated out by has_speech in the real router; shown for context)
    for lang in NEG_LANGS:
        wav = os.path.join(tempfile.gettempdir(), f"neg_{lang}.wav")
        raw = os.path.join(tempfile.gettempdir(), f"neg_{lang}.mp4")
        try:
            s3.download_file(BUCKET, f"multilingual-cert/{lang}/source.mp4", raw)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-vn", "-ac", "1", "-ar", "44100", wav], check=True)
            nb, bpm_d, cv, no, dens, rms_db, conf = _analyze(wav)
            rows.append({"name": f"neg_{lang}_speech", "kind": "neg_speech", "beats": nb, "bpm": bpm_d,
                         "cv": cv, "onsets": no, "dens": dens,
                         "routes": conf > 0.15, "confident": _confident(nb, bpm_d, cv, dens)})
        except Exception as e:
            rows.append({"name": f"neg_{lang}_speech", "kind": "neg_speech", "error": str(e)[:100]})
    return rows


@app.local_entrypoint()
def main():
    rows = run_cert.remote()
    print("\n============ BEAT CERT RE-RUN (synthetic incl. busy-percussion) ============")
    print(f"router gate = beats>={MIN_BEATS}  |  Brick-2 'confident' = +bpm/cv/onset-density<={MAX_ONSET_DENSITY}\n")
    hdr = f"{'clip':<20}{'kind':<11}{'beats':>6}{'bpm':>7}{'ons/s':>7}{'rmsDB':>7}{'tconf':>7}{'ROUTES?':>8}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        if "error" in r:
            print(f"{r['name']:<20}{r['kind']:<11}  ERROR: {r['error']}")
        else:
            print(f"{r['name']:<20}{r['kind']:<11}{r['beats']:>6}{r['bpm']:>7}{r['dens']:>7}{r.get('rms_db',0):>7}{r.get('conf',0):>7}"
                  f"{('YES' if r['routes'] else 'no'):>8}")
    pos = [r for r in rows if r.get("kind") == "pos_synth"]
    amb = [r for r in rows if r.get("kind") == "neg_ambient"]
    neg = [r for r in rows if r.get("kind") == "neg_speech" and "error" not in r]
    print("\n--- ROUTER signal (what actually decides hype: beat_grid non-empty, beats>=8) ---")
    print(f"music positives that route: {sum(1 for r in pos if r.get('routes'))}/{len(pos)}   (incl. busy-trap -> want ALL)")
    print(f"0-word AMBIENT/silent that route: {sum(1 for r in amb if r.get('routes'))}/{len(amb)}   (the real edge -> want ZERO)")
    print(f"speech that route: {sum(1 for r in neg if r.get('routes'))}/{len(neg)}   (IRRELEVANT — gated out by has_speech FIRST)")
    print("--- Brick-2 onset-density discriminant on busy percussion ---")
    for r in pos:
        note = "OK" if r.get("confident") else "EXCLUDED by density gate (dense onsets read like speech)"
        print(f"  {r['name']}: onset-density={r.get('dens')}/s -> {note}")
