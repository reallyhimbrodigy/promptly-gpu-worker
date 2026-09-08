#!/usr/bin/env python3
"""SMOKE: every round archives itself, and the archive is VERIFIED, not assumed.

/tmp/fixtures was wiped between rounds 25 and 26 and took rounds 6-25 with it —
every per-fixture log, every score.json. The streak audit that reset the count
from 3 to 0 was computed from those logs and can no longer be re-derived by
anyone, including the person who ran it. The conclusions survive only because
they were written into commit messages.

A record of how a pipeline was proven cannot live in a directory the OS is
entitled to delete, and a one-time manual upload rots the same way — so the
archive runs on EVERY round or it is not a record.
"""
import ast, pathlib, sys

fails = []
def check(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

here = pathlib.Path(__file__).parent
arch = (here / "archive_round.py").read_text()
runner = (here / "run_round.sh").read_text()

check("the archiver exists", bool(arch))
check("every round runs it — not a manual step",
      "archive_round.py" in runner,
      "a one-time upload rots exactly like the logs it was meant to save")

# VERIFIED, NOT ASSUMED — the whole family of failures in this lane.
check("the archiver HEADs each object back after writing",
      "head_object" in arch,
      "a put that silently no-ops looks identical to a successful one")
check("it compares the size it read back to the size it wrote",
      "ContentLength" in arch and "!=" in arch)
check("a partial archive FAILS LOUDLY rather than reading as done",
      "FAILED on" in arch and "sys.exit(1)" in arch)
check("an EMPTY round directory is a finding, not a clean archive",
      "is EMPTY" in arch,
      "zero files uploaded must never print as a successful archive")
check("it writes a manifest with per-file digests",
      "MANIFEST.json" in arch and "sha256" in arch)
# THIS PINNED THE BUG. It asserted the literal
# "reliability-fixtures-v1/rounds/round" appeared in the archiver — so it
# required the v1 hardcode, and would have gone RED on the fix and green on a
# v3 round filed under v1's prefix. A check that pins a constant cannot tell a
# correct constant from a wrong one; assert the PROPERTY instead: the prefix is
# derived from the round's own plan, and an unestablished corpus refuses.
check("the archive prefix is keyed by round",
      "rounds/round{ROUND}/" in arch or 'rounds/round" + ROUND' in arch
      or "/rounds/round" in arch)
check("the corpus is DERIVED from the round's plan, not hardcoded",
      "plan.tsv" in arch and "_corpus_of" in arch
      and "reliability-fixtures-v1/rounds" not in arch)
check("a round whose corpus cannot be established is REFUSED, not filed under a guess",
      "refusing to file it under a guess" in arch)

# It must not be able to silently skip when the round DID produce logs.
tree = ast.parse(arch)
exits = [n for n in ast.walk(tree)
         if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "exit"]
check("the archiver has explicit exit paths", len(exits) >= 2)

if fails:
    print(f"ROUND-ARCHIVE: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("ROUND-ARCHIVE: PASS")
