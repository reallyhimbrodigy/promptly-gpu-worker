#!/usr/bin/env python3
"""SMOKE — ruling 3: the platter derives from the REGISTRY, and every library
motion graphic is accounted for as REGISTERED or PENDING PORT, never as neither.

Zac 2026-09-21: "Until a component registers, it is OFF the platter. The platter
derives from the registry — the set the agent can be served — not from the
library. A leg fails on any platter line whose component isn't registered. The
library keeps the entry as PENDING PORT with the reason."

WHY THIS FILE AND NOT A LEG IN THE PLATTER BUILDER. `component_platter` lives in
chatcut_job_app.py, which is Builder 1's. So this asserts the INVARIANT that
makes a registry-derived platter safe, on the two files this lane owns: a name
is REGISTERED or it is PENDING PORT WITH A REASON, the two sets are disjoint,
and nothing is in neither. A name in neither is the failure this exists for —
it reads on the platter as available and refuses at registration time, which is
the shape where a capability the agent cannot be served is indistinguishable
from one it declined.

A REASON IS LOAD-BEARING, NOT DECORATION. A PENDING PORT line with an empty
reason is the same defect as a bare enum entry: the next person cannot tell a
component nobody has ported from one that CANNOT be ported, and re-derives the
answer instead of reading it.
"""
import json
import sys

FAILS = []


def check(label, cond, detail=""):
    if not cond:
        FAILS.append(label)
    print("  [%s] %s%s" % ("ok" if cond else "FAIL", label,
                           "\n         " + detail if detail and not cond else ""))


def main():
    lib = json.load(open("library_73.json", encoding="utf-8"))
    reg = json.load(open("chatcut_registry.json", encoding="utf-8"))

    family = lib.get("motion graphic") or []
    registered = set(reg.get("components") or {})
    pending_blk = (lib.get("_pending_port") or {}).get("components") or {}
    pending = set(pending_blk)
    superseded = set(reg.get("superseded") or {})

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    check("the library's motion-graphic family is non-empty", bool(family),
          "no population to check")
    check("the registered set is non-empty", bool(registered))
    check("the PENDING PORT block is non-empty", bool(pending))
    if FAILS:
        print("FAIL %d" % len(FAILS))
        return 1

    print("  population: %d in family, %d registered, %d pending, %d superseded"
          % (len(family), len(registered), len(pending), len(superseded)))

    both = sorted(registered & pending)
    check("no component is REGISTERED and PENDING PORT at once", not both, str(both))

    neither = sorted(n for n in family
                     if n not in registered and n not in pending and n not in superseded)
    check("every library motion graphic is registered, pending, or superseded",
          not neither,
          "in NEITHER set, so the platter would offer what cannot be served: %s"
          % neither)

    unreasoned = sorted(n for n, v in pending_blk.items()
                        if not (v.get("reason") or "").strip())
    check("every PENDING PORT line carries a reason", not unreasoned, str(unreasoned))

    unstatused = sorted(n for n, v in pending_blk.items()
                        if v.get("status") != "PENDING PORT")
    check("every PENDING PORT line is marked PENDING PORT", not unstatused,
          str(unstatused))

    stray = sorted(n for n in pending if n not in family)
    check("every PENDING PORT name is still IN the library", not stray,
          "the ruling KEEPS the entry; a pending name absent from the library "
          "has been deleted rather than marked: %s" % stray)

    # The reasons are copied from chatcut_registry.json `refused` and must stay
    # that copy — two hand-maintained wordings drift and then disagree.
    refused = reg.get("refused") or {}
    drift = sorted(n for n, v in pending_blk.items()
                   if n in refused and v.get("reason") != refused[n].get("reason"))
    check("each reason still matches chatcut_registry.json `refused`", not drift,
          str(drift))

    print(("FAIL %d" % len(FAILS)) if FAILS else "OK — %d pending, all accounted"
          % len(pending))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
