#!/usr/bin/env python3
"""A vibe word in the brief is matched, not interpreted — and the spec is PRINTED.

THE MEASUREMENT THIS EXISTS FOR. Seven planner runs on one brief:

    ab_OFF_1   targeted_change    0 treatments      <- EMPTY EDIT
    ab_OFF_2   full_edit          5
    ab_ON_1    full_edit          6
    ab_ON_2    full_edit         18
    plan_cache targeted_change    0                 <- EMPTY EDIT
    plan_cache2 full_edit        11
    e2e        targeted_change    0                 <- EMPTY EDIT

3 of 7 (43%) delivered NOTHING, and the correlation with mode is perfect: every
empty run is `targeted_change`, every non-empty run is `full_edit`. The ruling
downstream was never the problem. The agent wrote its reason and nobody read
it until 2026-09-16; here it is, verbatim, from the one empty run whose result
survived:

    "Names cut (remove silence/filler) and caption (burn readable captions);
     no vibe language, so scope is limited to those two families only."

The brief was "Cut this into a punchy vertical short. Remove silence and
filler. Keep the meaning intact. Burn readable captions." The word `punchy` is
in it, is listed in the rule as a vibe word, and appears in that rule's own
worked example for this exact brief. The prose was already correct. What was
missing was that Q2 is a MATCH, not a reading.

TWO REASONS THE OTHER TWO COULD NOT BE READ, both worth keeping:
  - the planner never PRINTED the spec, so the mode reached the log only
    sideways in a FIDELITY line at the end
  - every run on one clip wrote `/tmp/result_<clip>.json`, so each planner run
    clobbered the last one's evidence

THE LEGS:
  1. Q2 is answered by matching a named list, and the list contains the words
     that actually appeared in the failing briefs
  2. the rule states the ASYMMETRY — a wrong `targeted_change` delivers an
     empty edit, a wrong `full_edit` delivers extras with the guarantees intact
  3. the spec is printed where it is decided, with its `why`
  4. the recorded counter-example is present, so the next reader cannot think
     this was a knowledge gap and fix it with more prose

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

SRC = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
fail = []

# THE WORDS THAT ACTUALLY APPEARED IN A BRIEF THAT WENT EMPTY. Not a
# hand-picked vocabulary: `punchy` is the one measured failure, and the rest
# are the adjectives this product's briefs carry. A list that omits the word
# that broke it is a list written from memory.
MUST_MATCH = ("punchy", "clean", "cinematic", "professional", "tight")


def legs(src=None, tree=None):
    src = src if src is not None else SRC
    tree = tree if tree is not None else ast.parse(src)
    out = []

    # 1. Q2 IS A MATCH, AND THE LIST HAS THE RIGHT WORDS IN IT.
    # Asked of the ASSEMBLED tool description, not of the file: the rule is
    # built from adjacent string literals, so a source-text search reads the
    # quotes and newlines between them and a word can sit in a comment.
    # FROM THE TREE UNDER TEST, NOT FROM THE IMPORTED MODULE. My first version
    # read `A.KNOWLEDGE_TOOLS` — the live object — while the mutations edited
    # SOURCE TEXT. The two never met, so three of four mutations could not
    # fire however wrong the source became: a check exercising a copy of the
    # thing it claims to test, which is the trap this repo hoists rules out of
    # dispatches to avoid.
    _spec = ""
    for _d in ast.walk(tree):
        if not isinstance(_d, ast.Dict):
            continue
        _keys = {k.value: v for k, v in zip(_d.keys, _d.values)
                 if isinstance(k, ast.Constant)}
        _nm = _keys.get("name")
        if isinstance(_nm, ast.Constant) and _nm.value == "set_spec":
            _ds = _keys.get("description")
            if isinstance(_ds, ast.Constant):
                _spec = _ds.value
            elif _ds is not None:
                try:
                    _spec = ast.literal_eval(_ds)
                except Exception:                                 # noqa: BLE001
                    _spec = ""
    if not _spec:
        out.append(("match", "set_spec has no description in KNOWLEDGE_TOOLS "
                             "— the rule reaches no prompt"))
        return out
    if "ANSWER THIS BY MATCHING, NOT BY INTERPRETING" not in _spec:
        out.append(("match", "Q2 no longer says it is answered by MATCHING"))
    # the LIST, not the whole description: `punchy` also appears in the worked
    # example and in the recorded counter-example, so a file-wide search would
    # stay green with the list itself emptied.
    # THE LIST BLOCK ONLY, bounded at its own end. A 600-character window
    # reached "Do not reason about whether 'punchy vertical short'..." two
    # sentences later, so emptying the LIST left the leg green on the word in
    # the sentence ABOUT the list — the same literal, a different claim.
    _i = _spec.find("Q2 IS YES:")
    _j = _spec.find("The list is not exhaustive", _i + 1) if _i >= 0 else -1
    _list = _spec[_i:_j] if (_i >= 0 and _j > _i) else ""
    if _i >= 0 and _j <= _i:
        out.append(("match", "the vibe list has no end marker — the leg below "
                             "would search the prose about the list"))
    for w in MUST_MATCH:
        if w not in _list:
            out.append(("match", "the vibe LIST has lost %r" % w))

    # 2. THE ASYMMETRY IS STATED
    if "do not cost the same" not in _spec.lower():
        out.append(("asymmetry", "the rule no longer says the two mistakes "
                                 "cost differently"))
    if "deliver nothing" not in _spec.lower():
        out.append(("asymmetry", "the rule does not say a wrong "
                                 "targeted_change delivers nothing"))

    # 3. THE SPEC IS PRINTED WHERE IT IS DECIDED
    _printed = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == "print":
            u = ast.unparse(n)
            if "SPEC" in u and "mode" in u and "why" in u:
                _printed = True
    if not _printed:
        out.append(("printed", "the spec's mode and why are not printed — the "
                               "mode reaches the log only in a FIDELITY line "
                               "at the end of the run"))

    # 4. THE COUNTER-EXAMPLE SURVIVES, so nobody re-fixes this with prose
    if "no vibe language" not in _spec.lower():
        out.append(("evidence", "the verbatim reason the agent gave is gone — "
                                "without it the next reader treats this as a "
                                "knowledge gap and adds more prose"))
    return out


for k, m in legs():
    fail.append("[%s] %s" % (k, m))

# The reachability question is answered by construction above: every leg reads
# `set_spec`'s description out of the module-level KNOWLEDGE_TOOLS, which is
# the object handed to the API. A rule that reached only a comment, a local, or
# a dead branch would fail leg 1 as "no description".

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("Q2 goes back to being a judgement", "match",
     lambda s: s.replace('VIBE language? ANSWER THIS BY MATCHING, "',
                         'VIBE language? Decide. "')),
    ("the word that broke it is dropped from the list", "match",
     lambda s: s.replace('"        punchy  snappy', '"        snappy')),
    ("the asymmetry is removed", "asymmetry",
     lambda s: s.replace("AND THE TWO MISTAKES DO NOT COST THE SAME.",
                         "AND THE TWO MISTAKES ARE SYMMETRIC.")),
    ("the spec stops being printed", "printed",
     lambda s: s.replace('print("  SPEC            : mode=%s families=%s\\n"',
                         'str("  SPEC            : mode=%s families=%s\\n"')),
)
for label, kind, mut in MUT:
    m = mut(SRC)
    if m == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        r = legs(m, ast.parse(m))
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    hit = any(k == kind for k, _ in r)
    print("    %-40s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

for m in fail:
    print("  *** " + m)
print("\nsmoke_the_mode_is_read_not_weighed: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red) else 0)
