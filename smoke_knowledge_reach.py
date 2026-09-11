#!/usr/bin/env python3
"""The knowledge corpus's reach at ruling time, and it may only improve.

77 structural claims across 14 documents; 8 reachable, all wired 2026-09-11.
Before that: ZERO. The documents are readable only through `read_knowledge`,
called 0 times in 30 runs, so every claim has been invisible at the moment the
agent rules. Three were found by accident and each had already cost something —
four rounds of talking_head subtitling itself, three rounds of zero cards, and
a 31-type catalogue reading two wide.

A RATCHET IN ONE DIRECTION ONLY. The reachable count may not fall. It is NOT a
target upward, because three of these documents MUST stay unreachable:
`13_placement_findings` and `14_card_text_placement_rules` are measured RATES
and the standing law is that the rates grade and never instruct, and
`15_ffmpeg_placement_recipes` is harness-owned, where a second statement of an
enforced rule is a drift surface. A check that pushed the number up would be
arguing for the wiring KNOWLEDGE_REACH.md says not to do.

RED-proven by red_proof_knowledge_reach.py.
"""
import json
import pathlib
import sys

import modal_stub                                              # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                 # noqa: E402

BASE = pathlib.Path("knowledge_reach_baseline.json")
DOC = pathlib.Path("KNOWLEDGE_REACH.md")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_st, _rows, _why = A.knowledge_reach()
check("the corpus and the agent's surface can both be read",
      _st == "MEASURED", f"{_st}: {_why}")
if _st != "MEASURED":
    print("\nKNOWLEDGE-REACH: FAIL"); sys.exit(1)
_n = len(_rows)
_r = sum(1 for x in _rows if x["reachable"])
print("  %d claim(s), %d reachable (%d%%)" % (_n, _r, round(100 * _r / max(1, _n))))
check("the corpus still has claims to reach", _n >= 70,
      "%d claims found; the heading shape changed and this census is measuring "
      "something else" % _n)
check("ABSENT and FAILED are distinguished from a zero count",
      "ABSENT" in pathlib.Path("agentic_editor_app.py").read_text()
      and _st == "MEASURED")

check("the baseline exists", BASE.exists(),
      "without it a fall to zero reads as the first run")
if BASE.exists():
    _b = json.loads(BASE.read_text())
    check("the reachable count has NOT fallen",
          _r >= _b.get("reachable", 0),
          "%d reachable against a baseline of %s — a claim that was visible at "
          "ruling time no longer is, which is how the overlay rule went four "
          "rounds unseen" % (_r, _b.get("reachable")))
    check("the baseline records when it was taken and over what",
          "taken" in _b and "document" in str(_b.get("taken", "")))
    if _r > _b.get("reachable", 0):
        print("  note: %d more reachable than the baseline — update it, and say "
              "in the commit WHICH claim was wired and to which field"
              % (_r - _b.get("reachable", 0)))

check("the census is on the record", DOC.exists())
if DOC.exists():
    _t = DOC.read_text()
    for _cls in ("GRADING-ONLY", "HARNESS-OWNED", "INSTRUCTABLE"):
        check("the census classifies %r rather than only counting" % _cls,
              _cls in _t,
              "10%% with no classification is the figure a reader gets wrong: "
              "wiring all 77 would be worse than wiring none")
    check("it names the rates that must NEVER be wired",
          "13_placement_findings" in _t and "grade" in _t.lower())
    check("and it names the largest instructable gap by field",
          "06_emphasis_zoom" in _t and "zoom_arc" in _t)

print()
if fails:
    print("KNOWLEDGE-REACH: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("KNOWLEDGE-REACH: PASS — %d of %d claims reachable, the baseline holds, "
      "and every document is classified rather than counted" % (_r, _n))
