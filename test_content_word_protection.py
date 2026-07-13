"""FINDING 3 — content-word protection (Zac 2026-07-12). Gemini's cut_refinements
('YOUR CUT PASS') removed the content phrase "to edit" from "It took five minutes
to edit. I did nothing." — a flowing sentence. _gemini_cut_span_removable is the
structural gate: a gemini_cut span is removable ONLY if it's filler, a verbatim
restart, or dead-air-bounded — never content words in a flow."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def W(word, start=0.0, end=0.0):
    return {"word": word, "punctuated_word": word, "start": start, "end": end}

# THE BUG CASE: "to edit" in "...five minutes to edit. I did nothing." — content
# words, prev='minutes' (not sentence-final), no repeat, fast flow (tiny gap).
span = [W("to", 19.177, 19.337), W("edit.", 19.337, 19.657)]
foll = [W("I"), W("did"), W("nothing")]
prev = W("minutes", 18.857, 19.177)
check("content span 'to edit' in a flow is NOT removable (the bug → kept)",
      H._gemini_cut_span_removable(span, foll, prev, 19.177 - 19.177) is False)

# (i) all filler → removable
check("all-filler span ('um uh') IS removable",
      H._gemini_cut_span_removable([W("um"), W("uh")], [W("so")], W("okay."), 0.0) is True)
check("single filler 'like' (paren-filler) removable",
      H._gemini_cut_span_removable([W("like")], [], W("it's"), 0.0) is True)

# (ii) verbatim restart → removable
check("verbatim restart (span prefixes the following words) IS removable",
      H._gemini_cut_span_removable([W("the"), W("cat")], [W("the"), W("cat"), W("sat")], W("and"), 0.0) is True)
check("NON-matching content span is NOT a restart (kept)",
      H._gemini_cut_span_removable([W("to"), W("edit")], [W("I"), W("did")], W("minutes"), 0.02) is False)

# (iii) dead-air on a sentence-final boundary → removable
check("dead-air-bounded span (prev sentence-final + >=0.70s pause) IS removable",
      H._gemini_cut_span_removable([W("anyway")], [W("so")], W("done."), 0.85) is True)
check("same span but prev NOT sentence-final → NOT removable",
      H._gemini_cut_span_removable([W("anyway")], [W("so")], W("really"), 0.85) is False)
check("same span, sentence-final but pause too short (<0.70) → NOT removable",
      H._gemini_cut_span_removable([W("anyway")], [W("so")], W("done."), 0.20) is False)

# empty span → vacuously removable (no content to protect)
check("empty span is removable (nothing to protect)", H._gemini_cut_span_removable([], [], None, 0.0) is True)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CONTENT-WORD-PROTECTION CASES PASS")
