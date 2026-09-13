#!/usr/bin/env python3
"""RED proof for smoke_red_proof_census.

Every mutation is to an ARTIFACT (the census file, the set of files on disk),
never to a leg of the gate. Mutating a gate's own legs makes it PASS, which is
how four expectations in this repo once pointed the wrong way.

The sandbox holds NAME-ONLY stubs for the harnesses, because the property under
test is the SET OF NAMES and nothing else; the gate never opens a red proof.
"""
import json, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
GATE = "smoke_red_proof_census.py"
CENSUS = "red_proof_census.json"
fails = []


def build(tmp):
    shutil.copy(HERE / GATE, tmp / GATE)
    shutil.copy(HERE / CENSUS, tmp / CENSUS)
    for p in HERE.glob("red_proof_*.py"):
        (tmp / p.name).write_text("# name-only stub\n")
    return tmp


def run(tmp):
    r = subprocess.run([sys.executable, GATE], cwd=tmp,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# EVERY CASE THAT RUNS IS RECORDED, so the exit can carry a floor. A harness
# whose `case(...)` calls were all deleted runs nothing, collects no failures
# and exits 0 — success reported for zero legs, which is the family this whole
# registry exists to refuse.
RAN = []
REDS = 0


def _must_parse(_src, _label):
    """A .py MUTANT THAT DOES NOT COMPILE NEVER RAN. Ported in on the merge
    without this lane's guard: if a mutation writes Python the gate cannot
    import, the gate dies on the SyntaxError rather than on the property, and
    the leg counts RED having proved nothing. The JSON cases are deliberately
    corrupt and are not routed through here — they test the gate's own
    ABSENT/FAILED handling, which is the opposite property."""
    import ast
    try:
        ast.parse(_src)
    except SyntaxError as _e:
        fails.append("%s: the MUTANT .py does not parse (%s) — the gate would "
                     "die on the syntax, not on the property" % (_label, _e))


def case(label, mutate, expect_phrase):
    RAN.append(label)
    with tempfile.TemporaryDirectory() as d:
        tmp = build(pathlib.Path(d))
        # BASELINE FIRST: an unmutated sandbox must be GREEN, or a red result
        # below proves nothing about the mutation.
        rc0, out0 = run(tmp)
        if rc0 != 0:
            fails.append(f"{label}: BASELINE NOT GREEN (rc={rc0}) — the sandbox "
                         f"is wrong, not the gate\n{out0}")
            print(f"  [FAIL] {label} :: baseline not green")
            return
        mutate(tmp)
        rc, out = run(tmp)
        red = rc != 0
        said = expect_phrase.lower() in out.lower()
        ok = red and said
        globals()["REDS"] = globals().get("REDS", 0) + (1 if ok else 0)
        if not ok:
            fails.append(f"{label}: rc={rc} red={red} "
                         f"phrase({expect_phrase!r})={said}\n{out}")
        print(f"  [{'RED' if ok else 'NOT RED'}] {label}")


def _del_one(tmp):
    (tmp / "red_proof_anchor.py").unlink()


def _add_one(tmp):
    _new_src = "# new\n"
    _must_parse(_new_src, "a red proof present but unrecorded")
    (tmp / "red_proof_zzz_unrecorded.py").write_text(_new_src)


def _empty_census(tmp):
    o = json.loads((tmp / CENSUS).read_text())
    o["red_proofs"] = []
    (tmp / CENSUS).write_text(json.dumps(o))


def _drop_census(tmp):
    (tmp / CENSUS).unlink()


def _corrupt_census(tmp):
    (tmp / CENSUS).write_text("{ this is not json")


def _rename_one(tmp):
    (tmp / "red_proof_anchor.py").rename(tmp / "red_proof_anchor_v2.py")


print("RED PROOF — red-proof census")
case("a recorded red proof deleted", _del_one, "MISSING")
case("a red proof added but unrecorded", _add_one, "unrecorded")
case("the census emptied (vacuity)", _empty_census, "non-vacuous")
case("the census file removed (ABSENT is not a pass)", _drop_census, "ABSENT")
case("the census unparseable (FAILED is not a pass)", _corrupt_census, "parses")
case("a red proof renamed (a rename is a loss AND an addition)",
     _rename_one, "MISSING")

print()
if fails:
    print("RED PROOF: FAILED TO GO RED")
    for f in fails:
        print("  - " + f)
else:
    print("RED PROOF: PASS — %d artifact mutations, %d reds, baseline green "
          "each time" % (len(RAN), len(RAN)))
# THE FLOOR, IN THE SECOND OF THE TWO SPELLINGS THE GUARDS ACCEPT:
# `reds and reds == len(RAN)`. `if fails: exit(1)` reports SUCCESS for a
# harness whose mutation list was emptied — zero legs run, zero failures,
# exit 0. Counting the legs that actually went RED says more than the absence
# of failures: it cannot be satisfied by a harness that ran nothing.
sys.exit(0 if (REDS and REDS == len(RAN) and not fails) else 1)
