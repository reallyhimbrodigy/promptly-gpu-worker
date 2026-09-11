#!/usr/bin/env python3
"""A re-edit modifies what it names and leaves everything else identical.

TWO PROOFS, and the second is the one that catches a plausible-looking failure:

  NO-OP        an instruction naming nothing must return a BYTE-IDENTICAL file.
               Renders are byte-identical on a fixed plan now that the x264
               thread count is pinned, so identical verdicts in means identical
               bytes out. This fails the moment the path re-plans instead of
               modifying.
  NAMED-ONLY   a real instruction must change ONLY the entries it names, and
               every other entry must be UNCHANGED BY ID. A re-edit that looks
               right on screen while silently re-deriving six untouched
               placements is invisible in the video and caught here.

WHAT THIS FILE DRIVES is the shipped merge logic — the load, the allow-list and
the replacement — on synthetic verdicts. It does NOT render: a render is real
traffic and costs Modal spend, so the byte comparison belongs to a watched run,
not to a smoke. What a smoke CAN prove is that identical verdicts survive the
round trip unchanged, which is the precondition for identical bytes; the render
half is the observation that follows.

RED-proven by red_proof_reedit_surgical.py.
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


_ns = {"hashlib": __import__("hashlib")}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_t2, "id", "") in ("PLAN_ORPHAN", "PLAN_UNPLACEABLE",
                                       "VERDICT_FIELDS")
            for t in _n.targets for _t2 in ast.walk(t)):
        try:
            exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
        except Exception:
            pass
    if isinstance(_n, ast.FunctionDef) and _n.name in (
            "plan_anchor_id", "durable_plan", "plan_onto_beats", "reedit_merge"):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
_ns.setdefault("VERDICT_FIELDS", ["beat", "treatment", "cut", "text_content"])
_dp, _po = _ns["durable_plan"], _ns["plan_onto_beats"]

BEATS = [{"i": 0, "t_start": 0.0, "t_end": 4.0},
         {"i": 1, "t_start": 4.0, "t_end": 9.0},
         {"i": 2, "t_start": 9.0, "t_end": 14.0}]
V0 = [{"beat": 0, "treatment": ["text"], "cut": "keep", "text_content": "A"},
      {"beat": 1, "treatment": ["zoom"], "cut": "keep", "text_content": ""},
      {"beat": 2, "treatment": ["sfx"], "cut": "keep", "text_content": ""}]
PLAN0, _ = _dp(BEATS, V0)


# THE SHIPPED FUNCTION, NOT A COPY. The first version of this file
# reimplemented the merge here — and two mutations to the real dispatch passed
# green, because the smoke was driving its own reimplementation while the
# shipped path went untested. That is the defect `spec_shortfall` was hoisted
# out of the dispatch to fix, repeated. reedit_merge is now module-level and
# this drives it.
def _merge(prior_verdicts, targets, incoming):
    _out, _ref = _ns["reedit_merge"](prior_verdicts, targets, incoming)
    return _out, [r.get("beat") for r in _ref]


# ── 1. THE NO-OP ────────────────────────────────────────────────────────────
_loaded, _probs = _po(PLAN0, BEATS)
check("a no-op re-edit loads every prior ruling", not _probs and len(_loaded) == 3,
      f"{len(_loaded)} loaded, problems={_probs}")
_merged, _ref = _merge(_loaded, set(), [])
_replan, _ = _dp(BEATS, _merged)
check("a no-op re-edit reproduces the plan EXACTLY, id for id",
      [e["id"] for e in _replan] == [e["id"] for e in PLAN0],
      f"{[e['id'] for e in _replan]} vs {[e['id'] for e in PLAN0]} — identical "
      f"verdicts must round-trip to identical ids, which is the precondition "
      f"for identical bytes")
check("a no-op re-edit changes no field of any entry",
      all(a == b for a, b in zip(sorted(map(str, _replan)),
                                 sorted(map(str, PLAN0)))))

# ── 2. NAMED-ONLY ───────────────────────────────────────────────────────────
_changed = {"beat": 1, "treatment": ["zoom", "text"], "cut": "keep",
            "text_content": "NEW"}
_m2, _ref2 = _merge(_loaded, {1}, [_changed])
_plan2, _ = _dp(BEATS, _m2)
_by_beat = {v.get("beat"): v for v in _m2}
check("the named beat changed", _by_beat[1].get("text_content") == "NEW")
_ids0 = {e["src_t0"]: e["id"] for e in PLAN0}
_ids2 = {e["src_t0"]: e["id"] for e in _plan2}
check("EVERY UNNAMED ENTRY IS UNCHANGED BY ID",
      _ids0[0.0] == _ids2[0.0] and _ids0[9.0] == _ids2[9.0],
      f"beat0 {_ids0[0.0]}->{_ids2[0.0]}  beat2 {_ids0[9.0]}->{_ids2[9.0]} — a "
      f"re-edit that re-derives untouched placements is invisible in the video")
check("the named entry's id DID change (it is a different ruling now)",
      _ids0[4.0] != _ids2[4.0])
check("exactly one entry differs", sum(
    1 for k in _ids0 if _ids0[k] != _ids2.get(k)) == 1)

# ── 3. THE ALLOW-LIST REFUSES ───────────────────────────────────────────────
_m3, _ref3 = _merge(_loaded, {1}, [_changed, {"beat": 2, "treatment": ["card"],
                                              "cut": "cut", "text_content": "X"}])
check("a ruling outside the declared scope is REFUSED", _ref3 == [2], f"{_ref3}")
_p3, _ = _dp(BEATS, _m3)
check("and the refused beat's entry is untouched",
      {e["src_t0"]: e["id"] for e in _p3}[9.0] == _ids0[9.0])
_m4, _ref4 = _merge(_loaded, set(), [_changed])
check("with NO scope declared, nothing changes at all", _ref4 == [1]
      and {e["src_t0"]: e["id"] for e in _dp(BEATS, _m4)[0]} == _ids0,
      "an empty target set must be a no-op, not a free hand")

# ── 4. IT IS WIRED, not merely present ──────────────────────────────────────
for _needle, _what in (
        ("prior_plan: list = None", "edit() takes a prior plan"),
        ("_reedit = bool(prior_plan)", "re-edit mode is derived from it"),
        ("plan_onto_beats(prior_plan, _beats)", "the plan is loaded onto beats"),
        ('led.setdefault("reedit_refused"', "out-of-scope rulings are counted"),
        ("_reedit_targets = set(", "the allow-list comes from the declared scope"),
        ('fail("reedit_prior_lost"', "a lost prior ruling fails loudly"),
        ("_reedit_block", "the instruction and plan reach the prompt")):
    check(_what, _needle in src, f"missing: {_needle}")

print()
if fails:
    print("REEDIT-SURGICAL: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("REEDIT-SURGICAL: PASS — no-op reproduces the plan id-for-id, a named "
      "change moves exactly one entry, out-of-scope rulings refused, empty "
      "scope is a no-op")
