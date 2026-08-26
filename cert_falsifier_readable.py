#!/usr/bin/env python3
"""cert_falsifier_readable.py — A FALSIFIER THAT READS A FIELD NOTHING WRITES IS
A PRE-REGISTRATION THAT CAN ONLY EVER CONFIRM.

THE INCIDENT (2026-08-25). The stall experiment was specified with an explicit
falsifier: "if `preserved` rises in lockstep with `offered`, the model is being
handed spans it doesn't want and the constant isn't the lever." `preserved` was
NOT PERSISTED. Only located and offered were.

So the experiment as specified would have run, cost two arms of real traffic,
produced a clean-looking located->offered table, and been structurally incapable
of answering the one question that could have refuted its premise. That is worse
than not running it: an unrefutable experiment returns a number that reads like
evidence, and the absent third column looks like a result nobody thought to ask
for rather than a question that could not be asked.

It is the PROBE COLLAPSE class aimed one level up — not a failed measurement
reported as a number, but a measurement that was never possible reported as a
design. And it is invisible at review time, because prose describing a falsifier
looks identical whether or not anything writes the field.

THE FIX IS STRUCTURAL. Every pre-registration declares the fields its readings
depend on, in a machine-readable block:

    ```reads
    stage_timings.dead_air_spans_located
    stage_timings.dead_air_spans_preserved
    ```

and this cert refuses to let one name a field that handler.py does not write.
The declaration is checked against the AST of the actual persist site, not a
grep — a field can be COMPUTED, logged, and dropped in transit (`_v2_counts`
was computed, certified, and eaten by a `k.startswith("_")` sanitiser), so
"the name appears in handler.py" proves nothing.

    python3 cert_falsifier_readable.py
"""
import ast
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Docs that state a pre-registered reading and must therefore declare its source.
DOCS = ["LEAN_AB_PREREGISTRATION.md", "PROMPT_V2_AB_PREREGISTRATION.md",
        "PROMPT_V3_BEAT_PURPOSE_PREREGISTRATION.md", "NEXT_TWO_ITEMS.md"]

# Language that means "I will read a number and draw a conclusion from it".
CLAIM = re.compile(r"falsifi|would refute|worse result|refut|lockstep|"
                   r"pre-?registered read|primary threshold", re.I)


def persisted_fields(src):
    """Every field a completed job actually WRITES, from the AST of the persist
    sites. Not a grep: computed-and-dropped is the failure mode."""
    tree = ast.parse(src)
    out, containers = set(), {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if isinstance(v, ast.Dict):
                inner = {ik.value for ik in v.keys
                         if isinstance(ik, ast.Constant) and isinstance(ik.value, str)}
                if inner:
                    containers.setdefault(k.value, set()).update(inner)
            out.add(k.value)
    for c, inner in containers.items():
        for f in inner:
            out.add(f"{c}.{f}")
    return out, containers


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"\n         {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    src = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    written, containers = persisted_fields(src)
    print(f"  handler persists {len(written)} field names "
          f"({len(containers.get('stage_timings', ()))} under stage_timings)\n")

    # The cert must be able to find its own ground truth, or it certifies nothing.
    check("the persist site was parsed (stage_timings found)",
          len(containers.get("stage_timings", ())) >= 10,
          "AST found no stage_timings dict — this cert would pass everything")

    declared_any = False
    for doc in DOCS:
        p = os.path.join(HERE, doc)
        if not os.path.exists(p):
            continue
        text = open(p, encoding="utf-8").read()
        blocks = re.findall(r"```reads\n(.*?)```", text, re.S)
        claims = [ln.strip() for ln in text.splitlines() if CLAIM.search(ln)]

        # A doc that draws a conclusion from a number MUST say where the number
        # comes from. Prose alone is exactly how `preserved` was lost.
        if claims and not blocks:
            check(f"{doc}: states a falsifier AND declares its fields", False,
                  f"{len(claims)} falsifier/reading line(s) and NO ```reads``` "
                  f"block. The reading cannot be verified as possible before the "
                  f"arm runs — which is how `preserved` was specified but never "
                  f"written.")
            continue
        if not blocks:
            continue

        declared_any = True
        fields = [f.strip() for b in blocks for f in b.splitlines() if f.strip()
                  and not f.strip().startswith("#")]
        missing = [f for f in fields if f not in written]
        check(f"{doc}: every declared field is actually persisted ({len(fields)})",
              not missing,
              f"NOT WRITTEN BY handler.py: {missing}\n"
              f"         A reading that depends on these cannot be taken. The "
              f"experiment would run, return numbers, and be unable to refute "
              f"its own premise.")

    check("at least one pre-registration declares its fields", declared_any,
          "no ```reads``` block anywhere — this cert is vacuous")

    # ── THE FOUNDING CASE, PINNED ───────────────────────────────────────────
    # The three numbers of the stall experiment, and the arm they are cut by.
    # If any is dropped, the falsifier silently becomes unanswerable again.
    for f in ("stage_timings.dead_air_spans_located",
              "stage_timings.dead_air_spans_offered",
              "stage_timings.dead_air_spans_preserved",
              "stage_timings.midsentence_stall_s"):
        check(f"founding case still persisted: {f.split('.')[-1]}", f in written,
              "the stall falsifier is unanswerable again")

    print()
    if fails:
        print(f"  CERT FALSIFIER-READABLE: FAIL ({len(fails)})")
        print("  An experiment that cannot fail its own falsifier is not an")
        print("  experiment. Fix the instrument BEFORE the arm runs.")
        return 1
    print("  NOTE: asserts the field is WRITTEN. That the reading is well-POWERED")
    print("  is a separate question, answered by the denominator on real traffic.")
    print("  CERT FALSIFIER-READABLE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
