#!/usr/bin/env python3
"""A beat ruled twice is VISIBLE: which beats, what changed, what was lost,
and which ruling the build used.

WHY THIS GATE EXISTS. Round 63 `motion` carried 12 `beat_verdicts` for 10
beats, `screen_recording` 38-for-36, and nothing printed it. Four re-ruled
beats across the round, and EVERY ONE lost fields the first ruling had
supplied — `zoom_arc` 'hook'->None with "zoom" still in treatment,
`text_content` 'ChatGPT'->None with "text" still in treatment. The singular
`beat_verdict` tool appends with no duplicate check, writes 4 of the schema's
fields, skips the half-ruling refusal that `rule_all_beats` applies, and
answers with a DEDUPED `"ruled": N` so the agent is told "10 of 10" and cannot
see that it contradicted itself.

Bounding that is Builder-1's (the merge and the tool are his). This gate holds
the line that the disagreement is RECORDED AND PRINTED, because a ledgered
counter that reaches no output answers nothing — and this one hides a latent
defect: the frozen `executed_verdicts` copy kept the first ruling, but the
build's own per-beat lookup is `{v.get("beat"): v for v in beat_verdicts}`, a
dict comprehension, so LAST WINS there. On round 63 that was inert only
because the second execute_plan was refused every time.

Wiring legs are AST — grep proves a string is present, only the AST proves the
code runs. Behaviour legs drive the SHIPPED function, never a copy of it.
"""
import ast, importlib.util, pathlib, sys

APP = pathlib.Path("agentic_editor_app.py")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


if not APP.exists():
    print("  [FAIL] the app is present"); print("         %s ABSENT" % APP)
    sys.exit(1)
_src = APP.read_text()
_tree = ast.parse(_src)

# ── WIRING, BY AST ────────────────────────────────────────────────────────────
_fns = {n.name: n for n in _tree.body if isinstance(n, ast.FunctionDef)}
check("`reruled_beats` is a module-level function (hoisted, so the gate can "
      "drive the shipped rule instead of a copy)",
      "reruled_beats" in _fns)

_calls = [n for n in ast.walk(_tree)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == "reruled_beats"]
check("the app CALLS it — a reporter nobody calls reports nothing",
      len(_calls) >= 1, f"{len(_calls)} call site(s)")

# It must be called with BOTH the ruling list and the frozen executed copy:
# `built_from` is DERIVED from the executed copy, and with one argument the
# question "which ruling built" cannot be answered at all.
check("it is called with the executed copy too, so `built_from` is derived "
      "rather than asserted",
      any(len(c.args) >= 2 for c in _calls),
      "every call site passes one argument — `built_from` would be unanswerable")

_assigned = set()
for n in ast.walk(_tree):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                _assigned.add(t.slice.value)
for _k in ("reruled_state", "reruled_beats", "reruled_count"):
    check(f"ledger key `{_k}` is assigned", _k in _assigned)

# PRINTED IN THE SAME COMMIT THAT ADDS IT. Three instances in one session of a
# counter reaching the ledger and no output; this leg is that rule, enforced.
_printed_names = set()
for n in ast.walk(_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name):
                _printed_names.add(sub.id)
check("the state reaches a print, not just the ledger",
      "_rr_state" in _printed_names,
      "sorted sample: %s" % sorted(x for x in _printed_names if x.startswith("_rr"))[:6])
# NOT "a name appears inside a print": the red proof mutated `for _r in _rr_rows`
# to `for _r in []` and that leg stayed green while nothing printed at all. The
# property is that the ROWS are iterated INTO a print, so assert the loop.
_row_loops = [n for n in ast.walk(_tree)
              if isinstance(n, ast.For) and isinstance(n.iter, ast.Name)
              and n.iter.id == "_rr_rows"
              and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                      and c.func.id == "print" for c in ast.walk(n))]
check("the per-beat rows are ITERATED into a print (a count alone cannot say "
      "WHICH beat or WHAT changed, and `for _r in []` prints nothing while "
      "still mentioning _r inside a print)",
      len(_row_loops) >= 1,
      "no `for _r in _rr_rows:` loop containing a print")

# ── BEHAVIOUR, DRIVING THE SHIPPED FUNCTION ──────────────────────────────────
_spec = importlib.util.spec_from_file_location("_app_rr", str(APP))
_app = importlib.util.module_from_spec(_spec)
sys.modules["_app_rr"] = _app
try:
    _spec.loader.exec_module(_app)
except Exception as _e:                      # noqa: BLE001
    check("the app imports so the shipped rule can be driven", False,
          f"{type(_e).__name__}: {_e}")
    print("\nRE-RULED VISIBLE: FAIL")
    sys.exit(1)
rb = _app.reruled_beats

# THREE STATES. The zero is ambiguous unless absence is its own answer.
check("a non-list is ABSENT, not a zero — 'never recorded rulings' and 'never "
      "re-ruled a beat' are different facts",
      rb(None)[0] == "ABSENT" and rb("nope")[0] == "ABSENT",
      f"{rb(None)[0]!r} / {rb('nope')[0]!r}")
check("a present list with no duplicate is a MEASURED zero",
      rb([{"beat": 0}, {"beat": 1}]) == ("MEASURED", []))

_dup = [{"beat": 0, "treatment": ["zoom"], "zoom_arc": "hook", "purpose": "hook"},
        {"beat": 1, "treatment": ["none"]},
        {"beat": 0, "treatment": ["zoom"], "zoom_arc": None, "purpose": None}]
_st, _rows = rb(_dup, executed=[_dup[0], _dup[1]])
check("a beat ruled twice is reported", _st == "MEASURED" and len(_rows) == 1,
      f"{_st} {_rows}")
_r = _rows[0] if _rows else {}
check("it names the beat and how many rulings",
      _r.get("beat") == 0 and _r.get("rulings") == 2, repr(_r)[:160])
check("it names the CHANGED field and both values",
      _r.get("changed", {}).get("zoom_arc") == ["hook", None],
      repr(_r.get("changed"))[:160])
check("it names the LOST field — non-empty then empty is the silent case, and "
      "the field that loses its value is the one nobody sees go",
      "zoom_arc" in _r.get("lost_fields", []) and "purpose" in _r.get("lost_fields", []),
      repr(_r.get("lost_fields")))
check("`built_from` reads `first` when the frozen copy kept the first ruling",
      _r.get("built_from") == "first", repr(_r.get("built_from")))

# built_from must actually FOLLOW the executed copy, or it is an assertion
# dressed as a measurement.
_st2, _rows2 = rb(_dup, executed=[_dup[2], _dup[1]])
check("`built_from` reads `later` when the frozen copy kept the later ruling — "
      "it is derived from the executed copy, not asserted from the merge rule",
      _rows2 and _rows2[0].get("built_from") == "later",
      repr(_rows2[0].get("built_from") if _rows2 else None))

_st3, _rows3 = rb(_dup, executed=[{"beat": 1, "treatment": ["none"]}])
check("a re-ruled beat missing from the executed copy reads NOT_EXECUTED, not "
      "`first`",
      _rows3 and _rows3[0].get("built_from") == "NOT_EXECUTED",
      repr(_rows3[0].get("built_from") if _rows3 else None))

# VACUITY: `all()` over an empty change set is True, so identical duplicates
# would read as a confident `first`. They are their own answer.
_ident = [{"beat": 3, "treatment": ["zoom"]}, {"beat": 3, "treatment": ["zoom"]}]
_st4, _rows4 = rb(_ident, executed=_ident[:1])
check("identical duplicate rulings read `identical`, not a vacuous `first` "
      "(all() over an empty change set is True)",
      _rows4 and _rows4[0].get("built_from") == "identical",
      repr(_rows4[0].get("built_from") if _rows4 else None))

check("a beat with no `beat` key cannot crash or count",
      rb([{"treatment": ["zoom"]}, {"treatment": ["zoom"]}]) == ("MEASURED", []))

print()
if fails:
    print("RE-RULED VISIBLE: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RE-RULED VISIBLE: PASS — hoisted, called with both lists, three ledger "
      "keys, printed per beat; ABSENT/zero/changed/lost/built_from all hold")
