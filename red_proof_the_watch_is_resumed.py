#!/usr/bin/env python3
"""RED proof for smoke_the_watch_is_resumed: every leg must be able to fail.

The leg this file exists for is "a MISSING jsonl raises". A `--resume` onto a
session that is not there starts a FRESH session silently — the edit runs, the
gates pass, and the reference layer was never in context. That failure is
INVISIBLE downstream, so the check for it has to be proven capable of firing.
"""
import ast
import io
import subprocess
import sys

sys.path.insert(0, ".")
import red_proof_anchor as RA                                   # noqa: E402

TARGET = "chatcut_job_app.py"
SMOKE = "smoke_the_watch_is_resumed.py"

# (label, anchor, replacement, leg_that_must_fail, precondition_needle)
# precondition: text that must be present in the UNMUTATED source, proving the
# target is doing something — a mutation that removes nothing proves nothing.
MUTATIONS = [
    # RE-AIMED 2026-09-17: the command is built by cli_command(sid, ...) and
    # edit() passes the installed name into it.
    ("the resume flag is dropped",
     '             *(["--resume", sid] if sid else []),\n',
     '',
     "the command resumes",
     '*(["--resume", sid] if sid else [])'),
    ("--resume is handed a literal instead of the session",
     '    _cmd = cli_command(_watch_sid, model, use_hands, agents if use_hands else None, _pm, effort=(effort or None))',
     '    _cmd = cli_command("some-session", model, use_hands, agents if use_hands else None, _pm, effort=(effort or None))',
     "--resume names the installed session",
     'cli_command(_watch_sid, model'),
    ("a missing watch degrades instead of raising",
     "        raise FileNotFoundError(\n"
     "            \"the watch session is not mounted",
     "        return \"\"  # noqa\n"
     "        raise FileNotFoundError(\n"
     "            \"the watch session is not mounted",
     "a MISSING jsonl raises, never degrades",
     "raise FileNotFoundError("),
    ("the jsonl mount is removed",
     '                    "/craft/watch_session.jsonl", copy=True)',
     '                    "/craft/NOTHING.jsonl", copy=True)',
     "the jsonl is mounted into the image",
     '"/craft/watch_session.jsonl"'),
    ("the run goes back to forking",
     '             *(["--resume", sid] if sid else []),',
     '             "--fork-session",\n             *(["--resume", sid] if sid else []),',
     "--fork-session is NOT passed",
     None),          # INJECTS a defect: new material cannot be vacuous
]


def run_smoke():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def leg_failed(out, leg):
    import re
    return re.search(r"^\s+%s\s+FAIL\s*$" % re.escape(leg), out, re.M) is not None


def main():
    src = io.open(TARGET, encoding="utf-8").read()          # backup, in memory

    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: the unmutated smoke is not green (rc=%d)\n%s"
              % (rc, out[-900:]))
        sys.exit(2)

    red, bad = 0, []
    for label, anchor, repl, leg, pre in MUTATIONS:
        if pre is not None and pre not in src:
            bad.append("VACUOUS: %s — %r is not in the source, so the edit "
                       "removes nothing" % (label, pre))
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
            print("  [RED]  %-46s (%s) -> %r failed" % (label, mode, leg))
        else:
            bad.append("NOT RED: %s — rc=%d leg_failed=%s" % (label, rc2, hit))
            print("  [NOT RED] %-44s rc=%d leg_failed=%s" % (label, rc2, hit))

    if io.open(TARGET, encoding="utf-8").read() != src:
        print("\nRESIDUE: %s left MUTATED — restoring" % TARGET)
        io.open(TARGET, "w", encoding="utf-8").write(src)
        bad.append("RESIDUE: %s did not match the pre-sweep source" % TARGET)

    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    for b in bad:
        print("  " + b)
    # THE FLOOR, in the exit and readable: `red` bare, so an emptied MUTATIONS
    # list makes it 0 and the predicate false.
    sys.exit(0 if red and red == len(MUTATIONS) and not bad else 1)


if __name__ == "__main__":
    main()
