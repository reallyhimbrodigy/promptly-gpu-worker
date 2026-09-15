#!/usr/bin/env python3
"""SMOKE — a text or card ruling that leaves a control blank is REFUSED.

WHY THIS EXISTS, measured 2026-09-13. The pipeline ruled a 25s clip in 5 turns
and handed the ChatCut executor a plan whose `size`, `hold_s` and `colour` were
NULL. The executing agent then had to decide them — and deciding is the whole
cost: 39 of 88 turns in the 728s run called no tool at all. A plan with holes
is not a plan, it is a plan plus three decisions, and the saving comes back.

All five fields said "OPTIONAL." in their own schema descriptions, so the model
answered the two it had opinions about (`case`, `where`) and skipped the rest.
That is not the model being careless; it is the surface saying they do not
matter. Both halves are fixed: the descriptions say REQUIRED, and this refusal
makes it true.

WHY REFUSING IS SAFE HERE — the trap `half_ruling_refusal` names one arm above.
Refusing a field a DERIVER would have filled turns "you pick" into an
unsatisfiable demand; that is why `sfx_name` is deliberately not refused. These
five have no deriver (`_derive_sfx_name` and `_derive_card_hero` are the only
two in the file). What they have is a silent BUILDER DEFAULT, which is a vote
for the incumbent: the overlay renders at whatever size the builder chose and
the ledger records the ruling as complete.

THE LEGS DRIVE THE SHIPPED FUNCTION. They do not restate the rule — a local
copy of this logic is exactly what let two mutations pass green on the re-edit
merge, and the rule is a module-level pure function so that a smoke can import
it rather than reimplement it.
"""
import sys

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                            # noqa: E402

CONTROLS = ("size", "case", "where", "colour", "hold_s")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


FULL = dict(beat=0, treatment=["text"], text_content="X", size="large",
            case="upper", where="upper_third",
            colour="white_on_footage", hold_s=2.5)

# ── 1. A COMPLETE RULING PASSES ─────────────────────────────────────────────
# The other half of the two-arm rule. A refusal that fires on everything is not
# a check either, and this arm is what separates "demands the controls" from
# "refuses text".
check("a text ruling answering all five is NOT refused",
      A.half_ruling_refusal(FULL) is None,
      repr(A.half_ruling_refusal(FULL))[:160])

# ── 2. EACH CONTROL IS INDIVIDUALLY LOAD-BEARING ────────────────────────────
# NAMED, NOT COUNTED. A floor on the number refused would stay green while one
# specific field quietly stopped being demanded — and the field that loses its
# guard is the one nobody sees go. (standing rule: a floor on a sum hides which
# contributor vanished.)
for f in CONTROLS:
    why = A.half_ruling_refusal({**FULL, f: None})
    check(f"a text ruling missing `{f}` IS refused", why is not None)
    if why is not None:
        check(f"  ...and the refusal NAMES `{f}`", f in why, why[:150])

# ── 3. IT DOES NOT OVER-DEMAND ──────────────────────────────────────────────
# A beat that places nothing has no controls to answer. A guard that refused
# these would refuse every uneventful beat in every edit, and a check that is
# always red is a check nobody reads.
check("a beat ruled `none` is NOT refused for missing controls",
      A.half_ruling_refusal(dict(beat=1, treatment=["none"])) is None)
check("a beat ruled `zoom` is not refused for a missing `colour`",
      "colour" not in (A.half_ruling_refusal(
          dict(beat=2, treatment=["zoom"], zoom_arc="payoff")) or ""))

# ── 4. CARD CARRIES THEM TOO ────────────────────────────────────────────────
check("a card ruling missing `hold_s` IS refused",
      A.half_ruling_refusal({**FULL, "treatment": ["card"],
                             "card_hero": "9", "hold_s": None}) is not None)

# ── 5. EVERY FIELD DEMANDED EXISTS IN THE SHIPPED SCHEMA ────────────────────
# The orphan guard, applied to the new arm: a refusal demanding a field the
# ruling surface does not offer is unsatisfiable forever.
_src = open("agentic_editor_app.py", encoding="utf-8").read()
for f in CONTROLS:
    check(f"`{f}` is offered by the ruling schema", f'"{f}": {{' in _src)
    check(f"`{f}` no longer advertises itself as OPTIONAL",
          f'"{f}": {{' not in _src or
          "OPTIONAL" not in _src.split(f'"{f}": {{', 1)[1][:600])

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
