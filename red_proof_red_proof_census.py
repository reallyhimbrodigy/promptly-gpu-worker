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


def case(label, mutate, expect_phrase):
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
        if not ok:
            fails.append(f"{label}: rc={rc} red={red} "
                         f"phrase({expect_phrase!r})={said}\n{out}")
        print(f"  [{'RED' if ok else 'NOT RED'}] {label}")


def _del_one(tmp):
    (tmp / "red_proof_anchor.py").unlink()


def _add_one(tmp):
    (tmp / "red_proof_zzz_unrecorded.py").write_text("# new\n")


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
    sys.exit(1)
print("RED PROOF: PASS — 6 artifact mutations, 6 reds, baseline green each time")
