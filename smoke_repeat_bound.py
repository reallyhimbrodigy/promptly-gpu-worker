#!/usr/bin/env python3
"""SMOKE: a byte-identical call is bounded, whichever tool emits it.

WHY GENERIC AND NOT PER-TOOL. The one-execution gate is execute_plan-specific,
and the loop the agent falls into is not a property of any one tool. A measured
run spent 21,728 tokens against 7,510 and 8,058 on IDENTICAL input — a 2.9x
spread — with probe_source called six times as the top consumer at 26%. The
lever was not rule_all_beats. It is whichever loop the agent lands in this
month, so the bound is on the SHAPE of the call, not on a name.

THE ARGUMENT IS INTERPRETATION-FREE, which is what makes a generic bound safe
here. These tools are deterministic given their input and the ledger they read,
so a repeated payload returns what the agent already has. A per-beat diff of one
looping run split 48% restatement / 52% genuine re-decision — and it does not
matter which, because a BYTE-IDENTICAL payload produces a byte-identical result
under either reading.

ONE REPEAT IS ANSWERED, THEN TERMINAL. Refusing the first repeat outright is how
the execute_plan gate livelocked pet_video: a refusal with no exit produced 19
rule_all_beats calls and no video. Answering once and then stopping is terminal
by construction — the loop ends, so it cannot spin.
"""
import ast
import json
import pathlib
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


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)
_edit = next((n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
check("edit() is present to walk", _edit is not None)

# ── 1. THE KEY IS THE PAYLOAD, NOT THE TOOL NAME ────────────────────────────
# SPLIT, because one assertion embedding the whole expression makes both legs
# fire on either mutation and neither of them diagnostic.
_rpt_expr = next((ln for ln in src.splitlines() if "_rpt_key = " in ln), "")
check("the bound keys on the tool AND its input",
      "tu.name" in _rpt_expr and "tu.input" in _rpt_expr,
      f"key is built from: {_rpt_expr.strip()!r} — keying on the name alone "
      f"would bound a tool called twice with DIFFERENT arguments, which is "
      f"ordinary work")
check("the payload is canonicalised so key order cannot fool it",
      "sort_keys=True" in _rpt_expr,
      f"key is built from: {_rpt_expr.strip()!r} — {{'a':1,'b':2}} and "
      f"{{'b':2,'a':1}} are the same call and must produce the same key")
# APPLIED BEFORE ANY PER-TOOL BRANCH. A bound placed inside one tool's arm is a
# per-tool bound wearing a generic name, and leaves whatever the agent loops on
# next month.
_i_key = src.index("_rpt_key = ")
_i_first_branch = src.index("if tu.name in _REPAIR_ONLY")
check("the bound runs before the dispatch picks a tool",
      _i_key < _i_first_branch,
      "a bound inside one tool's branch only ever bounds that tool")

# ── 2. ONE ANSWERED, THEN TERMINAL ──────────────────────────────────────────
check("the first repeat is ANSWERED, not refused",
      "_rpt_seen == 2" in src and "repeat_answered" in src,
      "refusing the first repeat is exactly how the execute_plan gate "
      "livelocked pet_video — 19 calls and no video")
check("the answered repeat SAYS it was a repeat",
      "repeat_note" in src,
      "serving it silently teaches nothing and the second one is unavoidable")
check("the second repeat is TERMINAL", "_rpt_seen > 2" in src)
check("terminal means the loop ENDS, not another refusal",
      "if _repeat_stop:" in src and "_repeat_stop = True" in src,
      "a refusal with no exit is the livelock; ending the loop cannot spin")
check("the stop flag is initialised before the loop",
      "_repeat_stop = False" in src,
      "the ordinary path reads it every turn and would raise NameError")

# ── 3. THE GAP IS RECORDED, NOT THE RUN CALLED CLEAN ────────────────────────
# BY CALL NAME, FROM THE AST. `_skip_fail("repeat_terminal"` still CONTAINS
# `fail("repeat_terminal"`, so the substring test passed on a mutation that
# removed the recording entirely. Seventh instance of this in one port, and the
# law is already written: grep proves a string is present, only the AST proves
# the code runs.
_fail_kinds = {n.args[0].value for n in ast.walk(_edit or tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "fail" and n.args
               and isinstance(n.args[0], ast.Constant)}
check("stopping records a failure", "repeat_terminal" in _fail_kinds,
      f"fail() kinds raised in edit(): {sorted(_fail_kinds)}")
check("what was outstanding is carried into the stop",
      "what_was_outstanding" in src and "spec_shortfall" in src,
      "a run that stopped early and reported nothing outstanding reads as a "
      "run that finished")

# ── 4. THE COUNTERS ARE PRINTED ─────────────────────────────────────────────
# BOTH PRINT SITES. An existence test passed when one of the two was mutated,
# because the other still matched — the same shape as the credit_charged leg in
# smoke_five_families, which counts rather than tests for presence.
check("the repeat counters are PRINTED on BOTH paths",
      src.count("REPEATED CALLS  :") == 2,
      f"found {src.count('REPEATED CALLS  :')} print site(s); there are two — "
      f"the fired path and the clean path — and a bound that fires silently is "
      f"the same dead end as no bound: the run is simply shorter and nobody can "
      f"tell a disciplined agent from a stopped one")
check("zero repeats prints a line rather than nothing",
      "none — " in src,
      "silence is indistinguishable from the counter never running")

# ── 5. THE ARITHMETIC, RUN ──────────────────────────────────────────────────
# The dispatch is inside edit() and cannot be imported, so the rule itself is
# replayed here on the same key construction the source uses.
def _verdict(seen, name, payload):
    k = f"{name}:{json.dumps(payload, sort_keys=True, default=str)}"
    seen[k] = seen.get(k, 0) + 1
    n = seen[k]
    return "terminal" if n > 2 else "answered" if n == 2 else "normal"


_s = {}
check("first call runs", _verdict(_s, "probe_source", {}) == "normal")
check("second identical call is answered once",
      _verdict(_s, "probe_source", {}) == "answered")
check("third identical call is terminal",
      _verdict(_s, "probe_source", {}) == "terminal")
_s2 = {}
check("differing payloads are NOT bounded",
      [_verdict(_s2, "rule_all_beats", {"v": i}) for i in range(4)]
      == ["normal"] * 4,
      "re-ruling with genuinely different verdicts is the agent doing its job")
_s3 = {}
check("key ORDER does not create a false distinction",
      _verdict(_s3, "t", {"a": 1, "b": 2}) == "normal"
      and _verdict(_s3, "t", {"b": 2, "a": 1}) == "answered",
      "the same payload written in another order is the same payload")
_s4 = {}
check("the same payload to DIFFERENT tools is not conflated",
      _verdict(_s4, "probe_source", {}) == "normal"
      and _verdict(_s4, "inspect_output", {}) == "normal")

if fails:
    print(f"REPEAT-BOUND: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("REPEAT-BOUND: PASS")
