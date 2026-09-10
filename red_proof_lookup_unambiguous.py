#!/usr/bin/env python3
"""RED proof for smoke_lookup_unambiguous.py.

Both mutations reproduce real shapes rather than synthetic ones: a nested helper
shadowing a module-level name (the *scope is not text* class this repo has paid
for twice) and a lookup left behind after its function was renamed.

Four guards: anchor count, prose-match, precondition for weakening mutations,
and ast.parse on the mutant.
"""
import ast
import io
import pathlib
import subprocess
import sys
import tokenize

APP = pathlib.Path("agentic_editor_app.py")
SMOKE = pathlib.Path("smoke_lookup_unambiguous.py")
ORIG = APP.read_text()
_INJECTS = None


def _prose_spans(src):
    _st, _acc = [], 0
    for _l in src.split("\n"):
        _st.append(_acc); _acc += len(_l) + 1
    out = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type in (tokenize.STRING, tokenize.COMMENT):
                out.append((_st[t.start[0] - 1] + t.start[1],
                            _st[t.end[0] - 1] + t.end[1]))
    except (tokenize.TokenError, IndentationError):
        return []
    return out


def _match_is_prose(src, old):
    i = src.find(old)
    return i >= 0 and any(a <= i and i + len(old) <= b
                          for a, b in _prose_spans(src))


# A name a check actually looks up, so the mutation lands where it matters.
MUTATIONS = [
    ("a nested helper SHADOWS a module-level name a check looks up",
     "def source_duration_state(meta):",
     # SHADOWS `count_cuts`, which IS looked up by name (smoke_cut_count).
     # The first version shadowed fps_verdict, which no check looks up — so the
     # mutant was correct to pass and the mutation was testing nothing. A
     # mutation aimed outside the check's population proves nothing about the
     # check, and it looks identical to a blind check in the tally.
     "def source_duration_state(meta):\n    def count_cuts(*a, **k):\n"
     "        return 0\n",
     "defined twice in the app", _INJECTS),
    ("a check looks up a function the app no longer defines",
     "def source_duration_state(meta):",
     "def source_duration_state_RENAMED(meta):",
     "defined NOWHERE in the app", _INJECTS),
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
        print(f"  HARNESS FAILURE  {label}  :: anchor matches only in a string "
              f"or comment")
        continue
    if precond is not None and not precond(txt):
        harness.append(f"{label}: VACUOUS")
        print(f"  VACUOUS          {label}")
        continue
    _mutant = txt.replace(old, new, 1)
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        harness.append(f"{label}: mutant does not parse ({_se.msg})")
        print(f"  HARNESS FAILURE  {label}  :: mutant does not parse "
              f"({_se.msg}) — it never ran, so it proved nothing")
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
print(f"\nRESTORED exit={frc}  app unchanged={APP.read_text() == ORIG}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
# A HARNESS WITH NO LEGS MUST NOT EXIT 0.
sys.exit(0 if red and red == len(MUTATIONS) and not harness and frc == 0 else 1)
