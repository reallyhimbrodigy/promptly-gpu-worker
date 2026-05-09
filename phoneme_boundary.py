"""Phoneme-class-aware word boundary correction for Deepgram transcripts.

Deepgram's `word.end` timestamp lands at the peak of the last
high-energy phoneme inside the word, not at the audible end of the
word. For words ending in low-energy phonemes — diphthongs (/oʊ/,
/aʊ/, /eɪ/, /aɪ/), long vowels (/iː/, /uː/), nasals (/m/, /n/, /ŋ/),
liquids (/l/, /r/), glides (/w/, /j/), or voiced fricatives — the
audible decay tail lives in the gap between `word.end` and
`next_word.start`, and is silently lost when the renderer cuts at
`word.end`. Stop-ending words ("stop", "back") have crisp acoustic
ends and don't suffer this.

This module corrects `word["end"]` IN-PLACE on the word list right
after Deepgram intake, before any downstream consumer (Gemini prompt
serialization, splicer, audio renderer, captions) reads it. The
extension is bounded by:

  1. A per-phoneme-class constant chosen to match the typical acoustic
     decay length of that class (e.g., diphthongs: 60 ms, voiced
     fricatives: 30 ms, stops: 0 ms).
  2. The next word's `start` timestamp (hard cap; never overlap into
     adjacent word content). For the last word in the transcript we
     fall back to `video_duration` when known; if unknown, downstream
     `e > _vd: e = _vd` clamping in build_clips_from_words handles
     overshoot.

Coverage: 100% by construction. The phonemizer (espeak-ng) is
rules-based G2P, so every input — real word, brand name, neologism,
gibberish — yields phonemes. Failure modes:

  * espeak misclassifies a stop-ending word as low-energy class →
    word gets +60ms it shouldn't, but the cap at next_word.start
    ensures we never overlap into the next word. Worst case: 60ms of
    silence inside the kept clip's tail.
  * Word phonemes empty (e.g., emoji-only token) → skip extension,
    behavior identical to today.
  * espeak binary missing / phonemize raises → ALL words skipped, log
    once at intake; behavior identical to today (graceful degradation).

The acoustic-phonetics constants below are not a uniform buffer.
Each value matches the physical decay time of its phoneme class:
voiceless stops have ~5 ms release; voiced fricatives ~30 ms voicing
tail; nasals ~50 ms murmur; diphthongs 50–150 ms vowel decay.
"""

from __future__ import annotations

import re
from typing import List, Optional


# Lazy-loaded espeak backend — single instance per process.
_BACKEND = None
_BACKEND_LOAD_ATTEMPTED = False


def _get_backend():
    """Initialize the espeak-ng phonemizer backend on first call.

    Subsequent calls return the cached instance (or None if the prior
    init failed — in which case all extension is skipped).
    """
    global _BACKEND, _BACKEND_LOAD_ATTEMPTED
    if _BACKEND_LOAD_ATTEMPTED:
        return _BACKEND
    _BACKEND_LOAD_ATTEMPTED = True
    try:
        from phonemizer.backend import EspeakBackend
        _BACKEND = EspeakBackend(
            language="en-us",
            preserve_punctuation=False,
            with_stress=False,
        )
    except Exception as e:
        print(
            f"[phoneme] espeak backend unavailable: {e!r} — "
            f"word boundaries will not be corrected (graceful fallback)",
            flush=True,
        )
        _BACKEND = None
    return _BACKEND


# Trailing IPA suffix → extension milliseconds. Ordered: longer suffixes
# FIRST so longest match wins (e.g., "oʊ" matches before any 1-char ending
# would). Constants reflect typical acoustic decay of each phoneme class.
# Symbols verified against `espeak-ng -q --ipa -v en-us` output (v1.52).
_TRAILING_SUFFIXES = [
    # Diphthongs — vowel decay 50-150ms; 60ms captures the audible tail
    # without spilling far into post-word silence.
    ("oʊ", 60), ("əʊ", 60), ("aʊ", 60), ("aɪ", 60), ("eɪ", 60), ("ɔɪ", 60),
    # Long vowels (espeak emits length marker `ː` for tense vowels).
    ("iː", 50), ("uː", 50), ("ɑː", 50), ("ɔː", 50), ("ɜː", 50), ("ɛː", 50),
    # R-colored vowels (rare in espeak en-us output but possible).
    ("ɝ", 50), ("ɚ", 50),
    # Nasals — murmur tail ~50ms.
    ("ŋ", 50), ("m", 50), ("n", 50),
    # Lateral, glides, rhotic — formant transition ~40ms. American English
    # R is /ɹ/ (alveolar approximant); espeak en-us emits this for word-
    # final R in "door", "for", "are", "her", "you're". /r/ included for
    # other voices/dialects that emit the trill.
    ("l", 40), ("w", 40), ("j", 40), ("ɹ", 40), ("r", 40),
    # Voiced fricatives — voicing tail ~30ms.
    ("ð", 30), ("ʒ", 30), ("v", 30), ("z", 30),
    # Word-final short tense /i/ — common in -y words ("happy", "really",
    # "city", "Promptly"). espeak emits bare /i/ (no length marker) here,
    # distinct from stressed long /iː/. Audible decay ~30ms.
    ("i", 30),
]

# Strip stress markers and whitespace (espeak emits these alongside
# phoneme glyphs even with with_stress=False, depending on version).
# Keep length marker `ː` since it's part of the phoneme identity for
# long-vowel matching.
_STRESS_AND_SPACE = re.compile(r"[ˈˌ\s]+")

# Punctuation to strip from the word text before phonemizing. Deepgram's
# `word` field is usually unpunctuated, but `punctuated_word` can have
# trailing comma / period / quote that confuses the phonemizer.
_TRIM_PUNCT = ",.!?;:\"'“”‘’—–-"

# Words that espeak phonemizes as their isolated letter-name (long form)
# but that Deepgram captures in their fluent-speech reduced form. Without
# an override we'd extend every "a" article in the transcript by +60ms
# (espeak: /eɪ/, actual fluent speech: /ə/). Add only the words confirmed
# to suffer this systematically; over-listing risks UNDER-extension on
# valid uses.
_NO_EXTEND_WORDS = {"a"}


def _classify_extension_ms(phones: str) -> int:
    """Return the per-class extension (ms) for an IPA string's trailing phoneme.

    Returns 0 for stops, voiceless fricatives, affricates, schwa, and
    unrecognized endings (those have crisp acoustic ends — no extension
    needed). The longest matching suffix wins.
    """
    if not phones:
        return 0
    cleaned = _STRESS_AND_SPACE.sub("", phones)
    if not cleaned:
        return 0
    for suffix, ms in _TRAILING_SUFFIXES:
        if cleaned.endswith(suffix):
            return ms
    return 0


def correct_word_ends(
    words: List[dict],
    video_duration: Optional[float] = None,
) -> dict:
    """Mutate words[i]['end'] in-place to capture audible word tails.

    For each word: phonemize, classify trailing phoneme, extend `end`
    by the per-class amount, capped at `next_word.start` (or
    `video_duration` for the last word; uncapped if neither known —
    downstream clamping handles overshoot).

    Words ending in stop-class phonemes get no extension and are
    bit-identical to today.

    Returns a stats dict for logging:
        {applied, skipped, capped, total_extended_ms, by_ms}
    """
    stats = {
        "applied": 0, "skipped": 0, "capped": 0,
        "total_extended_ms": 0.0, "by_ms": {},
    }
    if not words:
        return stats

    backend = _get_backend()
    if backend is None:
        # espeak unavailable — silent skip. Behavior identical to today.
        stats["skipped"] = len(words)
        return stats

    cleaned_words: List[str] = []
    for w in words:
        text = (w.get("word") or "").strip().strip(_TRIM_PUNCT)
        cleaned_words.append(text)

    # One batch call. phonemizer returns a list aligned with input.
    try:
        from phonemizer.separator import Separator
        phones_list = backend.phonemize(
            cleaned_words,
            separator=Separator(phone="", word=None, syllable=None),
            strip=True,
            njobs=1,
        )
    except Exception as e:
        print(
            f"[phoneme] phonemize batch failed: {e!r} — "
            f"word boundaries unchanged for this transcript",
            flush=True,
        )
        stats["skipped"] = len(words)
        return stats

    if len(phones_list) != len(words):
        # Sanity check — phonemizer returning a different length than input
        # would shift extensions onto the wrong words. Refuse to apply.
        print(
            f"[phoneme] phonemize length mismatch: "
            f"{len(phones_list)} phones vs {len(words)} words — skipping",
            flush=True,
        )
        stats["skipped"] = len(words)
        return stats

    n = len(words)
    for i, w in enumerate(words):
        # Skip words whose isolated phonemization disagrees with their
        # fluent-speech form (e.g., "a" article).
        if cleaned_words[i].lower() in _NO_EXTEND_WORDS:
            stats["skipped"] += 1
            continue
        ext_ms = _classify_extension_ms(phones_list[i])
        if ext_ms <= 0:
            stats["skipped"] += 1
            continue

        # Determine the upper bound for this word's end.
        if i + 1 < n:
            upper = float(words[i + 1]["start"])
        elif video_duration is not None:
            upper = float(video_duration)
        else:
            upper = float("inf")

        original_end = float(w["end"])
        proposed_end = original_end + ext_ms / 1000.0
        new_end = min(proposed_end, upper)

        if new_end <= original_end:
            # Cap kicked in at or below the original — no actual extension.
            stats["skipped"] += 1
            continue

        actual_ms = (new_end - original_end) * 1000.0
        if proposed_end > upper:
            stats["capped"] += 1
        w["end"] = new_end
        stats["applied"] += 1
        stats["total_extended_ms"] += actual_ms
        stats["by_ms"][ext_ms] = stats["by_ms"].get(ext_ms, 0) + 1

    return stats
