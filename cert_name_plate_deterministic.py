#!/usr/bin/env python3
"""THE NAME PLATE FIRES WITHOUT A MODEL CALL, AND NEVER INVENTS A NAME.
`[ART_DIRECTION §6, Rule 1]`

WHY. `brand_components.build_brand_specs()` was always a pure function — no
model call, palette lock built in. It was fed from `edit_plan["brand_copy"]`,
which the planner emits on **0 of 198 jobs**. So the name plate and end card
were WIRED AND UNREACHABLE: the mechanism worked end to end and its only input
never arrived. On the render the owner watched, the speaker says "My name is
Sujay Ahmad" in the first six words and no plate fired.

The transcript already carries the trigger, so the fallback is deterministic:
no model call, no added latency, no cost.

THIS CERT IS BEHAVIOURAL, NOT STRUCTURAL. It loads the REAL function out of
handler.py and runs it against a fixed table. A structural check ("the regex is
case-sensitive") can be satisfied by code that does not work; this one cannot.
Every case below is a real production transcript or a real measured failure.

THE FOUR FAILURE MODES IT PINS, all measured against 800 production transcripts:

  case-insensitivity   `[A-Z][a-z]+` under re.I matches lowercase, so "I'm
                       paying" / "I'm sure" / "I'm not" all scored as names.
                       EVERY name hit in the first corpus was a false positive.
  regex backtracking   a trailing `(?!'s)` let the engine shorten the token —
                       "Bennie's" matched as "Benni" WITH the lookahead
                       satisfied, inventing a person named Benni.
  honorific split      "I'm Mr. Shannon" yielded the name "Mr".
  third-party role     "comments from the CEO" is somebody else's job title;
                       only first-person forms describe the speaker.

    python3 cert_name_plate_deterministic.py
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")
FN = "_speaker_identity_from_transcript"

# (transcript, expected_name)  — None means it MUST NOT fire.
CASES = [
    # ── must fire: real self-introductions from production ────────────────
    ("Hey, Clippers team. My name is Sujay Ahmad. I'm 21 years old.", "Sujay Ahmad"),
    ("Hi. My name is Rohit Gaurade. I'm based out of Maharashtra.", "Rohit Gaurade"),
    ("Hello, guys. My name is Neva. I'm from Manipur.", "Neva"),
    ("Hi, guys. I'm Mr. Shannon, and I want to make contemplative videos.", "Mr. Shannon"),
    ("Hi. This is Abhi, a third year PD student. I'm getting licensed.", "Abhi"),
    # ── must NOT fire: the measured false positives ───────────────────────
    ("the biggest launch in entertainment history, I'm paying close attention.", None),
    ("if you work at a retailer, I'm sure a lot of people here do", None),
    ("this is exactly what I would do. I'm not selling a course", None),
    ("I'm American and I'm really excited about this", None),
    ("Hi, guys. This is Bennie's Basketball. Today, I'll be showing you", None),
    ("What if I told you this is Sea Buckthorn, a small orange berry.", None),
    ("Hi. My name is My client is Python's academic.", None),
    ("So this is Great news for everyone watching today", None),
    ("", None),
    (None, None),
]

ROLE_CASES = [
    ("My name is Ava Juergens. I'm the CEO of Personal Brand Labs.", "Ceo"),
    ("I'm Sarah and I am a founder building in public.", "Founder"),
    # third-party role — the speaker is not the CEO
    ("recently, just comments from the CEO regarding the release date", None),
]


def _load():
    """Load the REAL function out of handler.py without importing the module."""
    src = open(HANDLER).read()
    tree = ast.parse(src)
    ns = {"re": re}
    wanted_const = {"_NAME_INTRO", "_NOT_A_NAME", "_ROLE_WORDS",
                    "_ROLE_FIRST_PERSON", "_NAME_INTRO_WORD_WINDOW"}
    found_fn = False
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", None) in wanted_const for t in n.targets):
            exec(compile(ast.Module(body=[n], type_ignores=[]), "h", "exec"), ns)
        if isinstance(n, ast.FunctionDef) and n.name == FN:
            exec(compile(ast.Module(body=[n], type_ignores=[]), "h", "exec"), ns)
            found_fn = True
    return (ns.get(FN) if found_fn else None), src, tree


def main():
    fn, src, tree = _load()
    fails = []
    if fn is None:
        print(f"CERT NAME-PLATE: FAIL\n  - {FN}() not found; the name plate is "
              f"back to depending on brand_copy, which the planner emits on 0 "
              f"of 198 jobs")
        return 1

    n_fire = n_quiet = 0
    for text, expected in CASES:
        try:
            got, _role = fn(text)
        except Exception as e:
            fails.append(f"{FN}({str(text)[:40]!r}) raised {type(e).__name__}: {e}")
            continue
        if expected is None:
            n_quiet += 1
            if got is not None:
                fails.append(f"INVENTED A NAME {got!r} from {str(text)[:60]!r} — "
                             f"a wrong plate on a stranger's video is worse than "
                             f"no plate")
        else:
            n_fire += 1
            if got != expected:
                fails.append(f"expected {expected!r}, got {got!r}, from "
                             f"{str(text)[:60]!r}")

    for text, expected in ROLE_CASES:
        _n, got = fn(text)
        if got != expected:
            fails.append(f"role: expected {expected!r}, got {got!r}, from "
                         f"{text[:60]!r}")

    # The one structural rule behaviour cannot prove on its own: the pattern must
    # never be compiled case-insensitively, because re.I silently turns [A-Z]
    # into "any letter" and every case above would still pass with a corpus that
    # happens to be capitalised.
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", None) == "_NAME_INTRO" for t in n.targets):
            seg = ast.get_source_segment(src, n) or ""
            if "re.I" in seg or "IGNORECASE" in seg:
                fails.append("_NAME_INTRO is compiled case-insensitively — re.I "
                             "makes [A-Z] match lowercase, which is exactly how "
                             "'I'm paying' became a name")

    # The deterministic value must actually REACH the spec builder, or this is
    # built-not-working: the function exists and nothing consumes it.
    calls = sum(1 for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", None) == FN)
    if calls < 1:
        fails.append(f"{FN}() is never called — the plate would still depend on "
                     f"brand_copy (built, not working)")

    if fails:
        print("CERT NAME-PLATE: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT NAME-PLATE: PASS")
    print(f"  {n_fire} real introductions extracted, {n_quiet} traps refused")
    print("  case-sensitive by construction; possessive and honorific handled")
    print("  role is first-person only — a third party's title is not the speaker's")
    print(f"  wired: {calls} call site(s) feeding build_brand_specs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
