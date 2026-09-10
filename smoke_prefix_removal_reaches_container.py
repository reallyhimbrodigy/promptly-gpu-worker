#!/usr/bin/env python3
"""AN ABLATION ARM THAT CLAIMS 'OFF' MUST ACTUALLY BE OFF.

THE NEAR-MISS. `prefix_material_enabled()` reads PROMPTLY_DISABLE_<NAME> with
os.environ.get — evaluated IN THE CONTAINER — and NOTHING ANYWHERE SET IT THERE.
`@app.local_entrypoint()` runs on the developer's machine, and Modal does not
forward local environment to the container. So round 49's ablation, launched
with the variable exported locally, would have run BOTH arms with the material
fully ON.

That is a FABRICATED NULL: the arm reports no effect because the arm never
happened. It is the most expensive result this lane can produce, because the
registration says a NULL is the attributable one — a fabricated null does not
read as a broken arm, it reads as a finding.

A consumer with no producer, in the mechanism an entire round's attribution was
about to depend on.

FOUR LEGS:

  PARAMETER   edit() takes prefix_removals and the entrypoint forwards it.
              A parameter nothing passes is the same defect one layer up.
  APPLIED     it writes os.environ BEFORE the prompt is assembled. Applying it
              after prefix_material_enabled() has already been read is a no-op
              that looks identical to working.
  PREDICATE   the reported state comes from the SAME predicate the injection
              uses — never a second copy that can drift.
  ROUND-TRIP  actually set it and read it back: removal in, REMOVED out.

  python3 smoke_prefix_removal_reaches_container.py    exit 0 = an OFF arm is off
"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "agentic_editor_app.py")
SRC = open(APP, encoding="utf-8").read()
TREE = ast.parse(SRC)
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

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
import agentic_editor_app as app                                    # noqa: E402

# ── LEG 1: the parameter exists on BOTH sides and is forwarded ───────────────
_fns = {n.name: n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)}
for fname in ("edit", "main"):
    fn = _fns.get(fname)
    ok(fn is not None, f"{fname}() is gone")
    if fn is None:
        continue
    args = [a.arg for a in list(fn.args.args) + list(fn.args.kwonlyargs)]
    ok("prefix_removals" in args,
       f"{fname}() has no prefix_removals parameter — the ablation arm has no "
       f"way to reach the container and would run with the material ON while "
       f"reporting itself as the OFF arm")

# FORWARDED, not merely declared. A parameter the caller never passes is the
# same consumer-with-no-producer defect one layer up.
_main = _fns.get("main")
_forwarded = False
if _main is not None:
    for n in ast.walk(_main):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "remote":
            for kw in n.keywords:
                if kw.arg == "prefix_removals":
                    _forwarded = True
ok(_forwarded,
   "main() never passes prefix_removals to edit.remote() — the parameter "
   "exists and nothing fills it, which is exactly the shape this check exists "
   "to catch, moved one frame out")

# ── LEG 2: APPLIED BEFORE THE PROMPT IS BUILT ────────────────────────────────
# Applying the removal AFTER prefix_material_enabled() has been read is a no-op
# that is byte-different and behaviourally identical to not applying it at all.
_edit = _fns.get("edit")
if _edit is not None:
    _set_line = None
    for n in ast.walk(_edit):
        if (isinstance(n, ast.Assign) and n.targets
                and isinstance(n.targets[0], ast.Subscript)
                and getattr(n.targets[0].value, "attr", "") == "environ"):
            _set_line = n.lineno if _set_line is None else min(_set_line, n.lineno)
    ok(_set_line is not None,
       "edit() never writes os.environ — prefix_removals is accepted and "
       "discarded, so the OFF arm runs ON")
    # ORDERING, ASSERTED AS POSITION IN THE BODY — not against
    # prefix_material_enabled call sites inside edit(), because THERE ARE NONE:
    # the predicate is read at module scope while the prompt blocks are built
    # (lines ~5438 and ~5524). The first version of this leg compared the
    # environ write against an EMPTY list of reads and therefore asserted
    # nothing — it passed with the write relocated to the middle of the
    # function, which is the exact no-op it exists to forbid.
    #
    # Vacuity again, in a leg written the same hour the vacuity rule went into
    # CLAUDE.md. The property that is actually checkable here is POSITION: the
    # removal must be applied among the FIRST statements of edit(), before any
    # work that could read the flag.
    _stmt_idx = None
    for _i, _st in enumerate(_edit.body):
        for _n in ast.walk(_st):
            if (isinstance(_n, ast.Assign) and _n.targets
                    and isinstance(_n.targets[0], ast.Subscript)
                    and getattr(_n.targets[0].value, "attr", "") == "environ"):
                _stmt_idx = _i if _stmt_idx is None else min(_stmt_idx, _i)
    ok(_stmt_idx is not None,
       "edit() never writes os.environ — prefix_removals is accepted and "
       "discarded, so the OFF arm runs ON")
    if _stmt_idx is not None:
        ok(_stmt_idx <= 4,
           f"the removal is applied at statement {_stmt_idx} of edit(), not in "
           f"the first few — anything before it that reads the flag sees the "
           f"material still ON, and a removal applied too late is a no-op that "
           f"is byte-different and behaviourally identical to no removal")

# ── LEG 3: ONE PREDICATE, NOT TWO ────────────────────────────────────────────
_state = _fns.get("prefix_material_state")
ok(_state is not None, "prefix_material_state is gone — nothing reports the arm")
if _state is not None:
    calls = [n for n in ast.walk(_state) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "prefix_material_enabled"]
    ok(calls,
       "prefix_material_state does not call prefix_material_enabled — it has "
       "its own copy of the predicate, so the REPORTED state can drift from "
       "the ACTUAL one and the log would confirm an arm that never ran")

# ── LEG 3b: THE OBSERVABLE IS COMPUTED ON THE SIDE IT DESCRIBES ──────────────
#
# AN OBSERVABLE MUST BE COMPUTED ON THE SIDE OF THE BOUNDARY IT DESCRIBES.
#
# prefix_material_state() was called in main() — an @app.local_entrypoint, which
# runs on the DEVELOPER'S MACHINE — while the material it reports is gated
# inside edit(), which runs in the CONTAINER. Same function, same predicate,
# same source file, different process; os.environ is per-process.
#
# It fails in whichever direction the two environments disagree:
#   var exported locally, nothing passed  -> log says REMOVED, container runs ON
#   parameter passed, clean local shell   -> log says ON, container removes
# The first CONFIRMS a fabricated null. The second makes a real arm
# unverifiable. Neither is visible from the log, because the log is the thing
# that is wrong — "a check that would have caught the failure" was itself on
# the wrong machine.
_main = _fns.get("main")
_edit_fn = _fns.get("edit")
ok(_main is not None and _edit_fn is not None, "main/edit missing")
if _main is not None:
    _local_calls = [n.lineno for n in ast.walk(_main)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "prefix_material_state"]
    ok(not _local_calls,
       f"prefix_material_state() is called inside main() at {_local_calls} — "
       f"main is the LOCAL entrypoint, so that line reports THIS machine's "
       f"environment while the material is gated in the container. The report "
       f"must come from the ledger the container filled")
if _edit_fn is not None:
    _cont_calls = [n.lineno for n in ast.walk(_edit_fn)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "prefix_material_state"]
    ok(_cont_calls,
       "prefix_material_state() is never called inside edit() — nothing "
       "measures the arm on the side that actually runs it, so the printed "
       "state is a restatement of what was requested rather than a measurement "
       "of what happened")
ok('led["prefix_material_state"]' in SRC,
   "the container never records its state in the ledger — main() has nothing "
   "truthful to print")
# ABSENT MUST NOT PRINT AS A DEFAULT ARM.
ok("PREFIX MATERIAL : UNKNOWN" in SRC,
   "a run whose ledger carries no prefix state prints as though it were a "
   "default run — an unknown arm rendering as a known one is the fabricated "
   "null with a report's clothes on")

# ── LEG 4: ROUND-TRIP, on the real functions ─────────────────────────────────
_saved = {k: os.environ.get(k) for k in
          ("PROMPTLY_DISABLE_REFERENCE_EXAMPLES",
           "PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE")}
try:
    for k in _saved:
        os.environ.pop(k, None)
    ok(app.prefix_material_state() == {"reference_examples": "ON",
                                       "ruling_time_knowledge": "ON"},
       f"unset does not mean ON: {app.prefix_material_state()}")
    os.environ["PROMPTLY_DISABLE_REFERENCE_EXAMPLES"] = "1"
    _st = app.prefix_material_state()
    ok(_st["reference_examples"] == "REMOVED",
       f"setting the variable did not remove the material: {_st}")
    ok(_st["ruling_time_knowledge"] == "ON",
       f"removing one removed the other too — the arms are not separable: {_st}")
finally:
    for k, v in _saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v

print()
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("ok smoke_prefix_removal_reaches_container — an OFF arm reaches the "
      "container, before the prompt, through one predicate")
