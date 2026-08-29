"""CERT — non-Latin grounding is CORRECT as-is, and the "unicode splitter fix" is a TRAP.

WHAT THIS PINS, and why it is a cert rather than a comment.

I classified 30 of 56 MG drops (53.6%) as a NON-LATIN BUG CLASS and proposed a
unicode-aware splitter, having "measured" 60% recovery with 0 false-pass. All of
that was wrong, and the way it was wrong is the reason this file exists.

  1. `\\w` DOES NOT MATCH INDIC COMBINING MARKS. Virama and matras are category
     Mn, so `re.split(r"[^\\w.]+", ...)` SHATTERS Indic words:
         'பாயிண்ட்' -> ['ப','ய','ண','ட','']
         'कुल'      -> ['क','ल']
     That is fragmentation into single consonants, not tokenisation.

  2. THE 60% RECOVERY WAS AN ARTIFACT. My probe applied the same shattering to
     the KNOWN side, so fragments matched fragments. Matching single Tamil
     consonants against a Tamil transcript grounds almost unconditionally — the
     consonant inventory is small and shared. The false-pass leg could not see
     it because it only covered ASCII cards.

  3. THE PREDICATE IS ALREADY UNICODE-CORRECT. _mg_norm_token keeps isalnum()
     characters, which is unicode-aware, and BOTH sides normalise identically.
     A non-Latin card whose word is in the dialogue grounds at 1.0 today.

So the non-Latin drops are LEGITIMATE — the words are not in the dialogue. Same
class as the ascii genuinely-ungrounded bucket. I inferred a defect from a
correlation (script) without ever checking whether those drops were wrong.

REAL fixable share of MG drops is ~23% (the short-token class, fixed by the
abbreviation floor in v589) — not the ~77% I reported.

Offline. Zero network, zero Modal, zero Gemini.
"""
import re
import sys

import handler as H

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


def known_from(transcript):
    """Build the known set the way _mg_known_sets does."""
    out = set()
    for raw in transcript.split():
        subs = [t for t in re.split(r"[^0-9A-Za-z.]+", raw) if t]
        j = H._mg_norm_token(raw)
        for p in subs + ([j] if j else []):
            t = H._mg_norm_token(p)
            if t:
                out.add(t)
    return out


THR = H._MG_GROUNDING_THRESHOLD

print("=== C1: non-Latin GROUNDS when its word is in the dialogue ===")
for card, tr in (("பாயிண்ட்", "இது ஒரு பாயிண்ட் ஆகும்"),
                 ("कुल पीस", "इसमें कुल पीस बनाए"),
                 ("सच्ची आज़ादी", "यही सच्ची आज़ादी है")):
    f = H._mg_grounding_fraction(card, known_from(tr))
    check(f"{card!r} grounds ({f:.2f})", f >= THR,
          f"got {f:.2f} — non-Latin grounding regressed")

print("\n=== C2: non-Latin DROPS when its word is absent (the 30 are legitimate) ===")
for card in ("பாயிண்ட்", "वर्कआउट प्रयास", "வளர்ச்சி முறை"):
    f = H._mg_grounding_fraction(card, known_from("completely different words here"))
    check(f"{card!r} drops ({f:.2f})", f < THR,
          f"got {f:.2f} — ungrounded non-Latin now ships")

print("\n=== C3: THE TRAP — a unicode split would shatter, not tokenise ===")
# Pinned so the "obvious fix" cannot be re-proposed without meeting this.
for s, minparts in (("பாயிண்ட்", 3), ("कुल", 2)):
    parts = [p for p in re.split(r"[^\w.]+", s, flags=re.UNICODE) if p]
    check(f"re.UNICODE split shatters {s!r} into {len(parts)} pieces {parts}",
          len(parts) >= minparts,
          "if this stops shattering, re-evaluate — the trap may have closed")
check("virama is NOT a \\w character", not re.match(r"\w", "்"))
check("Devanagari matra is NOT a \\w character", not re.match(r"\w", "ु"))

print("\n=== C4: the ASCII splitter is INTENTIONAL on both sides ===")
_src = open(H.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
check("both splitters still ASCII (symmetric — the docstring's own rule)",
      _src.count(r'[^0-9A-Za-z.]+') >= 2,
      "the sides have diverged; asymmetric splitting is the bug the docstring "
      "records already fixing once")

print("\n=== C5: the abbreviation floor (v589) still holds ===")
check("' MIN' grounds", H._mg_grounding_fraction(" MIN", known_from("thirty minutes each")) >= THR)
check("'OFFICIAL' does not ground on 'off'",
      H._mg_grounding_fraction("OFFICIAL", known_from("off we go")) < THR)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
