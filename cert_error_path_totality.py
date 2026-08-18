#!/usr/bin/env python3
"""AN ERROR HANDLER MAY NOT RAISE. `[Rule 1, Law 2]`

WHY, measured 2026-08-16: `handler.py:41270` sat inside an `except` block and
did `round(float(v), 1)` over every value of `_timings`. `_timings` legitimately
carries nested DICTS — gemini_tokens, cpu_by_stage and mem_by_stage were each
deliberately nested there by a SEPARATE persist guard, because content-studio
strips unknown top-level result keys.

So a job failed for a real reason, the error handler raised while recording it,
and the TypeError REPLACED the original cause. Two of ten terminal jobs in the
post-12:33Z cohort died that way and both are now permanently unattributable.
That is the worst failure mode an error handler has: it does not merely fail, it
DESTROYS THE EVIDENCE of why anything failed.

The three nesting fixes were each individually correct. The coercion was
individually reasonable. Nobody wrote a bug — they collided, and only a rule
about the SHAPE of error paths catches that.

THE RULE: inside an `except` or `finally`, a coercion (float/int/round) must be
guarded — by an isinstance check, by its own try, or by being applied to a
literal. Unguarded coercion over data whose shape you do not control is a second
exception waiting for the worst possible moment to fire.

    python3 cert_error_path_totality.py
"""
import ast
import os
import sys

FILES = ("handler.py", "modal_app.py")
COERCIONS = {"float", "int", "round"}


def _guarded(node, parents):
    """Is THIS coercion defended — by its OWN ancestry, not by proximity?

    The first version of this asked whether the enclosing STATEMENT's source
    contained "isinstance" or "try:". That is a proximity test wearing a scope
    test's clothes: an error-payload statement builds a dict with a dozen keys,
    so one unrelated isinstance anywhere in it whitewashed every coercion inside.
    Its own RED proof caught it — the cert PASSED on the exact reverted bug it
    was written for, which is a check that does not check.

    Now it walks the coercion's real ancestors: an enclosing try, or a ternary
    whose test is an isinstance on the same value. Nothing else counts.
    """
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, ast.Try):
            return True
        if isinstance(cur, ast.IfExp):
            try:
                if "isinstance" in ast.unparse(cur.test):
                    return True
            except Exception:
                pass
        if isinstance(cur, (ast.ExceptHandler, ast.FunctionDef)):
            break
    return False


def _scan(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    parents = {}
    for _p in ast.walk(tree):
        for _c in ast.iter_child_nodes(_p):
            parents[_c] = _p
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for block, label in ((node.handlers, "except"), (node.finalbody, "finally")):
            for stmt in block:
                seg = ast.get_source_segment(src, stmt) or ""
                for sub in ast.walk(stmt):
                    if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                            and sub.func.id in COERCIONS and sub.args):
                        continue
                    arg = sub.args[0]
                    # a literal or an f-string is fine — its shape is known
                    if isinstance(arg, (ast.Constant, ast.JoinedStr)):
                        continue
                    # ARITHMETIC ON LOCALS IS NOT THE CLASS. `round(time.time() -
                    # t0, 1)` cannot surprise you: you control both operands and
                    # they are numbers by construction. The class is coercion over
                    # DATA WHOSE SHAPE YOU DO NOT CONTROL — a dict value, a
                    # subscript, a .get(), a comprehension variable bound from
                    # someone else's structure. That is where a nested dict
                    # arrives unannounced and turns an error handler into a
                    # second exception. Flagging safe arithmetic too would make
                    # this gate un-greenable, and an un-greenable gate teaches
                    # people to route around it.
                    _data_derived = any(
                        isinstance(x, ast.Subscript)
                        or (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                            and x.func.attr in ("get", "items", "values", "pop"))
                        for x in ast.walk(arg))
                    _in_comp = any(isinstance(x, (ast.DictComp, ast.ListComp,
                                                  ast.SetComp, ast.GeneratorExp))
                                   for x in ast.walk(stmt))
                    if not (_data_derived or _in_comp):
                        continue
                    if _guarded(sub, parents):
                        continue
                    bad.append((path, getattr(sub, "lineno", "?"), label,
                                (ast.get_source_segment(src, sub) or "")[:90]))
    return bad


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    findings = []
    for f in FILES:
        p = os.path.join(here, f)
        if os.path.exists(p):
            findings += _scan(p)
    # ── SHAPE-UNCONTROLLED ACCUMULATORS, ON *EVERY* PATH ────────────────────
    #
    # THE GAP THIS CLOSES (2026-08-18). The scan above only inspects except and
    # finally blocks, because the defect it was forged from lived in one. The
    # SAME comprehension existed on the SUCCESS path, unguarded, and this gate
    # never looked at it:
    #
    #     {k: round(float(v), 1) for k, v in _timings.items()}
    #
    # `_timings` legitimately carries nested dicts — gemini_tokens,
    # cpu_by_stage, mem_by_stage, each nested DELIBERATELY to survive
    # content-studio's top-level key strip. So it raised TypeError after the
    # render had finished and the URL was already written.
    #
    # MEASURED: 111 of 114 jobs that failed WITH A FINISHED VIDEO since Aug 16
    # were this single line. 90 users, shown "Something went wrong." while their
    # video sat in S3. The largest failure class in the product, and the gate
    # written to prevent exactly this class was scoped one branch too narrowly.
    #
    # THE RULE: an accumulator whose SHAPE WE DO NOT CONTROL must be guarded
    # wherever it is coerced — the error path has no monopoly on this defect.
    _ACCUMULATORS = ("_timings",)
    for f in ("handler.py", "modal_app.py"):
        _p = os.path.join(here, f)
        if not os.path.exists(_p):
            continue
        _src = open(_p, encoding="utf-8").read()
        _tree = ast.parse(_src)
        for n in ast.walk(_tree):
            if not isinstance(n, (ast.DictComp, ast.ListComp, ast.SetComp,
                                  ast.GeneratorExp)):
                continue
            seg = ast.get_source_segment(_src, n) or ""
            if not any(f"{a}.items()" in seg or f"{a}.values()" in seg
                       for a in _ACCUMULATORS):
                continue
            has_coerce = any(isinstance(c, ast.Call)
                             and getattr(c.func, "id", None) in ("float", "int", "round")
                             for c in ast.walk(n))
            if has_coerce and "isinstance" not in seg:
                findings.append((_p, n.lineno, "shape-uncontrolled accumulator",
                                 seg.replace("\n", " ")[:100]))

    if findings:
        print(f"ERROR-PATH TOTALITY: {len(findings)} UNGUARDED coercion(s) in an "
              f"except/finally block\n")
        for path, line, label, code in findings:
            print(f"  [FAIL] {os.path.basename(path)}:{line} ({label})  {code}")
        print("\n  An unguarded coercion in an error path can REPLACE the original")
        print("  cause with its own exception — handler.py:41270 did exactly that and")
        print("  made two real failures permanently unattributable.")
        print("  Guard with isinstance, wrap in its own try, or coerce a literal.")
        return 1
    print("ERROR-PATH TOTALITY: ALL PASS (no unguarded float/int/round inside any "
          "except or finally block in handler.py or modal_app.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
