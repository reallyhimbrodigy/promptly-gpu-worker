"""GEMINI-vs-DEEPGRAM WORD-TIMESTAMP ACCURACY (Zac 2026-07-28, ~$1 approved).

THE GATING MEASUREMENT for cut authority. If Gemini is demoted-to / promoted-to the
timestamp source (so the cutter rides Gemini timings instead of Deepgram's), the
cutter INHERITS Gemini's timestamp error. This measures that error directly:

  For each clip: Deepgram (language=multi) word timestamps  vs  Gemini word
  timestamps on the SAME audio. Align by word text (difflib matching blocks),
  delta = |gemini_start - deepgram_start| per aligned word. Report median / p90 /
  max in ms AND frames@30 (the delivery fps), plus the fraction within 1 and 2
  frames. On the ENGLISH clip Deepgram is the ±5ms acoustic authority, so the delta
  ≈ Gemini's ABSOLUTE accuracy; on the Hindi clip it is Gemini-vs-Deepgram-multi
  (both imperfect — agreement is the signal).

Also runs a short IN-LANGUAGE transcription-fidelity review (Gemini rates the
Deepgram transcript against the audio) — the "is Deepgram competent in this
language" half of the language-authority question.

Report the number BEFORE designing cut authority (Zac). No edit is rendered.
"""
import os, sys, json, difflib
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-gemini-vs-deepgram-timing", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("gemini-vertex")]

# The cert reports the DETECTED language per clip (semantic review + per-word tag
# majority) rather than trusting the label — the first run proved 0f739aeb, labelled
# "engaging edit", is actually Hindi. Candidates span likely-English (ec702499 test
# account) + known non-English (Hindi/Tamil corpus) so at least one gives the clean
# absolute number (English → Deepgram is the ±5ms authority) and the rest give
# Gemini-vs-Deepgram agreement.
CLIPS = [
    {"label": "ec702499-a", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"},
    {"label": "ec702499-b", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"},
    {"label": "hindi-15c392d6", "url": "https://d1iax8jos987n3.cloudfront.net/sources/15c392d6-26bf-4838-92c4-40afe386b9e0/1785208983103-930A4D00-CF5D-4337-BB24-0F65D408538F_L0_001.mp4"},
]
FPS = 30.0


def _norm(w):
    return "".join(ch for ch in str(w or "").lower() if ch.isalnum())


def _gm_word_text(x):
    if not isinstance(x, dict):
        return None
    for k in ("w", "word", "text", "token"):
        if x.get(k) is not None:
            return x.get(k)
    return None


def _gm_word_time(x):
    if not isinstance(x, dict):
        return None
    for k in ("t", "start", "start_s", "start_seconds", "time", "startTime"):
        if x.get(k) is not None:
            return x.get(k)
    return None


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        s = "".join(ch for ch in str(v or "") if ch.isdigit() or ch in ".-")
        try:
            return float(s)
        except ValueError:
            return 0.0


def _gm_words_from_response(txt):
    """Gemini may return {"words":[...]}, a bare [...], or {"transcript":{"words":[...]}}.
    Normalise to a list of {w,t} dicts."""
    try:
        obj = json.loads(txt or "{}")
    except Exception:
        return [], "json_decode_failed"
    words = None
    if isinstance(obj, list):
        words = obj
    elif isinstance(obj, dict):
        for k in ("words", "tokens", "transcript"):
            v = obj.get(k)
            if isinstance(v, list):
                words = v; break
            if isinstance(v, dict) and isinstance(v.get("words"), list):
                words = v["words"]; break
    if not isinstance(words, list):
        return [], f"unexpected_shape:{type(obj).__name__}"
    out = []
    for x in words:
        w = _gm_word_text(x)
        if w is None:
            continue
        out.append({"w": w, "t": _safe_float(_gm_word_time(x))})
    return out, None


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=1200)
def run() -> dict:
    import uuid, urllib.request, traceback, statistics as stats
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    out = {"clips": []}
    for clip in CLIPS:
        rec = {"label": clip["label"], "url": clip["url"][-60:]}
        try:
            from collections import Counter as _Counter
            path = f"/tmp/{uuid.uuid4()}.mp4"
            urllib.request.urlretrieve(clip["url"], path)

            # 1) Deepgram (language=multi) — the current authority
            dg = H.transcribe_audio(path, language="multi")
            dg_words = dg.get("words") or []
            rec["deepgram_lang"] = dg.get("detected_language")
            rec["deepgram_word_count"] = len(dg_words)
            _wl = _Counter(str(w.get("language") or "").split("-")[0] for w in dg_words if w.get("language"))
            rec["dg_word_lang_majority"] = (_wl.most_common(1)[0][0] if _wl else None)

            # 2) Gemini word timestamps on the same audio (FLAC), seconds
            audio = H.prepare_audio_for_deepgram(path)
            prompt = (
                "Transcribe this audio into INDIVIDUAL SPOKEN WORDS with a precise START "
                "TIME in SECONDS (decimal, millisecond precision) for each word. Return JSON "
                '{"words":[{"w":"<exact spoken word in its native script>","t":<start_seconds>}]}, '
                "one entry per spoken word, in spoken order. Do NOT translate; do NOT add "
                "punctuation-only tokens. Times are measured from the very start of the audio."
            )
            _client = H._get_genai_client()
            _resp = _client.models.generate_content(
                model=H.GEMINI_MODEL,
                contents=[H.genai_types.Part.from_bytes(data=audio, mime_type="audio/flac"), prompt],
                config=H.genai_types.GenerateContentConfig(temperature=0.0,
                                                           response_mime_type="application/json"))
            gm_words, _gerr = _gm_words_from_response(_resp.text or "{}")
            if _gerr:
                rec["gemini_parse_error"] = _gerr
            rec["gemini_word_count"] = len(gm_words)

            # 3) align by normalized word text; delta = |gem_start - dg_start|
            dg_toks = [_norm(w.get("word")) for w in dg_words]
            gm_toks = [_norm(x.get("w")) for x in gm_words]
            sm = difflib.SequenceMatcher(None, dg_toks, gm_toks, autojunk=False)
            deltas, signed, dg_starts, samples = [], [], [], []
            for a, b, size in sm.get_matching_blocks():
                for k in range(size):
                    if not dg_toks[a + k]:
                        continue
                    dgt = float(dg_words[a + k].get("start") or 0.0)
                    g = gm_words[b + k]
                    gmt = float(g.get("t", 0.0) or 0.0)
                    deltas.append(abs(gmt - dgt))
                    signed.append(gmt - dgt)
                    dg_starts.append(dgt)
                    samples.append((str(dg_words[a + k].get("word"))[:14], round(dgt, 2), round(gmt, 2)))
            rec["aligned_words"] = len(deltas)
            rec["alignment_rate"] = round(len(deltas) / max(1, min(len(dg_toks), len(gm_toks))), 3)
            if deltas:
                import numpy as _np
                frame_ms = 1000.0 / FPS
                dms = sorted(d * 1000.0 for d in deltas)
                def pct(arr, p):
                    return arr[min(len(arr) - 1, int(p * len(arr)))]
                rec["delta_ms"] = {"median": round(stats.median(dms), 1), "mean": round(sum(dms) / len(dms), 1),
                                   "p90": round(pct(dms, 0.90), 1), "max": round(max(dms), 1)}
                rec["within_1_frame_pct"] = round(100.0 * sum(1 for d in dms if d <= frame_ms) / len(dms), 1)
                rec["median_frames_at_30"] = round(stats.median(dms) / frame_ms, 2)
                # DIAGNOSIS — constant OFFSET (calibratable) vs DRIFT/random (not).
                _x, _y = _np.array(dg_starts), _np.array(signed)
                if len(_x) >= 3 and _x.std() > 1e-6:
                    _slope, _icpt = _np.polyfit(_x, _y, 1)
                    _resid = _y - (_slope * _x + _icpt)
                    rec["fit"] = {
                        "offset_intercept_ms": round(float(_icpt) * 1000, 1),          # uniform early(+)/late shift
                        "drift_slope_ms_per_s": round(float(_slope) * 1000, 1),        # timing error ACCUMULATED per second of clip
                        "detrended_resid_std_ms": round(float(_resid.std()) * 1000, 1),  # irreducible error AFTER removing offset+drift
                        "detrended_resid_p90_ms": round(float(_np.percentile(_np.abs(_resid), 90)) * 1000, 1),
                    }
                # |delta| after removing just the MEDIAN offset (simplest calibration)
                _mo = stats.median(signed)
                _off = sorted(abs((s - _mo) * 1000.0) for s in signed)
                rec["offset_removed_delta_ms"] = {"median": round(stats.median(_off), 1), "p90": round(pct(_off, 0.90), 1)}
                _n = len(samples)
                rec["samples_word_dgS_gmS"] = [samples[i] for i in (0, _n // 4, _n // 2, 3 * _n // 4, _n - 1)] if _n >= 5 else samples

            # 4) in-language transcription-fidelity review (bonus)
            try:
                dg_text = dg.get("text") or ""
                rprompt = (
                    "You are a native reviewer of the language spoken in this audio. Here is an "
                    "automatic transcript:\n\n\"" + dg_text[:2000] + "\"\n\n"
                    "Rate how accurately it captures the SPOKEN WORDS (not translation). Return JSON "
                    '{"language":"<name>","fidelity_1to5":<int>,"notes":"<one line: wrong/missing words or clean>"}.'
                )
                _rr = _client.models.generate_content(
                    model=H.GEMINI_MODEL,
                    contents=[H.genai_types.Part.from_bytes(data=audio, mime_type="audio/flac"), rprompt],
                    config=H.genai_types.GenerateContentConfig(temperature=0.0,
                                                               response_mime_type="application/json"))
                rec["semantic_review"] = json.loads((_rr.text or "{}"))
            except Exception as _e:
                rec["semantic_review_error"] = f"{type(_e).__name__}: {str(_e)[:120]}"
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            rec["tb"] = traceback.format_exc()[-600:]
        out["clips"].append(rec)
    return out


@app.local_entrypoint()
def main():
    print("=== GEMINI vs DEEPGRAM WORD-TIMESTAMP ACCURACY (gating measurement) ===")
    o = run.remote()
    for c in o.get("clips", []):
        print("\n" + "=" * 60)
        print(f"CLIP {c.get('label')}  deepgram_lang={c.get('deepgram_lang')} "
              f"word_lang_maj={c.get('dg_word_lang_majority')} "
              f"review_lang={(c.get('semantic_review') or {}).get('language')}")
        if c.get("error"):
            print("  ERROR:", c["error"]); print("  tb:", c.get("tb", "")); continue
        print(f"  words: deepgram={c.get('deepgram_word_count')} gemini={c.get('gemini_word_count')} "
              f"aligned={c.get('aligned_words')} (rate={c.get('alignment_rate')})")
        if c.get("gemini_parse_error"):
            print("  gemini_parse_error:", c["gemini_parse_error"])
        if c.get("delta_ms"):
            d = c["delta_ms"]
            print(f"  |gemini - deepgram| ms: median={d['median']} mean={d['mean']} p90={d['p90']} max={d['max']}"
                  f"  (median={c.get('median_frames_at_30')} frames@30)")
            print(f"  within 1 frame(33ms): {c.get('within_1_frame_pct')}%")
            if c.get("fit"):
                f = c["fit"]
                print(f"  FIT: offset={f['offset_intercept_ms']}ms  drift={f['drift_slope_ms_per_s']}ms per sec-of-clip  "
                      f"detrended residual: std={f['detrended_resid_std_ms']}ms p90={f['detrended_resid_p90_ms']}ms")
            if c.get("offset_removed_delta_ms"):
                o = c["offset_removed_delta_ms"]
                print(f"  after removing median offset: |delta| median={o['median']}ms p90={o['p90']}ms")
            if c.get("samples_word_dgS_gmS"):
                print(f"  samples (word, deepgram_s, gemini_s): {c['samples_word_dgS_gmS']}")
        print(f"  semantic_review: {json.dumps(c.get('semantic_review') or c.get('semantic_review_error'))}")
    print("\n" + "=" * 60)
    print("RAW:", json.dumps(o)[:1500])
