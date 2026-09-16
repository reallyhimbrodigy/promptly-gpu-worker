#!/usr/bin/env python3
"""Every family the planner can RULE, the translator can BUILD. And every one
of them gets acceptance criteria of its OWN KIND.

THE MEASUREMENT THIS EXISTS FOR, 2026-09-16. Closing the mode flip made runs
produce full edits for the first time, and all three replicates were then
REFUSED at the translator:

    rep 1  Unmapped: cutaway
    rep 2  Unmapped: transition
    rep 3  Unmapped: cutaway

    planner can RULE        card cutaway none sfx text transition zoom
    translator VERIFIED     caption card cut sfx text zoom
    RULABLE BUT UNBUILDABLE cutaway, transition

The empty plans had been the only ones getting through, because a
targeted_change scoped to cut+caption contains nothing the translator cannot
express. A capability in the schema will be used; a refused plan is a wasted
run. Both families are now verified against a live timeline.

THE LEGS:
  1. rulable ⊆ buildable. A family the planner offers and the translator
     refuses is a run that dies at the boundary every time it is reached for.
  2. every buildable family has an EMITTER — verified with nothing writing it
     is the same mismatch one step along, and the reconciliation gate is what
     caught that.
  3. every family's acceptance criteria are of ITS OWN KIND. A cutaway asked
     "is it legible" and a transition asked "is it clear of the face" is the
     text-shaped check applied to everything — the defect that already had to
     be fixed once in the completeness gate.
  4. a family with content that is not derivable declares it, so a half-ruling
     is refused where it is made.

RED-proven at the bottom.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402
import plan_for_chatcut as T                                     # noqa: E402

PLAN_SRC = open(os.path.join(HERE, "plan_for_chatcut.py"), encoding="utf-8").read()
fail = []


def bad(m):
    fail.append(m)


# ── 1. RULABLE ⊆ BUILDABLE ──────────────────────────────────────────────────
rulable = {str(f).lower() for f in (getattr(A, "_TREATMENT_FAMILIES", []) or [])}
rulable.discard("none")          # `none` is the absence of a placement
buildable = {k for k, v in T.FAMILY_MAP.items() if v.get("verified")}
if not rulable:
    bad("[population] the planner's family list is empty — this leg would "
        "pass on a planner that can rule nothing")
gap = sorted(rulable - buildable)
if gap:
    bad("[rulable] the planner can rule %s and the translator cannot build "
        "them — every plan reaching for one is refused at the boundary" % gap)

# ── 2. EVERY BUILDABLE FAMILY HAS AN EMITTER ────────────────────────────────
# Asked of the SOURCE: a family is emitted if something increments its counter
# in the reconciliation ledger. `verified` with nothing writing it is what the
# reconciliation gate caught as "THESE RULINGS DO NOT REACH THE PLAN".
def _emitters(src):
    """Families the plan writes — LITERAL and LOOP-VARIABLE forms both.

    `text` and `card` are incremented as `_emitted[_t]` inside
    `for _t in ("text", "card")`. A regex for the literal form reported both
    as unwritten, which is the grep-cannot-see-the-AST trap in the check
    written to catch a producer with no consumer.
    """
    found = set(re.findall(r'_emitted\[[\'"](\w+)[\'"]\]', src))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return found
    for n in ast.walk(tree):
        if not isinstance(n, ast.For) or not isinstance(n.target, ast.Name):
            continue
        var = n.target.id
        try:
            names = [x for x in ast.literal_eval(n.iter)
                     if isinstance(x, str)]
        except Exception:                                         # noqa: BLE001
            continue
        body = ast.unparse(n)
        if re.search(r'_emitted\[%s\]' % re.escape(var), body):
            found |= set(names)
    return found


emitted = _emitters(PLAN_SRC)
for f in sorted(buildable - {"cut"}):        # `cut` is the spans, not an add
    if f not in emitted:
        bad("[emitter] %r is verified and nothing in the plan writes it" % f)

# ── 3. ACCEPTANCE CRITERIA OF ITS OWN KIND ──────────────────────────────────
# Each family that reaches the acceptance block must contribute at least one
# criterion line that is NOT the text one.
_i = PLAN_SRC.find("WHAT WRONG LOOKS LIKE, PER FAMILY")
_blk = PLAN_SRC[_i:_i + 4200] if _i >= 0 else ""
if not _blk:
    bad("[criteria] there is no per-family acceptance block")
else:
    for kind, needle in (("CUTAWAY", "covers, not replaces"),
                         ("TRANSITION", "has a seam"),
                         ("SFX", "audible"),
                         ("ZOOM", "moves")):
        if kind not in _blk or needle not in _blk:
            bad("[criteria] %s has no criterion of its own kind (%r)"
                % (kind, needle))
    # and the LAYER questions must not be asked of the families that have no
    # layer — the defect this leg is named after
    if "_ON_A_LAYER" not in PLAN_SRC:
        bad("[criteria] the face/collision lines are not restricted to "
            "families that sit on a layer — a transition asked whether it is "
            "clear of the speaker's face is the text-shaped check again")

# ── 4. NON-DERIVABLE CONTENT IS DEMANDED AT RULING TIME ─────────────────────
# sfx -> sfx_name, card -> card_hero, transition -> transition_name. Each is a
# choice no downstream step can make for the agent.
_spec = ""
for _t in getattr(A, "KNOWLEDGE_TOOLS", []):
    if _t.get("name") == "rule_all_beats":
        _spec = str(_t)
for fam, field in (("sfx", "sfx_name"), ("card", "card_hero"),
                   ("transition", "transition_name")):
    if fam in buildable and field not in _spec:
        bad("[halfruling] %r is buildable but %r is not in the ruling schema — "
            "the agent can rule the family and never say which" % (fam, field))

# ── 5. A CONTROL IS TALLIED ONLY ACROSS FAMILIES THAT HAVE IT ───────────────
# THIRD INSTANCE of the family-blind shape, and the quiet one: it refuses
# nothing. `used_so_far` counted `case`/`size`/`where` across EVERY verdict, so
# a run placing a cutaway, a transition and a sound reported
#     case: (not set) x3, upper x2
# — "(not set)" the majority, in the report built to make repetition visible,
# while every text placement in that edit was `upper`. Degrading a signal in
# the direction that hides what it exists to show.
#
# Driven by BEHAVIOUR on the shipped function, not by reading the source.
_MIXED = [{"beat": 0, "treatment": ["text"], "size": "large",
           "case": "upper", "where": "upper_third"},
          {"beat": 1, "treatment": ["text"], "size": "large",
           "case": "upper", "where": "upper_third"},
          {"beat": 2, "treatment": ["cutaway"], "cutaway_from_s": 3.0},
          {"beat": 3, "treatment": ["transition"], "transition_name": "flash"},
          {"beat": 4, "treatment": ["sfx"], "sfx_name": "boom"}]
_st, _txt = A.used_so_far(_MIXED)
if _st != "MEASURED":
    bad("[tally] used_so_far returned %r on five real verdicts" % _st)
else:
    if "(not set)" in _txt:
        bad("[tally] a control is counted across families that do not have "
            "it — %r. The families are in the same report, so the reader "
            "cannot tell an unset control from a family that has none."
            % _txt[_txt.find("case:"):][:80])
    # and the families themselves MUST still all be counted
    for _f in ("cutaway", "transition", "sfx"):
        if _f not in _txt:
            bad("[tally] %r vanished from the families line — restricting the "
                "CONTROL tallies must not drop the family count" % _f)
    if "upper x2" not in _txt:
        bad("[tally] the text placements' own case is no longer reported: %r"
            % _txt[:120])

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("a family goes back to unverified", "rulable",
     lambda s: s.replace('"cutaway": {\n        "item_kind": "video-item",\n'
                         '        "verified": True,',
                         '"cutaway": {\n        "item_kind": "video-item",\n'
                         '        "verified": False,')),
    ("the cutaway emitter is removed", "emitter",
     lambda s: s.replace('_emitted["cutaway"] = _emitted.get("cutaway", 0) + 1',
                         'pass')),
    # RENAME EVERY OCCURRENCE. Renaming only the assignment left the name in
    # its own use sites, so the leg's substring test stayed satisfied — the
    # mutation changed the file and not the property, which is the vacuous
    # mutation this repo has a precondition rule for.
    ("the layer restriction is removed", "criteria",
     lambda s: s.replace("_ON_A_LAYER", "_OTHER_NAME")),
)


def legs_on(plan_src):
    """Re-run legs 1-3 against a mutated plan_for_chatcut source."""
    out = []
    ns = {}
    try:
        exec(compile(plan_src, "<mutant>", "exec"), ns)
    except Exception as e:                                        # noqa: BLE001
        return [("import", str(e)[:80])]
    _bld = {k for k, v in (ns.get("FAMILY_MAP") or {}).items()
            if v.get("verified")}
    if sorted(rulable - _bld):
        out.append(("rulable", "gap"))
    _em = _emitters(plan_src)
    for f in sorted(_bld - {"cut"}):
        if f not in _em:
            out.append(("emitter", f))
    if "_ON_A_LAYER" not in plan_src:
        out.append(("criteria", "layer restriction gone"))
    return out


for label, kind, mut in MUT:
    m = mut(PLAN_SRC)
    if m == PLAN_SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    hit = any(k == kind for k, _ in legs_on(m))
    print("    %-38s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

for m in fail:
    print("  *** " + m)
print("\nsmoke_nothing_rulable_is_unbuildable: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red) else 0)
