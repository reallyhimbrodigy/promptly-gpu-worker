#!/usr/bin/env python3
"""Wiring smoke test for align_audio.py.

Runs WITHOUT requiring a GPU or the wav2vec2 model — exercises the
module's import surface, the zero-crossing snap helper, and the input
validation. Real alignment is exercised only inside the Modal container
on every production render; this catches local regressions in the
helper code that are easy to introduce and hard to detect otherwise.

Usage: python3 scripts/test_forced_align.py
Exit 0 on success, non-zero on failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


def _write_synthetic_wav(path: str, duration_sec: float = 1.0, freq_hz: float = 200.0) -> None:
    """Write a 16kHz mono PCM wav containing a sine wave at `freq_hz`."""
    sr = 16000
    n = int(round(duration_sec * sr))
    t = np.linspace(0, duration_sec, n, endpoint=False)
    samples = (np.sin(2 * np.pi * freq_hz * t) * 16000).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def test_zero_crossing_snap_finds_nearest() -> None:
    """A sine wave has a zero-crossing every half-period; snap should locate one."""
    from align_audio import _snap_to_zero_crossing, SAMPLE_RATE

    # 200Hz sine wave: period 80 samples at 16kHz, half-period 40 samples.
    n = SAMPLE_RATE  # 1 second
    t = np.linspace(0, 1.0, n, endpoint=False)
    samples = np.sin(2 * np.pi * 200.0 * t).astype(np.float32)

    # Target deliberately off a zero-crossing — should snap to within
    # one half-period (40 samples).
    target = 5000  # 0.3125s — sin(2π·200·0.3125) ≈ sin(125π) = 0, but we
    # add a small offset to make sure we're not already on a zc.
    target = 5005
    snapped = _snap_to_zero_crossing(samples, target, SAMPLE_RATE, search_window_ms=50.0)

    # Snapped index should differ from target (we're not on a zc) and
    # should be within ±50ms = 800 samples.
    assert abs(snapped - target) <= 800, (
        f"snap moved {snapped - target} samples — outside 50ms window"
    )
    # And it should be near a true zero-crossing — i.e., the sample value
    # at `snapped` is small in absolute terms.
    assert abs(samples[snapped]) < abs(samples[target]) or abs(samples[snapped]) < 0.1, (
        f"snap landed at sample value {samples[snapped]:.3f}, "
        f"vs target value {samples[target]:.3f} — should be closer to zero"
    )


def test_zero_crossing_snap_no_movement_on_silence() -> None:
    """Pure silence has no sign-change; snap should return the original index."""
    from align_audio import _snap_to_zero_crossing, SAMPLE_RATE

    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    target = 8000
    snapped = _snap_to_zero_crossing(samples, target, SAMPLE_RATE, search_window_ms=50.0)
    assert snapped == target, (
        f"snap on pure silence should be a no-op; moved {target} → {snapped}"
    )


def test_wav_reader_validates_format() -> None:
    """forced_align rejects non-16kHz / non-mono wavs loudly."""
    from align_audio import _read_wav_mono_16k

    # 16kHz mono — should pass.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        _write_synthetic_wav(path)
        arr = _read_wav_mono_16k(path)
        assert arr.dtype == np.float32
        assert arr.ndim == 1
        assert len(arr) == 16000  # 1 second at 16kHz
        assert -1.0 <= arr.min() and arr.max() <= 1.0
    finally:
        os.unlink(path)

    # 48kHz mono — should raise.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        sr_wrong = 48000
        n = sr_wrong
        samples = np.zeros(n, dtype=np.int16)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr_wrong)
            wf.writeframes(samples.tobytes())
        try:
            _read_wav_mono_16k(path)
        except RuntimeError as e:
            assert "16000Hz" in str(e) or "16000" in str(e)
        else:
            raise AssertionError("expected RuntimeError for 48kHz wav, got nothing")
    finally:
        os.unlink(path)


def test_empty_word_list_returns_empty() -> None:
    """forced_align must short-circuit cleanly on empty transcripts."""
    # Don't import torch / load model — empty input takes the early-return
    # path before _get_aligner() is called.
    from align_audio import forced_align

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        _write_synthetic_wav(path)
        result = forced_align(path, [])
        assert result == [], f"expected [] for empty input, got {result!r}"
    finally:
        os.unlink(path)


def main() -> int:
    tests = [
        ("zero_crossing snap finds nearest", test_zero_crossing_snap_finds_nearest),
        ("zero_crossing snap no-op on silence", test_zero_crossing_snap_no_movement_on_silence),
        ("wav reader validates 16kHz mono", test_wav_reader_validates_format),
        ("empty word list returns empty", test_empty_word_list_returns_empty),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[align-test] PASS: {name}")
        except Exception as e:
            failed += 1
            print(f"[align-test] FAIL: {name} — {type(e).__name__}: {e}", file=sys.stderr)
    if failed:
        print(f"[align-test] {failed} test(s) failed", file=sys.stderr)
        return 1
    print(f"[align-test] all {len(tests)} test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
