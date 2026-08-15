#!/usr/bin/env python3
"""RED PROOFS THAT CANNOT PASS FOR THE WRONG REASON.

WHY THIS EXISTS [Rule 1]. A gate is only worth what its RED proof is worth, and
this repo has now produced the same failure THREE times: a "RED proof" that
reported RED-then-GREEN while never actually exercising the thing it claimed to
test.

  1. `__smoke_result_rmw_audit.js` — the assertion matched `updated_at` inside a
     COMMENT in the select list, so deleting the real column still passed.
  2. `_no_gpu_on_worker_app` — the injected `gpu="H100"` did not match any
     anchor, so the file was never mutated, the gate passed on an UNMODIFIED
     file, and the run was nearly recorded as "RED proven".
  3. (and `_surface` in predeploy_no_regress carries its own note that comment
     stripping is "a bug this repo has now written five times, most recently in
     the very gate written to prevent it".)

Every one of those looked identical to a real proof from the outside: a non-zero
exit, then a zero exit. The missing step is never the check — it is the
VERIFICATION THAT THE MUTATION LANDED.

So this harness refuses to report RED unless it can prove, byte for byte, that
the file actually changed and that the injected marker is really present. A
mutation that does not apply is a HARNESS FAILURE, reported as loudly as a gate
that failed to fire — because they are the same defect wearing different clothes.

    python3 red_proof.py --file modal_app.py \
        --anchor '@app.function(' --insert-after '    gpu="H100",' \
        --marker 'gpu=' --cmd 'python3 validate_deploy.py'

    python3 red_proof.py --file lib/x.js --replace 'FOO' --with '' \
        --marker-absent 'FOO' --cmd 'node lib/__smoke_x.js'

Exit 0 = the check genuinely fired on a genuinely mutated file and the file was
restored. Anything else is a failure worth reading.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--anchor", help="first line whose STRIPPED form equals this")
    ap.add_argument("--insert-after", help="line to insert after the anchor")
    ap.add_argument("--replace", help="exact substring to replace")
    ap.add_argument("--with", dest="with_", default="", help="replacement text")
    ap.add_argument("--marker", help="token that MUST be present after mutating")
    ap.add_argument("--marker-absent", help="token that MUST be gone after mutating")
    ap.add_argument("--expect", help="the check's output MUST contain this. Without it a "
                                     "proof only shows SOMETHING failed, not the right thing.")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args(argv)

    path = a.file
    if not os.path.exists(path):
        print(f"RED-PROOF: FAIL — {path} does not exist")
        return 2

    before_sha = _sha(path)
    backup = os.path.join(tempfile.gettempdir(), f"redproof_{os.path.basename(path)}.bak")
    # STALE-MUTATION GUARD (2026-08-15, learned the hard way). The restore lives
    # in a `finally`, which does NOT run if the process is KILLED — and a
    # long-running gate is exactly the thing that gets killed or backgrounded.
    # That leaves the working tree MUTATED with nothing saying so, and the next
    # commit ships the mutation. If a backup is already sitting here, a previous
    # proof did not finish: refuse, and say where the good copy is.
    if os.path.exists(backup):
        print(f"RED-PROOF: REFUSING — a stale backup exists at {backup}, so an earlier "
              f"proof was killed before it restored {path}. Your working copy is probably "
              f"still MUTATED. Restore it first:\n    cp {backup} {path}\n"
              f"then delete the backup and re-run.")
        return 2
    shutil.copy2(path, backup)

    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()

        if a.replace is not None:
            if a.replace not in src:
                print(f"RED-PROOF: FAIL — --replace text not found in {path}. "
                      "The mutation could not be applied, so ANY result below would "
                      "be a pass-for-the-wrong-reason.")
                return 2
            mutated = src.replace(a.replace, a.with_, 1)
        elif a.anchor is not None:
            lines = src.split("\n")
            hit = next((i for i, l in enumerate(lines) if l.strip() == a.anchor.strip()), None)
            if hit is None:
                print(f"RED-PROOF: FAIL — anchor {a.anchor!r} not found in {path}. "
                      "Nothing was mutated; the check would have run on a clean file.")
                return 2
            lines.insert(hit + 1, a.insert_after or "")
            mutated = "\n".join(lines)
        else:
            print("RED-PROOF: FAIL — give --replace or --anchor")
            return 2

        with open(path, "w", encoding="utf-8") as f:
            f.write(mutated)

        # ── THE STEP THAT WAS MISSING ALL THREE TIMES ──────────────────────
        after_sha = _sha(path)
        if after_sha == before_sha:
            print(f"RED-PROOF: FAIL — {path} is byte-identical after mutating. "
                  "The check never saw a broken file.")
            return 2
        if a.marker and a.marker not in mutated:
            print(f"RED-PROOF: FAIL — marker {a.marker!r} absent after mutating; "
                  "the injection did not land where it was aimed.")
            return 2
        if a.marker_absent and a.marker_absent in mutated:
            print(f"RED-PROOF: FAIL — {a.marker_absent!r} is STILL present after "
                  "mutating; the removal did not take.")
            return 2
        print(f"  mutation verified: {path} {before_sha[:8]} -> {after_sha[:8]}"
              + (f", marker {a.marker!r} present" if a.marker else "")
              + (f", {a.marker_absent!r} removed" if a.marker_absent else ""))

        r = subprocess.run(a.cmd, shell=True, capture_output=True, text=True,
                           timeout=a.timeout)
        fired = r.returncode != 0
        tail = "\n".join((r.stdout or "").splitlines()[-3:])
        print(f"  check exit={r.returncode} on the mutated file")
        if tail:
            print("  " + tail.replace("\n", "\n  "))
        if not fired:
            print("RED-PROOF: FAIL — the check PASSED on a file proven to be broken. "
                  "The gate does not cover what it claims to cover.")
            return 1
        # THE SECOND WAY A PROOF PASSES FOR THE WRONG REASON, learned from this
        # harness's own use (2026-08-15): breaking a liveness call made the gate
        # go red on PYFLAKES undefined-name, not on the liveness assertion — which
        # did not exist. The mutation landed, the check fired, and the proof was
        # still meaningless. Verifying the file changed is necessary and NOT
        # sufficient; the failure has to be the one you were testing for.
        if a.expect:
            _all = (r.stdout or "") + (r.stderr or "")
            if a.expect not in _all:
                print(f"RED-PROOF: FAIL — the check failed, but NOT for the expected "
                      f"reason. Wanted {a.expect!r} in its output; it failed on something "
                      f"else, so this proves nothing about the assertion under test.")
                return 1
            print(f"  failure reason confirmed: {a.expect!r}")
    finally:
        shutil.copy2(backup, path)
        os.remove(backup)

    restored = _sha(path)
    if restored != before_sha:
        print(f"RED-PROOF: FAIL — {path} was NOT restored ({restored[:8]} != "
              f"{before_sha[:8]}). Fix the file before doing anything else.")
        return 2

    print(f"RED-PROOF: PASS — mutation landed, check fired, {path} restored clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
