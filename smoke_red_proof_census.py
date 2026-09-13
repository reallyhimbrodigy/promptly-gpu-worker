#!/usr/bin/env python3
"""Every red proof that has ever existed still exists.

THE CLASS THIS CLOSES: a floor on a count cannot see a deletion.
`smoke_red_proofs_guarded` asserts `len(_harnesses) >= 10`, then iterates and
checks each harness it FINDS — so no present harness is hidden by the total.
But the set can shrink from 34 to 10 and the floor stays green, and a red proof
is the only evidence that a check has ever actually failed. Lose the proof and
the check silently returns to unproven, which is the state
`false-green-checks` was written about.

Same family as the per-document wired-claim floor: a total is not a per-member
count, and the member that disappears is the one nobody sees go. The fix in both
cases is the same — NAME the members.

Run with `--adopt` to record newly added proofs (additions are expected and
fine; losses are not).
"""
import json, pathlib, sys

CENSUS = pathlib.Path("red_proof_census.json")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# THREE STATES, not a number: the census can be MEASURED, ABSENT (no file) or
# FAILED (unparseable). Absent must not read as "nothing is missing".
if not CENSUS.exists():
    print("  [FAIL] the census itself is present")
    print("         %s is ABSENT — with no census this check cannot answer its "
          "question, and an empty answer is not a pass" % CENSUS)
    sys.exit(1)
try:
    _recorded = set(json.loads(CENSUS.read_text())["red_proofs"])
except Exception as _e:          # noqa: BLE001 - any read failure is FAILED
    print("  [FAIL] the census parses")
    print("         %s: %r" % (CENSUS, _e))
    sys.exit(1)

_present = {p.stem for p in pathlib.Path(".").glob("red_proof_*.py")}

if "--adopt" in sys.argv:
    _new = sorted(_present - _recorded)
    _obj = json.loads(CENSUS.read_text())
    _obj["red_proofs"] = sorted(_recorded | _present)
    CENSUS.write_text(json.dumps(_obj, indent=1) + "\n")
    print("adopted %d new: %s" % (len(_new), _new or "none"))
    sys.exit(0)

print("RED-PROOF CENSUS")
print("  recorded %d   present %d" % (len(_recorded), len(_present)))

_gone = sorted(_recorded - _present)
check("every recorded red proof is still on disk",
      not _gone,
      "MISSING: %s — a red proof is the only evidence its check has ever "
      "failed; the check it proved is now unproven. If the check was "
      "deliberately retired, remove BOTH and say so in the commit." % _gone)

_new = sorted(_present - _recorded)
check("no red proof is present but unrecorded",
      not _new,
      "unrecorded: %s — additions are welcome, run `%s --adopt` so the next "
      "deletion is visible" % (_new, pathlib.Path(__file__).name))

# The census must not be able to pass by being empty — the vacuity precondition
# that the floor was reaching for, stated as its own leg.
check("the census is non-vacuous", len(_recorded) >= 10,
      "%d recorded — too few to be the real set; an empty census passes every "
      "other leg here" % len(_recorded))

print()
if fails:
    print("RED-PROOF CENSUS: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RED-PROOF CENSUS: PASS — all %d recorded proofs present" % len(_recorded))
