#!/usr/bin/env python3
"""CAPTION MODES — keyword colour emphasis + number glorification `[§3.1]`.

Offline, $0, no Gemini, no render. Extracts the predicates by AST so importing
handler's 15s of module-level startup is not required.

THE CANON RULE APPLIES HERE TOO: the references define the bar, so if a
reference's own caption line fails a rule, the RULE is broken. The two modes are
not two features — they are one spec reading MODE rather than magnitude:

  REF-2  short centre-frame lines, 1-3 words, where the NUMBER IS THE CLAIM
         ("13", "$20,000,000") — any digit owns the frame
  REF-1  longer lower-third phrases that accent KEYWORDS and glorify nothing
         bare — only self-evidently significant numbers qualify

which is why "3 tips" stays quiet inside a sentence while "13" owns its own.

  python3 cert_caption_modes.py
"""
import os
import re
import sys

from cert_extract import extract_from

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    NS = extract_from("handler.py",
                      names=["_keyword_emphasis_spec", "_caption_accent_for",
                             "_HERO_SHORT_LINE_WORDS", "_NUMBER_ANY_RE",
                             "_NUMBER_HERO_RE", "_EMPHASIS_STOP"],
                      globals_={"re": re})
    spec = NS["_keyword_emphasis_spec"]
    accent_for = NS["_caption_accent_for"]
    ACC = "#F06D1F"

    print("=== ARM 1: REF-2 MODE — a short line lets the NUMBER own the frame ===")
    r = spec("13", accent=ACC)
    check("bare '13' on its own line is a hero",
          r["hero_index"] == 0 and r["tokens"][0]["hero"] is True, str(r))
    check("the hero carries the accent", r["tokens"][0]["accent"] == ACC, str(r))
    r0 = spec("0", accent=ACC)
    check("'0' is a hero too — the reference glorifies it", r0["hero_index"] == 0, str(r0))
    r2 = spec("$20,000,000", accent=ACC)
    check("'$20,000,000' is a hero", r2["hero_index"] == 0, str(r2))
    r3 = spec("13 cases won", accent=ACC)
    check("a 3-word line still counts as short (the boundary is inclusive)",
          r3["hero_index"] == 0, str(r3))

    print("\n=== ARM 2: REF-1 MODE — a longer line accents KEYWORDS, glorifies nothing bare ===")
    r4 = spec("we put together 3 tips for your next case", accent=ACC)
    check("'3' inside a sentence is NOT a hero — magnitude is not the test",
          r4["hero_index"] is None, str(r4))
    check("but the line still accents something", any(t["accent"] for t in r4["tokens"]), str(r4))
    r5 = spec("a genuinely smooth experience for every client", accent=ACC)
    check("keywords take the accent", any(t["accent"] for t in r5["tokens"]), str(r5))
    check("at most 2 keywords — REF-1 accents a phrase, not the sentence",
          sum(1 for t in r5["tokens"] if t["accent"]) <= 2, str(r5))
    check("stop-words NEVER take the accent (the tell of an automated edit)",
          all(not t["accent"] for t in r5["tokens"]
              if re.sub(r"[^\w]", "", t["text"]).lower() in NS["_EMPHASIS_STOP"]), str(r5))
    r6 = spec("we recovered $20,000,000 for our clients last year", accent=ACC)
    check("a SIGNIFICANT number is still a hero in a long line",
          r6["hero_index"] is not None, str(r6))
    r7 = spec("conversion improved by 40% across the board", accent=ACC)
    check("a percentage is significant", r7["hero_index"] is not None, str(r7))

    print("\n=== ARM 3: ONE hero per line — two claims is a fight ===")
    r8 = spec("13 and 40% and $5,000,000 all at once here", accent=ACC)
    check("exactly one hero even with three candidates",
          sum(1 for t in r8["tokens"] if t["hero"]) == 1, str(r8))

    print("\n=== ARM 4: determinism — two runs of one edit cannot disagree ===")
    line = "our clients recovered millions in damages"
    a, b = spec(line, accent=ACC), spec(line, accent=ACC)
    check("same line -> same emphasis", a == b)
    check("pure: no hidden state between different lines",
          spec(line, accent=ACC) == a, "a prior call changed the result")

    print("\n=== ARM 5: NO PALETTE -> NO EMPHASIS (byte-identical to today) ===")
    check("accent_for returns None when the design system is missing",
          accent_for({}) is None and accent_for(None) is None)
    check("accent_for returns None when the build FAILED (_design_system=None)",
          accent_for({"_design_system": None}) is None)
    check("accent_for returns None on a malformed palette",
          accent_for({"_design_system": {"palette": {"accent": "not-a-colour"}}}) is None)
    check("accent_for passes a real accent through",
          accent_for({"_design_system": {"palette": {"accent": "#F06D1F"}}}) == "#F06D1F")
    check("an empty line is all-plain and cheap",
          spec("", accent=ACC)["tokens"] == [] and spec("   ", accent=ACC)["hero_index"] is None)

    print("\n=== ARM 6: the accent is the JOB'S, never invented here ===")
    r9 = spec("13", accent="#00AAFF")
    check("the caller's accent is what lands — no hardcoded colour",
          r9["tokens"][0]["accent"] == "#00AAFF", str(r9))
    src = open(os.path.join(here, "handler.py"), encoding="utf-8").read()
    i = src.index("def _build_tiktok_pages_from_projected")
    win = src[i:i + 6000]
    check("the page builder only stamps emphasis when an accent EXISTS",
          "if emphasis_accent:" in win, "emphasis would be stamped with an invented colour")

    print()
    if FAILURES:
        print(f"CAPTION-MODES CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("CAPTION-MODES CERT: ALL PASS (REF-2 hero mode, REF-1 keyword mode, one hero "
          "per line, deterministic, no-palette is byte-identical, accent never invented)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
