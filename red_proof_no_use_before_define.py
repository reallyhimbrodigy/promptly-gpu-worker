#!/usr/bin/env python3
"""RED proof for smoke_no_use_before_define.py.

`scope_test_removed` reproduces Builder 1's two failed attempts exactly: drop
the enclosing-function test and the rule convicts every deferred reference,
which is how both brace-counting versions refused 37 of 37 accepted bodies.
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
SMOKE = os.path.join(HERE, "smoke_no_use_before_define.py")
WATCHED = ["check_use_before_define.mjs", "smoke_no_use_before_define.py"]

MUTATIONS = [
    # THE SCOPE TEST GOES — Builder 1's defect, restored. A nested arrow reading
    # a later outer const is legal and everywhere; without this line the rule
    # convicts all of them.
    ("scope_test_removed", "check_use_before_define.mjs",
     "      if (ref.from.variableScope !== v.scope.variableScope) continue;",
     "      if (false) continue;",
     "L2 a_nested_deferred_reference_is_legal",
     lambda s: "ref.from.variableScope" in s),
    # THE TDZ KINDS GO, so let/const stop being special and nothing is ever
    # reported — the rule asleep while printing a tidy line.
    ("tdz_kinds_ignored", "check_use_before_define.mjs",
     '      const isTdz = kind === "let" || kind === "const" || def.type === "ClassName";',
     "      const isTdz = false;",
     "L1 a_declaration_moved_below_its_use_is_caught",
     lambda s: 'kind === "let"' in s),
    # THE POSITION TEST INVERTS, so a correct declaration-then-use reads as the
    # error and the 37 accepted bodies are convicted.
    ("position_test_inverted", "check_use_before_define.mjs",
     "      if (useStart >= declStart) continue;",
     "      if (useStart <= declStart) continue;",
     "L0 every_chatcut_accepted_blob_passes",
     lambda s: "useStart >= declStart" in s),
    # A PARSE FAILURE READS AS CLEAN. The whole class walks through an
    # unparseable body, and the output looks identical to a pass.
    ("parse_error_reads_clean", "check_use_before_define.mjs",
     '    return { state: "PARSE_ERROR", detail: `${e.message}`, findings: [] };',
     '    return { state: "CLEAN", detail: "", findings: [] };',
     "L3 unparseable_is_reported_not_passed",
     lambda s: '"PARSE_ERROR"' in s),
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
            print("  %-26s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-26s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-26s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
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
