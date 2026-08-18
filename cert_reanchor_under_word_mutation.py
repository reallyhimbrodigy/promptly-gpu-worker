#!/usr/bin/env python3
"""RE-ANCHORING SURVIVES A WORD-SPACE MUTATION. `[Rule 1]`

THE LOAD-BEARING CORRECTNESS PROPERTY OF THE WHOLE DOCUMENT MODEL.

`edit_recipe` is an editable document and every anchor in it is a WORD INDEX:

    emphasis_moments      word_indices[0]
    transitions           after_word_index
    broll_clips           (start_word_index, end_word_index)
    motion_graphics       (start_word_index, end_word_index)
    text_overlays         start_word_index

Those are stable ONLY while the kept-word space is unchanged. The moment a
re-edit removes words — "cut the dead air", "make it 30 seconds" — every index
downstream of the removal shifts, and every anchor that is not re-anchored now
points at the wrong word or at a word that no longer exists.

`_reanchor_entry_to_survivors` claims FOUR properties in its docstring:
idempotent · never mutates the input · content byte-identical · returns None
ONLY when the whole span is gone. Nothing proved any of them. This does, by
driving the REAL function extracted from handler.py.

WHY IT MATTERS MORE THAN IT LOOKS: a silent mis-anchor produces a rendered video
where a graphic lands on the wrong word. That is not a crash, not a failed job,
and no gate anywhere would see it — it is a quality defect the user notices and
we cannot measure. That is the worst class this project has, and it is exactly
what the parked cut-removal work would have shipped.

    python3 cert_reanchor_under_word_mutation.py
"""
import ast
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")
WANT = ("_snap_forward", "_snap_backward", "_nearest_survivor",
        "_reanchor_entry_to_survivors")


def _load():
    src = open(HANDLER).read()
    tree = ast.parse(src)
    ns = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in WANT:
            exec(compile(ast.Module(body=[n], type_ignores=[]), "h", "exec"), ns)
    return ns, src, tree


def main():
    ns, src, tree = _load()
    missing = [f for f in WANT if f not in ns]
    if missing:
        print(f"CERT REANCHOR: FAIL\n  - not found: {missing}")
        return 1
    f = ns["_reanchor_entry_to_survivors"]
    fails = []

    # A 20-word space with words 5,6,7 and 12 removed.
    kept = [i for i in range(20) if i not in (5, 6, 7, 12)]

    def chk(name, cond, detail=""):
        if not cond:
            fails.append(f"{name}{(' — ' + detail) if detail else ''}")

    # 1. A SURVIVING ANCHOR IS UNCHANGED. The most important case, because it is
    #    the common one: most anchors are not near a cut and must not move.
    e = {"word_index": 3, "type": "SnapReframe"}
    got = f(e, kept)
    chk("a surviving point anchor must NOT move",
        got and got.get("word_index") == 3, f"got {got}")

    # 2. A REMOVED POINT ANCHOR SNAPS TO A SURVIVOR — and lands on a kept word.
    e = {"after_word_index": 6, "type": "SlideOver"}
    got = f(e, kept)
    chk("a removed point anchor must land on a SURVIVING word",
        got and got.get("after_word_index") in kept,
        f"got {got.get('after_word_index') if got else None}, kept={kept[:9]}…")

    # 3. RANGES SNAP INWARD and the invariant start <= end holds.
    #    NOTE ON THE CASE CHOICE, corrected after the first run: 5..7 is the
    #    WRONG probe — 5, 6 AND 7 are all removed, so that span is genuinely
    #    gone and None is right. Survivors either SIDE of a dead span do not
    #    make it alive. A range must PARTIALLY survive to test snapping.
    e = {"start_word_index": 4, "end_word_index": 8, "type": "StatCard"}
    got = f(e, kept)
    if got is None:
        chk("a range with surviving endpoints must snap, not drop", False,
            "returned None")
    else:
        chk("range start must land on a survivor",
            got["start_word_index"] in kept, str(got))
        chk("range end must land on a survivor",
            got["end_word_index"] in kept, str(got))
        chk("range invariant start <= end must hold after re-anchoring",
            got["start_word_index"] <= got["end_word_index"], str(got))

    # 3b. A FULLY-REMOVED INTERIOR SPAN IS A CORRECT DROP even with survivors
    #     on both sides — this is what the first run of this cert taught me, and
    #     it is the distinction the whole drop rule turns on.
    chk("a span whose every word is removed must DROP even with neighbours alive",
        f({"start_word_index": 5, "end_word_index": 7}, kept) is None)

    # 4. WHOLE SPAN GONE => None. THE ONLY CORRECT DROP.
    kept_narrow = [0, 1, 2, 3]
    e = {"start_word_index": 10, "end_word_index": 14}
    chk("a range entirely past every survivor must DROP (None)",
        f(e, kept_narrow) is None, str(f(e, kept_narrow)))

    # 5. IDEMPOTENT. f(f(x)) == f(x). A re-edit chain re-runs this pass, so a
    #    non-idempotent snap would drift the anchor a little further every time.
    e = {"start_word_index": 5, "end_word_index": 13, "word_indices": [6, 12, 15]}
    once = f(e, kept)
    twice = f(once, kept) if once else None
    chk("re-anchoring must be IDEMPOTENT (a re-edit chain re-runs it)",
        once == twice, f"once={once} twice={twice}")

    # 6. NEVER MUTATES THE INPUT. The caller keeps the prior plan for diffing;
    #    in-place mutation would corrupt the document it is being compared to.
    e = {"start_word_index": 4, "end_word_index": 8, "word_indices": [6]}
    before = copy.deepcopy(e)
    f(e, kept)
    chk("the input entry must NOT be mutated", e == before, f"{before} -> {e}")

    # 7. CONTENT BYTE-IDENTICAL — only anchor keys may change. A re-anchor that
    #    also rewrote props would be an edit masquerading as a move.
    e = {"start_word_index": 4, "end_word_index": 8,
         "props": {"value": 13, "label": "YEARS OLD"}, "why": "the hook"}
    got = f(e, kept) or {}
    chk("props must survive re-anchoring byte-identically",
        got.get("props") == {"value": 13, "label": "YEARS OLD"}, str(got.get("props")))
    chk("non-anchor fields must survive re-anchoring",
        got.get("why") == "the hook", str(got.get("why")))

    # 8. word_indices members each snap, dedupe, and stay non-empty.
    e = {"word_indices": [5, 6, 7]}
    got = f(e, kept)
    if got is None:
        chk("a word_indices list with survivors nearby must not drop", False)
    else:
        chk("every word_indices member must land on a survivor",
            all(w in kept for w in got["word_indices"]), str(got))
        chk("word_indices must dedupe after snapping (5,6,7 collapse)",
            len(got["word_indices"]) == len(set(got["word_indices"])), str(got))

    # 9. THE PASS IS ACTUALLY WIRED. A proven function nobody calls is the
    #    built-not-working class, which this repo has now seen nine times.
    calls = sum(1 for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "_reanchor_entry_to_survivors")
    chk("_reanchor_entry_to_survivors must be CALLED by the scoped-copy pass",
        calls >= 1, f"{calls} call sites")

    if fails:
        print("CERT REANCHOR: FAIL")
        for x in fails:
            print(f"  - {x}")
        return 1
    print("CERT REANCHOR: PASS")
    print("  survivors unchanged · removed anchors snap to survivors · ranges keep start<=end")
    print("  whole-span-gone is the ONLY drop · idempotent · input never mutated")
    print("  content byte-identical · word_indices snap+dedupe · and the pass is wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
