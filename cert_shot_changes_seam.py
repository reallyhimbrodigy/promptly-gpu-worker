"""CERT — the shot_changes seam contract (RULE-1 check for the v584 __round__ regression).

WHAT REGRESSED, so the next reader does not re-derive it:

  15acc4f changed `_do_shot_changes` from `return changes` to
  `return (changes, scores)` — correct, an out-parameter cannot cross a
  container boundary. It updated ONE of the two `future_shot_changes.result()`
  consumers. The other stayed `_shots = future.result()`, so `_shots` became the
  2-TUPLE and rode into the Gemini prompt as `shot_changes=`. It died 1,300
  lines later at `[round(s, 3) for s in _shots[:80]]`:

      TypeError: type list doesn't define __round__ method

  17 jobs / 7 users, all inside 3h14m of v584, every one UNKNOWN:unclassified,
  every one dead before the renderer. The stale comment two lines above the
  change said "so BOTH future_shot_changes.result() consumers stay unchanged" —
  it named the exact hazard and was left asserting the opposite of the new code.

WHY THESE CHECKS AND NOT A REGEX. A regex over call sites is what passes while
a contract rots: it reads text, and the defect was a SHAPE. C2 walks the AST and
asserts every consumer of that future binds a 2-tuple, so a third consumer added
later cannot repeat this. C1/C3 are behavioural — they run the real guard on the
real broken value.

RED-PROVEN: C2 fails on 15acc4f..9755768 (one consumer binds a bare Name) and
C1/C3 fail there too (`_assert_flat_times` does not exist). Verified by running
this file against the pre-fix worktree — see the session report.

Offline. Zero network, zero Modal, zero Gemini.
"""
import ast
import io
import os
import sys
import contextlib

import handler as H

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


_SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_SRC = open(_SRC_PATH, encoding="utf-8").read()
_TREE = ast.parse(_SRC)

print("=== C1: the seam guard accepts what is legal and rejects the regression ===")

# Legal shapes. Empty is LEGAL — a single-take source genuinely has no cuts, and
# a guard that rejected it would turn a normal video into a page.
check("flat float list accepted", H._assert_flat_times("t", [0.5, 1.25, 9.0]) == [0.5, 1.25, 9.0])
check("empty accepted (single-take source has no cuts)", H._assert_flat_times("t", []) == [])
check("ints accepted", H._assert_flat_times("t", [1, 2]) == [1, 2])

# THE REGRESSION SHAPE, built exactly as production built it: the callee returns
# (changes, scores); a consumer that does not unpack gets the pair; the prompt
# does list(pair) → [list, dict].
_regression = list(([1.0, 2.0, 3.0], {"1.0": 8.2}))
check("regression shape is genuinely [list, dict] (the cert tests the real thing)",
      isinstance(_regression[0], list) and isinstance(_regression[1], dict),
      f"got {[type(x).__name__ for x in _regression]}")

_raised = None
try:
    H._assert_flat_times("shot_changes (edit_recipe consumer)", _regression)
except TypeError as _e:
    _raised = str(_e)
check("guard REJECTS the unpacked-pair shape", _raised is not None,
      "the guard accepted the exact value that killed 17 jobs")
check("rejection names the seam, not the arithmetic",
      bool(_raised) and "seam contract is broken upstream" in _raised,
      f"message was: {_raised!r}")
check("rejection names the missing unpack (the actual cause)",
      bool(_raised) and "without unpacking" in _raised, f"message was: {_raised!r}")

# Booleans are ints in Python; a bool in a times list is a shape error, not a time.
_bool_raised = False
try:
    H._assert_flat_times("t", [1.0, True])
except TypeError:
    _bool_raised = True
check("bool rejected (bool is an int subclass — would round() to 1)", _bool_raised)

_str_raised = False
try:
    H._assert_flat_times("t", "1.0,2.0")
except TypeError:
    _str_raised = True
check("bare string rejected (iterable, but not a list of times)", _str_raised)

print("\n=== C2: SEMANTIC — every consumer of the future binds a 2-tuple ===")
# The check that makes a THIRD stale consumer impossible. Walks assignments and
# finds any whose value mentions this future's .result, however it is wrapped —
# called directly, passed as a bare callable to _tl_wait, or inside a lambda.
_consumers = []
for _n in ast.walk(_TREE):
    if not isinstance(_n, ast.Assign):
        continue
    _dump = ast.dump(_n.value)
    if "future_shot_changes" not in _dump or "'result'" not in _dump:
        continue
    _tgt = _n.targets[0]
    _consumers.append((
        _n.lineno,
        isinstance(_tgt, ast.Tuple) and len(_tgt.elts) == 2,
        type(_tgt).__name__,
    ))

check("both consumers found (neither deleted to make this green)",
      len(_consumers) == 2, f"found {len(_consumers)}: {_consumers}")
_bad = [(ln, kind) for ln, ok, kind in _consumers if not ok]
check("EVERY consumer binds exactly 2 names", not _bad,
      f"these bind a non-pair — the v584 defect, exactly: {_bad}")

# And the callee still returns the pair, so the unpack above is not unpacking air.
_do = next((n for n in ast.walk(_TREE)
            if isinstance(n, ast.FunctionDef) and n.name == "_do_shot_changes"), None)
check("_do_shot_changes exists", _do is not None)
_rets = [n for n in ast.walk(_do)] if _do else []
_ret_tuples = [n for n in _rets if isinstance(n, ast.Return)
               and isinstance(n.value, ast.Tuple) and len(n.value.elts) == 2]
check("_do_shot_changes returns a 2-tuple (contract both sides agree on)",
      len(_ret_tuples) >= 1, "callee no longer returns a pair — consumers unpack air")

# The callee guards its own output before returning it.
check("_do_shot_changes asserts its return is well-typed before returning",
      _do is not None and "_assert_flat_times" in ast.dump(_do),
      "a relocated call must page on a bad return, not hand it downstream")

print("\n=== C3: the arithmetic site is now unreachable with a bad shape ===")
# The frame that actually raised in production. Prove BOTH directions: the bad
# value really does blow up there (so the cert is testing a live hazard), and
# the seam guard now fires FIRST, at the boundary, naming the cause.
_round_died = False
try:
    _ = [round(s, 3) for s in _regression[:80]]
except TypeError as _e:
    _round_died = "__round__" in str(_e)
check("the round() site still dies on this shape (hazard is real, not hypothetical)",
      _round_died, "the reproduction no longer reproduces — recheck the cert")

_seam_fires_first = False
try:
    H._assert_flat_times("shot_changes", _regression)
except TypeError:
    _seam_fires_first = True
check("the seam raises before any arithmetic runs", _seam_fires_first)

print("\n=== C4: UNKNOWN carries its frame to the operator ===")
# The instrument was never absent — `error_where` held "handler.py:7506 in
# <listcomp>" on 17/17 rows. Triage read `error_cause` (UNKNOWN:unclassified),
# concluded no traceback existed, and guessed five round() sites. So the frame
# now rides the line that ANNOUNCES the bucket.
try:
    H._assert_flat_times("shot_changes (probe)", _regression)
except TypeError as _e:
    _exc = _e

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _classified = H.classify_error(_exc)
_log = _buf.getvalue()

check("novel shape still lands UNKNOWN (subcode contract untouched)",
      _classified.get("error_code") == "UNKNOWN"
      and _classified.get("error_subcode") == "unclassified",
      f"got {_classified.get('error_code')}:{_classified.get('error_subcode')}")
check("[error-fallback] line carries the exception TYPE",
      "TypeError" in _log, f"log was: {_log[:300]!r}")
check("[error-fallback] line carries the FRAME (file:line in fn)",
      "frame=handler.py:" in _log, f"log was: {_log[:300]!r}")
check("[error-fallback] line carries the offending SOURCE LINE",
      "line=" in _log, f"log was: {_log[:300]!r}")

# The operator page must carry it too — that is where a human first sees UNKNOWN.
_alert = next((n for n in ast.walk(_TREE) if isinstance(n, ast.FunctionDef)
               and n.name == "handler"), None)
check("operator page for at-fault failures includes _err_where",
      _alert is not None and "_err_where" in ast.dump(_alert)
      and _SRC.count("_err_where") >= 3,
      "the page still carries only str(e) — the frame stays invisible to the pager")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
