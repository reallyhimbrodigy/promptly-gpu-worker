#!/usr/bin/env python3
"""RED proof for smoke_face_clearance_is_answered: every leg must be able to fail.

EACH MUTATION NAMES THE LEG IT MUST BREAK, and a red whose output does not
contain THAT leg failing is reported NOT RED. A harness that crashes, or that
fails for an unrelated reason, produces a red that proves nothing — the seventh
way a mutation misleads, and both instances of it in this repo came from
mutating a guard until the file stopped parsing.

THE BACKUP IS IN MEMORY. A backup at a fixed /tmp path is shared across every
branch and worktree on this machine, and one such backup silently restored
another branch's 914-line file while its harness printed 19/19 RED-PROVEN.
A post-run `git status` catches the case memory cannot: a kill between mutate
and restore.
"""
import ast
import io
import re
import subprocess
import sys

sys.path.insert(0, ".")
import red_proof_anchor as RA                                   # noqa: E402

TARGET = "chatcut_gate.py"
SMOKE = "smoke_face_clearance_is_answered.py"

# (label, anchor, replacement, leg_that_must_fail, precondition)
# precondition: a callable over the UNMUTATED source+module proving the target
# actually DOES something, or None for a mutation that INJECTS a defect.
MUTATIONS = [
    ("the no-trajectory guard is removed",
     "            if not face_traj:",
     "            if False:",
     "measured without a trajectory",
     lambda G: "NO TRAJECTORY ARRIVED" in "\n".join(
         G.acceptance_lines([_R("text", "middle")], _SPANS, 30.0,
                            face_state="MEASURED", face_traj=None))),
    ("collision detection is disabled",
     "            elif _mine and _mine in _occ:",
     "            elif False:",
     "face center, text in center",
     lambda G: "COLLISION" in "\n".join(
         G.acceptance_lines([_R("text", "middle")], _SPANS, 30.0,
                            face_state="MEASURED", face_traj=_traj(960)))),
    ("the occupied band stops being named",
     '                           % (", ".join(sorted(_occ)) or "no band", a["src_t"],\n'
     '                              a["src_t"] + a["hold_s"], _mine))',
     '                           % ("no band", a["src_t"],\n'
     '                              a["src_t"] + a["hold_s"], _mine))',
     "the occupied band is named",
     lambda G: "center" in "\n".join(
         G.acceptance_lines([_R("text", "upper_third")], _SPANS, 30.0,
                            face_state="MEASURED", face_traj=_traj(960)))),
    ("the cutaway exemption is removed",
     '        if a["fam"] == "cutaway":',
     '        if False:',
     "cutaway is exempt",
     lambda G: "covered by" in "\n".join(
         G.acceptance_lines([{"beat": 4, "treatment": ["cutaway"],
                              "where": "full_frame", "src_t0": 2.0,
                              "hold_s": 1.0}], _SPANS, 30.0,
                            face_state="MEASURED", face_traj=_traj(960)))),
    ("FAILED is admitted to the measured branch",
     '        elif _fs.startswith("MEASURED"):',
     '        elif "MEASURED" in _fs or "FAILED" in _fs:',
     "FAILED never reads as measured",
     lambda G: "NOT CHECKED" in "\n".join(
         G.acceptance_lines([_R("text", "middle")], _SPANS, 30.0,
                            face_state="FAILED — cv2 missing",
                            face_traj=_traj(960)))),
    ("ABSENT stops saying nobody looked",
     '"this run (%s). Nobody looked. JUDGE IT BY EYE at frame "',
     '"this run (%s). JUDGE IT BY EYE at frame "',
     "absent says nobody looked",
     lambda G: "Nobody looked" in "\n".join(
         G.acceptance_lines([_R("text", "middle")], _SPANS, 30.0,
                            face_state="ABSENT"))),
]

_SPANS = [(0.0, 10.0, 0, 300)]


def _R(fam, where):
    return {"beat": 3, "treatment": [fam], "where": where, "src_t0": 2.0,
            "hold_s": 1.0, "text_content": "SEVENTY PERCENT"}


def _traj(cy):
    return [{"t": round(i * 0.25, 2), "found": True, "cy": float(cy)}
            for i in range(41)]


def run_smoke():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def leg_failed(out, leg):
    return re.search(r"^\s+%s\s+FAIL\s*$" % re.escape(leg), out, re.M) is not None


def main():
    src = io.open(TARGET, encoding="utf-8").read()          # THE BACKUP, in memory

    # THE SANDBOX MUST BE GREEN FIRST. A red produced by a broken tree rather
    # than by the mutation has fired twice for real in this repo.
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: the unmutated smoke is not green (rc=%d)\n%s"
              % (rc, out[-900:]))
        sys.exit(2)

    import chatcut_gate as G
    red, bad = 0, []
    for label, anchor, repl, leg, pre in MUTATIONS:
        if pre is not None:
            try:
                ok = bool(pre(G))
            except Exception as e:                            # noqa: BLE001
                ok = False
                label += " [precondition raised %s]" % type(e).__name__
            if not ok:
                bad.append("VACUOUS: %s — the target does nothing on the "
                           "fixture, so removing it cannot change a result"
                           % label)
                print("  [VACUOUS] %s" % label)
                continue
        mode, mutant = RA.apply_one(src, anchor, repl)
        if mutant is None:
            bad.append("HARNESS FAILURE: %s — anchor %s" % (label, mode))
            print("  [ANCHOR %s] %s" % (mode, label))
            continue
        try:
            ast.parse(mutant)
        except SyntaxError as e:
            bad.append("HARNESS FAILURE: %s — mutant will not parse: %s"
                       % (label, e))
            print("  [UNPARSEABLE] %s" % label)
            continue
        io.open(TARGET, "w", encoding="utf-8").write(mutant)
        try:
            rc2, out2 = run_smoke()
        finally:
            io.open(TARGET, "w", encoding="utf-8").write(src)
        hit = leg_failed(out2, leg)
        if rc2 != 0 and hit:
            red += 1
            print("  [RED]  %-42s (%s) -> leg %r failed" % (label, mode, leg))
        else:
            bad.append("NOT RED: %s — rc=%d leg_failed=%s (a red that is not "
                       "about the property is as wrong as a green that is not)"
                       % (label, rc2, hit))
            print("  [NOT RED] %-40s rc=%d leg_failed=%s" % (label, rc2, hit))

    # THE TREE MUST BE AS THE SWEEP FOUND IT. Compared against the IN-MEMORY
    # backup, not against git HEAD — `git status` answers "does this differ
    # from the last commit", which is a different question and is TRUE for any
    # uncommitted work in the file. The first version of this check asked git,
    # fired on my own unrelated edits, and would have taught the next reader to
    # ignore it: a check that is always red stops being read.
    if io.open(TARGET, encoding="utf-8").read() != src:
        print("\nRESIDUE: %s was left MUTATED by this harness — restoring"
              % TARGET)
        io.open(TARGET, "w", encoding="utf-8").write(src)
        bad.append("RESIDUE: %s did not match the pre-sweep source" % TARGET)

    # THE FLOOR. `all([])` is True and 0 == len([]) is True, so a harness whose
    # mutations were deleted reports success. 26 of 27 red proofs here once did.
    # `bad` is in the condition because a residue or a vacuous mutation must
    # fail the run even when every mutation went red.
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    for b in bad:
        print("  " + b)
    # THE FLOOR, IN THE EXIT ITSELF. `red` appears as a bare truthy operand, so
    # an emptied MUTATIONS list makes red 0 and the whole predicate false —
    # a harness whose mutations were deleted CANNOT report success. `bad`
    # carries residue and vacuity, which must fail the run even at 5/5.
    # sys.exit HERE, not `return` — the floor has to live inside the exit CALL
    # so a static reader can evaluate it. `sys.exit(main())` hides the
    # predicate one frame down, and a floor nothing can read is a floor nobody
    # can trust is still there.
    sys.exit(0 if red and red == len(MUTATIONS) and not bad else 1)


if __name__ == "__main__":
    main()
