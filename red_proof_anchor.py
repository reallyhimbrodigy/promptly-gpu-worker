#!/usr/bin/env python3
"""One anchor resolver for every red proof, because six of mine went stale in
an hour.

WHAT ACTUALLY ORPHANED THEM, diagnosed rather than assumed:

    2 of 6  the anchor was a MULTI-LINE BLOCK and only one line of it changed.
            The block included an `if` that gained a `round(...)`, and a return
            that moved inside a different test. A one-line anchor on the
            distinctive part would have survived both.
    1 of 6  a STRING LITERAL WRAPPED ACROSS LINES was re-wrapped when its text
            grew. Nothing about the code changed; the line breaks moved.
    1 of 6  the rule MOVED INTO A NEW FUNCTION. No textual anchor survives that
            and none should — the mutation should be re-aimed by hand.
    2 of 6  were not anchors at all: the mutant applied and the smoke was too
            weak to notice. A resolver cannot help with that.

So this file fixes the two mechanical causes and REFUSES to paper over the
other two. `find_one` matches exactly where it can, falls back to a
whitespace-insensitive match where the anchor is a wrapped literal, and REPORTS
WHICH — because a loose match is itself news: the source drifted under the
mutation, and the next drift may be semantic.

It deliberately does NOT do fuzzy or partial matching. An anchor that no longer
matches on tokens is an anchor pointing at code that no longer exists, and that
must fail loudly (`anchor 0x`) rather than land somewhere plausible.
"""
import re

EXACT, LOOSE, NONE, MANY = "exact", "loose (whitespace drifted)", "0x", "Nx"


def find_one(src, anchor):
    """(mode, start, end) for a single occurrence of `anchor` in `src`.

    mode is EXACT, LOOSE, NONE or MANY. Only EXACT and LOOSE carry offsets.
    """
    n = src.count(anchor)
    if n == 1:
        i = src.index(anchor)
        return (EXACT, i, i + len(anchor))
    if n > 1:
        return (MANY, n, None)
    # Whitespace-insensitive: every run of whitespace in the anchor may match
    # any run in the source. This is what rescues a re-wrapped string literal
    # and nothing else — token order and every non-space character still have
    # to match exactly.
    pat = r"\s+".join(re.escape(tok) for tok in anchor.split())
    hits = list(re.finditer(pat, src))
    if len(hits) == 1:
        return (LOOSE, hits[0].start(), hits[0].end())
    if len(hits) > 1:
        return (MANY, len(hits), None)
    return (NONE, 0, None)


def apply_one(src, anchor, replacement):
    """(mode, mutated_src). mutated_src is None unless the anchor resolved."""
    mode, a, b = find_one(src, anchor)
    if mode not in (EXACT, LOOSE):
        return (mode, None)
    return (mode, src[:a] + replacement + src[b:])


if __name__ == "__main__":
    import sys
    _bad = []
    _s = 'def f():\n    if x <= y:\n        return (A, b)\n    t = ("one "\n         "two")\n'
    if find_one(_s, "return (A, b)")[0] != EXACT:
        _bad.append("an exact single occurrence must report EXACT")
    if find_one(_s, '("one " "two")')[0] != LOOSE:
        _bad.append("a re-wrapped literal must resolve LOOSE, not 0x — this is "
                    "the case that orphaned a real mutation")
    if find_one(_s, "return")[0] != EXACT or find_one(_s + _s, "return (A, b)")[0] != MANY:
        _bad.append("two occurrences must report MANY, never pick one")
    if find_one(_s, "return (A, c)")[0] != NONE:
        _bad.append("an anchor whose TOKENS changed must be 0x — a resolver "
                    "that lands somewhere plausible is worse than one that fails")
    if find_one(_s, "if x < y:")[0] != NONE:
        _bad.append("a changed operator must be 0x; whitespace tolerance must "
                    "not become semantic tolerance")
    _m, _out = apply_one(_s, '("one " "two")', '("three")')
    if _m != LOOSE or "three" not in (_out or ""):
        _bad.append("apply_one must mutate through a LOOSE match")
    if apply_one(_s, "nope", "x") != (NONE, None):
        _bad.append("apply_one must refuse an unresolved anchor")
    if _bad:
        print("RED-PROOF-ANCHOR: FAIL")
        for _b in _bad:
            print("  - " + _b)
        sys.exit(1)
    print("RED-PROOF-ANCHOR: PASS — exact, whitespace-loose, 0x on a token "
          "change, Nx on ambiguity, and never a plausible landing")
