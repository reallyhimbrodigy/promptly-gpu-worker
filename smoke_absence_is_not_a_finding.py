#!/usr/bin/env python3
"""A family the corpus cannot RECORD is never reported as one editors never USE.

THE ZERO WAS NEVER A MEASUREMENT. The decision surface told the agent
"never here: transition" at every purpose, on the strength of
`transition: 0 of 153` in reference_index.json. Both statements are true and
neither is evidence:

  * build_reference_records.py's annotator prompt declares
    `"treatment": ["cut"|"punch_in"|"cutaway"|"card"|"text_placement"|"sfx"]`
    — a CLOSED enum of six, no transition;
  * REFERENCE_CORPUS_SPEC.md:111 declares
    `cut | punch_in | cutaway | card | overlay_text | sfx | none`
    — also six, also no transition;
  * so the annotator could not have written the word if every beat had one,
    and 0 of 153 is the enum's shape, not the corpus's behaviour.

WHAT THIS COST. The instruction was to re-read the reference corpus at 5 fps
because "the sentence came from a sampler that couldn't see them". A 5 fps
re-read would have returned 0 of 153 again — the sample rate cannot make a
model emit a word it was not offered — and the finding would have been "rate is
not the cause", at the full price of the pass. The question was never asked.

Same family as the alpha guard (ffmpeg exits 234, None comes back, the guard
reads `x is not None and x <= 260` and the round goes green) and effective_cores
(a number that does not move when the machine changes 32-fold). A failed
measurement and a clean result are indistinguishable once you are only reading
the number.

FOUR PROPERTIES:
  1. transition is UNMEASURABLE by this corpus — derived from
     REFERENCE_FAMILY_NAME, which already recorded it as None and which nothing
     read;
  2. no unmeasurable family appears in the "never here" list at any purpose;
  3. the surface SAYS the corpus cannot record it, rather than staying silent —
     an unexplained omission is how the claim comes back;
  4. the leg is not vacuous: a family the corpus CAN record and did not use at
     a purpose is still reported as never-here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0

# 1. DERIVED FROM THE SHIPPED INDEX, NOT FROM A LIST OF FAMILY NAMES.
#    THIS SMOKE USED TO NAME THEM: it asserted `transition` IS unmeasurable and
#    that `sfx` is NOT. Both were facts about the SIX-WORD corpus and both are
#    now false — transition measures 16 occurrences across 8 of 10 videos, and
#    sfx turns out to be the unmeasurable one because the annotator is sent
#    frames and a transcript and receives NO AUDIO, so it cannot hear a sound
#    effect however many there are.
#
#    A check that hardcodes which families are missing has learned one corpus,
#    not the property. It would have had to be edited every time the corpus was
#    re-read — and an assertion you edit to match new data is not an assertion.
#    So: assert the PROPERTY on whatever the index actually says.
unmeas = A.reference_unmeasurable()
meta = A.load_reference_index()[1]
builds = meta.get("builds_as") or {}
rulable = {f for f in A._rulable_treatments() if f != "none"}

if builds:
    # An open-vocabulary index answers it directly: a harness family is
    # unmeasurable iff NO discovered corpus family maps to it.
    expect = rulable - {v for v in builds.values() if v}
    if unmeas != expect:
        print(f"  *** unmeasurable={sorted(unmeas)} does not follow from the "
              f"index's own capability map (expected {sorted(expect)})")
        fail += 1
    for f in unmeas:
        if f in {v for v in builds.values() if v}:
            print(f"  *** {f} is marked unmeasurable while a corpus family "
                  f"maps to it")
            fail += 1
else:
    # Six-name index: the fallback is REFERENCE_FAMILY_NAME's None mapping.
    for f in unmeas:
        if A.REFERENCE_FAMILY_NAME.get(f):
            print(f"  *** {f} is called unmeasurable but the corpus has a name "
                  f"for it ({A.REFERENCE_FAMILY_NAME[f]!r})")
            fail += 1

# NOT VACUOUS IN EITHER DIRECTION. If nothing is unmeasurable the properties
# below pass for the wrong reason; if EVERYTHING is, the surface is empty and
# that is the state this file was written after seeing.
# NOTHING UNMEASURABLE IS NOW A LEGITIMATE STATE — and this leg used to FAIL on
# it, asserting "this corpus has always had at least one family it cannot
# record". That was true of every corpus up to 2026-09-11 and stopped being
# true the moment the listening arm landed and sfx became measurable. A check
# that fails when the system IMPROVES is a check pinned to a defect.
#
# But the properties below genuinely are vacuous with an empty set, so the
# mechanism is exercised on a SYNTHETIC unmeasurable family instead of waiting
# for a real gap to exist.
if not unmeas:
    print(f"  (note: no family is unmeasurable — the merged corpus records all "
          f"{len(rulable)}. Properties 2-3 run against a synthetic family.)")
if unmeas >= rulable:
    print(f"  *** EVERY rulable family is unmeasurable ({sorted(unmeas)}) — "
          f"that is the emptied-surface state, not a finding")
    fail += 1

# 2 & 3. THE SURFACE ITSELF.
# Driven with a beat at every purpose, so every purpose's line is rendered and
# no "never here" can hide behind an empty pool.
_our = [{"i": i, "purpose": p, "t_start": float(i), "t_end": float(i) + 2.0,
         "role": p, "text": "a line of speech for this beat"}
        for i, p in enumerate(A.BEAT_PURPOSES)]
try:
    block = A._reference_block(_our)
except Exception as _e:                                          # noqa: BLE001
    print(f"  *** the decision surface raised {type(_e).__name__}: {_e}")
    block = ""
if not block:
    print("  *** the decision surface could not be rendered, so properties 2-4 "
          "are ABSENT, not passing")
    fail += 1
else:
    # BOUNDED TO THE LIST ITSELF. The never-here names run from "never here: "
    # to the full stop before "Choose among"; the sentence that EXPLAINS the
    # unmeasurable family sits after it on the same line and would otherwise
    # read as the thing it exists to replace.
    def _never_list(line):
        if "never here:" not in line:
            return ""
        tail = line.split("never here:", 1)[1]
        return tail.split(". Choose among", 1)[0]
    for f in unmeas:
        for line in block.splitlines():
            if f in _never_list(line):
                print(f"  *** {f!r} is reported as never-here: {line.strip()!r}")
                fail += 1
    # THE MECHANISM, EXERCISED WHATEVER THE CORPUS SAYS. Pick a family that IS
    # currently offered somewhere, declare it unmeasurable, and assert the
    # surface stops calling it never-used and starts naming it as unrecordable.
    _probe = next((f for f in sorted(rulable)
                   if any(A.offered_treatments(p)[0].get(f)
                          for p in A.BEAT_PURPOSES)), None)
    if _probe is None:
        print("  *** no family is offered anywhere, so the synthetic probe "
              "cannot run — this check is ABSENT, not passing")
        fail += 1
    else:
        _orig = A.reference_unmeasurable
        A.reference_unmeasurable = lambda: {_probe}
        try:
            _b2 = A._reference_block(_our)
        finally:
            A.reference_unmeasurable = _orig
        _hits = [l for l in _b2.splitlines() if _probe in _never_list(l)]
        if _hits:
            print(f"  *** with {_probe!r} unmeasurable the surface still "
                  f"reports it as never-here: {_hits[0].strip()[:90]!r}")
            fail += 1
        if _probe not in _b2 or "not evidence" not in _b2:
            print(f"  *** with {_probe!r} unmeasurable the surface does not "
                  f"name it as unrecordable")
            fail += 1
    # NAMED, NOT MERELY OMITTED. Dropping transition from the never-here list
    # and saying nothing leaves the agent with no idea the corpus is silent on
    # it — and leaves the next reader free to "restore" the claim.
    for f in unmeas:
        if f not in block:
            print(f"  *** {f!r} is omitted from the surface silently rather "
                  f"than named as unrecordable")
            fail += 1
    if unmeas and "not evidence" not in block:
        print("  *** the surface does not say the absence is not evidence")
        fail += 1
    # 4. NOT VACUOUS.
    if "never here:" not in block:
        print("  *** nothing is reported as never-here at any purpose, so "
              "property 2 passes for the wrong reason")
        fail += 1

# 5. THE EXEMPTION LIFTS ITSELF. It must key off the VOCABULARY THE INDEX WAS
#    ANNOTATED UNDER, not off the annotator source — the two diverge the
#    moment the annotator is changed and before the corpus is re-read, which
#    is exactly the state this file was written in. An exemption that has to
#    be remembered is one that rots.
_meta = A.load_reference_index()[1]
_vocab = set(_meta.get("vocabulary") or [])
if _vocab and not builds:
    # A vocabulary is recorded but no capability map: nothing the annotator
    # could have written may be called unmeasurable.
    _wrong = {f for f in unmeas
              if (A.REFERENCE_FAMILY_NAME.get(f) or f) in _vocab}
    if _wrong:
        print(f"  *** {sorted(_wrong)} are in the index's own recorded "
              f"vocabulary, so their zero IS a finding and must be reported "
              f"normally")
        fail += 1
elif not _vocab and not builds:
    # No vocabulary at all — the six-name index. The fallback must still name
    # whatever REFERENCE_FAMILY_NAME maps to None, or the claim comes back.
    _none_mapped = {f for f in rulable if not A.REFERENCE_FAMILY_NAME.get(f)}
    if _none_mapped - unmeas:
        print(f"  *** {sorted(_none_mapped - unmeas)} map to no corpus name "
              f"and are not marked unmeasurable — the fallback has stopped "
              f"working")
        fail += 1

# 6. AND THE ANNOTATOR CARRIES THE SLOT NOW, so the next corpus can answer.
_rec = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "build_reference_records.py")).read()
# THE ANNOTATOR MUST NOT CARRY A CLOSED SET AT ALL. This used to check that
# the enum line CONTAINED "transition" — which was the right fix for the wrong
# problem: adding one name to a closed list of six leaves the seventh, eighth
# and ninth families exactly as unsayable as transition was. The field is now
# open, so the property is that no closed enum remains.
if "OPEN VOCABULARY" not in _rec:
    print("  *** the annotator no longer declares its treatment field OPEN — "
          "a closed set makes every family outside it unsayable, which is how "
          "a zero became a finding for the life of the corpus")
    fail += 1
_closed = [l for l in _rec.splitlines()
           if '"treatment":' in l and l.count('"|"') >= 3]
if _closed:
    print(f"  *** the annotator declares a CLOSED treatment enum again: "
          f"{_closed[0].strip()[:90]}")
    fail += 1
# AND EVERY NAME MUST SAY WHAT IT DOES — the discipline that replaces the enum.
if "what_it_does" not in _rec:
    print("  *** the annotator does not require what_it_does — with free "
          "naming a bare label is worth nothing and would still be COUNTED")
    fail += 1

print(f"smoke_absence_is_not_a_finding: unmeasurable={sorted(unmeas)}, "
      f"{fail} wrong")
sys.exit(1 if fail else 0)
