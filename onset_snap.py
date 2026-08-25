#!/usr/bin/env python3
"""onset_snap.py — CUTS LAND ON THE BEAT, OR THEY DO NOT MOVE.

MEASURED on ten owner-selected references (LEVER_ONSET_SNAPPING.md): cuts land
within 120ms of an audio onset at a median 68% (range 40-90%), median delta
72ms. Our pipeline aligns cuts to audio NOWHERE — ours are mechanical, silence
and filler, placed off the transcript. An on-beat cut and a 200ms-late one are
invisible to every instrument we own, and we make the late one by default.

WHAT THIS DOES: for each mechanical cut, find the nearest audio onset. If it is
within TOL and lands in the SILENCE BETWEEN WORDS, move the cut there. Otherwise
leave it exactly where it was.

WHAT IT REFUSES TO DO, and this is the constraint that binds:

  **NEVER ACROSS A WORD BOUNDARY.** Every timing in this pipeline derives from a
  word index through the timing authority. An onset sitting mid-word is a
  perfectly good drum hit and a catastrophic cut point: snapping there would
  clip a syllable AND introduce a time that no word index can express — the
  second clock this repo has paid for twice. The onsets that matter for a cut
  are in the gaps, which is where the measured 27-37ms deltas already are.

  **NEVER BEYOND TOL.** 120ms is the join tolerance that produced the corpus
  numbers. A cut further than that from any onset is not a near-miss, it is a
  cut that belongs where the words put it.

EVERY MOVE IS LEDGERED WITH ITS DELTA. A silent improvement is indistinguishable
from a no-op, and this repo has nine features that shipped and did nothing. The
ledger is what makes "snapping fires on N% of cuts, median Ams" answerable from
production instead of from a harness.
"""
from typing import Any, Dict, List, Optional

# The corpus join tolerance. Cuts sit a median 72ms from their nearest onset
# across the references; 120ms admits the near-misses without dragging a cut
# somewhere the transcript did not put it.
DEFAULT_TOL_S = 0.12


def _word_spans(words) -> List[tuple]:
    """(start, end) per word, from the RAW fields. Malformed entries dropped."""
    out = []
    for w in (words or []):
        try:
            s, e = float(w.get("start")), float(w.get("end"))
        except (TypeError, ValueError, AttributeError):
            continue
        if e > s:
            out.append((s, e))
    return out


def in_word(t: float, spans: List[tuple]) -> bool:
    """Is t inside a spoken word? Boundaries are NOT inside — a cut exactly on a
    word edge is the normal case and must stay legal."""
    return any(s < t < e for s, e in spans)


def snap_cuts(cuts: List[float], onsets: List[float], words,
              tol_s: float = DEFAULT_TOL_S,
              ledger=None) -> Dict[str, Any]:
    """Returns {cuts, moved, ledger} — the snapped list plus what it cost.

    The returned list is ALWAYS the same length and order as the input: this
    moves cuts, it never adds, drops or reorders them. A caller that already
    validated cut count keeps that guarantee.
    """
    spans = _word_spans(words)
    out: List[float] = []
    moves: List[Dict[str, Any]] = []
    skipped_in_word = 0
    skipped_far = 0

    for c in cuts:
        try:
            ct = float(c)
        except (TypeError, ValueError):
            out.append(c)
            continue
        if not onsets:
            out.append(c)
            continue
        o = min(onsets, key=lambda x: abs(x - ct))
        d = o - ct
        if abs(d) > tol_s:
            skipped_far += 1
            out.append(c)
            continue
        if in_word(o, spans):
            # A real onset in the middle of a word. Correct to detect, wrong to
            # cut on — leave the cut where the transcript put it.
            skipped_in_word += 1
            out.append(c)
            continue
        out.append(round(o, 4))
        moves.append({"from": round(ct, 4), "to": round(o, 4),
                      "delta_ms": round(d * 1000, 1)})

    rec = {
        "n_cuts": len(cuts),
        "moved": len(moves),
        "moved_frac": round(len(moves) / len(cuts), 3) if cuts else 0.0,
        "median_delta_ms": (sorted(abs(m["delta_ms"]) for m in moves)[len(moves) // 2]
                            if moves else None),
        "skipped_in_word": skipped_in_word,
        "skipped_beyond_tol": skipped_far,
        "tol_s": tol_s,
        "n_onsets": len(onsets or []),
        "moves": moves[:40],
    }
    if ledger:
        try:
            ledger("cut_boundary", "onset_snap", rec)
        except Exception:
            pass
    return {"cuts": out, "moved": len(moves), "ledger": rec}


def onsets_from_audio(path: str) -> Optional[List[float]]:
    """Free — reuses the Pass A envelope. None on probe failure, NEVER [].

    A silent track and a failed probe are different facts; collapsing them would
    make "snapping never fired" unreadable, which is the class this repo keeps
    paying for.
    """
    try:
        from pass_a_signal import audio_envelope
    except Exception:
        return None
    env = audio_envelope(path)
    return None if env is None else (env.get("onsets_s") or [])
