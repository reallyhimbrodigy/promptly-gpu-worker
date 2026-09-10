#!/usr/bin/env python3
"""Put the two craft reports into the cached prefix, as TWO documents.

PRECEDENCE IS WRITTEN INTO THE FILES, not assumed. Zac's ten are confirmed
good edits; the hundred are other people's work. Where they disagree, his win,
and the agent has to be able to tell which document a line came from — so each
file opens by saying what it is and how much authority it carries. A merged
document cannot be overruled in half.

Run after run_craft_synthesis.py --both.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "knowledge")

STD_HEAD = """THE STANDARD — HOW THE EXAMPLES YOU ARE JUDGED AGAINST WERE EDITED

This is the combined editorial understanding of TEN videos Zac chose himself
as examples of the editing he wants. They are the standard. It was written by
watching each one moment by moment and asking why each choice lands, not by
counting anything.

Read it as WHEN, not HOW MANY. Every line is a condition and an action: when
this is true at this moment, do this. There are no rates in it, deliberately —
an editor at a moment cannot act on a rate, and a video that places two zooms
because two moments deserved them is correct.

WHERE THIS DOCUMENT AND "THE WIDER FIELD" DISAGREE, THIS ONE WINS.

"""

FIELD_HEAD = """THE WIDER FIELD — WHAT OTHER PEOPLE'S VIDEOS DO

This is the combined understanding of short-form videos gathered in bulk from
what is working publicly. They are NOT the standard and they are not Zac's
taste. They are breadth: what the form does widely, useful for recognising a
move and for knowing which moves are reflexes rather than decisions.

WHERE THIS DOCUMENT AND "THE STANDARD" DISAGREE, THE STANDARD WINS. Do not
average them. If a habit here is not in the standard, treat it as available,
not as expected.

"""

PAIRS = [("/tmp/craft_report_standard.md", "16_craft_the_standard.md",
          STD_HEAD, "/tmp/craft_out"),
         ("/tmp/craft_report_field.md", "17_craft_the_wider_field.md",
          FIELD_HEAD, "/tmp/craft_out_field")]


def corpus_note(d):
    """WHAT THE REPORT WAS READ FROM, measured at install time.

    The field analyses run visibly thinner than the references. That is a
    property of the corpus, not a defect in the pass — a hundred strangers'
    videos have less in them worth explaining than ten videos chosen because
    they are good — and it belongs beside the report so a thinner document
    reads as honest signal rather than a weaker instrument. Computed from the
    files, never from memory: a remembered number is the one that drifts.
    """
    import glob
    import json as _j
    w = []
    for f in glob.glob(f"{d}/*.json"):
        try:
            r = _j.load(open(f))
        except Exception:                                         # noqa: BLE001
            continue
        if r.get("state") == "MEASURED" and r.get("prose"):
            w.append(len(r["prose"].split()))
    if not w:
        return "READ FROM: no analyses could be counted — this document's "\
               "source is UNVERIFIED.\n\n"
    w.sort()
    return (f"READ FROM: {len(w)} videos watched one at a time. The accounts "
            f"they produced run {w[0]} to {w[-1]} words, median "
            f"{w[len(w) // 2]}.\n\n")


def main():
    missing = [s for s, _, _, _ in PAIRS if not os.path.isfile(s)]
    if missing:
        print(f"  *** not written — these reports do not exist yet: {missing}")
        return 1
    total = 0
    for src, name, head, adir in PAIRS:
        body = open(src, encoding="utf-8").read().strip()
        if len(body) < 2000:
            print(f"  *** {src} is {len(body)} chars — that is not a report")
            return 1
        text = head + corpus_note(adir) + body + "\n"
        open(os.path.join(K, name), "w", encoding="utf-8").write(text)
        total += len(text)
        print(f"  {name}: {len(text):,} chars, ~{len(text) / 3.8:,.0f} tok "
              f"(estimate; the exact number comes from cache_creation on the "
              f"next round)")
    print(f"  both: {total:,} chars, ~{total / 3.8:,.0f} tok added to a prefix "
          f"written ONCE per job")
    return 0


if __name__ == "__main__":
    sys.exit(main())
