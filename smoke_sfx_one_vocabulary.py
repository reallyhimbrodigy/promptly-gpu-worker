#!/usr/bin/env python3
"""A beat that names `sfx` in its treatment has decided the moment needs sound.

TWO VOCABULARIES FOR ONE INTENT. The agent says "this beat has a sound" by
putting `sfx` in `treatment`; the BUILD gates on the separate `sfx: "yes"`
field. Say one and not the other and the ruling is accepted, carried through the
plan, and silently skipped at build time.

MEASURED over 37 runs / 11 rounds in this lane, and reproduced independently by
Builder-2 on theirs at the same figures:

    sfx in treatment                              75
      field "yes" + sfx_name           -> BUILT   50
      field ABSENT, no name            -> DROPPED 17
      field None,   no name            -> DROPPED  4
      field None,   WITH name          -> DROPPED  2   <- recoverable
      field "no",   no name            -> DROPPED  2

INVISIBLE AT BOTH ENDS. `half_ruling_stripped` read ZERO across all 37 runs
while 25 placements vanished, because the stripper's sfx arm keys on the SAME
wrong field — a beat with treatment ["sfx"] and no field is never in `_nosfx`,
so nothing refuses it at ruling time and nothing reports it at build time. It
surfaces only as ruled > built.

WHAT THE FIX DOES AND DOES NOT DO. Deriving the field recovers 2. The other 23
are genuine half-rulings — the agent named the family and never said WHICH
sound, which is not derivable from timing — and they are now REFUSED where the
agent is still holding the beat instead of skipped where the only outcome is a
lost placement. (6 of those 23 are refused on a zoom problem on the same beat,
because the zoom arm is checked first.)

FIVE PROPERTIES:
  1. treatment + a name builds, with or without the field;
  2. treatment + NO name is refused, not silently dropped;
  3. treatment + field "no" is refused as the contradiction it is;
  4. the agent's own value always wins — deriving never overwrites;
  5. the derivation is COUNTED, so the next mismatch cannot hide.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0
BUILDS = lambda r: (str(r.get("sfx", "no")).lower() == "yes"
                    and bool((r.get("sfx_name") or "").strip()))


# THE FIVE CONTROLS ARE PART OF A `text` RULING, NOT DECORATION.
# `half_ruling_refusal` made size/case/where/colour/hold_s mandatory for any
# beat ruled `text` — they are how the words READ — and this fixture predates
# it. Without them admit_verdict refuses, `beat_verdicts` comes back EMPTY, and
# every leg below either passes vacuously or dies on an IndexError that looks
# like a defect in the admission surface. It was a FIXTURE GAP reading as a
# surface defect for however long it sat here.
TITLE_CONTROLS = {"size": "medium", "case": "upper", "where": "upper_third",
                  "colour": "white_on_footage", "hold_s": 2.0}


def admit(extra):
    v = {"beat": 1, "purpose": "hook", "cut": "keep", "why": "w"}
    v.update(TITLE_CONTROLS)
    v.update(extra)
    led, seen = {"beat_verdicts": []}, set()
    ok, rj = A.admit_verdict(led, dict(v), seen)
    return ok, rj, (led["beat_verdicts"][0] if led["beat_verdicts"] else {}), led


# 1. TREATMENT + NAME BUILDS, WITH OR WITHOUT THE FIELD.
for lbl, extra in (
        ("no field", {"treatment": ["sfx"], "sfx_name": "whoosh"}),
        ("field None", {"treatment": ["sfx"], "sfx": None, "sfx_name": "whoosh"}),
        ("field yes", {"treatment": ["sfx"], "sfx": "yes", "sfx_name": "whoosh"})):
    ok, rj, rec, led = admit(extra)
    if not ok or not BUILDS(rec):
        print(f"  *** treatment+name with {lbl} does not reach the build "
              f"predicate: admitted={ok} stored sfx={rec.get('sfx')!r} rj={rj}")
        fail += 1

# 2. NO NAME IS **ADMITTED**, BECAUSE A DERIVER IS WAITING FOR IT.
#    THIS LEG USED TO ASSERT THE OPPOSITE and the reversal is the point. I had
#    half_ruling_refusal refuse a nameless sfx, reasoning that WHICH sound
#    cannot be derived from timing. It can: `_derive_sfx_name` fills it from
#    the beat's role, and the refusal runs BEFORE any beat is in hand, so it
#    pre-empted a live deriver and turned "a sound here, you pick" — the one
#    thing the sfx field says that the treatment cannot — into an
#    unsatisfiable demand. That is the refused-forever shape: dropped-once
#    costs a placement, refused-forever costs the run.
#
#    The nameless case is caught AFTER derivation instead, by the second
#    `_nosfx` pass, which is why that pass says "Recompute AFTER derivation".
ok, rj, rec, led = admit({"treatment": ["sfx"]})
if not ok or rj:
    print(f"  *** sfx with no name was refused rather than admitted for "
          f"derivation: ok={ok} rj={rj}")
    fail += 1
if not led["beat_verdicts"]:
    print("  *** the ruling was not stored, so _derive_sfx_name never sees it")
    fail += 1
if str(rec.get("sfx") or "").lower() != "yes":
    print(f"  *** the sfx field was not derived from the treatment: "
          f"{rec.get('sfx')!r} — the build gates on this field")
    fail += 1
# AND THE POST-DERIVATION PASS MUST STILL EXIST. Admitting it here is only safe
# while something downstream reports what is still nameless.
_src0 = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
if "Recompute AFTER derivation" not in _src0:
    print("  *** nothing recomputes the nameless-sfx list after derivation, so "
          "admitting a nameless ruling now loses it silently")
    fail += 1

# 3. THE CONTRADICTION IS NAMED.
ok, rj, rec, led = admit({"treatment": ["sfx"], "sfx": "no",
                          "sfx_name": "whoosh"})
if ok or not rj:
    print("  *** treatment says sfx and the field says 'no', and it was "
          "admitted — those contradict and the agent must resolve it")
    fail += 1

# 4. THE AGENT'S VALUE WINS. Deriving must only FILL, never overwrite.
ok, rj, rec, led = admit({"treatment": ["sfx"], "sfx": "yes",
                          "sfx_name": "money-ching"})
if rec.get("sfx_name") != "money-ching":
    print(f"  *** the agent's sfx_name was overwritten: {rec.get('sfx_name')!r}")
    fail += 1
if led.get("sfx_field_derived"):
    print("  *** the field was 'derived' when the agent had already set it — "
          "a derivation that fires on a supplied value is a second opinion")
    fail += 1

# 5. COUNTED AND PRINTED. A derivation nobody can count is how the next
#    silent mismatch hides.
ok, rj, rec, led = admit({"treatment": ["sfx"], "sfx_name": "whoosh"})
if not led.get("sfx_field_derived"):
    print("  *** the derivation is not recorded in the ledger")
    fail += 1
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
if "sfx_field_derived" not in src.split("SFX FIELD")[0][-4000:] and \
        "SFX FIELD" not in src:
    print("  *** the counter is never PRINTED — a counter in the ledger and "
          "nowhere else answers no question anyone can ask")
    fail += 1

# 6. NON-VACUITY: the refusal must still admit a well-formed ruling, or
#    properties 2-3 pass because everything is refused.
ok, _, rec, _ = admit({"treatment": ["text"], "text_content": "HI"})
if not ok:
    print("  *** a well-formed non-sfx ruling is refused — the sfx arm is "
          "rejecting everything and the legs above mean nothing")
    fail += 1

print(f"smoke_sfx_one_vocabulary: {fail} wrong")
sys.exit(1 if fail else 0)
