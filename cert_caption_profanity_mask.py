"""CERT — caption profanity mask (Zac's ruling 2026-08-31).

Both directions, because "nothing was masked" and "the cert never ran" are
otherwise identical:
  * a masked word renders masked AND KEEPS ITS TIMING and slot
  * an unmasked sentence is untouched, byte for byte
  * a non-aligning filtered pair REFUSES rather than guessing
  * masking is first-letter + asterisks, not Deepgram's full '*****'

Run:  python3 cert_caption_profanity_mask.py     (exit 0 = green)
RED:  PROMPTLY_CERT_REDPROVE=1 python3 ...       (must exit 1)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handler as H

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}: {detail}")
        FAILURES.append(name)


def W(word, s, e, pw=None):
    return {"word": word, "punctuated_word": pw or word, "start": s, "end": e}


# RED-PROVE: neuter the masker and every masking assertion below must fail.
if os.environ.get("PROMPTLY_CERT_REDPROVE") == "1":
    H._mask_caption_profanity = lambda words, vocab: words
    print("  [RED-PROVE] masker replaced with a no-op — expect FAILures\n")

# ── vocabulary derivation ────────────────────────────────────────────────────
base = [W("what", 0.10, 0.30), W("nigga", 0.30, 0.62), W("a", 0.62, 0.70),
        W("fuck", 0.70, 1.02), W("day", 1.02, 1.30)]
filt = [W("what", 0.10, 0.30), W("*****", 0.30, 0.62), W("a", 0.62, 0.70),
        W("****", 0.70, 1.02), W("day", 1.02, 1.30)]

vocab = H._profanity_vocab(base, filt)
check("vocab derived from the filtered pair", vocab == {"nigga", "fuck"}, str(vocab))

# A transcription DIFFERENCE (not asterisks) must never enter the vocab —
# otherwise an ordinary misheard word gets masked on screen.
mis = [W("what", 0.1, 0.3), W("their", 0.3, 0.6)]
mis_f = [W("what", 0.1, 0.3), W("there", 0.3, 0.6)]
check("a non-asterisk difference is NOT treated as profanity",
      H._profanity_vocab(mis, mis_f) == set(), str(H._profanity_vocab(mis, mis_f)))

# Fails closed on a misaligned pair.
check("misaligned pair refuses (empty vocab)",
      H._profanity_vocab(base, filt[:-1]) == set())

# ── direction 1: a masked word is masked, and KEEPS ITS TIMING ───────────────
out = H._mask_caption_profanity(base, vocab)
check("word count preserved", len(out) == len(base), f"{len(out)} vs {len(base)}")
check("profane word is masked", out[1]["word"] == "n****", out[1]["word"])
check("second profane word is masked", out[3]["word"] == "f***", out[3]["word"])
check("mask is FIRST LETTER + asterisks, not full-asterisk",
      out[1]["word"][0] == "n" and set(out[1]["word"][1:]) == {"*"}, out[1]["word"])
check("punctuated_word is ALSO masked (styles read it)",
      out[1]["punctuated_word"].startswith("n") and "*" in out[1]["punctuated_word"],
      out[1]["punctuated_word"])
check("masked word KEEPS start", out[1]["start"] == 0.30, str(out[1]["start"]))
check("masked word KEEPS end", out[1]["end"] == 0.62, str(out[1]["end"]))
check("every timing preserved across the stream",
      all(o["start"] == b["start"] and o["end"] == b["end"]
          for o, b in zip(out, base)))

# ── direction 2: a clean sentence is untouched ───────────────────────────────
clean = [W("we", 0.0, 0.2), W("shipped", 0.2, 0.6), W("it", 0.6, 0.8)]
clean_out = H._mask_caption_profanity(clean, vocab)
check("clean sentence is byte-identical", clean_out == clean)
check("empty vocab is a no-op", H._mask_caption_profanity(base, set()) == base)

# Punctuation-bearing and capitalised forms still match (normalised compare).
cap = [W("Fuck", 0.0, 0.3, pw="Fuck,")]
cap_out = H._mask_caption_profanity(cap, vocab)
check("capitalised + punctuated profanity is masked",
      cap_out[0]["word"] != "Fuck" and "*" in cap_out[0]["word"],
      str(cap_out[0]))

print()
if FAILURES:
    print(f"CERT RED — {len(FAILURES)} failure(s): {', '.join(FAILURES)}")
    sys.exit(1)
print("CERT GREEN — mask applies, timings preserved, clean text untouched")
sys.exit(0)
