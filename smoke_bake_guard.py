#!/usr/bin/env python3
"""The bake cannot silently lose a component.

MEASURED 2026-09-22: `bake_registry.py --write` took the artifact from 37 blobs
to 28. It builds the 28 components and overwrites the file wholesale, and the
NINE CAPTION STYLES in the committed artifact are not in its output. Running the
documented build step destroys nine registered caption styles, silently, inside
whatever commit happened to run it.

A SHRINK GUARD AND NOT AN EQUALITY GUARD. A deliberate addition must still
write, or the guard blocks every legitimate bake and is removed within a week.
Only a LOSS refuses — and the lost keys are NAMED, because a refusal that says
"fewer" without saying which is a second puzzle rather than an answer. My first
version named them "<unnamed:32>".."<unnamed:36>" and was exactly that.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bake_registry as bk                                     # noqa: E402

ART = os.path.join(HERE, "chatcut_registry_baked.json")
FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    cur = json.load(open(ART, encoding="utf-8"))
    keys = bk.component_keys(cur)

    # L0 POPULATION FLOOR. Without this every leg below asserts over nothing.
    #
    # WAS `len(keys) == 37 and len(caps) == 9`. The nine caption blobs were
    # dropped on 2026-09-23 — nothing read their baked pages — so a leg pinned
    # to 37/9 was a leg defending a DECISION that had been correctly reversed,
    # and it went red on the commit that reversed it. The floor is what it was
    # always for: enough components that the legs below assert something.
    caps = sorted(k for k in keys if str(k).startswith("caption:"))
    leg("L0 artifact_population", len(keys) >= 20 and not caps,
        "%d component(s), %d caption blob(s) (expected 0 since 2026-09-23)"
        % (len(keys), len(caps)))

    # L1 THE KEYS ARE NAMES, NOT POSITIONS. A counter renames everything on a
    # reorder and tells the reader nothing.
    # `"caption:Lumen" in keys` was the witness that a COLON-BEARING key
    # survives — the shape a counter would mangle. Lumen is gone, so the
    # witness moved to any real component name, and the property it proves is
    # unchanged: no key is a positional placeholder.
    leg("L1 keys_are_names_not_positions",
        bool(keys) and all(not str(k).startswith("<") for k in keys)
        and "StatCard" in keys,
        "sample: %s" % sorted(keys)[:3])

    # L2 A LOSS REFUSES, AND NAMES WHAT IS LOST.
    #
    # DRIVEN, NOT OBSERVED. This used to run the REAL bake and assert it was
    # refused, because the artifact held 37 while the bake produced 28. That
    # made the leg depend on the build step being BROKEN: the day the artifact
    # and the bake agreed — which is the day the nine were dropped, and a good
    # day — the leg failed for the right reason and reported it as a defect.
    #
    # A check that needs the system to stay wrong is a check that will be
    # deleted the moment it is fixed. So the loss is CONSTRUCTED: drop three
    # real components from a copy and assert the guard refuses and names all
    # three. Same property, no dependence on today's bake.
    victims = sorted(keys)[:3]
    shrunk = json.loads(json.dumps(cur))
    for v in victims:
        shrunk["components"].pop(v, None)
    ok, why = bk.shrink_guard(shrunk, ART)
    named = sum(1 for c in victims if c in why)
    leg("L2 a_loss_refuses_and_names_what_is_lost",
        not ok and named == len(victims),
        "refused=%s, %d of %d named: %s" % (not ok, named, len(victims), victims))

    # L3 AN IDENTICAL WRITE IS ALLOWED.
    ok2, _ = bk.shrink_guard(cur, ART)
    leg("L3 identical_write_allowed", ok2, "ok=%s" % ok2)

    # L4 AN ADDITION IS ALLOWED — shrink guard, not equality. An equality guard
    # blocks every legitimate bake and gets deleted.
    plus = json.loads(json.dumps(cur))
    plus["components"]["_NEW_"] = {"code": "const Component = () => null;"}
    ok3, _ = bk.shrink_guard(plus, ART)
    leg("L4 addition_allowed_shrink_not_equality", ok3, "ok=%s" % ok3)

    # L5 UNREADABLE IS NOT EMPTY. Treating a corrupt artifact as zero components
    # would wave through the one write that cannot be undone.
    bad = os.path.join(HERE, "_bakeguard_corrupt.json")
    try:
        open(bad, "w").write("{oops")
        ok4, why4 = bk.shrink_guard(cur, bad)
        leg("L5 unreadable_artifact_refuses",
            not ok4 and "UNREADABLE" in why4, "refused=%s" % (not ok4))
    finally:
        if os.path.exists(bad):
            os.remove(bad)

    # L6 A MISSING ARTIFACT IS A FIRST WRITE, NOT A LOSS.
    ok5, why5 = bk.shrink_guard(cur, os.path.join(HERE, "_bakeguard_absent.json"))
    leg("L6 first_write_allowed", ok5 and "first write" in why5, "ok=%s" % ok5)

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
