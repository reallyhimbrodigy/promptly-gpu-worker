"""A genuinely SILENT clip should get a music-paced edit, not its own footage back.

MEASURED BASIS (2026-08-03, 387 completions since 08-01, editorial events =
(segments-1) + decorations, counted across BOTH recipe shapes):

    route                  n    silent   med editorial
    minimal_speech_uncut  141   141 100%       0
    moodreel               73     1   1%       5
    hype                    9     0   0%      14
    standard              143     1   1%      10

143 of 387 completions (37%, 140 distinct users) deliver ZERO editorial events,
and 141 of those are `minimal_speech_uncut` — the route hands the user their own
footage back. moodreel produces a median of 5 editorial events on the same class
of input, needs no transcript, and already ships.

THE RULE THIS PINS. Route to moodreel ONLY when the clip is genuinely silent:
  * the reason is already a no-speech reason, OR
  * the reason took the uncut path but VAD confirms there is no real speech.
Never when speech is present. `minimal_speech_uncut` exists because
build_minimal_plan cuts at MOTION PEAKS (~2.5s), which would chop the very
untranscribed speech that route protects — the Urdu-class law, destroyed content
being worse than an honest failure. So the VAD check must FAIL SAFE: anything it
cannot confirm stays uncut.
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
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def restore():
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    return restore


def with_vad(silence, available=True):
    o1, o2 = H._detect_silence_regions_vad, H._vad_available
    H._detect_silence_regions_vad = lambda *a, **k: silence
    H._vad_available = lambda: available

    def restore():
        H._detect_silence_regions_vad = o1
        H._vad_available = o2
    return restore


print("=== M0: the flag is DARK by default ===")
r = env(PROMPTLY_SILENT_TO_MOODREEL=None)
check("default OFF", H._silent_to_moodreel_enabled() is False)
r()

print("\n=== M1: VAD confirms silence -> eligible ===")
r = env(PROMPTLY_SILENT_TO_MOODREEL="1")
un = with_vad([(0.0, 30.0)])          # entire 30s clip is non-speech
check("a fully silent 30s clip is confirmed silent",
      H._vad_confirms_silence("/x.mp4", 30.0) is True)
un()

print("\n=== M2: REAL SPEECH must never be routed to a motion-cut edit ===")
un = with_vad([(0.0, 2.0)])           # 28s of speech in a 30s clip
check("a speech-bearing clip is NOT confirmed silent",
      H._vad_confirms_silence("/x.mp4", 30.0) is False,
      "routing this to moodreel would chop the speech uncut exists to protect")
un()

print("\n=== M3: FAIL SAFE — anything unmeasurable stays uncut ===")
un = with_vad([], available=False)     # silero not importable
check("VAD unavailable -> NOT confirmed silent", H._vad_confirms_silence("/x.mp4", 30.0) is False)
un()
un = with_vad([(0.0, 30.0)])
check("no duration -> NOT confirmed silent", H._vad_confirms_silence("/x.mp4", 0.0) is False)
un()


def _boom(*a, **k):
    raise RuntimeError("silero exploded")


_o = H._detect_silence_regions_vad
H._detect_silence_regions_vad = _boom
check("VAD raising -> NOT confirmed silent (never guess into motion cuts)",
      H._vad_confirms_silence("/x.mp4", 30.0) is False)
H._detect_silence_regions_vad = _o

print("\n=== M4: the [] ambiguity, again ===")
# _detect_silence_regions_vad returns [] for BOTH 'no silence gap' (continuous
# speech — the WORST case to mis-route) and 'silero unavailable'.
un = with_vad([], available=True)
check("VAD ran and found NO silence (continuous speech) -> NOT silent",
      H._vad_confirms_silence("/x.mp4", 30.0) is False)
un()

print("\n=== M5: a borderline clip is not 'silent' ===")
un = with_vad([(0.0, 26.0)])          # 4s of speech in 30s
check("4s of speech in 30s is NOT confirmed silent",
      H._vad_confirms_silence("/x.mp4", 30.0) is False)
un()

print("\n=== M6: eligibility — which reasons may be re-routed ===")
r2 = env(PROMPTLY_SILENT_TO_MOODREEL="1")
un = with_vad([(0.0, 30.0)])
check("no_speech_muted + VAD silence -> eligible",
      H._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is True)
check("transcription_incomplete + VAD silence -> eligible",
      H._silent_route_eligible("transcription_incomplete", "/x.mp4", 30.0) is True)
check("too_short is NOT re-routed (duration, not silence)",
      H._silent_route_eligible("too_short", "/x.mp4", 30.0) is False)
un()
un = with_vad([(0.0, 2.0)])
check("no_speech_muted WITH speech present -> NOT eligible",
      H._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is False)
un()
r2()

print("\n=== M7: flag OFF -> nothing is ever eligible ===")
r3 = env(PROMPTLY_SILENT_TO_MOODREEL=None)
un = with_vad([(0.0, 30.0)])
check("flag off -> no re-route even on a fully silent clip",
      H._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is False)
un()
r3()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
