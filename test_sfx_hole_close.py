"""ITEM 1 — the SFX CORRECTION-HOLE close (Zac 2026-07-12). _audible_word_onset_s
corrected only words preceded by a detected silence; mid-phrase continuous-speech
words got NO correction and landed up to +250ms late. This closes the hole via a
per-word SPECTRAL-FLUX onset (the audio analog of the zoom motion-onset), bounded
to the plausible Deepgram-late range so it can only pull an onset EARLIER toward
the true audible onset, never over-correct. Deterministic, offline."""
import sys

import numpy as np

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

for _fn in ("_spectral_word_onset", "_WORD_ONSET_LAST", "_detect_word_onsets"):
    if not hasattr(H, _fn):
        print(f"  FAIL  {_fn} not implemented yet (RED)")
        print("\n=== RESULT: 0 passed, 1 failed ===")
        sys.exit(1)

SR = 16000
def _tone(freq, dur, amp=0.3):
    t = np.arange(int(dur * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)

# ─── post-silence word: near-silence, then a tone onset at 0.30s ────────────
sil = (np.random.RandomState(0).randn(int(0.30 * SR)) * 0.0008).astype(np.float32)
word = _tone(300, 0.40)
x1 = np.concatenate([sil, word])
# Deepgram marks the start 120ms late at 0.42s; true onset is 0.30s
on1 = H._spectral_word_onset(x1, SR, 0.42, prev_end_s=0.0)
check("post-silence: onset found near the true 0.30s (±40ms)",
      on1 is not None and abs(on1 - 0.30) <= 0.04, on1)

# ─── MID-PHRASE word: continuous tone, freq CHANGE at 0.30s (no energy dip) ──
# this is the hole — no silence to snap to; spectral flux finds the boundary.
x2 = np.concatenate([_tone(200, 0.30), _tone(500, 0.40)])
on2 = H._spectral_word_onset(x2, SR, 0.42, prev_end_s=0.0)
check("MID-PHRASE (no energy dip): spectral flux finds the 0.30s boundary (±40ms)",
      on2 is not None and abs(on2 - 0.30) <= 0.04, on2)

# ─── on-time word (Deepgram ≈ true onset): no over-correction (returns None) ─
x3 = np.concatenate([sil, _tone(300, 0.40)])
# Deepgram marks 0.305 (≈ the true 0.30 onset, ~on time) → nothing to correct
on3 = H._spectral_word_onset(x3, SR, 0.305, prev_end_s=0.0)
check("on-time word: no correction (onset within 10ms of dg → None)", on3 is None, on3)

# ─── the bound: an onset >300ms before dg is out of the plausible late range ─
# a spurious early transient shouldn't pull the onset way back
x4 = np.concatenate([_tone(300, 0.60)])   # tone from 0.0; dg late-marked at 0.55
on4 = H._spectral_word_onset(x4, SR, 0.55, prev_end_s=0.0)
check("bounded: no correction beyond the 300ms plausible-late window",
      on4 is None or on4 >= 0.55 - 0.30, on4)

# ─── _audible_word_onset_s consumes the registry for mid-phrase words ────────
H._WORD_ONSET_LAST.clear()
H._LEVEL_SILENCES_LAST[:] = []
H._WITHIN_WORD_SILENCES_LAST[:] = []
_dg = [{"start": 1.00, "end": 1.30, "word": "a"},
       {"start": 1.52, "end": 1.90, "word": "mobile"}]   # word 1 has no preceding silence
# without a registry entry → falls back to Deepgram start (the hole)
check("hole present: mid-phrase word uncorrected without the onset registry",
      abs(H._audible_word_onset_s(_dg, 1) - 1.52) < 1e-6)
# with the spectral onset registry entry (true onset 1.41 = 110ms early) → corrected
H._WORD_ONSET_LAST[1] = 1.41
check("HOLE CLOSED: registry onset corrects the mid-phrase word",
      abs(H._audible_word_onset_s(_dg, 1) - 1.41) < 1e-6, H._audible_word_onset_s(_dg, 1))
# clamped to the previous word's tail (never reach into prior speech)
H._WORD_ONSET_LAST[1] = 1.10   # absurdly early
check("clamped to prev word tail − 80ms (never eats prior speech)",
      H._audible_word_onset_s(_dg, 1) >= 1.30 - 0.08 - 1e-6, H._audible_word_onset_s(_dg, 1))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL SFX HOLE-CLOSE CASES PASS")
