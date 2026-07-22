"""Step 1 perception-machinery unit tests — deterministic, local, no aubio, no
real video, no dependence on the (held) real-user-audio cert corpus.

Tests the MACHINERY (gating, fail-safe, shape, inertness, the shake curve_out
plumbing). aubio's detection ACCURACY is certified separately (Brick 2).
"""
import os
import sys
import json
import dataclasses

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import general_editor as ge


def test_beat_grid_gated_on_has_audio():
    # no-audio job pays nothing: returns [] without touching aubio
    assert ge.compute_beat_grid("anything.wav", has_audio=False) == []
    # has_audio but no path -> []
    assert ge.compute_beat_grid(None, has_audio=True) == []


def test_beat_grid_uses_aubio_when_present(monkeypatch=None):
    # stub the isolated aubio call; compute_beat_grid must pass through
    _orig = ge._aubio_beats
    try:
        ge._aubio_beats = lambda p: [0.5, 1.0, 1.5, 2.0]
        assert ge.compute_beat_grid("song.wav", has_audio=True) == [0.5, 1.0, 1.5, 2.0]
    finally:
        ge._aubio_beats = _orig


def test_aubio_beats_failsafe_without_aubio():
    # aubio is Modal-image-only; locally the import fails -> [] (never raises)
    assert ge._aubio_beats("nonexistent.wav") == []


def test_perception_carries_new_fields_and_defaults_inert():
    # defaults: new fields empty/inert
    p0 = ge.build_perception(has_speech=True, has_audio=True, faces=True,
                             content_class="talking_head")
    assert p0.beat_grid == [] and p0.motion_curve == [] and p0.has_music is False
    # populated: beat_grid + motion_curve carried through
    p1 = ge.build_perception(has_speech=False, has_audio=True, faces=False,
                             content_class="music",
                             beat_grid=[0.5, 1.0], motion_curve=[1.2, 0.8, 1.1])
    assert p1.beat_grid == [0.5, 1.0]
    assert p1.motion_curve == [1.2, 0.8, 1.1]
    # asdict must be JSON-safe (it is stored on edit_plan as a _foo dict)
    json.dumps(dataclasses.asdict(p1))


def test_timeline_n1_single_source():
    n1 = ge.Timeline(clips=[ge.TimelineClip(0, 0, 120), ge.TimelineClip(0, 120, 90)])
    assert n1.is_single_source is True   # N=1 -> current path
    n2 = ge.Timeline(clips=[ge.TimelineClip(0, 0, 120), ge.TimelineClip(1, 0, 90)])
    assert n2.is_single_source is False  # N>=2 -> Step 4 assembly


def test_shake_curve_out_preserves_scalar_contract():
    # curve_out must NOT change the scalar return contract. cv2 (opencv) is
    # Modal-image-only; inject a minimal fake so the real fail-closed path runs:
    # an unopenable source returns 0.0 (a float, NOT a tuple) and leaves curve_out
    # empty. Proves the byte-identity-critical deshake score is untouched.
    import types
    fake_cv2 = types.ModuleType("cv2")

    class _Cap:
        def isOpened(self): return False
        def release(self): pass

    fake_cv2.VideoCapture = lambda p: _Cap()
    sys.modules["cv2"] = fake_cv2
    try:
        import handler
        curve = []
        score = handler._probe_shake_intensity("/nonexistent.mp4", curve_out=curve)
        assert isinstance(score, float) and score == 0.0, f"scalar contract broken: {score!r}"
        assert curve == [], f"curve_out should stay empty on fail path: {curve!r}"
    finally:
        sys.modules.pop("cv2", None)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} perception unit tests passed")
    sys.exit(0 if passed == len(tests) else 1)
