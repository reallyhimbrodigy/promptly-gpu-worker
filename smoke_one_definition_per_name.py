#!/usr/bin/env python3
"""SMOKE — one definition per top-level name, and the rule must discriminate.

THE CLASS THIS EXISTS FOR. Merging lane/duration-producer into
lane/agentic-editor left SEVEN functions defined twice at module level, with no
conflict marker near any of them: both lanes had written the same fix in the
same week and git kept both additions. Python binds the LAST definition; every
import-time cert in the app finds its subject with `next(n for n in ast.walk
(tree) if n.name == ...)`, which returns the FIRST. Four certs and 94 smokes
went green over code that does not execute, while the surviving `admit_verdict`
called a `half_ruling_refusal` of the wrong arity — a TypeError on the first
ruling of every arm of the next round.

AND ONE OF THE SEVEN WAS NOT A DUPLICATE AT ALL. Both lanes named a function
`_sync_verdict_surfaces` and gave it a DIFFERENT JOB: one copies the missing
FIELDS onto the singular ruling tool, the other copies the missing
DESCRIPTIONS. Merging them under one name did not duplicate a guarantee, it
deleted half of one — and the half that vanished was the one nothing else
checked.

DRIVEN FROM THE APP so this exercises the shipped rule, not a copy of it.
"""
import pathlib
import sys

import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(what, passed, detail=""):
    if not passed:
        fails.append(what + (f"  [{detail}]" if detail else ""))
        print(f"  [FAIL] {what}" + (f"  [{detail}]" if detail else ""))
    else:
        print(f"  [ok] {what}")


SRC = pathlib.Path("agentic_editor_app.py").read_text()

# ── 1. the shipped file is clean ────────────────────────────────────────────
try:
    A._assert_no_shadowed_definitions(SRC)
    check("agentic_editor_app defines every top-level name exactly once", True)
except AssertionError as e:
    check("agentic_editor_app defines every top-level name exactly once",
          False, str(e)[:400])

# ── 2. AND THE RULE MUST STILL DISCRIMINATE ─────────────────────────────────
# A checker that flags nothing is indistinguishable from one switched off.
_DUP = "def f():\n    pass\n\n\ndef f():\n    pass\n"
_WRAP = "def f():\n    pass\nf = _instrumented(f)\n"
_CLEAN = "def f():\n    pass\n\n\ndef g():\n    pass\n"
_ASSIGN_DUP = "X = 1\nX = 2\n"


def raises(src):
    try:
        A._assert_no_shadowed_definitions(src)
        return False
    except AssertionError:
        return True


check("it fires on the same function defined twice", raises(_DUP))
check("it fires on a top-level name assigned twice", raises(_ASSIGN_DUP))
check("it does NOT fire on `f = _instrumented(f)` — a self-wrap rebinds the "
      "name to a wrapper AROUND the same function and loses nothing; a checker "
      "that cries wolf on a correct idiom gets switched off",
      not raises(_WRAP))
check("it does NOT fire on two different names", not raises(_CLEAN))
check("empty source is ABSENT, not passing — a check that cannot read its "
      "subject must say so rather than report clean", raises(""))

# ── 3. THE TWO SYNCS KEEP TWO NAMES ─────────────────────────────────────────
# The specific collision that cost half a guarantee. Named, so re-merging one
# onto the other is a failure rather than a silent deletion.
check("_sync_verdict_surfaces (FIELDS) still exists", hasattr(A, "_sync_verdict_surfaces"))
check("_sync_verdict_descriptions (DESCRIPTIONS) still exists",
      hasattr(A, "_sync_verdict_descriptions"))
check("they are two different functions, not an alias — one name for two jobs "
      "is how the merge deleted the field sync",
      getattr(A, "_sync_verdict_surfaces", None)
      is not getattr(A, "_sync_verdict_descriptions", None))
# AND BOTH ARE ACTUALLY CALLED. A function nobody calls is the same absence
# wearing a definition's clothes.
check("the field sync is called at import", "VERDICT_SURFACES_SYNCED = _sync_verdict_surfaces()" in SRC)
check("the description sync is called at import",
      "_SYNCED_VERDICT_DESCRIPTIONS = _sync_verdict_descriptions()" in SRC)

# ── 4. THE ARITY THAT WOULD HAVE KILLED THE ROUND ───────────────────────────
# admit_verdict calls half_ruling_refusal. After the merge the caller passed two
# arguments and the surviving callee took one. Drive it, do not read it.
_led = {"beat_verdicts": []}
try:
    A.admit_verdict(_led, {"beat": 0, "treatment": ["none"], "cut": "keep",
                           "why": "x"}, set())
    check("admit_verdict admits a ruling without raising — the merged tree "
          "called half_ruling_refusal with the wrong arity and this is the "
          "TypeError that would have killed all five arms", True)
except Exception as e:
    check("admit_verdict admits a ruling without raising", False,
          f"{type(e).__name__}: {e}")

if fails:
    print("ONE-DEFINITION-PER-NAME: FAIL")
    sys.exit(1)
print("ONE-DEFINITION-PER-NAME: PASS")
