#!/usr/bin/env python3
"""RED proof for smoke_bake_guard.py.

`loss_allowed` is the live defect restored: the bake writes 28 over 37 and nine
caption styles vanish inside whatever commit happened to run it.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_bake_guard.py")
WATCHED = ["bake_registry.py", "smoke_bake_guard.py"]


# See the note in the other red proofs: a mutated .py re-run in a subprocess can
# be served a STALE .pyc, so the mutant reports the PREVIOUS mutation's
# behaviour. Measured on red_proof_what_landed: 6/7 with the cache, 7/7 without.
def _child_env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUTATIONS = [
    # THE GUARD STOPS GUARDING — the live defect, restored.
    ("loss_allowed", "bake_registry.py",
     '    lost = sorted(component_keys(old_reg) - component_keys(new_reg))',
     '    lost = []',
     "L2 a_loss_refuses_and_names_what_is_lost",
     lambda s: "component_keys(old_reg) - component_keys(new_reg)" in s),
    # IT BECOMES AN EQUALITY GUARD, so a deliberate ADDITION is refused too and
    # the guard is deleted by the first person who adds a component.
    ("equality_not_shrink", "bake_registry.py",
     '    lost = sorted(component_keys(old_reg) - component_keys(new_reg))',
     '    lost = sorted(component_keys(old_reg) ^ component_keys(new_reg))',
     "L4 addition_allowed_shrink_not_equality",
     lambda s: "component_keys(old_reg) - component_keys(new_reg)" in s),
    # AN UNREADABLE ARTIFACT IS TREATED AS EMPTY, which waves through the one
    # write that cannot be undone.
    ("unreadable_reads_as_empty", "bake_registry.py",
     '        return False, ("the artifact on disk is UNREADABLE (%s). Refusing: an "',
     '        return True, ("the artifact on disk is UNREADABLE (%s). Allowing: an "',
     "L5 unreadable_artifact_refuses",
     lambda s: "is UNREADABLE (%s). Refusing" in s),
    # THE NAMES GO BACK TO A COUNTER: the refusal says "fewer" without saying
    # which, and renames everything on a reorder.
    ("names_become_positional", "bake_registry.py",
     '                out.add(str(key) if key is not None else "<no key>")',
     '                out.add("<unnamed:%d>" % len(out))',
     "L1 keys_are_names_not_positions",
     lambda s: 'str(key) if key is not None' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_child_env())
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
            print("  %-28s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-28s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-28s HARNESS FAILURE  will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-28s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
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
