"""CLIP -> SOURCE MATCHER. Mechanical, never a model.

Zac: "The matching step is where the intelligence comes from and it's the
expensive part — clips without their source context are just finished edits."

THE MATCH IS MECHANICAL AND THAT IS A DESIGN RULE, NOT A SHORTCUT. A model asked
"where did this clip come from" will ALWAYS produce an offset, including when the
clip did not come from that source at all. A confident wrong offset is worse than
UNMATCHED because every downstream selection fact silently inherits it —
selection_ratio, "where in the source do performing clips live", "what was passed
over". Same rule as ffmpeg owning the cuts.

So: align the clip's transcript against the long-form transcript and take the
best contiguous window. UNMATCHED is a first-class return value.
"""
import difflib
import re

# Below this share of clip tokens located in the source, the pair is UNMATCHED.
# Deliberately not lower: a clip cut from a DIFFERENT episode by the same creator
# shares filler words and catchphrases, and that noise floor is exactly what a
# permissive threshold would admit as a match.
MIN_COVERAGE = 0.55
# A real clip is contiguous-ish in its source. If the located tokens sprawl over
# a window many times the clip's own length, they are scattered coincidences
# rather than one span.
MAX_SPRAWL = 4.0


def _norm(tokens):
    """Normalised comparison tokens. Punctuation and case carry no alignment
    signal and differ between two transcription passes of the same words."""
    out = []
    for t in tokens:
        w = re.sub(r"[^a-z0-9']", "", str(t.get("w") or t.get("word") or "").lower())
        out.append(w)
    return out


def match_clip_to_source(clip_words, source_words,
                         source_duration_s=None,
                         min_coverage=MIN_COVERAGE):
    """Locate `clip_words` inside `source_words`.

    Returns a dict always — never raises, never guesses:
      {method: 'transcript_align'|'UNMATCHED', t_start, t_end, confidence,
       selection_ratio, matched_tokens, clip_tokens, why}
    """
    def unmatched(why):
        return {"method": "UNMATCHED", "t_start": None, "t_end": None,
                "confidence": 0.0, "selection_ratio": None,
                "matched_tokens": 0, "clip_tokens": len(clip_words or []),
                "why": why}

    if not clip_words or not source_words:
        return unmatched("empty transcript on one side")

    c_norm, s_norm = _norm(clip_words), _norm(source_words)
    c_idx = [i for i, w in enumerate(c_norm) if w]
    if len(c_idx) < 8:
        # Too short to identify. Eight tokens of common speech appear in almost
        # any long-form transcript, so anything shorter cannot be evidence.
        return unmatched(f"clip has only {len(c_idx)} usable tokens (need 8)")

    c_seq = [c_norm[i] for i in c_idx]
    s_idx = [i for i, w in enumerate(s_norm) if w]
    s_seq = [s_norm[i] for i in s_idx]

    sm = difflib.SequenceMatcher(a=c_seq, b=s_seq, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size > 0]
    if not blocks:
        return unmatched("no matching blocks")

    matched = sum(b.size for b in blocks)
    coverage = matched / len(c_seq)
    if coverage < min_coverage:
        return unmatched(f"coverage {coverage:.2f} < {min_coverage}")

    # Window spanned in the SOURCE by the located tokens.
    first_b = min(b.b for b in blocks)
    last_b = max(b.b + b.size - 1 for b in blocks)
    src_lo, src_hi = s_idx[first_b], s_idx[last_b]

    def ts(w, key, alt):
        v = w.get(key)
        return float(v) if v is not None else float(w.get(alt) or 0.0)

    t_start = ts(source_words[src_lo], "s", "start")
    t_end = ts(source_words[src_hi], "e", "end")
    if t_end <= t_start:
        return unmatched("degenerate window")

    clip_span = (ts(clip_words[-1], "e", "end") - ts(clip_words[0], "s", "start")) or 0.0
    if clip_span > 0 and (t_end - t_start) > MAX_SPRAWL * clip_span:
        # Located tokens are scattered across the source rather than forming one
        # span — coincidental vocabulary overlap, not the clip's origin.
        return unmatched(
            f"window {t_end - t_start:.1f}s sprawls over {MAX_SPRAWL}x the "
            f"clip's own {clip_span:.1f}s")

    sel = None
    if source_duration_s and float(source_duration_s) > 0:
        sel = round((t_end - t_start) / float(source_duration_s), 5)

    return {"method": "transcript_align",
            "t_start": round(t_start, 3), "t_end": round(t_end, 3),
            "confidence": round(coverage, 4),
            "selection_ratio": sel,
            "matched_tokens": matched, "clip_tokens": len(c_seq),
            "why": f"{matched}/{len(c_seq)} clip tokens located"}
