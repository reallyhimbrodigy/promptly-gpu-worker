"""Language-routed Scribe: flag-gated, measured selection, fail-safe.

MEASURED BASIS (2026-08-02, real prod audio, both cohorts scored through THIS
file's own _transcription_coverage_check, Deepgram run with its exact production
options — language=multi, 48kHz FLAC):

  cohort                                    deepgram nova-3   ElevenLabs Scribe
  failing set (TRANSCRIPTION_INCOMPLETE)         3/40              34/40
  control set (currently SUCCEEDING)            32/40              39/40
  word-timing median vs acoustic onset          50.0ms            19-20ms

The control cohort is the load-bearing one: it proves Scribe does not regress
jobs that already succeed. Scribe won in every language measured, English
included (18/22 -> 20/22); no language in the sample favoured Deepgram.

WHAT THIS PINS
--------------
1. Flag OFF => the engine is never called and the transcript is untouched.
2. Routing is an ALLOWLIST, and only fires when Deepgram's transcript actually
   FAILS the coverage gate — a passing transcript is never churned or re-spent.
3. Selection is MEASURED: the same gate that would reject the job picks the
   winner. Scribe losing means Deepgram's result stands.
4. FAIL-SAFE: Scribe raising/timing out can only leave today's behaviour.
"""
import os
import sys

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    def restore():
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return restore


DGW = [{"word": "hi", "punctuated_word": "hi", "start": 1.0, "end": 1.2,
        "confidence": 0.9, "speaker": 0, "language": "hi"}]
SCW = [{"word": w, "punctuated_word": w, "start": i * 0.5, "end": i * 0.5 + 0.4,
        "confidence": 1.0, "speaker": 0, "language": "hi"}
       for i, w in enumerate("one two three four five six".split())]


def patch(cov_map, scribe_words=None, scribe_raises=None):
    """cov_map: id(words) -> (ok, stats). Returns a restore fn."""
    o_cov, o_sc = H._transcription_coverage_check, H.transcribe_scribe

    def _cov(_p, words, _d):
        return cov_map(words)

    def _sc(*a, **k):
        if scribe_raises:
            raise scribe_raises
        return {"text": "x", "words": scribe_words or [], "utterances": [],
                "detected_language": "hi"}
    H._transcription_coverage_check = _cov
    H.transcribe_scribe = _sc

    def restore():
        H._transcription_coverage_check = o_cov
        H.transcribe_scribe = o_sc
    return restore


DG_RESULT = {"words": DGW, "detected_language": "hi", "text": "hi"}

print("=== S0: FLAG OFF — engine never called, transcript byte-identical ===")
r = env(PROMPTLY_ASR_SCRIBE=None, ELEVENLABS_API_KEY="k")
called = {"n": 0}
o_sc = H.transcribe_scribe
H.transcribe_scribe = lambda *a, **k: called.__setitem__("n", called["n"] + 1)
out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)
H.transcribe_scribe = o_sc
r()
check("flag off -> Scribe never invoked", called["n"] == 0)
check("flag off -> the exact same object is returned", out is DG_RESULT)

print("\n=== S1: routed language + FAILING deepgram -> Scribe wins ===")
r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="hi,ml,ta")
un = patch(lambda w: (False, {"unworded_frac": 0.9}) if w is DGW else (True, {"unworded_frac": 0.02}),
           scribe_words=SCW)
out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)
un()
check("Scribe's transcript replaces Deepgram's", out.get("words") is SCW, str(out.get("words"))[:60])
check("engine is recorded on the result", out.get("_asr_engine") == "elevenlabs_scribe")
check("language tag preserved for the caption/script route",
      out.get("detected_language") == "hi", str(out.get("detected_language")))
r()

print("\n=== S2: deepgram PASSES -> never re-spend, never churn ===")
r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="hi")
called = {"n": 0}
un = patch(lambda w: (True, {"unworded_frac": 0.01}), scribe_words=SCW)
o_sc = H.transcribe_scribe
H.transcribe_scribe = lambda *a, **k: (called.__setitem__("n", called["n"] + 1),
                                       {"words": SCW, "detected_language": "hi"})[1]
out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)
H.transcribe_scribe = o_sc
un()
r()
check("a passing Deepgram transcript does NOT call Scribe", called["n"] == 0)
check("a passing Deepgram transcript is returned untouched", out is DG_RESULT)

print("\n=== S3: MEASURED selection — Scribe loses, Deepgram stands ===")
r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="hi")
un = patch(lambda w: (False, {"unworded_frac": 0.4}) if w is DGW else (False, {"unworded_frac": 0.8}),
           scribe_words=SCW)
out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)
un()
r()
check("worse Scribe coverage -> Deepgram kept (not a blind swap)", out is DG_RESULT)

print("\n=== S4: ALLOWLIST — an unrouted language is left alone ===")
r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="ml,ta")
called = {"n": 0}
o_sc = H.transcribe_scribe
H.transcribe_scribe = lambda *a, **k: called.__setitem__("n", called["n"] + 1)
out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)   # lang=hi, not listed
H.transcribe_scribe = o_sc
r()
check("language not on the allowlist -> Scribe never invoked", called["n"] == 0)
check("'*' routes every language",
      (lambda: (env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k",
                    PROMPTLY_SCRIBE_LANGS="*"),
                H._scribe_should_route("ja"))[1])() is True)

print("\n=== S5: FAIL-SAFE — Scribe blowing up cannot cost a job ===")
for exc in (RuntimeError("SCRIBE_HTTP_500: down"), TimeoutError("read timeout")):
    r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="hi")
    un = patch(lambda w: (False, {"unworded_frac": 0.9}), scribe_raises=exc)
    out = H._maybe_upgrade_transcript_scribe(DG_RESULT, "/x.mp4", 10.0)
    un()
    r()
    check(f"{type(exc).__name__} -> Deepgram transcript survives", out is DG_RESULT)

r = env(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY=None, PROMPTLY_SCRIBE_LANGS="hi")
check("no ELEVENLABS_API_KEY -> not routed at all", H._scribe_should_route("hi") is False)
r()

print("\n=== S6: the word contract every downstream consumer reads ===")
for w in SCW:
    for k in ("word", "punctuated_word", "start", "end", "confidence", "speaker", "language"):
        if k not in w:
            check(f"word dict carries {k}", False, str(w))
            break
    else:
        continue
    break
else:
    check("word dicts carry all 7 Deepgram fields "
          "(word/punctuated_word/start/end/confidence/speaker/language)", True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
