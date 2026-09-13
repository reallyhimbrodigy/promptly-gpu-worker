#!/usr/bin/env python3
"""The exemplars are indexed by PURPOSE, and purpose is a required ruling.

WHY. The old block matched our beats to reference beats BY DURATION. Measured:
a 7-beat fixture and a 36-beat fixture produced a byte-identical block (sha
e0237dcb69) — with 39 index beats and k=3 nearest-by-duration the same handful
always won. It was never per-beat retrieval; it was a fixed block chosen by the
weakest available key. Duration is not a craft signal. A beat is a hook or a
claim or a payoff, and that is what an editor answers.

THE ORDERING PROBLEM. Retrieval runs when the brief is built, before the agent
rules, so OUR purpose does not exist yet. Indexing by purpose needs none: the
block shows what each of the seven looks like and the agent names its beat's
purpose while ruling. This file asserts the block does NOT depend on our beats,
which is the property that makes that true.

RED-proven by red_proof_purpose_join.py.
"""
import ast
import hashlib
import json
import os
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


# ── DRIVE THE REAL MODULE, NOT AN AST REPLICA ───────────────────────────────
# This used to rebuild the module by exec'ing its top-level nodes into a bare
# namespace, one at a time, swallowing every failure. That is a SECOND LOADER
# with no relationship to the one the container uses: a literal that calls a
# helper defined further down (KNOWLEDGE_TOOLS needs FAMILY_CORPUS_CRAFT, which
# is a call) raised on the one pass it got, was swallowed, and the function
# under test then died with `NameError: KNOWLEDGE_TOOLS` from INSIDE the
# subject — a missing fixture reported as a defect in the code being tested.
# Iterating the replica to a fixpoint patches the symptom and keeps the second
# loader. Importing removes it, and is what "exercise the shipped path" means.
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as _APP                                 # noqa: E402
_ns = vars(_APP)
check("the tool schemas are bound — without them `_rulable_treatments` dies "
      "with a NameError inside the subject and a missing FIXTURE reads as a "
      "defect in the code under test",
      bool(_ns.get("KNOWLEDGE_TOOLS")) and bool(_ns.get("TOOLS")))

check("the block function is drivable", "_reference_block" in _ns)
if "_reference_block" not in _ns:
    print("\nPURPOSE-JOIN: FAIL"); sys.exit(1)
_blk = _ns["_reference_block"]
_PURPOSES = _ns.get("BEAT_PURPOSES", ())
check("the seven-value vocabulary is a named constant",
      len(_PURPOSES) == 7 and "hook" in _PURPOSES and "payoff" in _PURPOSES,
      f"{_PURPOSES}")

# ── THE PROPERTY THAT DISSOLVES THE ORDERING PROBLEM ────────────────────────
_a = _blk([{"i": 0, "t_start": 0.0, "t_end": 3.0}])
_b2 = _blk([{"i": i, "t_start": i * 0.7, "t_end": i * 0.7 + 0.7} for i in range(36)])
_c = _blk([])
check("the block does NOT depend on our beats",
      _a == _b2 == _c,
      "if it varies with our beats it needs a key we do not have at brief time, "
      "which is the ordering problem it exists to dissolve")
check("and that is a CHANGE — the old block did vary with duration profile",
      hashlib.sha1(_a.encode()).hexdigest()[:10] != "e0237dcb69",
      "the measured hash of the duration-joined block")

# ── every purpose is present and labelled ───────────────────────────────────
for _p in _PURPOSES:
    check(f"{_p} has a section", _p.upper() in _a, _a[:120])
check("each section names how many the corpus holds",
      _a.count("in corpus") + _a.count("carry this purpose") >= 5,
      "a count is what makes 'thin' distinguishable from 'absent'")
check("the editor's READ is carried, not just the treatment",
      len([l for l in _a.split("\n") if l.startswith("  ") and len(l) > 60]) >= 7,
      "the read is the whole value of the corpus")

# ── absence is spoken, in all four places ───────────────────────────────────
_BLKDEF = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == "_reference_block")


def _blk_with(**over):
    """The shipped function re-bound against a patched namespace, so the absence
    paths are DRIVEN rather than asserted from the source text."""
    _n2 = dict(_ns)
    _n2.update(over)
    exec(compile(ast.Module(body=[_BLKDEF], type_ignores=[]), "<c>", "exec"), _n2)
    return _n2["_reference_block"]


check("a removed block says it was REMOVED, not absent",
      "REMOVED for this run"
      in _blk_with(prefix_material_enabled=lambda n: False)([]))
check("an unreadable index says so",
      "NONE AVAILABLE"
      in _blk_with(load_reference_index=lambda *a, **k: ([], {"why": "x"}))([]))
# THE STUB IS DERIVED FROM THE LIVE INDEX, NOT A LIST OF CORPUS NAMES. This
# hardcoded {"overlay_text","cut","card","punch_in","sfx"} — the SIX-WORD
# corpus's vocabulary — to force the "everything here is unbuildable" branch.
# Against an open-vocabulary index those names appear nowhere, so the filter
# removed nothing, a pool survived, and the branch under test never ran. The
# leg did not catch a regression; it stopped being able to reach its own
# subject. Make the stub say "every treatment this corpus actually contains is
# unbuildable" and it reaches the branch whatever the vocabulary is.
# READ THE SHIPPED INDEX FILE DIRECTLY. This smoke deliberately never imports
# the module — it execs one compiled block against a stub namespace — so it has
# no load_reference_index to call.
_all_treats = {_t for _x in (json.loads(
                   pathlib.Path("reference_index.json").read_text()
               ).get("beats") or [])
               for _t in (_x.get("treat") or [])}
check("the unbuildable stub covers the shipped vocabulary (non-vacuity)",
      bool(_all_treats),
      "the index carries no treatments at all, so the leg below cannot reach "
      "the branch it tests")
# THE BRANCH IS DRIVEN DIRECTLY, because the corpus can no longer reach it
# through the unbuildable stub alone. The filter is
# `not (_unbuildable & set(beat["treat"]))`, and a BARE beat has an empty treat
# set — so it survives any filter, correctly: an editor holding is a buildable
# example. The merged corpus carries 38 bare beats where the six-word corpus
# carried ZERO (captions were recorded as a treatment on every beat), so the
# stub that used to empty every pool now cannot empty any.
#
# That is the corpus improving, not the check failing. Supply an index whose
# beats ALL carry an unbuildable treatment, and the branch is reachable again
# whatever the real corpus looks like.
_UNB = "__unbuildable_family__"
_fake = [{"i": _i, "purpose": _p, "dur": 2.0, "treat": [_UNB],
          "spk": True, "card_text": None, "read": "x"}
         for _i, _p in enumerate(_PURPOSES)]
check("a purpose with no BUILDABLE example says how many carry it",
      "no buildable example" in _blk_with(
          load_reference_index=lambda *a, **k: (_fake, {"state": "COMPLETE",
                                                        "beats_in_corpus": len(_fake),
                                                        "builds_as": {},
                                                        "vocabulary": [_UNB],
                                                        "why": ""}),
          reference_unbuildable=lambda *a, **k: {_UNB})([]),
      "a header with nothing under it reads as 'editors place nothing here' — "
      "a judgement the corpus never made")

# ── purpose is REQUIRED on both ruling surfaces ─────────────────────────────
_reqs = []
for _n in ast.walk(tree):
    if isinstance(_n, ast.Dict):
        for _k, _v in zip(_n.keys, _n.values):
            if isinstance(_k, ast.Constant) and _k.value == "required" \
                    and isinstance(_v, ast.List):
                _vals = [c.value for c in _v.elts if isinstance(c, ast.Constant)]
                if "treatment" in _vals:
                    _reqs.append(_vals)
check(f"both ruling surfaces were found ({len(_reqs)}) — non-vacuity",
      len(_reqs) == 2, f"{_reqs}")
check("purpose is REQUIRED on every ruling surface",
      all("purpose" in r for r in _reqs), f"{_reqs}",)
# ── TWO AXES, NOT TWO NAMES FOR ONE ─────────────────────────────────────────
# `zoom_arc` ALREADY asked "what this moment IS in the arc" with six values
# (hook build mid_peak payoff breather close) and ZOOM_ARC_HOMES maps each to
# its components. I added `purpose` beside it with seven. They share hook,
# payoff and close. That is the two-names-one-thing class and I introduced it —
# so the vocabularies must be DECLARED distinct and their overlap must be
# CHECKED, not trusted to prose.
_pay = [[c.value for c in v.elts if isinstance(c, ast.Constant)]
        for n in ast.walk(tree) if isinstance(n, ast.Dict)
        for k, v in zip(n.keys, n.values)
        if isinstance(k, ast.Constant) and k.value == "enum"
        and isinstance(v, ast.List)
        and any(getattr(c, "value", "") == "payoff" for c in v.elts)]
_purpose_enums = [e for e in _pay if sorted(e) == sorted(_PURPOSES)]
_arc_enums = [e for e in _pay if sorted(e) != sorted(_PURPOSES)]
check(f"the purpose enum appears on BOTH ruling surfaces ({len(_purpose_enums)})",
      len(_purpose_enums) == 2, f"{_purpose_enums}")
_ARC = ["hook", "build", "mid_peak", "payoff", "breather", "close"]
check(f"the zoom_arc vocabulary is still its own, on every surface it appears ({len(_arc_enums)})",
      bool(_arc_enums) and all(e == _ARC for e in _arc_enums), f"{_arc_enums}")
_shared = set(_PURPOSES) & set(_arc_enums[0] if _arc_enums else [])
check("the two vocabularies overlap on exactly hook/payoff/close",
      _shared == {"hook", "payoff", "close"}, f"{sorted(_shared)}")
check("purpose declares it is FUNCTION, not the arc",
      "NOT THE SAME AXIS AS `zoom_arc`" in src)
check("zoom_arc declares it is ENERGY POSITION, not function",
      "ENERGY POSITION, not " in src)
check("and the overlap is CHECKED at runtime, not merely described",
      'led["axis_incoherent"]' in src and 'fail("axis_incoherent"' in src,
      "a beat ruled purpose=hook and zoom_arc=close would send the reference "
      "join and the zoom lookup to opposite ends of the video")

# ── the distribution is PRINTED, not just ledgered ──────────────────────────
check("the purpose distribution reaches the ledger",
      'led["purpose_distribution"]' in src)
check("and is PRINTED — a counter that reaches only the ledger answers nothing",
      "PURPOSE MIX" in src)
check("a dominant purpose is flagged as possible decoration",
      "_share >= 0.9" in src,
      "the first registered failure mode: a vocabulary that does not "
      "discriminate makes the join confident and meaningless")
check("an unnamed purpose fails loudly", 'fail("purpose_unnamed"' in src)

# ── THE GATE MUST NOT REJECT ON PURPOSE, and this is a regression guard for a
# failure that cost THREE ROUNDS OF ZERO CARDS. The acceptance gate once
# demanded `card_type` after the schema stopped offering it: the agent could not
# satisfy it, was rejected, re-ruled, and burned five turns placing nothing.
#
# `purpose` is REQUIRED IN THE SCHEMA — so the model supplies it — and must NOT
# be a rejection condition in the harness. A miss is reported loudly at the end
# instead. Marking a field required and ALSO rejecting on it is how a loop
# starts, and the two look identical in a diff.
# BOUNDED BY THE FUNCTION, not by a line window. The gate used to be inline in
# `edit` — 3,000 lines — so this sliced the source between two literals that
# happened to bracket it. It is now `half_ruling_refusal`, a named pure
# function, so the bound is exact and cannot drift when the code around it
# moves. (It moved: that slice broke the moment the gate was extracted, which
# is the check working.)
_hrr = next((n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)
             and n.name == "half_ruling_refusal"), None)
if _hrr is None:
    print("PURPOSE-JOIN: FAIL\n  - half_ruling_refusal not found; the "
          "acceptance gate cannot be bounded")
    sys.exit(1)
_gate = ast.get_source_segment(src, _hrr) or ""
# ASKED OF THE FIELDS THE GATE READS, not of its source text. The text form
# failed the moment the gate got a docstring that NAMES purpose as one of the
# fields the other ruling surface used to drop — prose about a field read as a
# demand for it. The property is that the gate does not READ purpose.
_gate_reads = {_n.args[0].value for _n in ast.walk(_hrr)
               if isinstance(_n, ast.Call)
               and getattr(_n.func, "attr", "") == "get"
               and getattr(getattr(_n.func, "value", None), "id", "") == "v"
               and _n.args and isinstance(_n.args[0], ast.Constant)
               and isinstance(_n.args[0].value, str)}
check("the acceptance gate does NOT reject a verdict for a missing purpose",
      "purpose" not in _gate_reads,
      "requiring a field in the schema AND rejecting on it in the harness is "
      "the orphaned-gate loop: three rounds built zero cards that way")
check("the gate still rejects on zoom_arc, so this leg is not vacuous",
      "zoom_arc" in _gate_reads,
      "if the gate stopped rejecting anything, the leg above would pass for "
      "the wrong reason")

print()
if fails:
    print("PURPOSE-JOIN: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"PURPOSE-JOIN: PASS — {len(_PURPOSES)} purposes indexed, block "
      f"independent of our beats, required on both surfaces, distribution "
      f"printed with the dominance flag")
