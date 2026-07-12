"""SFX ATTACK-MATCHED-TO-MEASURABILITY (Zac 2026-07-12). Per-word onset
re-detection was measured NOT accurate enough (offline harness: 54-64ms err >
the 55-113ms lateness) and removed. Instead: a SHARP-attack sound fires only
where the onset is MEASURABLE (a dB silence anchors it); a SOFT (swell) sound
fires anywhere (its attack ramp masks the imprecision). Gemini is taught to pick
soft sounds for mid-phrase emphasis; _sfx_may_fire is the physical guarantee."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# the dead detector is fully removed (proven inert 0/85 + wasted decode/FFT)
for _fn in ("_spectral_word_onset", "_detect_word_onsets", "_WORD_ONSET_LAST"):
    check(f"dead detector {_fn} removed", not hasattr(H, _fn))

for _fn in ("_sfx_onset_measurable", "_sfx_may_fire", "_SFX_SHARP_ATTACK_MS"):
    if not hasattr(H, _fn):
        print(f"  FAIL  {_fn} not implemented yet (RED)")
        print("\n=== RESULT: 0 passed, 1 failed ===")
        sys.exit(1)

check("sharp threshold is 200ms", H._SFX_SHARP_ATTACK_MS == 200, H._SFX_SHARP_ATTACK_MS)
# the attack table splits cleanly at 200: popsfx(32) sharp, boom(287) soft
check("popsfx is sharp (< threshold)", H._SFX_ATTACK_MS["popsfx"] < H._SFX_SHARP_ATTACK_MS)
check("boom is soft (>= threshold)", H._SFX_ATTACK_MS["boom"] >= H._SFX_SHARP_ATTACK_MS)

dg = [{"start": 1.0, "end": 1.3, "word": "a"}, {"start": 1.6, "end": 1.9, "word": "easy"}]

# MID-PHRASE (no silence): onset not measurable
H._LEVEL_SILENCES_LAST[:] = []
H._WITHIN_WORD_SILENCES_LAST[:] = []
check("mid-phrase word: onset NOT measurable", H._sfx_onset_measurable(dg, 1) is False)
check("sharp sound on mid-phrase → does NOT fire (would land off-beat)",
      H._sfx_may_fire("popsfx", dg, 1) is False)
check("soft sound on mid-phrase → fires (ramp masks the imprecision)",
      H._sfx_may_fire("boom", dg, 1) is True)

# POST-SILENCE: a dB silence ends at 1.52, just before the Deepgram 1.6 start
H._LEVEL_SILENCES_LAST[:] = [(1.2, 1.52)]
check("post-silence word: onset IS measurable", H._sfx_onset_measurable(dg, 1) is True)
check("sharp sound on measurable onset → fires (lands on the beat)",
      H._sfx_may_fire("popsfx", dg, 1) is True)
check("soft sound still fires on measurable onset", H._sfx_may_fire("boom", dg, 1) is True)

# unknown sound (not in the table) → treated as sharp (fire only when measurable)
H._LEVEL_SILENCES_LAST[:] = []
check("unknown sound treated as sharp on mid-phrase → no fire",
      H._sfx_may_fire("not-a-real-sound", dg, 1) is False)

H._LEVEL_SILENCES_LAST[:] = []
H._WITHIN_WORD_SILENCES_LAST[:] = []
print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SFX MEASURABILITY CASES PASS")
