#!/usr/bin/env python3
"""SMOKE — a caption refusal REFUSES. It is not merely reported.

THE DEFECT, CAUGHT BY WATCHING THE VIDEO AND BY NOTHING ELSE. Round 70,
car_short, ledger:

    caption_state       = REFUSED
    caption_state_why   = median word confidence 0.352 is below the 0.60 floor
                          over 2 word(s), all tagged ['de'] ...
    caption_render      = {pages: 1, frames: 100, ok: True}
    caption_composited  = True
    caption_scripts     = {'CYRILLIC': 5}

`ОЙ` is on screen at 00:06 of the delivered file. That is the exact round-65
defect the confidence gate was written to stop, shipping on the round that
reported catching it — and I read the REFUSED line and called it a save.

TWO CONSUMERS, ONE QUESTION, AND ONLY ONE OF THEM ASKED IT. The SRT path
honoured the gate: `cues` stays empty unless the state is MEASURED. The
Remotion path asked `bool(words)` — "did anybody say anything" — which is the
weaker question the gate exists to replace. So half the machinery obeyed a
verdict the other half re-derived badly, and the ledger displayed the verdict,
which is what made it look handled.

kept_words_out stays populated on a refusal ON PURPOSE: the zoom staging reads
it for word onsets and has nothing to do with captions. Emptying it would fix
this by breaking something else.
"""
import ast
import sys

import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(what, passed, detail=""):
    if not passed:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if passed else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not passed and detail else ""))


SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

# ── 1. THE GATE STILL DISCRIMINATES ─────────────────────────────────────────
# If this degrades to "always MEASURED" every leg below passes while the
# product ships noise again.
_m, _ = A.caption_confidence_state([{"w": "hello", "s": 0, "e": .4, "conf": .99},
                                    {"w": "world", "s": .5, "e": .9, "conf": .97}])
check("clean speech is MEASURED", _m == "MEASURED", _m)
_r, _why = A.caption_confidence_state([{"w": "ОЙ", "s": 0, "e": .3, "conf": .21}])
check("noise the model gave words to is REFUSED", _r == "REFUSED", _r)
check("and the refusal says WHY, with the number and the floor",
      "0.21" in _why and "0.60" in _why, _why)
_a, _ = A.caption_confidence_state([{"w": "x", "s": 0, "e": .1}])
check("no per-word confidence is ABSENT, never assumed good", _a == "ABSENT", _a)
_n, _ = A.caption_confidence_state([])
check("no words at all is NO_SPEECH", _n == "NO_SPEECH", _n)

# ── 2. THE BUILD READS THE GATE, NOT bool(words) ────────────────────────────
# The property is that the decision to BUILD consults caption_state. Read the
# assignment, because `caption_state` appearing anywhere in the file says
# nothing about whether this particular branch asks it.
_want = [n for n in ast.walk(TREE)
         if isinstance(n, ast.Assign)
         and any(getattr(t, "id", "") == "_want_caps" for t in n.targets)]
check("_want_caps is assigned exactly once", len(_want) == 1, str(len(_want)))
if _want:
    _expr = ast.unparse(_want[0].value)
    check("_want_caps consults the caption gate rather than only bool(words)",
          "_cap_gate" in _expr or "caption_state" in _expr, _expr[:120])
    check("and it still requires words — a gate that passes on an empty "
          "transcript would build an empty caption layer",
          "words" in _expr, _expr[:120])

# ── 3. THE INVARIANT IS A NAMED CONTRACT FAILURE ────────────────────────────
check("caption_refused_but_composited is a contract failure name",
      "caption_refused_but_composited" in A.CONTRACT_FAILURES)
# AND IT IS ACTUALLY RAISED. A name in a frozenset that nothing calls is the
# same absence wearing a declaration's clothes.
_calls = [n for n in ast.walk(TREE)
          if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
          and n.args and isinstance(n.args[0], ast.Constant)
          and n.args[0].value == "caption_refused_but_composited"]
check("and fail('caption_refused_but_composited', ...) is CALLED",
      len(_calls) >= 1, f"{len(_calls)} call site(s)")

# IT MUST SIT WITH THE COMPOSITE, not somewhere earlier. The whole defect was a
# check standing upstream of the thing it describes.
_comp = [n.lineno for n in ast.walk(TREE)
         if isinstance(n, ast.Assign)
         and "caption_composited" in ast.unparse(n)]
if _calls and _comp:
    check("the failure is raised at the composite, not upstream of it",
          min(abs(c.lineno - m) for c in _calls for m in _comp) < 20,
          f"fail at {[c.lineno for c in _calls]}, composite at {_comp}")

# ── 4. kept_words_out SURVIVES A REFUSAL ────────────────────────────────────
# Deliberate: the zoom staging reads it. Fixing the caption path by emptying it
# would retire a side-benefit, which this repo has paid for before.
# THREE SPELLINGS OF ONE OPERATION. This counted ast.Subscript only, so it saw
# the WRITE (`led["kept_words_out"] = ...`) and neither READ, both of which are
# `led.get("kept_words_out")` — a Call. It reported "1 site" and failed a
# correct file. The lane's own law, applied to the lane's own check: a
# subscript, an attribute and a .get are three spellings and matching one says
# nothing about the others.
_kw = [n for n in ast.walk(TREE)
       if (isinstance(n, ast.Subscript) and "kept_words_out" in ast.unparse(n))
       or (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
           and n.args and isinstance(n.args[0], ast.Constant)
           and n.args[0].value == "kept_words_out")]
check("kept_words_out is still written and read — the refusal gates the BUILD, "
      "not the data the zoom pass needs", len(_kw) >= 2, f"{len(_kw)} site(s)")

if fails:
    print("CAPTION-REFUSAL-HAS-A-CONSUMER: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CAPTION-REFUSAL-HAS-A-CONSUMER: PASS — the gate discriminates, the build "
      "reads it, and a composite under a refusal is a named contract failure")
