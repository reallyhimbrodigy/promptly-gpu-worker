"""B-roll context glue — regression tests for job 1a72b344 (UnboundLocalError: _sw).

Drives the REAL _broll_window_context with the dead job's geometry: a
135-word transcript and two b-roll entries with word spans [20-29] and
[86-99]. The first entry's indices arrive non-coercible (the stored-plan /
render_only path skips PostCutPlan validation), which unbound _sw in the
old inline block and killed the job holding a complete valid recipe.
"""
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

TX = [{"word": f"w{i}", "start": round(i * 0.4, 2), "end": round(i * 0.4 + 0.35, 2)}
      for i in range(135)]

print("=== G1: job 1a72b344 geometry — malformed first entry, valid second ===")
ENTRIES = [
    {"keyword": "typing", "start_word_index": None, "end_word_index": None,
     "word_span": "20-29", "reason": "r1", "duration": 2.0},
    {"keyword": "phone", "start_word_index": 86, "end_word_index": 99,
     "reason": "r2", "duration": 2.0},
]
try:
    results = [H._broll_window_context(bc, TX) for bc in ENTRIES]
    check("no raise across both entries", True)
except Exception as e:
    results = None
    check("no raise across both entries", False, repr(e))
if results:
    check("malformed entry degrades to ('', None)", results[0] == ("", None), str(results[0]))
    d2, m2 = results[1]
    check("valid entry [86-99] gets dialogue text", d2.startswith("w86") and d2.endswith("w99"), d2[:40])
    check("valid entry midpoint = (start[86]+end[99])/2",
          m2 is not None and abs(m2 - (TX[86]["start"] + TX[99]["end"]) / 2.0) < 1e-9, str(m2))

print("\n=== G2: no cross-entry state leak (valid entry BEFORE malformed) ===")
d, m = H._broll_window_context(
    {"start_word_index": 20, "end_word_index": 29}, TX)
d_bad, m_bad = H._broll_window_context(
    {"start_word_index": "20-29", "end_word_index": "x"}, TX)
check("valid [20-29] resolves", d.startswith("w20") and m is not None)
check("span-string '20-29' degrades cleanly (no stale midpoint)", (d_bad, m_bad) == ("", None),
      str((d_bad, m_bad)))

print("\n=== G3: hostile shapes — none may raise ===")
HOSTILE = [
    {},                                                     # keys absent
    {"start_word_index": "abc", "end_word_index": 5},       # ValueError
    {"start_word_index": [], "end_word_index": {}},         # TypeError
    {"start_word_index": 5, "end_word_index": 2},           # inverted
    {"start_word_index": -3, "end_word_index": 2},          # negative
    {"start_word_index": 130, "end_word_index": 200},       # out of range
    {"start_word_index": 0, "end_word_index": 134},         # full span (valid)
]
try:
    outs = [H._broll_window_context(bc, TX) for bc in HOSTILE]
    check("all hostile shapes survive", True)
    check("invalid shapes all degrade to ('', None)",
          all(o == ("", None) for o in outs[:-1]), str(outs[:-1]))
    check("boundary-valid full span resolves", outs[-1][0] != "" and outs[-1][1] is not None)
except Exception as e:
    check("all hostile shapes survive", False, repr(e))

print("\n=== G4: empty transcript + non-dict words — never raise ===")
try:
    o1 = H._broll_window_context({"start_word_index": 20, "end_word_index": 29}, [])
    o2 = H._broll_window_context({"start_word_index": 0, "end_word_index": 1},
                                 ["notadict", "alsonot"])
    check("empty transcript -> ('', None)", o1 == ("", None), str(o1))
    check("non-dict word entries degrade, no raise", o2[1] is None, str(o2))
except Exception as e:
    check("empty transcript -> ('', None)", False, repr(e))

print("\n=== G5: the handler loop actually calls the helper (no inline resurrection) ===")
import inspect
src = inspect.getsource(H)
loop_at = src.find("_broll_fetch_pool.submit")
window = src[max(0, loop_at - 2000):loop_at]
check("loop body calls _broll_window_context", "_broll_window_context(_bc, _broll_tx_words)" in window)
check("no inline _sw binding remains in the loop",
      "_sw = int(" not in window and "_ew = int(" not in window)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL BROLL-GLUE CASES PASS")
