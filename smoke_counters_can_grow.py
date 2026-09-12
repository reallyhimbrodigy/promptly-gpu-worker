#!/usr/bin/env python3
"""A counter that cannot increment is not a signal, and its zero is not a result.

ZAC, 2026-09-11: unsupported_request read zero for nine rounds and nobody could
distinguish no-demand from no-counting. The two look identical from the ledger,
so the ledger has to stop being the only place you can look.

WHAT THE AUDIT FOUND. 28 ledgers, rounds 51-60, 113 countable keys, 14 of them
ZERO in every single one. One was a phantom:

    led["skill_gate_blocks"] = led.get("skill_gate_blocks", 0)

A self-assignment whose only effect is to make the key exist. Nothing anywhere
incremented it, the C7 gate it counted was retired from the prompt, and the
counter and its report line were left behind — printing "0 render(s) blocked
before first search  (searched unprompted)" on ALL 28 RUNS, in a corpus where
skill_searches is EMPTY on all 28. The agent never searched once and the report
said it searched without being told to. A zero read as good news, on a wire
that could not carry anything.

THE MECHANICAL HALF, which is what this file gates: an assignment of the form
`led[K] = led.get(K, ...)` can never grow K. It is detectable with certainty
from the AST, it needs no traffic, and it is the shape the phantom had.

THE OTHER HALF NEEDS TRAFFIC AND JUDGEMENT, and is recorded rather than gated:
a counter with a real producer that has never fired is ambiguous, and only a
reason can settle it. `zero_counters_census.md` carries the 14, each classified.

RED-proven by red_proof_counters_can_grow.py.
"""
import ast
import pathlib
import sys

APP = pathlib.Path("agentic_editor_app.py")
CENSUS = pathlib.Path("zero_counters_census.md")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


check("the app is present", APP.exists())
if not APP.exists():
    print("\nCOUNTERS-CAN-GROW: FAIL"); sys.exit(1)
_tree = ast.parse(APP.read_text())


def _sub_key(node):
    """The literal key of led[...] / anything[...], or None."""
    if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)):
        return node.slice.value
    return None


# ── THE SELF-ASSIGNMENT THAT CANNOT GROW ────────────────────────────────────
_phantom = []
for _n in ast.walk(_tree):
    if not isinstance(_n, ast.Assign) or len(_n.targets) != 1:
        continue
    _k = _sub_key(_n.targets[0])
    if _k is None:
        continue
    _v = _n.value
    # led[K] = led.get(K, ...) — reads ITS OWN value and writes it back.
    #
    # THE CONTAINER HAS TO MATCH. The first version compared only the KEY, and
    # flagged `led["reel_frames"] = rc.get("reel_frames")` — which is a
    # perfectly ordinary read of the RENDER RESULT into the ledger under the
    # same name. A detector that cannot tell which object is being read finds
    # every same-named field in the file and calls it a phantom.
    _tgt_obj = ast.unparse(_n.targets[0].value)
    if (isinstance(_v, ast.Call) and isinstance(_v.func, ast.Attribute)
            and _v.func.attr == "get" and _v.args
            and isinstance(_v.args[0], ast.Constant)
            and _v.args[0].value == _k
            and ast.unparse(_v.func.value) == _tgt_obj):
        _phantom.append((_n.lineno, _k))
check("no ledger key is assigned from its own .get() — a self-assignment can "
      "never grow a counter, and its zero is not a measurement",
      not _phantom,
      "\n         ".join("L%d  %s" % (ln, k) for ln, k in _phantom[:8]))

# ── THE CENSUS IS ON THE RECORD, AND EVERY ALWAYS-ZERO COUNTER IS NAMED ─────
check("the always-zero census exists", CENSUS.exists(),
      "14 counters read zero on every one of 28 ledgers; without the census "
      "each one is a no-demand/no-counting ambiguity nobody can resolve")
if CENSUS.exists():
    _txt = CENSUS.read_text()
    _want = ["accounting_unbalanced", "axis_incoherent", "caption_recent_in",
             "cmds", "component_verdicts", "cut_word_intrusions",
             "framing_ruled", "knowledge_reads", "overlay_skips",
             "placement_effect_uncovered", "plan_problems", "skill_hits",
             "skill_searches"]
    _missing = [k for k in _want if k not in _txt]
    check("every always-zero counter from the census is named in it",
          not _missing, "missing: %s" % ", ".join(_missing))
    # EVERY COUNTER CARRIES A CLASSIFICATION IN ITS OWN ROW. A bare
    # `"UNREACHED" in _txt` passed while the defining sentence was mutated,
    # because the word also appears in seven table rows — the
    # ambiguous-literal class, in the check I wrote an hour after gating it.
    # What matters is that each row is classified, so read the rows.
    _rows = [l for l in _txt.splitlines()
             if l.startswith("| `") and l.count("|") >= 4]
    check("the census table has a row per always-zero counter",
          len(_rows) >= 13, "%d row(s)" % len(_rows))
    _unclassified = [l.split("|")[1].strip() for l in _rows
                     if not any(_c in l.split("|")[2]
                                for _c in ("GOOD ZERO", "NO WIRE", "UNREACHED"))]
    check("every row carries one of the three classifications",
          not _unclassified,
          "unclassified: %s — a zero with no class is read as a result by "
          "default, which is the whole defect" % ", ".join(_unclassified[:6]))
    for _cls in ("GOOD ZERO", "NO WIRE", "UNREACHED"):
        check("the %r class is actually used by a row" % _cls,
              any(_cls in l.split("|")[2] for l in _rows),
              "a vocabulary nothing uses is not a classification scheme")
    check("and it states the denominator it was taken over",
          "28 ledger" in _txt and "rounds 51-60" in _txt)
    check("the phantom is recorded as FIXED rather than quietly removed",
          "skill_gate_blocks" in _txt and "FIXED" in _txt)

# ── A READER'S ZERO NEEDS ITS DENOMINATOR IN THE SAME LEDGER ────────────────
# `read_knowledge` was called 0 times in 37 runs and `skill_searches` was empty
# on all of them. Both zeros are ONE CAUSE: every run was Haiku, and the
# judgment-only filter strips {read_knowledge, search_skills} before the loop —
# so the readers were OFFERED IN 0 OF 37 RUNS. The count of calls was true and
# said nothing, and it was quoted in a scope document as evidence the agent
# never needs them.
#
# A counter that has never incremented is a signal or a broken wire and the two
# look identical — UNLESS the number of chances is written beside it.
import ast as _ast
_src2 = pathlib.Path("agentic_editor_app.py").read_text()
_tree2 = _ast.parse(_src2)
_assigned2 = {t.slice.value for n in _ast.walk(_tree2)
              if isinstance(n, _ast.Assign)
              for t in n.targets
              if isinstance(t, _ast.Subscript) and isinstance(t.slice, _ast.Constant)
              and isinstance(t.slice.value, str)}
for _k in ("readers_offered", "readers_withheld"):
    check("the reader denominator `%s` is recorded" % _k, _k in _assigned2,
          "without it a reader's zero cannot be told from a withheld tool")
_rd_prints = [n for n in _ast.walk(_tree2) if isinstance(n, _ast.Call)
              and getattr(n.func, "id", "") == "print"
              and "READERS" in _ast.unparse(n)]
check("and PRINTED — a denominator in the ledger and nowhere else is how the "
      "zero got quoted without it in the first place",
      len(_rd_prints) >= 1)
# BOTH HALVES, AND NEITHER MAY CONSULT THE MODEL NAME. An `or` here was
# satisfied by its own mutant: replacing the `offered` expression left the
# `withheld` one standing and the leg stayed green. The property is that BOTH
# denominators are read off the tool list the agent actually got — a value
# re-derived from `_judgment_only` is a second source that can disagree with
# the list, which is the whole failure being instrumented.
_off_expr = '{t.get("name") for t in tools} & _READERS'
_wit_expr = '_READERS - {t.get("name") for t in tools}'
check("`readers_offered` is read off the tool list itself", _off_expr in _src2)
check("`readers_withheld` is read off the tool list itself", _wit_expr in _src2)
_den_fn = [n for n in _ast.walk(_tree2)
           if isinstance(n, _ast.Assign)
           and any(isinstance(t, _ast.Subscript)
                   and isinstance(t.slice, _ast.Constant)
                   and t.slice.value in ("readers_offered", "readers_withheld")
                   for t in n.targets)]
check("neither denominator is derived from the model role — a value restated "
      "from `_judgment_only` can disagree with the list the agent got",
      _den_fn and not any("_judgment_only" in _ast.unparse(n.value)
                          for n in _den_fn),
      "the denominator must come from the tools, not from the reason they were "
      "filtered")

print()
if fails:
    print("COUNTERS-CAN-GROW: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("COUNTERS-CAN-GROW: PASS — no self-assigned counter, and every "
      "always-zero counter named and classified")
