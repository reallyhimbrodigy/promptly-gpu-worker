#!/usr/bin/env python3
"""cert_doctrine_matches_schema.py — A FIELD THE DOCTRINE DEMANDS MUST EXIST IN
THE SCHEMA THAT CONSTRAINS THE MODEL.

PROSE LOSES TO SCHEMA. Structured output permits exactly what the schema
declares; a field described only in the prompt CANNOT be emitted, no matter how
emphatically it is described. Three instances, each expensive:

  generated_scenes   described, unschema'd, ~a month of "the model declines"
  brand_copy         same shape, 198 jobs
  arm B, entire      141k chars of beat-major doctrine against arm A's
                     component-major schema. `beats`, `place`, `read`,
                     `purpose`, `t_start`, `t_end` ALL ABSENT. Measured
                     2026-08-24: 89% silence across 9 runs, and the one run that
                     produced beats emitted `purpose` on NONE of them.

That last one cost $2.60 and two wrong diagnoses of mine — first "silence is
non-deterministic", then "v3's doctrine didn't reach the model" — before the
schema was read. The read took thirty seconds and was available from the start.

This cert asks the only question that matters: for each arm, is every field the
doctrine ASKS FOR present in the schema that ALLOWS?

    python3 cert_doctrine_matches_schema.py
"""
import json
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))

# What arm B's doctrine demands. Sourced from the doctrine TEXT rather than
# hardcoded belief: a field added to the prompt and not to this list would be
# invisible to the cert, which is the failure mode one layer up.
ARM_B_REQUIRED = ["beats", "read", "place", "purpose", "t_start", "t_end"]


def schema_fields(sch):
    """Every property name anywhere in a (possibly nested) response schema."""
    out = set()

    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("properties", "PROPERTIES") and isinstance(v, dict):
                    out.update(v.keys())
                walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(sch)
    return out


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"\n         {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    import handler as H

    # ── the doctrine actually asks for these ────────────────────────────────
    doctrine = ""
    try:
        import prompt_v2_editor as E
        doctrine = E.MASTER_EDITOR_DOCTRINE
    except Exception as e:
        check("arm B doctrine is importable", False, str(e))
        return 1

    asked = [f for f in ARM_B_REQUIRED if f in doctrine]
    print(f"  arm B doctrine demands: {asked}")
    check("the doctrine asks for the v3 beat fields",
          {"purpose", "t_start", "t_end"} <= set(asked),
          "the doctrine itself is missing them — fix the doctrine, not the schema")

    # ── the schema actually permits these ───────────────────────────────────
    # ARM B'S SCHEMA, not arm A's. The first cut of this cert read the no-arg
    # call and was therefore asserting against the wrong schema entirely — its
    # own wrong-key bug, in the cert written to catch wrong-schema bugs.
    try:
        sch = H._post_cuts_response_schema(v2=True)
    except Exception as e:
        check("the post-cuts response schema is buildable", False, str(e))
        return 1
    permitted = schema_fields(sch)
    blob = json.dumps(sch)
    print(f"  schema declares {len(permitted)} property names ({len(blob):,} chars)\n")

    # ── THE ASSERTION ───────────────────────────────────────────────────────
    missing = [f for f in asked if f not in permitted and f'"{f}"' not in blob]
    check("every field arm B's doctrine demands exists in its response schema",
          not missing,
          f"MISSING FROM SCHEMA: {missing}\n"
          f"         The model is CONSTRAINED to a schema without these. It cannot\n"
          f"         emit them however the doctrine is worded. This is the cause of\n"
          f"         arm B's 89% silence, not model difficulty.")

    # The beat container specifically — without it nothing beat-shaped survives.
    check("the schema has a `beats` container at all",
          "beats" in permitted or '"beats"' in blob,
          "arm B is emitting beat-major prose into a component-major schema")

    # ROUTING. A cert that asks for v2=True would pass even if no call site ever
    # passes it — the schema would exist and never be used, which is the
    # built-not-wired class and has nine precedents here. Assert the call sites.
    src = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src_nc = "\n".join(re.sub(r"#.*$", "", ln) for ln in src.splitlines())
    n_routed = len(re.findall(r"_post_cuts_response_schema\(v2=v2\)", src_nc))
    check("the call sites actually route the arm to the schema selector",
          n_routed >= 2,
          f"only {n_routed} call site(s) pass v2 — arm B would be handed arm A's\n"
          f"         schema at request time however well the selector is written")

    print()
    if fails:
        print(f"  CERT DOCTRINE-MATCHES-SCHEMA: FAIL ({len(fails)})")
        print("  Prose loses to schema. Three instances; this is the check.")
        return 1
    print("  CERT DOCTRINE-MATCHES-SCHEMA: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
