#!/usr/bin/env python3
"""cert_harness_exit_code.py — A FAILED RUN MUST NOT REPORT SUCCESS.

2026-08-24: the v3 cross-arm run was invoked as `modal run app > log 2>&1;
echo "MODAL_RC=$?"`. modal returned 1. The shell's status came from `echo`, so
the task reported SUCCESS, and the result was reported with the wrong
confidence — "19 cells, errors=0, I don't know why it stopped" when the truth
was "the run FAILED and the harness hid it". 19 of 26 cells survived only
because the per-cell S3 write worked.

Every measurement downstream of that session trusts this harness.

    python3 cert_harness_exit_code.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_modal.sh")


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    check("the sanctioned runner exists and is executable",
          os.path.isfile(RUNNER) and os.access(RUNNER, os.X_OK))
    if fails:
        print("\n  CERT HARNESS-EXIT-CODE: FAIL")
        return 1

    src = open(RUNNER, encoding="utf-8").read()

    # THE MECHANISM. pipefail + pipestatus is what carries modal's status
    # through the tee; without both, tee's success becomes the exit code.
    check("uses pipefail", "pipefail" in src)
    check("reads modal's status from pipestatus, not $?",
          "pipestatus[1]" in src or "PIPESTATUS[1]" in src)
    check("exits with the propagated code", "exit $RC" in src)

    # NOTHING MAY FOLLOW THE PROPAGATION. An echo after `exit $RC` is
    # unreachable, but an echo BEFORE it that overwrites RC is the original bug.
    tail = src[src.index("RC=${pipestatus[1]}"):]
    check("RC is never reassigned after capture",
          tail.count("RC=") == 1, "something overwrites the captured status")

    # 'could not run' must be distinguishable from 'ran and passed'.
    r = subprocess.run([RUNNER, "/nonexistent_app.py"], capture_output=True, text=True)
    check("a missing app exits 2 (could not run), not 0", r.returncode == 2,
          f"got {r.returncode}")

    # END TO END: a real app file whose entrypoint fails must propagate.
    probe = "/tmp/_cert_rc_probe.py"
    open(probe, "w").write(
        'import modal\napp = modal.App("rc-probe")\n'
        '@app.local_entrypoint()\ndef main():\n    raise SystemExit(3)\n')
    env = dict(os.environ, PROMPTLY_MODAL_LOG="/tmp/_cert_rc.log")
    r = subprocess.run([RUNNER, probe], capture_output=True, text=True, env=env)
    check("a failing run propagates a NON-ZERO exit", r.returncode != 0,
          f"got {r.returncode} — a failed run would report success")
    check("and it says so loudly", "THE RUN FAILED" in (r.stdout + r.stderr))

    print()
    if fails:
        print(f"  CERT HARNESS-EXIT-CODE: FAIL ({len(fails)})")
        return 1
    print("  CERT HARNESS-EXIT-CODE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
