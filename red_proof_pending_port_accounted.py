#!/usr/bin/env python3
"""RED PROOF for smoke_pending_port_accounted.py.

It mutates the DATA, never the checker, and each mutation is aimed at ONE leg.
A red whose output does not contain that leg's own words is reported NOT RED —
a harness that crashes, or that fails a different leg, has not exercised the
property named beside it.

The unmutated suite is run FIRST and must be green, so a red produced by a
broken tree rather than by the mutation is caught here instead of being counted.

Both files are restored from an IN-MEMORY copy in a finally block, and the tree
is checked afterwards: a backup on disk outlives the run that made it, and a
kill between mutate and restore leaves the mutant behind.
"""
import json
import subprocess
import sys

LIB = "library_73.json"
REG = "chatcut_registry.json"
SMOKE = "smoke_pending_port_accounted.py"


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def m_drop_reason(lib, reg):
    """A PENDING PORT line loses its reason."""
    lib["_pending_port"]["components"]["EndCard"]["reason"] = ""
    return lib, reg


def m_unmark_status(lib, reg):
    """A PENDING PORT line stops saying PENDING PORT."""
    lib["_pending_port"]["components"]["Notification"]["status"] = "ported"
    return lib, reg


def m_neither(lib, reg):
    """A component is dropped from PENDING PORT while still unregistered —
    the platter would then offer what cannot be served."""
    del lib["_pending_port"]["components"]["PillMarquee"]
    return lib, reg


def m_both(lib, reg):
    """A component is PENDING PORT and registered at once."""
    lib["_pending_port"]["components"]["Reticle"] = {
        "status": "PENDING PORT", "reason": "invented", "detail": ""}
    return lib, reg


def m_deleted_from_library(lib, reg):
    """The ruling KEEPS the entry; this deletes it instead of marking it."""
    lib["motion graphic"] = [n for n in lib["motion graphic"] if n != "ChatThread"]
    return lib, reg


def m_reason_drift(lib, reg):
    """The library's copy of a reason drifts from the registry's."""
    lib["_pending_port"]["components"]["TweetBubble"]["reason"] = "something else"
    return lib, reg


MUTATIONS = [
    (m_drop_reason,          "every PENDING PORT line carries a reason"),
    (m_unmark_status,        "every PENDING PORT line is marked PENDING PORT"),
    (m_neither,              "every library motion graphic is registered, pending, or superseded"),
    (m_both,                 "no component is REGISTERED and PENDING PORT at once"),
    (m_deleted_from_library, "every PENDING PORT name is still IN the library"),
    (m_reason_drift,         "each reason still matches chatcut_registry.json `refused`"),
]


def main():
    lib_orig = open(LIB, encoding="utf-8").read()
    reg_orig = open(REG, encoding="utf-8").read()

    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: the UNMUTATED suite is not green (rc=%d).\n%s"
              % (rc, out[-900:]))
        return 2
    print("baseline green\n")

    red = 0
    try:
        for fn, phrase in MUTATIONS:
            lib = json.loads(lib_orig)
            reg = json.loads(reg_orig)
            lib, reg = fn(lib, reg)
            json.dump(lib, open(LIB, "w"), indent=1, ensure_ascii=False)
            json.dump(reg, open(REG, "w"), indent=1, ensure_ascii=False)
            rc, out = run()
            # the leg's OWN words must appear on a FAIL line, not merely somewhere
            hit = any(l.startswith("  [FAIL]") and phrase in l
                      for l in out.splitlines())
            ok = rc != 0 and hit
            red += 1 if ok else 0
            print("  [%s] %-24s rc=%d leg_failed=%s" %
                  ("RED" if ok else "NOT RED", fn.__name__, rc, hit))
            if not ok:
                print("        expected the FAIL line: %s" % phrase)
    finally:
        open(LIB, "w", encoding="utf-8").write(lib_orig)
        open(REG, "w", encoding="utf-8").write(reg_orig)

    # RESIDUE IS MEASURED AGAINST THE STATE AT PROOF START, NOT AGAINST GIT HEAD.
    # The first version asked `git status --porcelain`, and it fired on this very
    # run — because library_73.json carried an uncommitted edit of mine BEFORE
    # the proof began. That is a red for the wrong reason, and the obvious
    # "fix" is to delete the check, which is how a residue check stops being one.
    # It is also WEAKER in the direction that matters: against HEAD, a file that
    # was already dirty hides any residue this proof adds on top of it.
    # The bytes captured in memory above are the exact baseline, so compare
    # to those and the answer is independent of what git thinks.
    residue = [p for p, orig in ((LIB, lib_orig), (REG, reg_orig))
               if open(p, encoding="utf-8").read() != orig]
    if residue:
        print("\nHARNESS FAILURE: residue left behind by this proof: %s" % residue)
        return 2

    floor = MUTATIONS and red == len(MUTATIONS)
    print("\n%d/%d RED-proven%s" % (red, len(MUTATIONS),
                                    "" if floor else "  <-- FAILED"))
    return 0 if floor else 1


if __name__ == "__main__":
    sys.exit(main())
