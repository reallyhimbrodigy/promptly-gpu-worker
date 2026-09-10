#!/usr/bin/env python3
"""RED proof for smoke_cutaway_block_matches_builder.py.

Every mutation breaks the BLOCK/BUILDER agreement in one direction or the other
— the block promising what the builder refuses, or the builder enforcing what
the block never published. That second direction is the one that costs
placements silently, and it is the one card_props and the sfx names both hit.

Three guards: anchor count, prose-match (an anchor landing only inside a string
or comment proves nothing), and a precondition for anything that WEAKENS rather
than injects.
"""
import io
import pathlib
import subprocess
import sys
import tokenize

APP = pathlib.Path("agentic_editor_app.py")
SMOKE = pathlib.Path("smoke_cutaway_block_matches_builder.py")
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
    if i < 0:
        return False
    return any(a <= i and i + len(old) <= b for a, b in _prose_spans(src))


# NOTE ON THE PROSE GUARD HERE: the cutaway BLOCK *is* a string literal, so
# mutations that edit it legitimately land "in prose". Those declare
# prose_ok=True. The guard still protects the mutations aimed at CODE — the
# floor, the cap, the overlap test — which is where it matters.
MUTATIONS = [
    ("the builder's floor moves away from the 0.6s the block publishes",
     "_CUTAWAY_MIN_S = 0.6", "_CUTAWAY_MIN_S = 1.9",
     "IS the floor the builder uses", _INJECTS, False),
    ("the builder's cap moves away from the 4.0s the block publishes",
     "_CUTAWAY_MAX_S = 4.0", "_CUTAWAY_MAX_S = 9.0",
     "IS the cap the builder uses", _INJECTS, False),
    ("the builder REFUSES near the end instead of sliding back",
     "            f0 = max(0.0, src_dur - want)      # slide back rather than refuse",
     "            rejects.append({'beat': bi, 'why': 'too near the end'}); continue",
     "SLIDES BACK rather than being refused", _INJECTS, False),
    ("the block stops publishing the own-footage refusal",
     "  footage: cutting from a beat to itself shows the same picture.",
     "  footage.", "every rejection reason the builder emits is published",
     _INJECTS, True),
    ("a frequency target appears in the block",
     "Rule it by putting \"cutaway\" in `treatment`",
     "The reference places one on 72 of 153 beats. Rule it by putting "
     "\"cutaway\" in `treatment`",
     "states no rate, frequency or count target", _INJECTS, True),
    ("the block moves out of SYSTEM and behind the knowledge flag",
     "CUTAWAY — SHOW THE THING, KEEP THE VOICE",
     "CUTAWAY - moved out of SYSTEM, KEEP THE VOICE",
     "is IN SYSTEM, not behind the knowledge flag", _INJECTS, True),
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
for label, old, new, expect, precond, prose_ok in MUTATIONS:
    txt = APP.read_text()
    n = txt.count(old)
    if n != 1:
        harness.append(f"{label}: anchor {n}x")
        print(f"  HARNESS FAILURE  {label}  :: anchor {n}x")
        continue
    if not prose_ok and _match_is_prose(txt, old):
        harness.append(f"{label}: anchor lands in prose")
        print(f"  HARNESS FAILURE  {label}  :: anchor matches only inside a "
              f"string or comment")
        continue
    if precond is not None and not precond(txt):
        harness.append(f"{label}: VACUOUS")
        print(f"  VACUOUS          {label}")
        continue
    APP.write_text(txt.replace(old, new))
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
# A FLOOR, BECAUSE 0 == len([]) IS TRUE. Caught by
# smoke_red_proofs_have_floors the moment this harness arrived from the other
# lane: without it, emptying the mutation list reports SUCCESS — the one thing
# a red proof must never do. `MUTATIONS and` makes an empty list falsy.
sys.exit(0 if MUTATIONS and red == len(MUTATIONS) and not harness and frc == 0
         else 1)
