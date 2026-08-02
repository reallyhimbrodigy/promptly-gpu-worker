"""The coverage gate must FAIL an empty transcript over real speech.

WHY THIS EXISTS
---------------
`_transcription_coverage_check` opened with `if _dur <= 0 or not words: return
True` — so a transcript with ZERO words PASSED the coverage gate. A total
transcription failure scored as fine.

That is not hypothetical. In the 2026-08-02 ASR bake-off, Deepgram nova-3
returned zero words on 11 of the 40 TRANSCRIPTION_INCOMPLETE clips, and every
one of those 11 passes the gate on today's code. It also flattered the control's
own average — excluding the zero-word clips lifted Deepgram's mean coverage from
53.6% to 73.9%. An unmeasurable failure is what let this class hide.

THE DISTINCTION THAT MATTERS
----------------------------
Zero words is only a DEFECT when there was speech to transcribe:
  * zero words + VAD-confirmed speech  -> TRANSCRIPTION_EMPTY (a real failure)
  * zero words + no VAD speech         -> genuinely silent; NO_SPEECH owns that,
                                          and this gate must stay quiet
  * unmeasurable (no duration, VAD threw) -> FAIL-OPEN, unchanged. The gate must
                                          never invent a failure it cannot see.
"""
import sys
import types

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def with_vad(silence_regions, available=True):
    """Swap the Silero call for a fixture; returns a restore fn.

    `available` is patched separately because [] is ambiguous in the real
    helper — it means BOTH "no silence gap >= 0.30s" (continuous speech, the
    worst case) and "silero_vad not importable" (unmeasurable). The production
    code disambiguates via _vad_available(), so the test must too rather than
    depending on whether this machine happens to have silero installed.
    """
    o1, o2 = H._detect_silence_regions_vad, H._vad_available
    H._detect_silence_regions_vad = lambda *a, **k: silence_regions
    H._vad_available = lambda: available

    def _restore():
        H._detect_silence_regions_vad = o1
        H._vad_available = o2
    return _restore


WORDS = [{"word": "hello", "start": 1.0, "end": 1.4},
         {"word": "there", "start": 1.5, "end": 1.9}]

print("=== C0: zero words over VAD-CONFIRMED SPEECH must FAIL ===")
# 10s clip, silence only in [0,0.5] -> ~9.5s of speech, and no transcript at all.
restore = with_vad([(0.0, 0.5)])
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
restore()
check("empty transcript over speech is REJECTED (was: passed)", ok is False, f"ok={ok} stats={st}")
check("reports the untranscribed speech it found", (st.get("vad_speech_s") or 0) > 5.0, str(st))
check("unworded_frac is 1.0 — none of the speech was transcribed",
      st.get("unworded_frac") == 1.0, str(st))

print("\n=== C1: zero words over SILENCE stays quiet (NO_SPEECH owns that) ===")
restore = with_vad([(0.0, 10.0)])          # entire clip is silence
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
restore()
check("a genuinely silent clip is NOT a coverage failure", ok is True, f"ok={ok} stats={st}")

print("\n=== C2: below the speech floor stays quiet (no over-fire on a cough) ===")
restore = with_vad([(0.0, 9.0)])           # 1.0s of 'speech' — under the 2.0s floor
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
restore()
check("a sub-floor blip does not trip the gate", ok is True, f"ok={ok} stats={st}")

print("\n=== C3: UNMEASURABLE still fails OPEN (never invent a failure) ===")
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 0.0)
check("no duration -> fail-open", ok is True, f"ok={ok}")


def _boom(*a, **k):
    raise RuntimeError("silero exploded")


_orig = H._detect_silence_regions_vad
H._detect_silence_regions_vad = _boom
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
H._detect_silence_regions_vad = _orig
check("VAD raising -> fail-open (measurement error is not a verdict)", ok is True, f"ok={ok}")

restore = with_vad([], available=False)   # silero not importable
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
restore()
check("VAD UNAVAILABLE -> fail-open, not a phantom reject", ok is True, f"ok={ok} stats={st}")

restore = with_vad([], available=True)    # VAD ran; found NO silence = all speech
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", [], 10.0)
restore()
check("VAD ran and found NO silence (continuous speech, 0 words) -> REJECT "
      "(the [] ambiguity that would otherwise hide the worst case)",
      ok is False, f"ok={ok} stats={st}")

print("\n=== C4: the populated-transcript paths are unchanged ===")
restore = with_vad([(0.0, 0.9), (2.0, 10.0)])   # speech only where the words are
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", WORDS, 10.0)
restore()
check("fully-covered speech still passes", ok is True, f"ok={ok} stats={st}")

restore = with_vad([(0.0, 0.5)])                # 9.5s speech, words cover ~1s
ok, st = H._transcription_coverage_check("/tmp/nonexistent.mp4", WORDS, 10.0)
restore()
check("mostly-untranscribed speech still rejects", ok is False, f"ok={ok} stats={st}")

print("\n=== C5: the class has its own honest, routable error code ===")
env = H.classify_error(RuntimeError(
    "TRANSCRIPTION_EMPTY: 9.5s of speech, transcript returned 0 words"))
check("TRANSCRIPTION_EMPTY classifies to itself (not UNKNOWN)",
      env.get("error_code") == "TRANSCRIPTION_EMPTY", env.get("error_code"))
check("carries a user message", bool(str(env.get("user_message") or "").strip()))
check("does not blame the user for an engine failure",
      env.get("requires_new_video") is not True, str(env))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
