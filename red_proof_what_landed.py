#!/usr/bin/env python3
"""RED proof for smoke_what_landed.py.

`no_measurement_reads_as_dropped` is the defect this whole judge exists to stop:
scoring dead air by assuming there was dead air, which convicts a correct edit
on a source that had none.
"""
import os
import re
import subprocess
import sys

# A MUTATED .py RE-RUN IN A SUBPROCESS CAN BE SERVED A STALE .pyc, AND THE
# MUTANT THEN REPORTS THE PREVIOUS MUTATION'S BEHAVIOUR.
#
# Python invalidates its bytecode cache on (mtime, size). A red proof writes a
# mutant, runs it, restores, writes the next — all inside one mtime second — so
# a size collision between two mutants serves the earlier one's .pyc to the
# later one's run. MEASURED HERE: red_proof_what_landed reported 6/7 with the
# cache live and 7/7 with PYTHONDONTWRITEBYTECODE=1, and the NOT RED mutation
# was failing a leg belonging to the PRECEDING mutation.
#
# That is a false NOT RED — a mutation that does bite, reported as one that
# does not — and the same mechanism can produce a false RED, which is worse.
# The guard costs nothing: the child never writes bytecode, so there is nothing
# stale to serve.
def _child_env():
    import os as _os
    e = dict(_os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_what_landed.py")
WATCHED = ["what_landed.py", "judge_v2.py", "smoke_what_landed.py"]

MUTATIONS = [
    # ABSENCE OF A MEASUREMENT BECOMES EVIDENCE OF ABSENCE.
    # MUTATE THE ANSWER, NOT THE GUARD. `if False:` on this branch makes
    # `left = [s for s in silence_spans]` iterate None and the module CRASHES —
    # rc=1 from a TypeError, with L5 never reached. That is a red that is not
    # about the property, and it would have been filed as proof that a leg was
    # enforced when nothing had tested it. Flipping the verdict string makes the
    # property false while the file still runs.
    ("no_measurement_reads_as_dropped", "judge_v2.py",
     '                out.append({"ask": ask, "verdict": "UNMEASURED",\n'
     '                            "evidence": "no silence measurement supplied; absence "',
     '                out.append({"ask": ask, "verdict": "DROPPED",\n'
     '                            "evidence": "no silence measurement supplied; absence "',
     "L5 dead_air_without_a_measurement_is_UNMEASURED",
     lambda s: "if silence_spans is None:" in s),
    # THE THRESHOLD GOES TO ZERO, so every gap between words is dead air and a
    # correct edit is convicted by its own word spacing.
    ("silence_threshold_to_zero", "judge_v2.py",
     "SILENCE_MS = 400.0", "SILENCE_MS = 0.0",
     "L7 sub_threshold_gaps_are_not_dead_air",
     lambda s: "SILENCE_MS = 400.0" in s),
    # AN UNREAD SURFACE RENDERS AS ZERO — the absent-as-a-value defect, in the
    # run line Zac reads.
    ("unread_surface_becomes_zero", "what_landed.py",
     '        if key not in surfaces:\n            return "NOT_READ"',
     '        if False:\n            return "NOT_READ"',
     "L2 unread_surface_never_prints_as_zero",
     lambda s: 'if key not in surfaces:' in s),
    # THE DEDUPE GOES, so every transition counts twice — once per endpoint.
    ("transitions_counted_per_endpoint", "what_landed.py",
     "        if tid is None or tid in seen:", "        if False:",
     "L3 transitions_dedupe_by_id",
     lambda s: "tid is None or tid in seen" in s),
    # THE SOURCE FIGURE IS REPLACED BY THE FRAME FIGURE, collapsing two true
    # numbers into one and inviting the other to be inferred from it.
    ("source_removed_reported_as_frames", "what_landed.py",
     '                     round(sum(c["source_removed_ms"] for c in cuts), 3),',
     '                     round(1000.0 / fps, 1),',
     "L4 cuts_report_source_and_timeline",
     lambda s: 'sum(c["source_removed_ms"] for c in cuts)' in s),
    # A NEGOTIATED ASK IS SCORED AS DROPPED, blaming the editor for a refusal
    # the classifier made before anything was typed into the box.
    ("negotiated_scored_as_dropped", "judge_v2.py",
     "        if a in neg:", "        if False:",
     "L8 negotiated_is_not_dropped",
     lambda s: "if a in neg:" in s),
    # AN ASK THE TABLE CANNOT ANSWER IS SCORED DROPPED — the reader's own gap
    # reported as a failure of the edit.
    # ALSO THE ANSWER, AND FOR A DIFFERENT REASON: `if False:` here is VACUOUS,
    # not a crash. Falling through gives rows.get(None) -> {} -> state None ->
    # UNMEASURED anyway, so the mutant changed the file and not the verdict. The
    # guard and the fallthrough agree, which is exactly the no-op branch case.
    ("unanswerable_ask_scored_as_dropped", "judge_v2.py",
     '            out.append({"ask": ask, "verdict": "UNMEASURED",\n'
     '                        "evidence": "no row in the table answers this ask"})',
     '            out.append({"ask": ask, "verdict": "DROPPED",\n'
     '                        "evidence": "no row in the table answers this ask"})',
     "L9 ask_with_no_row_is_UNMEASURED",
     lambda s: "no row in the table answers this ask" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot(paths):
    return {q: open(os.path.join(HERE, q), "rb").read() for q in paths}


def residue(base):
    return sorted(q for q, b in base.items()
                  if open(os.path.join(HERE, q), "rb").read() != b)


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")
    base = snapshot(WATCHED)

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-36s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-36s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-36s HARNESS FAILURE  will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-36s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue(base)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
