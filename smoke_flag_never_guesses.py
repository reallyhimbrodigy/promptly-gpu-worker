#!/usr/bin/env python3
"""A switch that carries an experiment never picks a side quietly.

THE DEFECT (Builder-1, 2026-09-09). `prefix_material_enabled` was
`os.environ.get(...).strip() != "1"`, so ONLY a literal "1" disabled the
material. An ablation arm set to "true", "yes" or "on" ran with the material IN
and reported a null — A FABRICATED NULL, in the one experiment whose entire
value is its null case.

INVERTING THE POLARITY DOES NOT FIX IT, and that was my first proposal. With OFF
as the explicit state a typo'd ON value silently runs OFF and the CONTROL becomes
the fabricated arm. The failure moves; it does not leave. The property is that
the switch NEVER GUESSES:

    unset                 -> ON   (an ordinary round is unaffected, and a
                                   forgotten variable cannot silently darken the
                                   material — the unset-global class in Rule 2)
    recognised spelling   -> that state, case-insensitively
    anything else         -> RAISE, naming variable and value

MEASURED / ABSENT / FAILED, one level up. Folding an unreadable value into ON is
a value standing in for "I could not read this" — alpha_layer_max returning None
and reading as a pass, paint_ms absent printing 0.0s, `or 0` turning absent into
a measured zero. A flag is not different because it is a string.

RED-proven by red_proof_flag_never_guesses.py.
"""
import ast
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


ns = {"os": os}
_want = ("prefix_material_enabled", "prefix_material_state")
for n in tree.body:
    if isinstance(n, ast.Assign) and any(
            getattr(t, "id", "").startswith("_FLAG_") for t in n.targets):
        exec(compile(ast.Module([n], []), "<c>", "exec"), ns)
    if isinstance(n, ast.FunctionDef) and n.name in _want:
        exec(compile(ast.Module([n], []), "<c>", "exec"), ns)
check("both flag functions are module-level and drivable",
      all(k in ns for k in _want), f"found {[k for k in _want if k in ns]}")
if not all(k in ns for k in _want):
    print("\nFLAG-NEVER-GUESSES: FAIL"); sys.exit(1)
f = ns["prefix_material_enabled"]
VAR = "PROMPTLY_DISABLE_REFERENCE_EXAMPLES"


def _with(val):
    os.environ.pop(VAR, None)
    if val is not None:
        os.environ[VAR] = val
    try:
        return ("OK", f("reference_examples"))
    except ValueError as e:
        return ("RAISED", str(e))
    except Exception as e:                                    # noqa: BLE001
        return ("WRONG-EXC", f"{type(e).__name__}: {e}")


# --------------------------------------------------- 1. the default is ON
for _unset in (None, "", "   "):
    _st, _v = _with(_unset)
    check(f"unset/blank ({_unset!r}) -> ON", (_st, _v) == ("OK", True), f"{_st} {_v!r}")

# ------------------------------------- 2. every accepted spelling, both ways
_OFF = ("1", "true", "TRUE", "Yes", "on", "ON")     # DISABLE=true -> removed
_ON = ("0", "false", "No", "off", "OFF")
for _s in _OFF:
    _st, _v = _with(_s)
    check(f"{_s!r} removes the material", (_st, _v) == ("OK", False), f"{_st} {_v!r}")
for _s in _ON:
    _st, _v = _with(_s)
    check(f"{_s!r} keeps the material", (_st, _v) == ("OK", True), f"{_st} {_v!r}")

# ------------------------------------------- 3. anything else RAISES, loudly
for _j in ("maybe", "2", "ON!", "tru e", "none", "null", "-1"):
    _st, _d = _with(_j)
    check(f"{_j!r} raises rather than picking a side", _st == "RAISED",
          f"{_st}: {_d!r} — a value that picks a side quietly turns an "
          f"ablation arm into a fabricated null")
    if _st == "RAISED":
        check(f"{_j!r}'s message names the variable and the value",
              VAR in _d and repr(_j) in _d, _d[:120])

# --------------------------- 4. the state the run REPORTS uses the same reader
os.environ.pop(VAR, None)
_st = ns["prefix_material_state"]()
check("prefix_material_state reports both materials",
      set(_st) == {"reference_examples", "ruling_time_knowledge"}, f"{_st}")
os.environ[VAR] = "yes"
_st2 = ns["prefix_material_state"]()
check("a removal shows in the reported state, not just in the predicate",
      _st2.get("reference_examples") == "REMOVED", f"{_st2}")
os.environ.pop(VAR, None)

# NON-VACUITY: the old silent-fold predicate must FAIL this file's own legs.
_old = lambda v: str(v or "").strip() != "1"                  # noqa: E731
check("the legs above can tell the new reader from the old one (non-vacuity)",
      _old("yes") is True and f("reference_examples") is True,
      "the old predicate returned ON for 'yes'; if that now passes, these legs "
      "are not testing the behaviour that changed")

print()
if fails:
    print("FLAG-NEVER-GUESSES: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"FLAG-NEVER-GUESSES: PASS — {len(_OFF)} off-spellings, {len(_ON)} "
      f"on-spellings, 7 junk values all raising, default ON")
