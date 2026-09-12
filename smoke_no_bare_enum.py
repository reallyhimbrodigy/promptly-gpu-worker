#!/usr/bin/env python3
"""Every enum the agent chooses from says what its values MEAN.

THIRD INSTANCE IN THIS LANE, and the first two are already written into
CLAUDE.md as law:

  * the 29-name component enum shipped as bare names. The agent picked
    StatCard every time — not taste, not incumbency: it had never been told
    what any of the other 28 was for. 469 tokens bought 29 usable options.
  * `treatment` prose offered three families while the schema offered six, and
    two runs reported sfx/zoom/cutaway at zero. Read as the agent declining
    them; it had never been offered them.
  * `cut: {"enum": ["keep", "cut"]}` — NO DESCRIPTION AT ALL, on the binary
    that decides what survives. Across 517 rulings the agent kept 93.6% of
    beats and ruled 0 trims, against a reference corpus that cuts on 53%.

The third one hid because "keep" and "cut" LOOK self-explanatory. They are not:
what the agent needed was not the words, it was what counts as a beat worth
cutting — and nothing anywhere said.

A capability the agent cannot NAME is indistinguishable from one it declined,
and a capability it cannot UNDERSTAND is indistinguishable from one it
rejected. Every silent default is a vote for the incumbent, and the incumbent
here was "keep everything".

TWO PROPERTIES:
  1. every enum field on every ruling tool carries a description;
  2. the description says something about the VALUES, not just the field —
     a description that names none of its own enum values has not explained
     the choice.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0
checked = 0


def props_of(t):
    s = t.get("input_schema") or {}
    if t.get("name") == "rule_all_beats":
        return (((s.get("properties") or {}).get("verdicts") or {})
                .get("items", {}).get("properties", {}))
    return s.get("properties") or {}


for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS):
    for fname, spec in (props_of(t) or {}).items():
        if not isinstance(spec, dict):
            continue
        vals = spec.get("enum")
        # an array-of-enum, like `treatment`, hides its values one level down
        if vals is None and isinstance(spec.get("items"), dict):
            vals = spec["items"].get("enum")
        if not vals:
            continue
        checked += 1
        desc = str(spec.get("description") or "")
        if not desc.strip():
            print(f"  *** {t['name']}.{fname} is a BARE ENUM {vals} — the agent "
                  f"is handed words with no statement of what choosing each "
                  f"one means")
            fail += 1
            continue
        # 2. IT MUST SAY SOMETHING ABOUT THE VALUES. A description explaining
        #    the field while never mentioning its options leaves the choice
        #    exactly as unexplained as no description at all.
        named = [v for v in vals if str(v).lower() in desc.lower()]
        if not named:
            print(f"  *** {t['name']}.{fname} has a description that names NONE "
                  f"of its own values {vals} — the field is explained and the "
                  f"CHOICE is not")
            fail += 1

if checked == 0:
    print("  *** no enum fields were found on any ruling tool — this check "
          "inspected nothing and would pass anything")
    fail += 1

print(f"smoke_no_bare_enum: {checked} enum field(s) checked, {fail} wrong")
sys.exit(1 if fail else 0)
