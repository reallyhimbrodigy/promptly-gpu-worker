"""GAP 1A — user spelling obedience (Zac 2026-07-12). A user asked to spell "Blue
filter" as "Blufilter" → the caption rendered "BLUE FILTER" (ignored). Explicit
spelling instructions are now a LITERAL, deterministic caption-text override — the
user's instruction wins over the transcript, no Gemini interpretation."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def W(w):
    return {"word": w, "punctuated_word": w, "start": 0.0, "end": 1.0}

# ── parse ──
check("'spell Blue filter as Blufilter' captured (the real request)",
      H._parse_caption_text_overrides("spell Blue filter as Blufilter") == {("blue", "filter"): "Blufilter"})
check("single-word respell captured",
      H._parse_caption_text_overrides("spell filter as philter") == {("filter",): "philter"})
check('quoted form: change the caption "hello" to "helo"',
      H._parse_caption_text_overrides('change the caption "hello" to "helo"').get(("hello",)) == "helo")
check("captured even in a MIXED request (spelling + other asks)",
      H._parse_caption_text_overrides("change hello to helo and make it punchier").get(("hello",)) == "helo")
check("non-spelling ask captures nothing (no false positives)",
      H._parse_caption_text_overrides("make it high energy, no zooms") == {})

# ── apply (multi-word phrase → one caption word with the exact spelling) ──
_out = H._apply_caption_text_overrides([W("Blue"), W("filter"), W("is"), W("great")],
                                       {("blue", "filter"): "Blufilter"})
check("'Blue filter' → 'Blufilter' (multi-word phrase collapses, exact spelling)",
      [w["word"] for w in _out] == ["Blufilter", "is", "great"], [w["word"] for w in _out])
check("the replacement spans the phrase's full time (start of first, end of last)",
      _out[0]["start"] == 0.0 and _out[0]["end"] == 1.0)
check("single-word respell applies", [w["word"] for w in H._apply_caption_text_overrides([W("filter")], {("filter",): "philter"})] == ["philter"])
check("no override → words untouched",
      [w["word"] for w in H._apply_caption_text_overrides([W("hello")], {})] == ["hello"])
# case/punctuation-insensitive matching
check("matches regardless of case + punctuation ('Filter.' matches 'filter')",
      [w["word"] for w in H._apply_caption_text_overrides([W("Filter.")], {("filter",): "philter"})] == ["philter"])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SPELLING-OVERRIDE CASES PASS")
