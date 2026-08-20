#!/usr/bin/env python3
"""cert_deadair_unpunctuated.py — AN ASR'S PUNCTUATION HABITS MUST NOT GATE A LANGUAGE.

MEASURED 2026-08-20, job cada6a1b (Arabic, 88 words): Deepgram populated
`punctuated_word` on 88 of 88 words and emitted ZERO terminal punctuation.

The dead-air gate reads "sentence-final OR >= _MIDSENTENCE_STALL_S". When
nothing is ever sentence-final, the first half can never fire, so every gap is
judged against 0.70s instead of the 0.03s trigger — a 23x stricter bar applied
to an entire language route as a SIDE EFFECT, never as a decision. All 3
inter-word gaps on that job (max 0.63s) fell under it; the dead-air path
returned zero and the edit shipped as a passthrough.

CLAUSES:

  1  NATIVE TERMINAL GLYPHS COUNT. `؟` (Arabic) and `。！？` (CJK) are terminal
     punctuation. Without them a correctly-punctuated non-Latin transcript is
     misread as unpunctuated.
  2  THE DETECTOR IS HONEST BOTH WAYS. A transcript with terminal punctuation
     reports punctuated; one without reports unpunctuated. Both directions, or
     the flag is decoration.
  3  ENGLISH IS UNTOUCHED. A punctuated transcript still escalates mid-sentence
     gaps to the stall bar — this fix must not loosen the gate where the
     linguistic signal is real.
  4  THE UNPUNCTUATED ROUTE IS NO LONGER GATED. With no terminal punctuation, a
     gap above the trim trigger but below the stall bar IS a candidate.

SIZE, STATED SO IT IS NEVER MISREAD AS THE PASSTHROUGH FIX: on cada6a1b this
recovers ~0.63s of a 34.9s edit. The passthrough is `cut_refinements` coming
back EMPTY (159/159 on 2026-08-04; absent on both renders of 2026-08-19).

    python3 cert_deadair_unpunctuated.py
"""
import os
import sys

os.environ.setdefault("APP_URL", "")


def _w(text, start, end):
    return {"word": text.strip(".?!؟。"), "punctuated_word": text,
            "start": start, "end": end}


def main():
    import handler as H
    fails = []

    # ── 1: native terminal glyphs ───────────────────────────────────────────
    for glyph, name in (("؟", "Arabic question mark"), ("。", "CJK full stop"),
                        ("！", "fullwidth bang"), ("？", "fullwidth question")):
        if not H._sentence_final_word({"punctuated_word": f"كلمة{glyph}"}):
            fails.append(f"{name} ({glyph}) not read as sentence-final")
    for glyph in (".", "?", "!", "…"):
        if not H._sentence_final_word({"punctuated_word": f"word{glyph}"}):
            fails.append(f"ASCII terminal {glyph!r} regressed")
    if H._sentence_final_word({"punctuated_word": "word"}):
        fails.append("a bare word is being read as sentence-final")
    print(f"  [1] native + ascii terminal glyphs: "
          f"{'ok' if not fails else 'FAIL'}")

    # ── 2: the detector, both directions ────────────────────────────────────
    ar = [_w("لو", 0.0, 0.3), _w("بتدور", 0.4, 0.9), _w("جوميرا", 1.0, 1.6)]
    en = [_w("This", 0.0, 0.3), _w("works.", 0.4, 0.9), _w("Next", 1.0, 1.6)]
    if H._transcript_is_punctuated(ar):
        fails.append("an unpunctuated transcript reported as punctuated")
    if not H._transcript_is_punctuated(en):
        fails.append("a punctuated transcript reported as unpunctuated")
    print(f"  [2] detector: arabic={H._transcript_is_punctuated(ar)} "
          f"english={H._transcript_is_punctuated(en)}  (want False / True)")

    # ── 3 + 4: the gate itself, read from the source ────────────────────────
    # The gate is deep inside detect_dead_air and needs real audio to reach, so
    # this asserts the CONDITION as written rather than pretending to drive it —
    # and says so, instead of implying an end-to-end run it did not do.
    src = open(H.__file__, encoding="utf-8").read()
    if "_punctuated = _transcript_is_punctuated(words)" not in src:
        fails.append("_punctuated is not bound once per transcript")
    if "if (_punctuated and not _sentence_final_word(words[a])" not in src:
        fails.append("the linguistic gate is not conditioned on _punctuated — "
                     "an unpunctuated route is still on the 0.70s bar")
    print(f"  [3] english gate still escalates mid-sentence : "
          f"{'if (_punctuated and not _sentence_final_word(words[a])' in src}")
    print(f"  [4] unpunctuated route skips the gate         : "
          f"{'_punctuated = _transcript_is_punctuated(words)' in src}")
    print("      (clauses 3-4 assert the CONDITION in source; the gate needs "
          "real audio to drive end-to-end)")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT DEADAIR-UNPUNCTUATED: FAIL")
        return 1
    print("  CERT DEADAIR-UNPUNCTUATED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
