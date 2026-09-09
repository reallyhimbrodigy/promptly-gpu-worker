#!/usr/bin/env python3
"""RETIRED BY THE DERIVATION RULING (2026-09-09). Kept as the record of why.

    smoke_card_props_taught      the agent must be TOLD each component's props
    smoke_mg_catalogue_wired     card_type's enum must BE the catalogue, with
                                 every type carrying its claim

Both asserted that the agent should CHOOSE a component well. Zac ruled it should
not choose at all: the agent says a beat carries a claim worth stamping, and the
harness derives WHICH component from what the claim contains — the zoom_arc
contract, where the agent names the moment and ZOOM_ARC_HOMES names the move.

So the enum is gone, the prop table the agent read is gone, and the two smokes
above assert a schema that no longer exists. They are INVERTED here rather than
deleted, because the reason they existed is the finding:

    round 39   a claim line for all 29 in the cached prefix   1 distinct of 29
    round 41   the prop shape for 25 of them                  1 distinct of 29
    round 42   zoom picked 3 distinct in the SAME round on the SAME prefix

Making the choice easier failed twice. Removing the choice is what was left.

WHAT THIS FILE NOW ASSERTS: that neither surface came back.
"""
import json
import sys
import types

_m = types.ModuleType("modal")


class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f


for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True
_m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


_schema = json.dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
check("the 29-name enum has NOT come back", '"card_type"' not in _schema,
      "offering 29 bare names produced 1 distinct of 29 for five rounds")
check("the prop table the agent read has NOT come back",
      '"card_props"' not in _schema,
      "the agent cannot supply a component's props when it does not pick the "
      "component")
check("the agent still names the PHRASE worth stamping", '"card_hero"' in _schema,
      "that judgement cannot be derived — it is the zoom_arc half")
check("the derivation exists", callable(getattr(A, "derive_card_type", None))
      and callable(getattr(A, "derive_card_props", None)))

# THE CATALOGUE ITSELF IS NOT RETIRED — only the agent's pick from it. The
# components, their claims and their prop shapes all still drive the harness,
# and a check that let those rot would be the wrong lesson from this.
check("the selectable catalogue still exists",
      len(A.MG_SELECTABLE_TYPES) == 29, str(len(A.MG_SELECTABLE_TYPES)))
# THE CLAIM INDEX IS RETIRED, not merely unused. It parsed the catalogue at
# IMPORT to feed the card_type enum description; b13730c retired that enum and
# the table kept running with zero readers. Asserting it still exists would have
# been this smoke keeping a dead thing alive — the check as the only consumer,
# which is circular and was exactly the situation the wiring audit found.
check("the claim index is GONE, not kept alive by its own check",
      not hasattr(A, "MG_CLAIM_INDEX") and not hasattr(A, "MG_CLAIM_LINES"),
      "a table whose only reader is the check asserting it exists is not wired")
check("and the invariant it carried moved to the cert",
      "Claim line in the catalogue" in
      __import__("pathlib").Path("cert_mg_prop_keys.py").read_text(),
      "the catalogue must still document every selectable type — that is real "
      "and belongs in a cert, off the import path")
check("the prop table still covers what it can derive",
      set(A.MG_PROP_KEYS) | set(A.MG_PROPS_UNDERIVABLE) == set(A.MG_SELECTABLE_TYPES))

if fails:
    print(f"CARD-CHOICE-RETIRED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("CARD-CHOICE-RETIRED: PASS — the enum and the agent-facing prop table are "
      "gone; the catalogue, claims and prop shapes remain for the harness")
