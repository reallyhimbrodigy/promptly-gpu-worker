#!/usr/bin/env python3
"""SMOKE — the one ToolSearch call can actually return every tool it asks for.

MEASURED, not suspected. run-1789432983 made 23 ToolSearch calls out of 44 tool
calls total, against a prompt that says "Fetch them in ONE call before you
start". The extra 22 were not waste — they were RETRY: `edit_item` re-fetched
six times before it would run, then `submit_export`/`track_export` sixteen, the
agent visibly probing the cap with max_results 1, 2, 10 and omitted.

The cause was one unstated default. ToolSearch's `max_results` is 5; the select
list is 26 names. The bulk call returned five schemas and every other tool
stayed uncallable, so the instruction could not be obeyed however the agent
read it. 69% of that run's idle gap time sits in the window those retries occupy.

The check has to tie the NUMBER to the LIST, because a hardcoded 26 would rot
the day someone adds a tool — which is the same failure one turn later.
"""
import re
import sys

SRC = open("chatcut_job_app.py", encoding="utf-8").read()

n_tools = len(re.search(r"NEEDED_TOOLS = \[(.*?)\]", SRC, re.S).group(1)
              .replace("\n", " ").split(",")) - 1  # trailing comma


def legs(s):
    bad = []
    if not re.search(r"^\s*_nsel = len\(NEEDED_TOOLS\)", s, re.M):
        bad.append("the count is not derived from NEEDED_TOOLS")
    # ACROSS THE LINE BREAK, not to end-of-line. The instruction is built from
    # adjacent f-string literals, so `max_results={_nsel}` sits on the NEXT
    # source line from the `select:` it belongs to. A `[^\n]*` anchor reported
    # both call sites as missing it while the assembled prompt was correct —
    # the reader wrong about correct code, for the fourth time this session.
    for m in re.finditer(r'ToolSearch query=\\"select:\{_sel\}\\"', s):
        window = s[m.end():m.end() + 220]
        if "max_results={_nsel}" not in window:
            bad.append("a ToolSearch instruction omits max_results={_nsel}")
    if len(re.findall(r'ToolSearch query=\\"select:\{_sel\}\\"', s)) < 2:
        bad.append("fewer ToolSearch instructions than expected (prompt moved?)")
    return bad


if __name__ == "__main__":
    print("  NEEDED_TOOLS carries %d tools; ToolSearch max_results default is 5"
          % n_tools)
    bad = legs(SRC)
    for b in bad:
        print("  [FAIL] %s" % b)
    if not bad:
        print("  [ok] every ToolSearch instruction passes max_results=len(NEEDED_TOOLS)")
        print("  [ok] the count is derived from the list, so it cannot drift")

    print("\n  RED PROOF")
    reds = [
        # THE MUTATION MUST MATCH THE REAL SOURCE. A spacing-exact string that
        # matches nothing makes a RED proof print "0 legs red" and look like a
        # check that cannot fail — which is the failure it exists to prevent.
        ("max_results dropped",
         SRC.replace('max_results={_nsel}', 'IGNORED')),
        ("count hardcoded instead of derived",
         SRC.replace("_nsel = len(NEEDED_TOOLS)", "_nsel = 26")),
    ]
    red_ok = True
    for label, mutated in reds:
        f = legs(mutated)
        print("    %-34s -> %d leg(s) red" % (label, len(f)))
        red_ok &= bool(f)

    ok = not bad and red_ok and n_tools > 5
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
