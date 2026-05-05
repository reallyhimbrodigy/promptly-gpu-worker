"""CTC forced alignment — refines Deepgram word boundaries to be waveform-accurate.

Why this exists
---------------
Deepgram word.start / word.end are model-predicted timestamps with ~30-150ms
imprecision. When the pipeline cuts at exactly word.end of the last kept word
in a clip and the next words are removed filler, the actual phoneme tail of
the kept word can extend past Deepgram's timestamp — and the start of the
adjacent (removed) word can begin before it. The half-handle audio model
reads source[clip_b_start, clip_b_start + 0.2s] for B_head_half, which
catches that bleed and produces the perceived "kno-" / "lear-" leakage at
transitions.

The fix is a CTC forced-alignment post-step: re-align each word against the
actual audio waveform using a wav2vec2-class CTC head trained at 16kHz,
20ms frame stride. This produces 10-20ms-accurate word boundaries — well
below the threshold at which phoneme leakage is perceptible.

Architecture
------------
This module runs INSIDE a GPU Modal container (align_audio_remote in
modal_app.py). The orchestrator extracts a 16kHz mono PCM wav and sends
its bytes + the Deepgram word list over RPC. We return the same word
list with `start` / `end` rewritten and `_align_logprob` added per word.

Confidence gate
---------------
CTC produces a per-word log-probability. When confidence is too low
(typically: heavy background music, overlapping speech, extreme accents
far from the training distribution), instead of falling back to Deepgram
timestamps (which would defeat the point), we snap that word's boundary
to the nearest audio zero-crossing within ±50ms. Deterministic, waveform-
derived, no second model. One branch — not a fallback chain.
"""

from __future__ import annotations

import os
import wave
from typing import Any

import numpy as np

# Lazy globals — model load is ~2-4s, hold across calls within a warm container.
_aligner_model = None
_aligner_tokenizer = None

# Default model path — baked into the Modal image at build time
# (see modal_app.py snapshot_download command).
_MODEL_PATH = os.environ.get("PROMPTLY_ALIGN_MODEL_PATH", "/models/aligner")

# CTC operates at 16kHz internally. The orchestrator extracts at 16kHz so
# we don't burn GPU time on a resample at request time.
SAMPLE_RATE = 16000

# Default per-frame confidence floor.
#
# The library returns SUMMED log-probability over a word's CTC frames, so
# the absolute score scales with word duration — a long word ("electrocuted")
# has a large negative sum even when correctly aligned, while a short word
# ("a") near zero. Comparing the sum against a fixed threshold systematically
# over-snaps long words.
#
# Per-frame normalization (score / num_frames) gives a duration-invariant
# confidence: ~-0.5 is matched speech, -1.0 is borderline, < -2.0 typically
# indicates OOV / mismatch / noise. Threshold of -1.5 catches the truly bad
# alignments without misfiring on normal multi-syllable words. Production
# log distribution will tell us if this needs further tuning (we log p10 /
# median / p90 of the score distribution per render).
DEFAULT_LOGPROB_PER_FRAME_THRESHOLD = -1.5

# CTC frame stride for wav2vec2/MMS at 16kHz. Conv layers downsample 16kHz
# audio to 50fps emissions (= 320 samples = 20ms per frame). Used to convert
# word duration in seconds → number of CTC frames for normalization.
CTC_FRAME_STRIDE_SEC = 0.020

# Zero-crossing search window for low-confidence words. ±50ms is short
# enough to stay near the CTC-predicted boundary but long enough to find
# a real zero-crossing in voiced speech (period of ~5-10ms at 100-200Hz F0).
DEFAULT_SNAP_WINDOW_MS = 50.0


def _get_aligner():
    """Lazy-load the wav2vec2/MMS CTC aligner. First call ~2-4s; subsequent calls free."""
    global _aligner_model, _aligner_tokenizer
    if _aligner_model is None:
        import torch
        from ctc_forced_aligner import load_alignment_model

        # fp16 halves VRAM and is lossless for forced alignment (CTC outputs
        # are softmax probabilities, not regression — fp16 precision is plenty).
        _aligner_model, _aligner_tokenizer = load_alignment_model(
            "cuda",
            dtype=torch.float16,
            model_path=_MODEL_PATH,
        )
        print(
            f"[align] loaded MMS-300M from {_MODEL_PATH} (fp16 on cuda)",
            flush=True,
        )
    return _aligner_model, _aligner_tokenizer


def _snap_to_zero_crossing(
    samples: np.ndarray,
    target_idx: int,
    sample_rate: int,
    search_window_ms: float = DEFAULT_SNAP_WINDOW_MS,
) -> int:
    """Find the nearest zero-crossing to `target_idx` within ±search_window_ms.

    A zero-crossing is a sample boundary where the signal changes sign — at
    that exact sample the audio is at silence by definition, so cutting
    there avoids any sample-edge transient.

    Returns target_idx unchanged if no zero-crossing exists in the window
    (rare in voiced speech; possible in pure silence where any sample is
    already "zero").
    """
    if len(samples) <= 1:
        return target_idx
    window = int(search_window_ms * sample_rate / 1000.0)
    lo = max(1, target_idx - window)
    hi = min(len(samples), target_idx + window)
    if hi <= lo:
        return target_idx

    # Sign-change between consecutive samples = zero-crossing.
    seg = samples[lo - 1: hi]
    signs = np.sign(seg)
    # Treat exact zeros as crossings too.
    signs[signs == 0] = 1
    crossings = np.where(np.diff(signs) != 0)[0]
    if len(crossings) == 0:
        return target_idx

    # Pick the crossing closest to target_idx in absolute samples.
    crossing_abs = lo + crossings  # sample indices in `samples` space
    best = crossing_abs[np.argmin(np.abs(crossing_abs - target_idx))]
    return int(best)


def _read_wav_mono_16k(path: str) -> np.ndarray:
    """Read a 16kHz mono PCM wav into a float32 numpy array in [-1, 1]."""
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        if sr != SAMPLE_RATE:
            raise RuntimeError(
                f"forced_align expects {SAMPLE_RATE}Hz wav, got {sr}Hz at {path}. "
                f"The orchestrator must extract at 16kHz before calling."
            )
        if wf.getnchannels() != 1:
            raise RuntimeError(
                f"forced_align expects mono wav, got {wf.getnchannels()} channels"
            )
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def forced_align(
    audio_wav_path: str,
    deepgram_words: list[dict[str, Any]],
    language: str = "eng",
    logprob_per_frame_threshold: float = DEFAULT_LOGPROB_PER_FRAME_THRESHOLD,
    snap_window_ms: float = DEFAULT_SNAP_WINDOW_MS,
) -> list[dict[str, Any]]:
    """Refine Deepgram word boundaries using CTC forced alignment.

    Args:
        audio_wav_path: 16kHz mono PCM wav file path.
        deepgram_words: List of Deepgram word dicts. Each must have at
            least `word` and `start` / `end`. Other fields (`punctuated_word`,
            `confidence`, `speaker`) are preserved verbatim.
        language: ISO-639-3 code for the aligner. "eng" by default; the
            MMS-300M model supports 1000+ languages.
        logprob_threshold: Words with summed CTC log-probability below this
            value have their boundaries snapped to zero-crossings.
        snap_window_ms: Half-width of the zero-crossing search window for
            low-confidence words.

    Returns:
        New list of dicts (same length and order as input) with:
          - `start` and `end` REPLACED with refined seconds-precision values
          - `_align_logprob` ADDED (float, summed log-prob from CTC)
          - `_align_snapped` ADDED (bool, true if zero-crossing snap fired)
          - all other fields preserved verbatim

    Raises:
        RuntimeError if alignment fails on the entire clip. We do NOT fall
        back to Deepgram timestamps — that defeats the purpose. Per-word
        failures snap to zero-crossings instead (see logprob_threshold).
    """
    if not deepgram_words:
        return []

    # Lazy imports — pulling torch in at module import time would cost ~1s
    # on every container start even when alignment is never called.
    import torch
    from ctc_forced_aligner import (
        generate_emissions,
        get_alignments,
        get_spans,
        load_audio,
        postprocess_results,
        preprocess_text,
    )

    model, tokenizer = _get_aligner()

    # Two reads of the audio: one as a torch tensor for the aligner
    # (their helper handles dtype/device placement), and one as a numpy
    # array for the zero-crossing snap.
    waveform = load_audio(audio_wav_path, model.dtype, model.device)
    samples = _read_wav_mono_16k(audio_wav_path)

    # Concatenate all words into one transcript string. The aligner's
    # `preprocess_text` strips punctuation and handles contractions
    # (e.g. "don't" → "dont"), and `split_size="word"` ensures the output
    # spans match the input list 1:1. OOV proper nouns are absorbed by
    # `<star>` tokens (`star_frequency="segment"`) — the neighboring words'
    # alignment stays accurate; only the OOV word itself snaps to ZC.
    text = " ".join(str(w.get("word") or "").strip() for w in deepgram_words)
    if not text.strip():
        # All words are empty strings — return input unmodified except mark
        # _align_logprob as None so callers can detect.
        return [
            {**w, "_align_logprob": None, "_align_snapped": False}
            for w in deepgram_words
        ]

    tokens_starred, text_starred = preprocess_text(
        text,
        romanize=True,
        language=language,
        split_size="word",
        star_frequency="segment",
    )

    # CTC forward pass + Viterbi decoding. batch_size controls chunking
    # for long audio — 16 is safe for 60s clips on L4.
    emissions, stride = generate_emissions(
        model, waveform, batch_size=16,
    )
    segments, scores, blank = get_alignments(
        emissions, tokens_starred, tokenizer,
    )
    spans = get_spans(tokens_starred, segments, blank)
    aligned = postprocess_results(text_starred, spans, stride, scores)

    # `aligned` is a list of {"text", "start", "end", "score"} per word,
    # in the same order as the input. Length should match deepgram_words
    # when split_size="word"; if not, the aligner couldn't process some
    # words and we fail loud rather than guessing the mapping.
    if len(aligned) != len(deepgram_words):
        raise RuntimeError(
            f"Alignment word count mismatch: aligner returned {len(aligned)} "
            f"words, expected {len(deepgram_words)}. Cannot zip refined "
            f"timestamps back onto Deepgram word list. Check transcript "
            f"normalization (contractions, punctuation, hyphenation)."
        )

    # Zip refined timestamps onto the original list, applying the
    # confidence gate + zero-crossing snap for low-logprob words.
    # Confidence is normalized PER CTC FRAME so the threshold is duration-
    # invariant (see DEFAULT_LOGPROB_PER_FRAME_THRESHOLD comment).
    n_snapped = 0
    refined: list[dict[str, Any]] = []
    for orig, ref in zip(deepgram_words, aligned):
        score = float(ref.get("score") or 0.0)
        start_sec = float(ref.get("start") or 0.0)
        end_sec = float(ref.get("end") or 0.0)
        snapped = False

        # Number of CTC frames spanning this word — used to normalize the
        # summed logprob into a per-frame confidence. Floor at 1 to avoid
        # divide-by-zero for degenerate spans.
        n_frames = max(1, int(round((end_sec - start_sec) / CTC_FRAME_STRIDE_SEC)))
        per_frame_score = score / n_frames

        if per_frame_score < logprob_per_frame_threshold:
            start_idx = int(round(start_sec * SAMPLE_RATE))
            end_idx = int(round(end_sec * SAMPLE_RATE))
            new_start_idx = _snap_to_zero_crossing(
                samples, start_idx, SAMPLE_RATE, snap_window_ms,
            )
            new_end_idx = _snap_to_zero_crossing(
                samples, end_idx, SAMPLE_RATE, snap_window_ms,
            )
            # Guard: end must remain after start. If snapping produced a
            # zero-or-negative span (rare but possible in dense voicing),
            # keep CTC's original boundaries for this word — the leakage
            # mitigation isn't worth a degenerate clip range.
            if new_end_idx > new_start_idx:
                start_sec = new_start_idx / SAMPLE_RATE
                end_sec = new_end_idx / SAMPLE_RATE
                snapped = True
                n_snapped += 1

        refined.append({
            **orig,
            "start": start_sec,
            "end": end_sec,
            "_align_logprob": score,
            "_align_snapped": snapped,
        })

    # Free GPU memory between calls — wav2vec2 emissions tensor for a 60s
    # clip is ~50-100MB and accumulates across calls otherwise.
    del waveform, emissions
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print(
        f"[align] refined {len(refined)} words "
        f"({n_snapped} snapped to zero-crossing, "
        f"per-frame threshold={logprob_per_frame_threshold})",
        flush=True,
    )
    return refined
