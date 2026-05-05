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

Why no zero-crossing snap / no buffer
-------------------------------------
CTC's output IS the answer. Layering a zero-crossing snap on top of low-
confidence words is just trading model uncertainty for an arbitrary
deterministic shift — a different flavor of the same buffer-style heuristic
this whole integration was meant to replace. If a word has weak alignment
(OOV, music overlap, accent mismatch), CTC's best estimate is still our
best estimate. The per-word logprob is logged so we can find systematic
weakness and address it at the source (e.g., language flag, model swap),
not paper over it with snaps.
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

# CTC frame stride for wav2vec2/MMS at 16kHz. Conv layers downsample 16kHz
# audio to 50fps emissions (= 320 samples = 20ms per frame). Used to convert
# word duration in seconds → number of CTC frames for normalized logprob
# logging (which is duration-invariant unlike the raw summed score).
CTC_FRAME_STRIDE_SEC = 0.020


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
) -> list[dict[str, Any]]:
    """Refine Deepgram word boundaries using CTC forced alignment.

    Args:
        audio_wav_path: 16kHz mono PCM wav file path.
        deepgram_words: List of Deepgram word dicts. Each must have at
            least `word` and `start` / `end`. Other fields (`punctuated_word`,
            `confidence`, `speaker`) are preserved verbatim.
        language: ISO-639-3 code for the aligner. "eng" by default; the
            MMS-300M model supports 1000+ languages.

    Returns:
        New list of dicts (same length and order as input) with:
          - `start` and `end` REPLACED with refined seconds-precision values
          - `_align_logprob` ADDED (float, summed log-prob from CTC over the
            word's frames; scales with duration, see CTC_FRAME_STRIDE_SEC)
          - all other fields preserved verbatim

    Raises:
        RuntimeError if alignment fails on the entire clip. We do NOT fall
        back to Deepgram timestamps — that defeats the purpose. The model's
        per-word output IS the answer; low-confidence words still report
        CTC's best estimate (no snaps, no buffers).
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
    waveform = load_audio(audio_wav_path, model.dtype, model.device)

    # Concatenate all words into one transcript string. The aligner's
    # `preprocess_text` strips punctuation and handles contractions
    # (e.g. "don't" → "dont"), and `split_size="word"` ensures the output
    # spans match the input list 1:1. OOV proper nouns are absorbed by
    # `<star>` tokens (`star_frequency="segment"`) — the neighboring words'
    # alignment stays accurate; the OOV word itself reports CTC's best guess
    # with a low logprob (visible in the score distribution log).
    text = " ".join(str(w.get("word") or "").strip() for w in deepgram_words)
    if not text.strip():
        return [{**w, "_align_logprob": None} for w in deepgram_words]

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

    # Zip refined timestamps onto the original list. Trust CTC's output —
    # no confidence gate, no snap. The model's prediction IS the answer.
    refined: list[dict[str, Any]] = []
    for orig, ref in zip(deepgram_words, aligned):
        refined.append({
            **orig,
            "start": float(ref.get("start") or 0.0),
            "end": float(ref.get("end") or 0.0),
            "_align_logprob": float(ref.get("score") or 0.0),
        })

    # Free GPU memory between calls — wav2vec2 emissions tensor for a 60s
    # clip is ~50-100MB and accumulates across calls otherwise.
    del waveform, emissions
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return refined
