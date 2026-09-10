#!/usr/bin/env python3
"""SMOKE: a value that might not exist must not reach a report as 0.

ZAC, 2026-09-09: "`or 0` on a value that might not exist should be an AST-checked
prohibition wherever a number reaches a report."

WHY IT IS WORTH A CHECK OF ITS OWN. Builder-1 found `paint_ms` printing 0.0s for
SIX ROUNDS against 458.6s of real wall — the key was never written for zoom, and
the printer said `or 0`. I had the same idiom in the two lines carrying the
edit-quality distributions, where "0 of 0 boundaries land inside a word" reads as
a clean edit rather than as a missing measurement. Two independent lanes, six
rounds, three characters.

THE RULE IS NOT "BAN `or 0`", and getting that wrong would make the check
useless:

    COUNTER      absent genuinely means zero. `execute_plan_calls` is written
                 only when a call happens, so no key means no calls. `or 0` is
                 CORRECT there.
    MEASUREMENT  absent means UNKNOWN. `paint_ms` absent does not mean the paint
                 took no time; it means nobody recorded it. `or 0` turns that
                 into a finding.

Static analysis cannot always tell them apart — `paint_ms` IS written, just not
on the zoom path — so this check does the part that IS decidable: it prohibits
the idiom inside a `print()` call, where any number is being reported, and pins
the known instances so the set can only shrink.

A pinned baseline rather than a clean sweep, because two of these are Builder-1's
printer and in flight; a check that fails on someone else's in-flight work is a
check that gets deleted.

STATED GAP — CROSS-FUNCTION LAUNDERING. Def-use is resolved WITHIN one function.
A default applied in `edit` and written to the ledger arrives in `main` as a
present, well-typed float, and nothing here can tell it from a measurement. That
is not a hole to patch with a wider scope; it is the reason the fix belongs at
the PRODUCER. `source_duration_s` below is exactly this shape and is pinned with
the producer's line number rather than this print's.
"""
import ast
import pathlib
import sys

SRC = pathlib.Path("agentic_editor_app.py")
src = SRC.read_text()
tree = ast.parse(src)

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


def _is_get_or_zero(n):
    return (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
            and len(n.values) == 2
            and isinstance(n.values[-1], ast.Constant)
            and n.values[-1].value == 0
            and isinstance(n.values[0], ast.Call)
            and getattr(n.values[0].func, "attr", "") == "get")


def _key_of(n):
    _a = n.values[0].args
    return (_a[0].value if _a and isinstance(_a[0], ast.Constant) else "?")


# DOES THE VALUE REACH A PRINT? That is the question, and neither of my first
# two scopes asked it.
#
#   inside print() only     TOO NARROW. My own defect was an ASSIGNMENT feeding
#                           a print, one line above it, so a check written
#                           against Builder-1's inline instance could not see
#                           mine. Two mutations reintroducing it walked through.
#   any function with       TOO WIDE. `edit` is 3,000 lines and contains plan
#   prints in it            construction — startMs, durationMs, frame counts —
#                           which are arithmetic, not reports. 17 hits, mostly
#                           innocent.
#
# Same failure as the union-vs-per-tool orphan check: scoped to the instance I
# happened to be looking at. The decidable question is DEF-USE — a `.get() or 0`
# is an offender when it is inside a print, or when its value is bound to a name
# that a print in the same function then uses.
_offenders = {}


def _names_in_prints(fn):
    _out = set()
    for _n in ast.walk(fn):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                and _n.func.id == "print":
            for _s in ast.walk(_n):
                if isinstance(_s, ast.Name):
                    _out.add(_s.id)
    return _out


for _fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    _printed = _names_in_prints(_fn)
    if not _printed:
        continue
    for _n in ast.walk(_fn):
        # (a) lexically inside a print
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                and _n.func.id == "print":
            for _sub in ast.walk(_n):
                if _is_get_or_zero(_sub):
                    _offenders.setdefault(_key_of(_sub), []).append(_sub.lineno)
        # (b) assigned to a name a print then uses — WALKING THE WHOLE ASSIGNED
        #     EXPRESSION, not just its top node. Both RED mutations wrapped the
        #     idiom in str(...), so `_is_get_or_zero(_n.value)` saw a Call and
        #     said no. One wrapper was enough to defeat the check, which is the
        #     thinnest disguise a defect has worn yet.
        if isinstance(_n, ast.Assign):
            _tgt = getattr(_n.targets[0], "id", None)
            if _tgt and _tgt in _printed:
                for _sub in ast.walk(_n.value):
                    if _is_get_or_zero(_sub):
                        _offenders.setdefault(_key_of(_sub), []).append(_n.lineno)

check("the scan finds print() calls at all",
      sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name) and n.func.id == "print") > 20,
      "no prints found — the prohibition below forbids nothing")

# THE PINNED SET. Each entry names WHO owns it and WHY it is still here. The
# check fails on anything NOT in this set, and fails if the set grows.
KNOWN = {
    # Builder-1's REMOTION PROCS printer. They found the defect and are landing
    # the fix — `paint_ms` never written on the zoom path, printing 0.0s against
    # 458.6s of wall. Theirs to remove, not mine to race.
    "paint_ms": "Builder-1, fix in flight (the defect that started this)",
    "bundle_ms": "Builder-1, same printer, same fix",
    # Absent coverage compares False against 0.995, so the note is simply not
    # printed. Conservative rather than a false measurement — but it is the same
    # idiom and stays listed so nobody has to re-derive that judgement.
    "coverage": "conservative: absent fails the >= comparison, prints nothing",
    # MINE, AND THE FIX IS NOT AT THIS LINE. Traced 2026-09-09: the ledger key
    # is written at 8801 from `_src_dur`, which is itself
    # `float(meta['format'].get('duration') or 0)` at 8797. The absence is
    # already laundered into a PRESENT 0.0 before this print ever runs, so
    # removing the `or 0` here changes nothing for the common case — the key is
    # there, it is a float, and it is fabricated. Absence is reachable only for
    # a run that died before 8801. Fix the PRODUCER; this line is the symptom.
    "source_duration_s": "MINE: symptom of the 8797 producer default, not the cause",
    # THE LEGITIMATE CASE, pinned so the distinction is documented rather than
    # re-argued. Both are COUNTERS incremented only when the thing happens, so
    # no key genuinely means it never happened. `or 0` is CORRECT here, and a
    # check that forced "?" on them would be worse than the defect it prevents.
    "execute_plan_calls": "COUNTER: written only on a call, so absent means 0 calls",
    "refused_second_execute": "COUNTER: written only on a refusal, absent means none",
    # PER-ITEM SUMS. `sum(x.get(k) or 0 for x in ...)` treats a turn that
    # recorded nothing as contributing nothing, which is what a sum means. The
    # denominator is len(tns), not the key, so an absence cannot masquerade as a
    # measured total.
    "rationale_bytes": "SUM: an item with no value contributes nothing to a total",
    "text_chars": "SUM: same, and the denominator is the item count",
    # THIS JUSTIFICATION WAS WRONG AND IS KEPT AS THE CORRECTION. It reads as
    # though the pinned site were a divisor; it is `_vdur` at 8692, and only the
    # 8772 use (`/ _vdur if _vdur else 0.0`) is guarded. `_vdur` is PRINTED at
    # 8750 and 8764 as a source duration, and passed as the SPAN to
    # segment_beats_visual and cover_unnarrated_edges — so an unreadable
    # duration segments a 0-second video and the visual route returns no beats.
    # MINE, to fix at the producer. Pinned with the real reason so nobody
    # re-derives "guarded downstream" from a note I wrote without checking.
    "duration": "MINE, to fix: `_vdur` 8692 — printed AND the beat span, not a divisor",
    # `float(wall_s or 0) or 1.0` — the second `or` makes it a DIVISOR guard,
    # never a reported value. Absent wall gives 1.0, so percentages read as
    # nonsense rather than as zeros, which is loud.
    "wall_s": "DIVISOR guard: `or 0` then `or 1.0`, never printed as a figure",
}
_new = {k: v for k, v in _offenders.items() if k not in KNOWN}
check("no NEW `.get(...) or 0` reaches a report", not _new,
      f"{ {k: v for k, v in _new.items()} } — a key that was never written for "
      f"this producer prints as a measured zero, which is how paint_ms reported "
      f"0.0s for six rounds")
check("the pinned set has not grown", len(_offenders) <= len(KNOWN),
      f"{len(_offenders)} offenders against {len(KNOWN)} pinned")
# The set must be able to SHRINK without editing the check: an entry that no
# longer appears is fine and is not an error.
check("every pinned entry names an owner or a reason",
      all(len(v) > 12 for v in KNOWN.values()),
      "a pinned exception with no reason is an allowlist, not a baseline")

# AND THE LINES I ALREADY FIXED MUST STAY FIXED — the two carrying the
# edit-quality distributions to Zac.
for _k in ("cut_boundaries_total", "painted_boxes_measured"):
    check(f"{_k} is not defaulted to 0 in a report", _k not in _offenders,
          "this denominator carries a distribution; a zero denominator turns an "
          "absence into a finding")

if fails:
    print(f"NO-ABSENT-AS-ZERO: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"NO-ABSENT-AS-ZERO: PASS — {len(_offenders)} pinned instance(s), "
      f"none new, and the report denominators stay explicit")
