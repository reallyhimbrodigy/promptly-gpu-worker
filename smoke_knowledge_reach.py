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

# WIRED CLAIMS ARE COUNTED BY A MARKER IN THE TEXT THE AGENT READS, not by a
# hand-kept list. knowledge_reach matches HEADINGS and understates reach: five
# claims were wired 2026-09-11 and the heading count stayed at 8.
_w = A.wired_claims()
check("wired claims are counted by their marker", bool(_w),
      "no [<doc>, wired <date>] markers on the agent's surface — a claim wired "
      "without one cannot be distinguished from one nobody wired")
check("at least five claims are wired, across two documents",
      sum(_w.values()) >= 5 and len(_w) >= 2, str(_w))
check("the marker names a real knowledge document",
      all(pathlib.Path("knowledge") / (_d + ".md") for _d in _w)
      and all((pathlib.Path("knowledge") / (_d + ".md")).exists() for _d in _w),
      "a marker naming a document that does not exist counts a claim that has "
      "no source: %s" % sorted(_w))

# THE MASK-ZOOM JOB, which I reported as absent and is not.
_ms, _marcs, _mtext = A.mask_zoom_job()
check("the mask-zoom rule is found in the catalogue", _ms == "MEASURED",
      "%s: %s — it is the ONLY guidance build and breather have, and a silent "
      "absence puts them back to being the cheap slot that took zoom 9-23x "
      "over reference in round 46" % (_ms, _mtext))
check("it names build and breather as the mask positions",
      set(_marcs or ()) == {"build", "breather"}, str(_marcs))
check("the harness's own type map agrees with it independently",
      A.ZOOM_ARC_HOMES.get("build") == A.ZOOM_ARC_HOMES.get("breather")
      == ("SnapReframe", "StepZoom"),
      "the mask text names SnapReframe/StepZoom as the small sub-second types; "
      "ZOOM_ARC_HOMES giving build or breather anything else means one of the "
      "two derivations drifted")
_teach = A.arc_jobs_teach(["hook", "build", "mid_peak", "payoff", "breather", "close"])
check("every one of the six arc values gets a job in the field text",
      all(_a in _teach for _a in
          ("hook", "build", "mid_peak", "payoff", "breather", "close")))
check("and the field says a mask position is NOT a peak",
      "NOT peaks" in _teach,
      "the defect was the agent claiming build for an emphasis zoom; the field "
      "has to say the position is functional")
check("no arc is left reading as having no guidance",
      "NO guidance" not in _teach,
      "an arc with no job is the cheap slot, and the census's claim that build "
      "and breather had none was a claim about a HEADING sweep, not the corpus")

# THE BODY-SWEEP RULES, extracted by anchor rather than transcribed.
_ar_state, _ar, _ar_why = A.arc_rules()
check("every arc-rule anchor still matches the catalogue",
      _ar_state == "MEASURED",
      "%s — an anchor that stops matching is a rule that left the catalogue or "
      "a sentence that was reworded, and the prompt must not ship without it "
      "silently" % _ar_why)
check("four arc rules are extracted", len(_ar) >= 4, "%d" % len(_ar))
check("they include the peaks rule that corroborates the mask job",
      any("Zooms belong to peaks" in _r for _r in _ar),
      "this is a THIRD independent statement that build is not a peak position, "
      "after the mask paragraph and ZOOM_ARC_HOMES")
check("and the breather/build confusion rule, which names the actual mistake",
      any("wearing a disguise" in _r for _r in _ar))
_teach2 = A.arc_jobs_teach(["hook", "build", "mid_peak", "payoff", "breather", "close"])
check("the rules reach the zoom_arc field text",
      all(_r[:40] in _teach2 for _r in _ar),
      "extracted and not delivered is the measured-table-with-no-reader defect")
check("a failed extraction degrades to PARTIAL rather than silence",
      "PARTIAL:" in pathlib.Path("agentic_editor_app.py").read_text())

# THE SELECTION ARROWS — the half that was missing. The WHEN conditions say
# which question a beat asks and the content keys say which component a payload
# selects; these say what each component is FOR.
_arw_state, _arw, _arw_why = A.component_selection_arrows()
check("the catalogue's selection arrows are found",
      _arw_state == "MEASURED", _arw_why)
check("at least 30 arrows across at least 18 components",
      len(_arw) >= 30 and len({_t for _c, _t in _arw}) >= 18,
      "%d arrows, %d components" % (len(_arw), len({_t for _c, _t in _arw})))
check("every arrow names a REAL component",
      all(_t in A.VALID_MG_TYPES for _c, _t in _arw),
      "an arrow naming a component that does not exist offers a capability "
      "that cannot fire: %s"
      % sorted({_t for _c, _t in _arw} - set(A.VALID_MG_TYPES)))
check("the table reaches the card_condition field",
      "Static numbers" in json.dumps(A.KNOWLEDGE_TOOLS),
      "extracted and not delivered is the measured-table-with-no-reader defect")
check("a shrunken table reports ABSENT rather than a short list",
      A.component_selection_arrows(min_arrows=999)[0] == "ABSENT",
      "the arrows are a prose convention; a rewrite that dropped them would "
      "read as a catalogue with three selectable components")

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
    # THE SAME LINE, not anywhere in the file: both names appear in the table
    # and in the prose, so "each is present" says nothing about whether the
    # census still connects the field to the document with the largest gap.
    check("the census CORRECTS its own over-count rather than replacing it",
          "over-counted" in _t and "not 27" in _t,
          "the 27-instructable figure was a document-to-field mapping, not an "
          "audit — it never asked whether a claim describes a field this lane "
          "exposes, and the correction is the evidence that mapping is not "
          "auditing")
    check("it records that cutaway is not a field on this lane",
          "not in this lane's treatment enum" in _t,
          "08_broll's six claims cannot be wired here and saying they are "
          "pending would be claiming work that is not this lane's to do")
    # THE GAP CLAIM SPECIFICALLY. Requiring both names on one line stopped
    # distinguishing once the addendum added a WIRED row carrying both — my own
    # edit satisfied the leg from a different sentence. The claim being tested
    # is that the census still NAMES the largest gap, so test that phrase.
    check("and it names the largest instructable gap by field",
          any("06_emphasis_zoom" in _l and "largest instructable gap" in _l
              for _l in _t.splitlines()),
          "no line names 06_emphasis_zoom as the largest instructable gap — a "
          "field answered on every beat with the most craft it cannot see is "
          "the finding, and a WIRED row mentioning both names is not it")

print()
if fails:
    print("KNOWLEDGE-REACH: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("KNOWLEDGE-REACH: PASS — %d of %d claims reachable, the baseline holds, "
      "and every document is classified rather than counted" % (_r, _n))
