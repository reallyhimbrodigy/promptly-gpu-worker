#!/usr/bin/env python3
"""A SILENT SOURCE DOES NOT PAY FOR A DEEPGRAM CALL — and an UNMEASURED one does.

MEASURED, round 48: five of five fixtures paid an audio extract and a Deepgram
call. TWO are silent (screen_recording at -91 dB, motion) and returned nothing
usable. The call sat BEFORE the route split — unconditional by construction
rather than by decision — so 40% of runs bought an API call to be told there
was no speech.

THE GATE ASKS "IS THIS FILE SILENT", NOT "IS THIS SPEECH". A speech threshold
fitted to five fixtures would silently drop real transcripts from quiet
talkers — the unrecoverable error, because the job then proceeds looking
normal. PEAK not RMS: RMS falls with sparse speech and peak does not.

  python3 smoke_asr_gate.py    exit 0 = the gate is safe in BOTH directions
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

_top = {}
for n in TREE.body:
    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
        try:
            _top[n.targets[0].id] = ast.literal_eval(n.value)
        except Exception:                                         # noqa: BLE001
            pass
thr = _top.get("_SILENT_PEAK_DBFS")
ok(thr is not None,
   "_SILENT_PEAK_DBFS is not a module constant — a threshold inlined in a "
   "branch cannot be found or reviewed")
ok(thr is not None and -80 <= thr <= -40,
   f"_SILENT_PEAK_DBFS is {thr} — outside the range where 'inaudible' is "
   f"defensible. Above -40 it refuses quiet speakers; below -80 it stops "
   f"catching digital silence")


def _decide(peak):
    if peak is None:
        return "TRANSCRIBE"
    return "SKIP" if peak <= thr else "TRANSCRIBE"


CASES = [("screen_recording silent", -78.4, "SKIP"),
         ("digital silence", float("-inf"), "SKIP"),
         ("talking_head", -1.2, "TRANSCRIBE"),
         ("car_short", -3.8, "TRANSCRIBE"),
         ("a QUIET talker", -38.0, "TRANSCRIBE"),
         ("probe FAILED", None, "TRANSCRIBE")]
for label, peak, want in CASES:
    got = _decide(peak)
    ok(got == want, f"{label} (peak={peak}) -> {got}, expected {want}")

# THE WINDOW STARTS AT THE GATE'S FIRST LINE. An earlier version sliced from the
# _skip_asr assignment — which comes AFTER the ffprobe — so it looked past the
# very call it was checking for and reported it missing. A check reading the
# wrong window is the same family as an observable computed on the wrong side of
# a boundary.
_g = SRC[SRC.index("# ── DOES THIS SOURCE HAVE AUDIBLE CONTENT AT ALL?"):]
_g = _g[:_g.index('led["asr_gate"]')]

ok("peak level UNMEASURED — transcribing rather than guessing" in SRC,
   "the app does not state what happens when the peak cannot be measured — an "
   "unmeasured probe must TRANSCRIBE, never skip")
ok("_peak_db is None" in _g and "elif" in _g,
   "the None case is not handled BEFORE the threshold comparison — "
   "None <= -60.0 raises in Python 3, or is folded into the silent branch")
ok("select_streams" in _g and "a:0" in _g,
   "the no-audio-stream case is not decided from ffprobe — it must cost no "
   "decode and no call")
ok("_audio_of" not in _g.split("_a_stream is None")[0],
   "audio is extracted BEFORE the no-stream check — a source with no audio "
   "would still pay for an extract")
ok('led["asr_gate"]' in SRC, "the gate decision never reaches the ledger")
ok("ASR GATE" in SRC,
   "the gate decision is never PRINTED — a counter in the ledger and nowhere "
   "else answers no question")

print(f"ASR-GATE  threshold {thr} dBFS, {len(CASES)} cases driven")
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("  silent skips, audible transcribes, UNMEASURED transcribes, reported")
