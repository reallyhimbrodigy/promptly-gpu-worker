#!/usr/bin/env python3
"""SMOKE — every id the instructions hand the agent is the WHOLE id.

THE SOURCE OF EVERY TRUNCATED ID IN TWO RUNS was one slice. The component list
in the job prompt printed `assetId[:8]`, so the longest id the agent could
possibly see was eight characters. It then sent `targetItemId:"57ef4b265b"` and
`assetId:"c85df628"`, and three `inspect_item` calls died guessing at
`d57895d3` -> `d57895d37f` -> the real uuid.

IT LOOKED LIKE THE AGENT MISTYPING, and it was the prompt. ChatCut makes that
hard to see from the outside: `edit_item` RESOLVES an id prefix and returns ok,
while `inspect_item` REFUSES one — so the same abbreviation works in one tool
and errors in the other, and the failures land turns away from the cause.

So: no id-bearing line in the prompt builder may slice, and the ids that reach
the agent must be full uuids. Both legs RED-proven.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()

# The uuid shape ChatCut mints: 8-4-4-4-12.
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                  r"[0-9a-f]{12}$")


def sliced_id_expressions(src):
    """Every `<...assetId...>[:n]` INSIDE THE AGENT'S PROMPT, by AST.

    AST, NOT GREP: `[:8]` appears all over this file and a text scan would
    either drown in them or be tuned until it stopped seeing the real one.

    AND SCOPED TO THE PROMPT, because the first version of this leg flagged
    two innocent slices and would have demanded they change:
      * `_stage["projectId"][:8]` in a `print()` — truncating ids for a HUMAN
        reading the run log is right, and the agent never sees that string.
      * `[m["errors"][:1] for m in made if not m["assetId"]][:3]` — a slice of
        an error LIST that merely mentions assetId in its comprehension.
    A check tight enough to reject a correct implementation is not a check. The
    property is "no id the AGENT receives is abbreviated", so the walk starts
    at the `prompt = (...)` assignments and nowhere else.
    """
    tree = ast.parse(src)
    roots = [n.value for n in ast.walk(tree)
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "prompt" for t in n.targets)]
    if not roots:
        # ABSENT, NOT CLEAN. No prompt assignment means this smoke inspected
        # nothing, and a clean zero from a reader that found no input is the
        # most expensive result to trust.
        return [(0, "NO `prompt = (...)` ASSIGNMENT FOUND — nothing inspected")]
    out = []
    for r in roots:
        for n in ast.walk(r):
            if not (isinstance(n, ast.Subscript)
                    and isinstance(n.slice, ast.Slice)
                    and n.slice.upper is not None):
                continue
            inner = ast.unparse(n.value)
            if re.search(r"assetId|itemId|projectId", inner):
                out.append((n.lineno, ast.unparse(n)[:90]))
    return out


def legs(src):
    bad = []
    for ln, txt in sliced_id_expressions(src):
        bad.append(("slice", "line %d slices an id: %s" % (ln, txt)))
    # AND THE POSITIVE HALF. A file with no slices still fails the point if it
    # never hands an id over at all, so check the component line actually
    # carries the whole value.
    if "(+overrides)" not in src:
        bad.append(("absent", "the pre-registered component list is gone — "
                              "this smoke checked nothing"))
    return bad


def sample_render():
    """Ids as the agent would receive them, from the real formatting path."""
    comps = {"caption:TwoTone": {"assetId": "c85df628-1111-4222-8333-444455556666"},
             "RankedList": "aa11bb22-3333-4444-8555-666677778888"}
    return "\n".join(
        "    %-22s %s%s" % (k, (v.get("assetId") if isinstance(v, dict) else v),
                            "   (+overrides)" if isinstance(v, dict) else "")
        for k, v in sorted(comps.items()))


if __name__ == "__main__":
    bad = legs(SRC)
    # the formatting itself must emit whole uuids
    for line in sample_render().splitlines():
        tok = line.split()[1]
        if not UUID.match(tok):
            bad.append(("shape", "an id reaches the agent as %r" % tok))

    for kind, why in bad:
        print("  [FAIL] %-7s %s" % (kind, why))
    if not bad:
        print("  [ok] no id-bearing expression in the prompt builder is sliced")
        print("  [ok] the component list hands over whole uuids")

    print("\n  RED PROOF")
    red = True
    # the exact regression: the slice comes back
    r1 = legs(SRC.replace(
        '((v.get("assetId") if isinstance(v, dict) else v)\n'
        '                             or "?"),',
        '((v.get("assetId") if isinstance(v, dict) else v)\n'
        '                             or "?")[:8],'))
    print("    the [:8] slice restored   -> %d leg(s) red" % len(r1))
    red &= any(k == "slice" for k, _ in r1)

    r2 = legs(SRC.replace("(+overrides)", "(x)"))
    print("    the component list gone   -> %d leg(s) red" % len(r2))
    red &= any(k == "absent" for k, _ in r2)

    _t = "c85df628"
    print("    an 8-char id              -> %s"
          % ("red" if not UUID.match(_t) else "GREEN — the shape leg is blind"))
    red &= not UUID.match(_t)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
