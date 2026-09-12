#!/usr/bin/env python3
"""Both ruling surfaces admit through ONE door, and it runs all three checks.

THE DEFECT. `rule_all_beats` ran the type boundary, the dedup and the
half-ruling refusal. The singular `beat_verdict` tool ran NONE of them: its
handler built a FOUR-key dict by hand out of the THIRTEEN fields its own schema
offers, appended it past the dedup, and answered with a DEDUPED count.

Four consequences, each invisible on its own:
  1. nine of thirteen fields dropped, so a second ruling REPLACED a complete
     first ruling with a stub — round 63 measured text_content 'ChatGPT' -> None
     with 'text' still in the treatment, an overlay with nothing to render;
  2. a zoom with no arc and a card with no hero stored as rulings and
     discovered at BUILD time as skips that blamed the agent for not saying;
  3. a bare-string treatment or a string beat admitted unnormalised — round 46's
     'c','a','r','d' families, and a dedup set bypassed because "1" != 1;
  4. two contradictory rulings for one beat reported back as one ruled beat,
     because the reply counted `len({v["beat"] for v in beat_verdicts})`.

It was LATENT, not absent: the build's per-beat lookup is a dict comprehension
(LAST WINS) while the frozen executed_verdicts copy keeps the FIRST, and the
only thing holding them together was `refused_second_execute` — a guard built
for an unrelated reason.

SIX PROPERTIES:
  1. a full ruling keeps EVERY field the schema offers, not four;
  2. a half-ruling (zoom with no arc) is REFUSED and stores nothing;
  3. the type boundary runs — a bare-string treatment does not get in;
  4. a string beat cannot bypass the dedup;
  5. a second ruling is DISCARDED, COUNTED, and the first survives intact;
  6. stored rulings can never contradict: one record per beat, always.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0


def _led():
    return {"beat_verdicts": []}


FULL = {"beat": 1, "purpose": "hook", "treatment": ["zoom", "text"],
        "cut": "keep", "why": "the claim lands here",
        "zoom_arc": sorted(A.ZOOM_ARC_HOMES)[0],
        "text_content": "ChatGPT", "framing": "blur", "card_label": "",
        "keep_from_s": 0.0, "keep_to_s": 3.0, "cutaway_from_s": None,
        "card_hero": ""}

# 1. EVERY FIELD THE SCHEMA OFFERS.
led, seen = _led(), set()
ok, rj = A.admit_verdict(led, dict(FULL), seen)
if not ok:
    print(f"  *** a complete ruling was refused: {rj}")
    fail += 1
else:
    rec = led["beat_verdicts"][0]
    missing = [k for k in A.VERDICT_FIELDS if k not in rec]
    if missing:
        print(f"  *** stored record is missing schema fields: {missing}")
        fail += 1
    if rec.get("text_content") != "ChatGPT" or not rec.get("zoom_arc"):
        print(f"  *** fields dropped on the way in: "
              f"text_content={rec.get('text_content')!r} "
              f"zoom_arc={rec.get('zoom_arc')!r}")
        fail += 1
    if len(rec) < 13:
        print(f"  *** only {len(rec)} fields stored; the schema offers "
              f"{len(A.VERDICT_FIELDS)}")
        fail += 1

# 2. THE HALF-RULING REFUSAL RUNS.
led, seen = _led(), set()
half = dict(FULL); half["zoom_arc"] = None
ok, rj = A.admit_verdict(led, half, seen)
if ok or not rj or "zoom_arc" not in str(rj.get("reason")):
    print(f"  *** a zoom with no arc was admitted: ok={ok} rj={rj}")
    fail += 1
if led["beat_verdicts"]:
    print("  *** a refused ruling was stored anyway")
    fail += 1

led, seen = _led(), set()
card = dict(FULL); card["treatment"] = ["card"]; card["card_hero"] = ""
ok, rj = A.admit_verdict(led, card, seen)
if ok or not rj or "card_hero" not in str(rj.get("reason")):
    print(f"  *** a card with no hero was admitted: ok={ok} rj={rj}")
    fail += 1

# 3. THE TYPE BOUNDARY RUNS.
led, seen = _led(), set()
bare = dict(FULL); bare["treatment"] = "card"
ok, rj = A.admit_verdict(led, bare, seen)
stored = led["beat_verdicts"][0] if led["beat_verdicts"] else {}
if isinstance(stored.get("treatment"), str):
    print("  *** a BARE STRING treatment was stored — seven consumers will "
          "iterate it into 'c','a','r','d' families")
    fail += 1

# 4. A STRING BEAT CANNOT BYPASS THE DEDUP.
led, seen = _led(), set()
A.admit_verdict(led, dict(FULL), seen)
strb = dict(FULL); strb["beat"] = "1"; strb["why"] = "second"
A.admit_verdict(led, strb, seen)
if len(led["beat_verdicts"]) != 1:
    print(f"  *** beat '1' (str) bypassed the dedup against beat 1 (int): "
          f"{len(led['beat_verdicts'])} stored")
    fail += 1

# 5. A SECOND RULING IS DISCARDED, COUNTED, AND THE FIRST SURVIVES.
led, seen = _led(), set()
A.admit_verdict(led, dict(FULL), seen)
stub = {"beat": 1, "purpose": "hook", "treatment": ["text"], "cut": "keep",
        "why": "re-ruled"}
ok, rj = A.admit_verdict(led, stub, seen)
if ok:
    print("  *** a second ruling of a ruled beat was admitted")
    fail += 1
if led.get("rulings_discarded") != 1:
    print(f"  *** the discard was not counted: "
          f"rulings_discarded={led.get('rulings_discarded')!r}")
    fail += 1
if led["beat_verdicts"][0].get("text_content") != "ChatGPT":
    print("  *** the first ruling LOST a field to the stub — this is the "
          "round-63 symptom the bound exists to make impossible")
    fail += 1

# 5b. THE SURGICAL GUARANTEE HOLDS ON BOTH SURFACES. The singular tool
#     bypassed reedit_merge entirely, so a re-edit through it could change a
#     beat the user never named — "surgical" was a property of one surface and
#     a claim on the other.
led, seen = _led(), set()
A.admit_verdict(led, dict(FULL), seen)
chg = dict(FULL); chg["text_content"] = "CHANGED"
ok, _ = A.admit_verdict(led, chg, seen, reedit=True, reedit_targets={2})
if ok or led["beat_verdicts"][0].get("text_content") != "ChatGPT":
    print("  *** a re-edit changed a beat the instruction did not name")
    fail += 1
if not led.get("reedit_refused"):
    print("  *** the out-of-scope re-edit was not recorded as refused")
    fail += 1
ok, _ = A.admit_verdict(led, chg, seen, reedit=True, reedit_targets={1})
if not ok or led["beat_verdicts"][0].get("text_content") != "CHANGED":
    print("  *** a re-edit of a NAMED beat was refused — the bound must not "
          "make the re-edit path unusable")
    fail += 1
if len(led["beat_verdicts"]) != 1:
    print(f"  *** the re-edit DUPLICATED the beat: "
          f"{len(led['beat_verdicts'])} records")
    fail += 1

# 6. STORED RULINGS CAN NEVER CONTRADICT.
if len(led["beat_verdicts"]) != len({v.get("beat") for v in led["beat_verdicts"]}):
    print("  *** two records for one beat: the build's LAST-WINS lookup and "
          "the frozen FIRST-wins copy would disagree")
    fail += 1

# 7. AND THE DOOR IS THE ONLY ONE. Structural, because properties 1-6 only
#    prove admit_verdict is right — not that the handlers call it.
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "agentic_editor_app.py")).read()
try:
    A._assert_one_admission_surface(src)
except AssertionError as e:
    print(f"  *** {e}")
    fail += 1

tree = ast.parse(src)
edit_fn = next((n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
calls = [n for n in ast.walk(edit_fn)
         if isinstance(n, ast.Call) and getattr(n.func, "id", "") ==
         "admit_verdict"] if edit_fn else []
if len(calls) < 2:
    print(f"  *** edit() calls admit_verdict {len(calls)} time(s); there are "
          f"TWO ruling surfaces and both must go through it")
    fail += 1

print(f"smoke_one_admission_surface: {len(A.VERDICT_FIELDS)} schema fields, "
      f"{len(calls)} admission call site(s), {fail} wrong")
sys.exit(1 if fail else 0)
