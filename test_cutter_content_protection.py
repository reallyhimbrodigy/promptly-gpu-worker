"""REGRESSION (Zac 2026-07-28): the cutter deleted CONTENT words at sentence
boundaries — via _gemini_cut_span_removable clause (iii) [left-boundary-only]
and the Step-1 remove_words bypass ("Gemini's decisions trusted"). This asserts
the words are KEPT after the fix. Pure cut-logic — no render, no Modal spend.

Reconstructs the THREE real failing jobs from the diagnosis (the full transcripts
+ Gemini cut_refinements are not persisted, so these reproduce the exact reported
contexts rather than replaying the raw jobs):
  631b0b7f, cb60003d : sentence-initial "So" deleted after a pause  (cut-refine gate, fix #1)
  39745dad           : Hindi "में" ("in") deleted mid-flow          (Step-1 bypass, fix #2)
"""
import sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker")
import handler as H


def _w(t, s, e):
    return {"word": t, "punctuated_word": t, "start": s, "end": e}


_fails = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        _fails.append(name)


# ── fix #1: sentence-opener CONTENT words KEPT (dead air only BEFORE, flows into next) ──
check("631b0b7f: sentence-initial 'So' KEPT (…again and again. [1.12s] So it's…)",
      not H._gemini_cut_span_removable(
          [_w("So", 10.62, 10.80)], [_w("it's", 10.85, 11.1), _w("usually", 11.1, 11.5)],
          _w("again.", 9.0, 9.5), 1.12, 0.05))
check("cb60003d: sentence-initial 'So' KEPT (…right property. [0.80s] So you…)",
      not H._gemini_cut_span_removable(
          [_w("So", 5.30, 5.48)], [_w("you", 5.53, 5.7), _w("can", 5.7, 5.9)],
          _w("property.", 4.0, 4.5), 0.80, 0.05))
check("reported defect: 'Next' in 'Next question' KEPT",
      not H._gemini_cut_span_removable(
          [_w("Next", 10.6, 10.8)], [_w("question", 10.85, 11.2)],
          _w("done.", 9.0, 9.5), 0.9, 0.05))

# ── fix #2 core: Hindi CONTENT word KEPT (fails all three gate clauses) ──
check("39745dad: Hindi 'में' KEPT mid-flow (not filler/restart/dead-air)",
      not H._gemini_cut_span_removable(
          [_w("में", 5.3, 5.5)], [_w("hai", 5.5, 5.7)], _w("kaam", 5.0, 5.3), 0.0, 0.0))

# ── SANITY: the fix must NOT break legitimate removals ──
check("SANITY: filler 'uh' still REMOVABLE (clause i)",
      H._gemini_cut_span_removable(
          [_w("uh", 10.3, 10.4)], [_w("okay", 11.3, 11.6)], _w("done.", 9.0, 9.5), 0.8, 0.9))
check("SANITY: genuine isolated fragment (dead air BOTH sides) still REMOVABLE (clause iii)",
      H._gemini_cut_span_removable(
          [_w("yeah", 10.3, 10.5)], [_w("anyway", 11.4, 11.8)], _w("done.", 9.0, 9.5), 0.8, 0.9))
check("SANITY: verbatim restart still REMOVABLE (clause ii)",
      H._gemini_cut_span_removable(
          [_w("the", 5.0, 5.1)], [_w("the", 5.15, 5.25), _w("cat", 5.25, 5.5)],
          _w("word.", 4.0, 4.5), 0.0, 0.0))
# the OLD bug would have cut 'So'/'Next' here (left boundary alone) — prove the fix by
# confirming a left-only dead-air boundary with NO trailing pause is now rejected:
check("REGRESSION GUARD: left-only dead-air boundary (no trailing pause) → content KEPT",
      not H._gemini_cut_span_removable(
          [_w("Basically", 10.6, 11.0)], [_w("we", 11.03, 11.2), _w("build", 11.2, 11.5)],
          _w("great.", 9.0, 9.5), 1.0, 0.03))

print()
if _fails:
    print("REGRESSION FAILED: " + "; ".join(_fails))
    sys.exit(1)
print("✅ ALL CUTTER CONTENT-PROTECTION REGRESSION TESTS PASS")
