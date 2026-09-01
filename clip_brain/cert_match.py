"""CERT — clip->source matcher, BOTH directions.

The direction that actually protects the corpus is the NEGATIVE one: a clip that
did not come from this source must return UNMATCHED. A matcher that always finds
something is indistinguishable from a matcher that works, right up until every
selection fact in the corpus is wrong.

Run:  python3 cert_match.py                        (exit 0 = green)
RED:  PROMPTLY_CERT_REDPROVE=1 python3 cert_match.py  (must exit 1)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match as M

FAILURES = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f": {detail}"))
    if not cond:
        FAILURES.append(name)


def words(text, t0=0.0, step=0.4):
    return [{"w": w, "s": round(t0 + i * step, 3), "e": round(t0 + (i + 1) * step, 3)}
            for i, w in enumerate(text.split())]


if os.environ.get("PROMPTLY_CERT_REDPROVE") == "1":
    # A matcher that always claims a match — the exact failure this cert exists
    # to make impossible.
    M.match_clip_to_source = lambda c, s, source_duration_s=None, **k: {
        "method": "transcript_align", "t_start": 0.0, "t_end": 1.0,
        "confidence": 0.99, "selection_ratio": 0.1,
        "matched_tokens": 99, "clip_tokens": 99, "why": "always"}
    print("  [RED-PROVE] matcher always claims a match — expect FAILures\n")

SOURCE_TEXT = (
    "welcome back to the channel today we are going to talk about why most "
    "people quit their job in the first year and what the data actually says "
    "about it the number one reason is not money it is that nobody ever told "
    "them what success looked like in the role so they guessed and they guessed "
    "wrong and then they left before anyone noticed the mismatch")
src = words(SOURCE_TEXT, t0=0.0, step=0.5)
SRC_DUR = src[-1]["e"]

# ── direction 1: a real excerpt IS located, with sane bounds ────────────────
CLIP_TEXT = ("the number one reason is not money it is that nobody ever told "
             "them what success looked like in the role")
clip = words(CLIP_TEXT, t0=0.0, step=0.5)
r = M.match_clip_to_source(clip, src, source_duration_s=SRC_DUR)
check("real excerpt matches", r["method"] == "transcript_align", r.get("why"))
check("confidence is high", r["confidence"] >= 0.9, str(r["confidence"]))

# LOCATE the excerpt's true start rather than hardcoding an index — the first
# draft hardcoded 26, which was "actually", and the cert failed a CORRECT
# matcher. A fixture that counts words by hand is its own defect.
_first = CLIP_TEXT.split()[0]
_seq = SOURCE_TEXT.split()
_ci = next(i for i in range(len(_seq))
           if _seq[i:i + 4] == CLIP_TEXT.split()[:4])
expect_start = src[_ci]["s"]
check("t_start lands on the excerpt's real position",
      r["t_start"] is not None and abs(r["t_start"] - expect_start) < 1.5,
      f"got {r['t_start']}, expected ~{expect_start}")
check("window is not longer than the source",
      r["t_end"] is not None and r["t_end"] <= SRC_DUR + 0.01, str(r["t_end"]))
check("selection_ratio computed and in (0,1]",
      r["selection_ratio"] and 0 < r["selection_ratio"] <= 1.0,
      str(r["selection_ratio"]))

# ── direction 2: THE NEGATIVE CONTROL ───────────────────────────────────────
foreign = words(
    "so I preheated the oven to four hundred degrees and roasted the carrots "
    "with olive oil until the edges caramelised which takes about forty minutes")
rn = M.match_clip_to_source(foreign, src, source_duration_s=SRC_DUR)
check("a clip from a DIFFERENT source is UNMATCHED",
      rn["method"] == "UNMATCHED", f"{rn['method']} conf={rn['confidence']}")

# Same creator, same filler vocabulary, different episode — the realistic false
# positive. Shares 'the/is/that/it/they/and' with the source and nothing else.
same_voice = words(
    "and that is the thing that nobody tells you and it is the reason they say "
    "it is so hard and they are not wrong about that at all it is just that")
rs = M.match_clip_to_source(same_voice, src, source_duration_s=SRC_DUR)
check("filler-word overlap alone does NOT match",
      rs["method"] == "UNMATCHED", f"{rs['method']} conf={rs['confidence']}")

# ── refusals ────────────────────────────────────────────────────────────────
check("too-short clip refuses",
      M.match_clip_to_source(words("it is that"), src)["method"] == "UNMATCHED")
check("empty clip refuses",
      M.match_clip_to_source([], src)["method"] == "UNMATCHED")
check("empty source refuses",
      M.match_clip_to_source(clip, [])["method"] == "UNMATCHED")
check("UNMATCHED always carries a reason",
      bool(rn.get("why")) and bool(rs.get("why")))

print()
if FAILURES:
    print(f"CERT RED — {len(FAILURES)} failure(s): {', '.join(FAILURES)}")
    sys.exit(1)
print("CERT GREEN — real excerpts locate, foreign clips refuse")
sys.exit(0)
