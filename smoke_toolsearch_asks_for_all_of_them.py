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
sys.path.insert(0,'.')
import chatcut_job_app as J
import sys

SRC = open("chatcut_job_app.py", encoding="utf-8").read()

# COUNTED FROM THE IMPORTED LIST, NOT FROM A REGEX OVER THE SOURCE. The
# regex counted commented-out entries and printed "10 tools" while
# NEEDED_TOOLS held 8 — a wrong number stated as fact, in the instrument
# whose whole job is that the count is right.
n_tools = len(J.NEEDED_TOOLS)
# THE DECISION MOVED (2026-09-17): the schema-fetch turn is GONE. When the run
# sets ENABLE_TOOL_SEARCH=false and `--tools` names every needed tool, there is
# no ToolSearch instruction to check — the property this smoke guards (the
# agent can reach every tool it needs in one step) holds by construction, and
# a leg demanding the instruction would defend a reversed decision.
import ast as _ast
_edit = next(n for n in _ast.walk(_ast.parse(SRC)) if isinstance(n, _ast.FunctionDef) and n.name == "edit")
_d = _ast.unparse(_edit)
if "_env['ENABLE_TOOL_SEARCH'] = 'false'" in _d:
    _cc = _ast.unparse(next(n for n in _ast.walk(_ast.parse(SRC)) if isinstance(n, _ast.FunctionDef) and n.name == "cli_command"))
    _ok = ("'--tools', 'Bash,Read,Write,Glob,Grep,' + _sel" in _cc
           and ("_sel = ','.join(('mcp__chatcut__' + t for t in NEEDED_TOOLS))" in _cc
                or "_sel = ','.join('mcp__chatcut__' + t for t in NEEDED_TOOLS)" in _cc))
    print("TOOLSEARCH: OFF — the tool block is eager and --tools carries the %d "
          "NEEDED_TOOLS: %s" % (n_tools, "OK" if _ok else "MISSING"))
    sys.exit(0 if _ok and n_tools > 5 else 1)


def legs(s):
    bad = []
    if not re.search(r"^\s*_nsel = len\(NEEDED_TOOLS\)", s, re.M):
        bad.append("the count is not derived from NEEDED_TOOLS")
    # ACROSS THE LINE BREAK, not to end-of-line. The instruction is built from
    # adjacent f-string literals, so `max_results={_nsel}` sits on the NEXT
    # source line from the `select:` it belongs to. A `[^\n]*` anchor reported
    # both call sites as missing it while the assembled prompt was correct —
    # the reader wrong about correct code, for the fourth time this session.
    # FORMAT-AGNOSTIC. This required the f-string spelling `{_sel}`/`{_nsel}`.
    # The deciding prompt was rewritten to one paragraph using %-formatting, so
    # the pattern stopped matching a CORRECT instruction — a reader keyed to
    # wording, which is the fifth time that class has bitten in this session.
    # The property is that every ToolSearch instruction names max_results,
    # because the default is 5 and NEEDED_TOOLS is longer than that; how the
    # value is interpolated is not the check's business.
    # The source escapes its quotes (query=\\"select:...), and the two
    # prompts interpolate differently, so match the instruction loosely and
    # judge it on what follows.
    # JOIN ADJACENT LITERALS FIRST. The prompt now splits "ToolSearch " and
    # "query=..." across two string literals, so a regex over the raw source
    # cannot see an instruction that is present in the assembled prompt. Same
    # trap as the phrase check in smoke_three_turns_two_rewatches, and it is
    # the reason a correct prompt read as having no ToolSearch instruction.
    s = re.sub(r'"\s*\n\s*"', "", s)
    _sites = list(re.finditer(r'ToolSearch query=\\?"?select:', s))
    for m in _sites:
        window = s[m.end():m.end() + 220]
        if "max_results" not in window:
            bad.append("a ToolSearch instruction omits max_results — the "
                       "default is 5 and %d tools would stay uncallable"
                       % len(J.NEEDED_TOOLS))
    if not _sites:
        bad.append("no ToolSearch instruction found in any prompt — the "
                   "schemas are deferred and would never be fetched")
    # and the count must be DERIVED, never a literal that drifts from the list
    for m in _sites:
        window = s[m.end():m.end() + 220]
        if re.search(r"max_results=\d", window):
            bad.append("a ToolSearch instruction hardcodes max_results — it "
                       "must derive from NEEDED_TOOLS or it rots when a tool "
                       "is added, which happened this session")
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
        # BOTH SPELLINGS. The deciding prompt is %-formatted and the plan
        # prompt is an f-string; a mutation that drops only one leaves the
        # other intact and no leg fires — it changed the file and not the
        # result, which is the recorded way a red proof stops proving.
        ("max_results dropped",
         SRC.replace('max_results={_nsel}', 'IGNORED')
            .replace('max_results=%d', 'IGNORED')),
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
