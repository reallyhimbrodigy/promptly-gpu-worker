#!/usr/bin/env python3
"""The runner must refuse to report green on a non-green population.

WHY THE LEGS BELOW DRIVE PURE FUNCTIONS INSTEAD OF RUNNING THE SUITE. The defect
this guards is an aggregation that says "16/16 green" over results containing a
failure. It CANNOT be mutation-tested through the real gates, because they all
pass: break the aggregation and nothing changes, the mutant is byte-different
and behaviourally identical, and the proof reads NOT RED with the code fully
broken. That is the vacuous-mutation trap, and it is the second time today it
decided a design -- the falsy-zero fix needed a fixture for exactly the same
reason, because no short sound peaks at 0.0.

So `verdict()` and `missing()` are module-level pure functions the check CALLS
with a population it constructs, one of which is a failing one. The runner's
real execution is covered by L1, which asserts every named gate exists; whether
they pass is what running them answers.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_gates as rg                                        # noqa: E402

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-40s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    names = rg.gates()

    # L0 EVERY SMOKE IS PAIRED WITH A RED PROOF. A smoke with no proof is a
    # check that has never failed, which is not yet a check.
    proofs = [n for n in names if n.startswith("red_proof_")]
    smokes = [n for n in names if n.startswith("smoke_")]
    paired = sorted(s.replace("smoke_", "red_proof_", 1) for s in smokes)
    leg("L0 every_smoke_has_a_red_proof",
        len(names) == rg.N_EXPECTED and len(set(names)) == len(names)
        and sorted(proofs) == paired,
        "%d gates, %d smokes, %d proofs, unpaired=%s"
        % (len(names), len(smokes), len(proofs),
           sorted(set(paired) ^ set(proofs)) or "none"))

    # L1 EVERY NAMED GATE HAS A FILE. A renamed or deleted gate must fail LOUDLY
    # rather than drop out of a list whose total still looks respectable.
    gone = rg.missing(names)
    leg("L1 no_named_gate_is_missing", not gone, "missing: %s" % (gone or "none"))

    # L2 A CLEAN POPULATION IS GREEN, or every leg below is asserting against a
    # verdict that never returns 0 and the suite can never pass.
    clean = {n: 0 for n in names}
    rc0, s0 = rg.verdict(clean)
    leg("L2 clean_population_is_green", rc0 == 0, "rc=%d %r" % (rc0, s0))

    # L3 ONE FAILURE MAKES THE WHOLE RUN FAIL. THIS IS THE PROPERTY. The commit
    # loop this replaces printed exit=1 for a failing gate and then committed
    # anyway, because the shell never saw it.
    dirty = dict(clean)
    dirty[names[0]] = 1
    rc1, s1 = rg.verdict(dirty)
    leg("L3 one_failure_fails_the_run",
        rc1 != 0 and names[0] in s1, "rc=%d %r" % (rc1, s1))

    # L3b AND A FAILURE ANYWHERE, not only first. A verdict that reads one end
    # of the population would pass L3 and miss the other fifteen.
    for idx in (len(names) // 2, len(names) - 1):
        d = dict(clean)
        d[names[idx]] = 2
        rci, si = rg.verdict(d)
        leg("L3b failure_at_%d_fails_the_run" % idx,
            rci != 0 and names[idx] in si, "rc=%d %r" % (rci, si))

    # L4 A SHORT POPULATION IS A HARNESS FAILURE, NOT A PASS. A runner that
    # silently ran eight of sixteen and reported green is the subset-as-total
    # failure, and it is how a suite rots into the checks that happen to pass.
    short = {n: 0 for n in names[:-1]}
    rc2, s2 = rg.verdict(short)
    leg("L4 short_population_is_harness_failure",
        rc2 == 2 and "HARNESS" in s2, "rc=%d %r" % (rc2, s2))

    # L5 missing() ACTUALLY LOOKS AT THE DISK. Driven with a name that cannot
    # exist, so a stubbed-out implementation returning [] is caught.
    probe = "smoke_this_gate_does_not_exist_" + "x" * 8
    leg("L5 missing_detects_an_absent_file",
        rg.missing([probe]) == [probe] and rg.missing(names[:1]) == [],
        "absent=%s present=%s" % (rg.missing([probe]), rg.missing(names[:1])))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
