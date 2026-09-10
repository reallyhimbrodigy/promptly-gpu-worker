#!/usr/bin/env python3
"""RED proof for smoke_truncated_lists.py.

Mutations restore the REAL defects — the unlabelled `sample` listing and the
uncounted `[:8]` — rather than synthetic ones, so the proof shows the check
catching what actually happened on 2026-09-09.

Three guards carried: anchor count, prose-match (an anchor that lands only
inside a string or comment proves nothing), and a per-mutation precondition for
anything that WEAKENS rather than injects.
"""
import io
import ast
import pathlib
import subprocess
import sys
import tokenize

APP = pathlib.Path("agentic_editor_app.py")
SMOKE = pathlib.Path("smoke_truncated_lists.py")
ORIG = APP.read_text()
_INJECTS = None


def _prose_spans(src):
    _starts, _acc = [], 0
    for _l in src.split("\n"):
        _starts.append(_acc)
        _acc += len(_l) + 1
    spans = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type in (tokenize.STRING, tokenize.COMMENT):
                spans.append((_starts[t.start[0] - 1] + t.start[1],
                              _starts[t.end[0] - 1] + t.end[1]))
    except (tokenize.TokenError, IndentationError):
        return []
    return spans


def _match_is_prose(src, old):
    i = src.find(old)
    if i < 0:
        return False
    return any(a <= i and i + len(old) <= b for a, b in _prose_spans(src))


MUTATIONS = [
    # THE WHOLE PRINT STATEMENT, not its first line. My first version
    # replaced only the opening line and left the `+ (f" of {_vn}" ...)`
    # continuation in place, so the mutant STILL stated a denominator and
    # the check was right to pass it. A mutation that edits part of an
    # expression tests the part it left alone.
    ("the sample listing stops saying it is a sample",
     '        print(f"     ^ SAMPLE: {len(_vs)} beat(s) shown"\n              + (f" of {_vn}" if _vn is not None else\n                 " — TOTAL NOT RECORDED, so this is a subset of an unknown "\n                 "number; do not count from it"))\n',
     '        pass\n',
     "self-declared subset", _INJECTS),
    ("the skip listing loses its count",
     '''        if len(_sks) > 8:
            print(f"       ... showing 8 of {len(_sks)} skip(s)")''',
     '''        pass''',
     # The message names the BOUND NAME, since the fix introduced one.
     "with no len(_sks) beside it", _INJECTS),
]


def run():
    r = subprocess.run([sys.executable, str(SMOKE)], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


rc, out = run()
if rc != 0:
    print("BASELINE IS NOT GREEN — nothing below means anything:\n" + out)
    sys.exit(2)
print("baseline: PASS\n")

red, harness = 0, []
for label, old, new, expect, precond in MUTATIONS:
    txt = APP.read_text()
    n = txt.count(old)
    if n != 1:
        harness.append(f"{label}: anchor {n}x")
        print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
        continue
    if _match_is_prose(txt, old):
        harness.append(f"{label}: anchor lands in prose")
        print(f"  HARNESS FAILURE  {label}  :: the anchor matches only inside a "
              f"string or comment — the mutation would edit prose")
        continue
    if precond is not None and not precond(txt):
        harness.append(f"{label}: VACUOUS")
        print(f"  VACUOUS          {label}")
        continue
    _mutant = txt.replace(old, new)
    # FOURTH WAY A MUTATION FAILS TO MUTATE: SYNTACTICALLY DEAD. (Builder-1,
    # 2026-09-09 — their mutant inserted a 4-space block before an 8-space
    # line.) A mutant that does not compile makes the check fail for a reason
    # unrelated to the property under test, and a check failing for the wrong
    # reason is a check reporting a pass it did not earn. The other guards are
    # all silent: the anchor matched, the operand was non-empty, the match was
    # in code.
    #
    #     anchor 0x             a refactor moved it     count guard
    #     operand is empty      the edit is a no-op     precondition
    #     match lands in prose  a comment now owns it   _match_is_prose
    #     mutant will not parse it never ran at all     THIS
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        harness.append(f"{label}: mutant does not parse ({_se.msg})")
        print(f"  HARNESS FAILURE  {label}  :: the mutant does not parse "
              f"({_se.msg} at line {_se.lineno}) — it never ran, so it proved "
              f"nothing")
        continue
    APP.write_text(_mutant)
    mrc, mout = run()
    APP.write_text(ORIG)
    if mrc == 0:
        print(f"  NOT RED          {label}  :: the mutant PASSED. Precondition "
              f"{'held' if precond else 'n/a (injects)'}")
        harness.append(f"{label}: mutant passed")
    elif expect not in mout:
        print(f"  WRONG REASON     {label}  :: expected '{expect}'")
        harness.append(f"{label}: wrong reason")
    else:
        red += 1
        print(f"  RED              {label}\n                   caught by: {expect}")

APP.write_text(ORIG)
frc, _ = run()
print(f"\nRESTORED exit={frc}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if red and red == len(MUTATIONS) and not harness and frc == 0 else 1)
