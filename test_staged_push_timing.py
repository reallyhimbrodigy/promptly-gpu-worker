"""STAGEDPUSH TIMING (Zac 2026-07-13, Phase 1 — the crux). Each of the 2-3 stage
peaks must land EXACTLY on its word's audible onset. The plan builds stage.atMs in
absolute source ms (the word's onset); the render threads each atMs through the SAME
source→clip-local conversion as a single event's startMs — (atMs - clip_start_ms)/pbr
→ msToFrames — so the stage PEAK lands on the identical clip-local frame the word
plays on. This asserts that frame-exact alignment across onsets, clip starts, and
playback rates, plus the degrade-to-SmoothPush and cutTerminated rules."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

FPS = 60.0

def _render_convert_to_frame(at_ms, clip_start_ms, pbr):
    # EXACT copy of the render projection (handler.py:19975 + the component msToFrames)
    clip_local_ms = int(round((at_ms - clip_start_ms) / pbr))
    return int(round(clip_local_ms / 1000.0 * FPS))   # StagedPush component: msToFrames(atMs)

def _word_clip_frame(onset_s, clip_start_s, pbr):
    # where the word actually plays in clip-local render frames
    return int(round((onset_s - clip_start_s) / pbr * FPS))

# mock deepgram words at chosen onsets (Lever B: audible onset == raw start)
def _dg(onsets):
    return [{"word": "w", "start": s, "end": s + 0.25} for s in onsets]

# ── the STAGE PEAK lands on the WORD's clip-local frame (≤1 frame — the precision gate) ──
CASES = [
    # (three consecutive building word onsets, clip_source_start_s, pbr)
    ([2.08, 2.88, 3.60], 0.0, 1.0),
    ([10.517, 11.30, 12.06], 8.0, 1.0),
    ([5.333, 6.10, 6.90], 4.0, 1.25),   # sped-up clip
    ([1.005, 1.80, 2.60], 0.5, 1.0),    # fractional-frame onset (the caption-lag zone)
]
for onsets, clip_start_s, pbr in CASES:
    _stages, _wis = H._staged_push_stages(onsets_indices := list(range(len(onsets))), _dg(onsets))
    clip_start_ms = clip_start_s * 1000.0
    for i, (st, onset_s) in enumerate(zip(_stages, onsets)):
        _peak_f = _render_convert_to_frame(st["atMs"], clip_start_ms, pbr)
        _word_f = _word_clip_frame(onset_s, clip_start_s, pbr)
        check(f"onsets{onsets} pbr={pbr}: stage {i+1} peak frame {_peak_f} == word frame {_word_f}",
              abs(_peak_f - _word_f) <= 1, f"peak={_peak_f} word={_word_f}")

# ── equal steps (Zac ruling): +8% per stage → 1.08 / 1.16 / 1.24 ──
_s3, _ = H._staged_push_stages([0, 1, 2], _dg([1.0, 1.8, 2.6]))
check("3-part equal steps → 1.08, 1.16, 1.24", [s["scale"] for s in _s3] == [1.08, 1.16, 1.24], [s["scale"] for s in _s3])
_s2, _ = H._staged_push_stages([0, 1], _dg([1.0, 1.8]))
check("2-part equal steps → 1.08, 1.16", [s["scale"] for s in _s2] == [1.08, 1.16], [s["scale"] for s in _s2])

# ── <2 building words → DEGRADE to SmoothPush (a staged push on 1 word is wrong) ──
_ze = {"type": "StagedPush", "events": [{"startMs": 700, "durationMs": 1200, "scale": 1.22}]}
H._augment_staged_push_event(_ze, [0], _dg([1.0]), [{"source_start": 0.0, "source_end": 5.0}])
check("1 word → degrades to SmoothPush (not a staged push)", _ze["type"] == "SmoothPush")

# ── cutTerminated: a clip source_end shortly after the last word ⇒ True (hold, no release) ──
_ze2 = {"type": "StagedPush", "events": [{"startMs": 700, "durationMs": 1200, "scale": 1.22}]}
H._augment_staged_push_event(_ze2, [0, 1, 2], _dg([1.0, 1.8, 2.6]), [{"source_start": 0.0, "source_end": 2.7}])
check("cut 0.1s after the last word → cutTerminated True", _ze2["events"][0]["cutTerminated"] is True)
_ze3 = {"type": "StagedPush", "events": [{"startMs": 700, "durationMs": 1200, "scale": 1.22}]}
H._augment_staged_push_event(_ze3, [0, 1, 2], _dg([1.0, 1.8, 2.6]), [{"source_start": 0.0, "source_end": 9.0}])
check("phrase continues (cut far away) → cutTerminated False (ease-out release)", _ze3["events"][0]["cutTerminated"] is False)
check("continuing event spans to release end (holdMs+releaseMs past last word)",
      _ze3["events"][0]["durationMs"] == (2600 + 260 + 360) - (1000 - 280), _ze3["events"][0]["durationMs"])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL STAGEDPUSH-TIMING CASES PASS")
