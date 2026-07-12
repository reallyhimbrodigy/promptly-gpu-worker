"""CAPTION ONSET (Zac 2026-07-12). The timing audit measured captions trailing the
beat by ~80ms (5 frames) because they alone used the raw Deepgram start while
SFX/zoom/MG key off the audible onset. Fix: caption page/token timing on the
audible onset. project_words_to_output emits `audible_start`; the caption builder
uses it. Deterministic, offline."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# ── the caption builder uses audible_start (not the raw start) ──────────────
pw = [{"start": 1.60, "audible_start": 1.52, "end": 1.90, "word": "hello", "punctuated_word": "hello"}]
pages = H._build_tiktok_pages_from_projected(pw, max_words_per_page=2)
check("page has one token", bool(pages) and len(pages[0]["tokens"]) == 1, pages)
check("token fromMs uses AUDIBLE start (1520), not raw (1600)",
      pages[0]["tokens"][0]["fromMs"] == 1520, pages[0]["tokens"][0]["fromMs"])
check("page startMs uses audible start (1520)", pages[0]["startMs"] == 1520, pages[0]["startMs"])
check("token toMs unchanged (word end 1900) — appears earlier, ends same",
      pages[0]["tokens"][0]["toMs"] == 1900, pages[0]["tokens"][0]["toMs"])
# no audible_start present → falls back to raw start (never crashes on old data)
pw2 = [{"start": 2.00, "end": 2.30, "word": "world", "punctuated_word": "world"}]
p2 = H._build_tiktok_pages_from_projected(pw2, max_words_per_page=2)
check("fallback to raw start when audible_start absent", p2[0]["startMs"] == 2000, p2[0]["startMs"])

# ── project_words_to_output emits audible_start = start − silence correction ──
H._LEVEL_SILENCES_LAST[:] = [(1.20, 1.52)]   # silence ends at 1.52, before the 1.60 dg start
H._WITHIN_WORD_SILENCES_LAST[:] = []
transcript = {"words": [{"start": 1.00, "end": 1.30, "word": "a"},
                        {"start": 1.60, "end": 1.90, "word": "b"}]}
cuts = [{"source_start": 0.0, "source_end": 2.0, "speed": 1.0}]
proj = H.project_words_to_output(transcript, cuts, [2.0])
_b = [w for w in proj if w.get("_word_index") == 1]
check("projected word b exists", bool(_b), proj)
if _b:
    b = _b[0]
    check("b raw start ≈ 1.60 (output)", abs(b["start"] - 1.60) < 0.02, b["start"])
    check("b audible_start ≈ 1.52 (pulled to the silence-anchored onset)",
          abs(b["audible_start"] - 1.52) < 0.02, b["audible_start"])
# a mid-phrase word (no silence) is NOT shifted → audible_start == start
_a = [w for w in proj if w.get("_word_index") == 0]
if _a:
    a = _a[0]
    check("mid-phrase word a: audible_start == start (no correction)",
          abs(a["audible_start"] - a["start"]) < 1e-6, (a["audible_start"], a["start"]))

H._LEVEL_SILENCES_LAST[:] = []
H._WITHIN_WORD_SILENCES_LAST[:] = []
print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CAPTION-ONSET CASES PASS")
