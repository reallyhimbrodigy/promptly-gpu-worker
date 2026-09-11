#!/usr/bin/env python3
"""A leg that tests a string appearing in the source must name it UNIQUELY.

THE RATE THAT EARNED THIS. Four legs of mine passed a mutant in one stretch,
and two of the four failed the same mechanical way: the literal they tested
appears in the app MORE THAN ONCE, so deleting the occurrence that mattered
left the other one standing and the check read green.

    "route_demand" in SRC      setdefault created the dict on one line and the
                               INCREMENT was on another. Deleting the increment
                               left the demand signal permanently empty with
                               the check passing — which is exactly how
                               unsupported_request read zero for nine rounds
                               and nobody could tell no-demand from no-counting.
    "_deferred_inert" in src   appears in the deferral AND in the block that
                               resolves the list, so gutting the deferral
                               changed nothing the leg could see.

This is the counter-with-no-consumer defect wearing a test's clothes: the name
is present, the behaviour is gone, and presence is what was measured.

WHAT THIS CANNOT DO, said plainly. The other two failures were a loose
substring that survived a meaning-inverting edit ("can create" accepted a
message saying the opposite) and a leg watching a downstream symptom instead of
the property. Neither is mechanically detectable from the literal alone, and
claiming otherwise would be the check overreaching. This closes the half that
counting can close.

RED-proven by red_proof_legs_are_unambiguous.py.
"""
import ast
import json
import pathlib
import sys

APP = pathlib.Path("agentic_editor_app.py")
SMOKES = sorted(p.name for p in pathlib.Path(".").glob("smoke_*.py"))
# Literals whose presence anywhere IS the property — a prompt sentence that
# must reach the agent, a code that must exist. Each is an argument on the
# record; the list is not a place to put a leg you could not be bothered to
# tighten.
ALLOWED_MULTI = {
    "K1.", "K2.", "K3.", "K4.", "K5.", "K6.",
    "credit_charged",
}
MIN_LEN = 6          # shorter than this is a fragment, not a claim
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


check("the app under test is present", APP.exists())
if not APP.exists():
    print("\nLEGS-ARE-UNAMBIGUOUS: FAIL"); sys.exit(1)
_src = APP.read_text()
check("there are smokes to inspect", bool(SMOKES), "no smoke_*.py found")

_amb, _vac, _n = [], [], 0
for _s in SMOKES:
    try:
        _tree = ast.parse(pathlib.Path(_s).read_text())
    except SyntaxError as _e:
        check(f"{_s} parses", False, str(_e)); continue
    for _node in ast.walk(_tree):
        if not isinstance(_node, ast.Compare) or len(_node.ops) != 1:
            continue
        if not isinstance(_node.ops[0], (ast.In, ast.NotIn)):
            continue
        _rhs = _node.comparators[0]
        if not (isinstance(_rhs, ast.Name) and _rhs.id in ("src", "SRC")):
            continue
        _lhs = _node.left
        if not (isinstance(_lhs, ast.Constant) and isinstance(_lhs.value, str)):
            continue
        _lit = _lhs.value
        if len(_lit) < MIN_LEN or _lit in ALLOWED_MULTI:
            continue
        _n += 1
        _count = _src.count(_lit)
        if isinstance(_node.ops[0], ast.In) and _count > 1:
            _amb.append((_s, _node.lineno, _lit[:60], _count))
        # A `not in` leg on a literal that was never there is vacuously true
        # forever: it proves the absence of something nobody wrote.
        if isinstance(_node.ops[0], ast.NotIn) and _count == 0:
            _vac.append((_s, _node.lineno, _lit[:60]))

# A RATCHET, NOT A PERMANENT RED. 67 smokes predate this check and a gate that
# is red on all of them becomes furniture — the twin rule to a check that has
# never failed. So the population as it stands is recorded in
# legs_ambiguous_baseline.json BY (file, literal), anything NOT in it fails,
# and the baseline COUNT is printed every run so it can only shrink. Removing
# an entry is a fix; adding one is a commit that has to say why.
_BASE = pathlib.Path("legs_ambiguous_baseline.json")
_base = set()
if _BASE.exists():
    try:
        _base = {(r["file"], r["literal"]) for r in json.loads(_BASE.read_text())}
    except Exception as _e:                                   # noqa: BLE001
        check("the baseline file parses", False, str(_e))
else:
    check("the baseline file exists", False,
          "without it every pre-existing leg reads as new and the gate is "
          "red on arrival, which is how a gate stops being read")
_new = [r for r in _amb if (r[0], r[2]) not in _base]
_fixed = _base - {(f, lit) for f, _ln, lit, _c in _amb}
check("no NEW source-presence leg tests a literal that appears more than once",
      not _new,
      "\n         ".join("%s:%d tests %r which appears %dx — deleting the one "
                         "that matters leaves the check green"
                         % (f, ln, lit, c) for f, ln, lit, c in _new[:8]))
print("  baseline: %d known ambiguous leg(s) carried, %d fixed since it was "
      "recorded%s" % (len(_base), len(_fixed),
                      " — remove them from the baseline" if _fixed else ""))
check("the baseline has not grown", len(_amb) <= len(_base) or not _base,
      "%d ambiguous legs against a baseline of %d" % (len(_amb), len(_base)))
# Vacuous absence legs are reported, not failed: several are deliberate
# tombstones for text that must never come back.
if _vac:
    print("  note: %d `not in` leg(s) on literals absent from the app — "
          "deliberate tombstones, or checks that can never fire:" % len(_vac))
    for f, ln, lit in _vac[:6]:
        print("        %s:%d  %r" % (f, ln, lit))
print("  inspected %d source-presence leg(s) across %d smoke(s)" % (_n, len(SMOKES)))

print()
if fails:
    print("LEGS-ARE-UNAMBIGUOUS: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("LEGS-ARE-UNAMBIGUOUS: PASS — %d leg(s) checked, none testing a literal "
      "that appears more than once" % _n)
