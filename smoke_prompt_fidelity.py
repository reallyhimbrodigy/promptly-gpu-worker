#!/usr/bin/env python3
"""Did the output contain what was asked, and NOTHING THAT WAS NOT?

THE REQUIREMENT. The user's prompt is the source of truth. "Just add captions"
gets captions and nothing else; "make it viral" gets the full treatment; "cut
the bit where I stumble" gets exactly that. A BRIEF THAT ASKS FOR LITTLE MUST
PRODUCE LITTLE — placing more than was asked is a failure, not generosity. It is
the edit the user did not request, delivered over the one they did.

TWO DIRECTIONS, AND ONLY ONE WAS EVER MEASURED. `not_asked_for` recorded
families built outside a targeted scope at build time. Nothing recorded a family
ASKED FOR AND NEVER DELIVERED — an edit that quietly drops the one thing
requested reads as a successful run, and "0 blocks" with no denominator is how
that stays invisible.

FOUR STATES, and UNSCOPED is not a pass:

    FAITHFUL     asked for X, delivered X
    SHORT        asked for X, did not deliver it
    OVERREACHED  delivered Y that was not asked for
    UNSCOPED     the run declared full_edit, so there IS no scope to judge
                 against. That is the ABSENCE of the question, not an answer to
                 it, and it is reported so a minimal brief declared full_edit is
                 visible rather than excused.

RED-proven by red_proof_prompt_fidelity.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "").startswith("FIDELITY_")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name == "spec_fidelity":
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("spec_fidelity is module-level and pure", "spec_fidelity" in _ns)
if "spec_fidelity" not in _ns:
    print("\nPROMPT-FIDELITY: FAIL"); sys.exit(1)
f = _ns["spec_fidelity"]
OK, SHORT, OVER, UNSCOPED = (_ns["FIDELITY_OK"], _ns["FIDELITY_SHORT"],
                             _ns["FIDELITY_OVER"], _ns["FIDELITY_UNSCOPED"])


def _P(*fams):
    return [{"family": x} for x in fams]


T = lambda *f: {"mode": "targeted_change", "families": list(f)}   # noqa: E731

# ── THE REQUIREMENT, CASE BY CASE ───────────────────────────────────────────
check("'just add captions' delivering text only is FAITHFUL",
      f(T("text"), _P("text"))[0] == OK)
check("'just add captions' that also ships zooms has OVERREACHED",
      f(T("text"), _P("text", "zoom"))[:3] == (OVER, [], ["zoom"]),
      f"{f(T('text'), _P('text', 'zoom'))}")
check("and the overreach NAMES what was not asked for",
      "zoom" in f(T("text"), _P("text", "zoom"))[3])
check("'just add captions' delivering nothing is SHORT",
      f(T("text"), _P())[:2] == (SHORT, ["text"]),
      "an edit that drops the one thing requested reads as a successful run")
check("asked two families, delivered a third: both directions reported",
      f(T("text", "sfx"), _P("zoom"))[1:3] == (["sfx", "text"], ["zoom"]),
      f"{f(T('text','sfx'), _P('zoom'))}")

# ── UNSCOPED IS NOT A PASS ──────────────────────────────────────────────────
_u = f({"mode": "full_edit"}, _P("text", "card", "zoom"))
check("a full_edit is UNSCOPED, not FAITHFUL", _u[0] == UNSCOPED, f"{_u[0]}")
check("and it says a minimal brief declared full_edit would be invisible here",
      "full_edit" in _u[3] and "cannot be judged" in _u[3], _u[3])
check("it still reports what WAS placed, so the reader can judge the brief",
      _u[2] == ["card", "text", "zoom"], f"{_u[2]}")

# ── THE CUT COUNTS AS A FAMILY WHEN ONE WAS MADE ────────────────────────────
check("'cut the bit where I stumble' is FAITHFUL when only a cut happened",
      f(T("cut"), _P(), cut_made=True)[0] == OK,
      "a cut leaves no placement, so without this a cut-only request always "
      "reads SHORT")
check("and a cut nobody asked for is an overreach",
      f(T("text"), _P("text"), cut_made=True)[:3] == (OVER, [], ["cut"]))

# ── IT RUNS ON EVERY RUN, AND SAYS SO ───────────────────────────────────────
check("fidelity reaches the ledger", 'led["fidelity"]' in src)
check("and is PRINTED", "FIDELITY        :" in src,
      "a measure that reaches only the ledger answers nothing")
check("SHORT fails loudly", 'fail("fidelity_short"' in src)
check("OVERREACHED fails loudly", 'fail("fidelity_overreached"' in src)
check("it is computed for EVERY run, not only targeted ones",
      src.index("spec_fidelity(") < src.index('led["fidelity"]') + 400
      and 'if _sc2 and _sc2.get("mode") == "targeted_change"' in src,
      "the build-time gate stays scoped to targeted_change; the REPORT is "
      "unconditional, which is how an unscoped run becomes visible")

# ── THE RULE REACHES THE AGENT ──────────────────────────────────────────────
# MATCH THE ASSEMBLED DESCRIPTION, NOT THE RAW SOURCE. The prompt is built from
# adjacent string fragments, so "never because you are unsure" is split across
# two of them and appears NOWHERE contiguously in the file. Grepping the source
# for prompt text asserts something about the LAYOUT of the literal rather than
# about what the agent reads — the third time today a check of mine matched
# rendered text instead of the value.
_spec_desc = ""
for _n2 in ast.walk(tree):
    if isinstance(_n2, ast.Dict):
        _kv = {k.value: v for k, v in zip(_n2.keys, _n2.values)
               if isinstance(k, ast.Constant)}
        if getattr(_kv.get("name"), "value", "") == "set_spec" \
                and "description" in _kv:
            _spec_desc = "".join(
                c.value for c in ast.walk(_kv["description"])
                if isinstance(c, ast.Constant) and isinstance(c.value, str))
check("the set_spec description could be assembled (non-vacuity)",
      len(_spec_desc) > 400, f"{len(_spec_desc)} chars")
check("set_spec tells the agent a small brief must produce a small edit",
      "LITTLE MUST PRODUCE LITTLE" in _spec_desc)
check("and warns that full_edit is how a narrow request escapes scope",
      "never because you are unsure" in _spec_desc,
      "full_edit has no family scope, so nothing downstream can object")

print()
if fails:
    print("PROMPT-FIDELITY: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("PROMPT-FIDELITY: PASS — four states, both directions, cut counted, "
      "reported on every run and failing loudly in each direction")
