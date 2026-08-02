#!/usr/bin/env python3
"""Score the bake-off on the pipeline's OWN two criteria.

(a) COVERAGE — _transcription_coverage_check replicated VERBATIM from
    handler.py:20683 (Silero VAD speech, edge-deletable at any size + interior
    spans >= 1.5s), so a PASS here is a pass at the real gate.
(b) WORD TIMING — scored against an INDEPENDENT acoustic energy onset.
    _audible_word_onset_s is `deepgram_start - lead`, i.e. Deepgram-derived, so
    using it as truth would be circular in a bake-off where Deepgram is the
    control. The ±5ms figure that method was validated against is the ENERGY
    ONSET, which is what we measure here — engine-agnostic by construction.
"""
import glob, json, math, os, struct, sys, wave
from collections import defaultdict

# ── constants, verbatim from handler.py ────────────────────────────────────
_COVERAGE_MIN_UNWORDED_S = 2.0
_COVERAGE_MIN_UNWORDED_FRAC = 0.10
_COVERAGE_TAIL_KEEP_S = 0.5
_COVERAGE_MIN_INTERIOR_S = 1.5

_VAD_CACHE = "vad_cache.json"
_vad = json.load(open(_VAD_CACHE)) if os.path.exists(_VAD_CACHE) else {}


def silence_regions(wav, min_silence_s=0.30):
    """Silero VAD → silence (non-speech) regions, matching _detect_silence_regions_vad."""
    key = os.path.basename(wav)
    if key in _vad:
        return [tuple(x) for x in _vad[key]]
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps
    model = silence_regions._m = getattr(silence_regions, "_m", None) or load_silero_vad()
    # read_audio() routes through torchaudio (which now demands torchcodec); our
    # wavs are ALREADY the 16kHz mono PCM16 Silero wants, so decode directly.
    with wave.open(wav) as _w:
        assert _w.getframerate() == 16000 and _w.getnchannels() == 1, wav
        _n = _w.getnframes()
        _pcm = struct.unpack(f"<{_n}h", _w.readframes(_n))
    audio = torch.tensor(_pcm, dtype=torch.float32) / 32768.0
    sp = get_speech_timestamps(audio, model, sampling_rate=16000, return_seconds=True)
    dur = len(audio) / 16000.0
    sil, prev = [], 0.0
    for s in sp:
        if s["start"] - prev >= min_silence_s:
            sil.append((prev, s["start"]))
        prev = s["end"]
    if dur - prev >= min_silence_s:
        sil.append((prev, dur))
    _vad[key] = sil
    json.dump(_vad, open(_VAD_CACHE, "w"))
    return sil


def coverage_check(wav, words, dur):
    """VERBATIM port of handler._transcription_coverage_check."""
    stats = {"unworded_speech_s": None, "unworded_frac": None, "vad_speech_s": None}
    if dur <= 0 or not words:
        return True, stats
    sil = sorted(silence_regions(wav))
    wrd = sorted((float(w["start"]), max(float(w["end"]), float(w["start"])))
                 for w in words if str(w.get("word") or "").strip())
    if not wrd:
        return True, stats

    def _iniv(iv, t):
        for a, b in iv:
            if a - 1e-6 <= t <= b + 1e-6:
                return True
            if a > t:
                break
        return False

    first_ws = wrd[0][0]
    last_we = max(e for _s, e in wrd)
    tail_keep = last_we + _COVERAGE_TAIL_KEEP_S
    BIN = 0.1
    nb = int(dur / BIN) + 1
    speech = edge_deletable = 0.0
    _int_run, _int_spans = 0, []
    for i in range(nb):
        t = i * BIN + BIN / 2.0
        if _iniv(sil, t):
            if _int_run:
                _int_spans.append(_int_run * BIN); _int_run = 0
            continue
        speech += BIN
        if t < first_ws or t > tail_keep:
            edge_deletable += BIN
            if _int_run:
                _int_spans.append(_int_run * BIN); _int_run = 0
        elif not _iniv(wrd, t):
            _int_run += 1
        elif _int_run:
            _int_spans.append(_int_run * BIN); _int_run = 0
    if _int_run:
        _int_spans.append(_int_run * BIN)
    interior_reject = sum(s for s in _int_spans if s >= _COVERAGE_MIN_INTERIOR_S)
    reject_speech = edge_deletable + interior_reject
    frac = (reject_speech / speech) if speech > 0 else 0.0
    stats = {"unworded_speech_s": round(reject_speech, 1), "unworded_frac": round(frac, 3),
             "vad_speech_s": round(speech, 1)}
    ok = not (reject_speech >= _COVERAGE_MIN_UNWORDED_S and frac >= _COVERAGE_MIN_UNWORDED_FRAC)
    return ok, stats


# ── (b) independent acoustic energy onsets ─────────────────────────────────
def energy_onsets(wav, hop=0.010, win=0.025):
    with wave.open(wav) as w:
        n, sr = w.getnframes(), w.getframerate()
        pcm = struct.unpack(f"<{n}h", w.readframes(n))
    H, W = int(sr * hop), int(sr * win)
    env = []
    for i in range(0, max(0, n - W), H):
        seg = pcm[i:i + W]
        env.append(math.sqrt(sum(float(s) * s for s in seg) / len(seg)) if seg else 0.0)
    if not env:
        return [], sr
    mx = max(env) or 1.0
    env = [e / mx for e in env]
    # onset = a rising edge that clears a small floor (engine-agnostic)
    ons = []
    for i in range(1, len(env) - 1):
        rise = env[i] - env[i - 1]
        if rise > 0.06 and env[i] > 0.05 and env[i] >= env[i - 1]:
            ons.append(i * hop)
    return ons, sr


def timing_score(wav, words):
    """Median |engine word start - nearest acoustic onset|, and %% within 50ms."""
    ons, _ = energy_onsets(wav)
    if not ons or not words:
        return None
    devs = []
    for w in words:
        t = float(w["start"])
        lo, hi = t - 0.25, t + 0.25
        cand = [o for o in ons if lo <= o <= hi]
        if cand:
            devs.append(min(abs(o - t) for o in cand))
    if len(devs) < 5:
        return None
    devs.sort()
    return {"n": len(devs),
            "median_ms": round(devs[len(devs) // 2] * 1000, 1),
            "p90_ms": round(devs[int(0.9 * (len(devs) - 1))] * 1000, 1),
            "within_50ms_pct": round(100 * sum(1 for d in devs if d <= 0.050) / len(devs), 1),
            "matched_pct": round(100 * len(devs) / len(words), 1)}


# ── run ────────────────────────────────────────────────────────────────────
durs = json.load(open("asr_dur.json"))["durs"]
dur8 = {k[:8]: v for k, v in durs.items()}
res = defaultdict(dict)
for f in sorted(glob.glob("asr_raw/*.json")):
    cid, eng = os.path.basename(f)[:-5].split("__")
    d = json.load(open(f))
    if d.get("error"):
        res[cid][eng] = {"error": d["error"][:80]}
        continue
    wav = f"audio/{cid}.wav"
    words = d.get("words") or []
    dur = dur8.get(cid) or 0
    ok, st = coverage_check(wav, words, dur)
    res[cid][eng] = {"lang": d.get("lang"), "n_words": len(words), "gate_pass": ok,
                     "coverage_pct": round(100 * (1 - (st["unworded_frac"] or 0)), 1)
                     if st["unworded_frac"] is not None else None,
                     "unworded_s": st["unworded_speech_s"], "vad_speech_s": st["vad_speech_s"],
                     "timing": timing_score(wav, words), "dur": round(dur, 1)}
    print(f"  {cid} {eng:22} {res[cid][eng]['coverage_pct']}% pass={ok} "
          f"lang={d.get('lang')} w={len(words)}", flush=True)
json.dump(res, open("asr_scores.json", "w"), indent=1)
print(f"\nwrote asr_scores.json ({len(res)} clips)")
