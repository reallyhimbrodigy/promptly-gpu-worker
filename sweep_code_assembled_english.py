"""SWEEP — every site that ASSEMBLES user-facing English in Python.

A string the model wrote can be steered by a prompt (reply_language does that).
A string PYTHON BUILT cannot: no instruction reaches it, so it renders English
to every reader whatever their device says. Those sites need a CODE the client
renders — the mechanism the error copy and the re-edit summary codes now use.

WHY AST AND NOT GREP. "Is this value CONSTRUCTED or PASSED THROUGH" is a
property of the expression, not of the text. A grep for `user_message` counted
26 sites when the truth was 11 emitting and 5 uncoded, because comments cannot
emit and `"user_message": None` is not a message.

WHY PER-FUNCTION AND NOT MODULE-WIDE — the correction that made this usable.
Flow analysis over the whole module treats `_parts` in _deterministic_ree edit
(a user sentence) and `_parts` in a prompt builder (text FOR the model) as one
name, so the sweep reported prompt scaffolding as user-facing copy. Scope is not
text. Each function is analysed in its own scope.

CALIBRATION, stated because the number moved three times before it was worth
anything: 4 -> 5 -> 40 -> 31 -> the count below. The first missed AugAssign and
multi-hop flow; the third leaked into prompt construction. It is calibrated
against sites ALREADY KNOWN to exist (the five language-gated English tails and
the surgical "(note: …)"), and it reports whether it found them — a sweep that
cannot find what you already know is there has not earned the rest of its list.
"""
import ast
import sys

# Fields a human reads off the job row.
USER_FACING = {
    "user_message", "human_summary", "clarification_question", "step_message",
}

# PROMPT SCAFFOLDING. These reach a user-facing field through a REAL dataflow
# path — prompt -> model -> parsed -> human_summary — so the transitive closure
# is not wrong, it is semantically backwards: that English is INPUT to the
# model, not output to a reader. Dataflow cannot tell the two apart; the
# direction has to be declared.
PROMPT_NAMES = {"prompt", "prompt_parts", "contents", "post_user", "mode_rule",
                "_ctx_lines", "_content_parts", "diff_lines", "system",
                "_post_user_attempt", "sys_prompt", "instruction"}

# Known-truth control: sites proven to exist by earlier work. If the sweep
# cannot find these, its other findings are not trustworthy.
KNOWN = {
    "handler.py": [
        ("_summary (+=)", "everything else untouched"),
        ("human_summary", "everything else untouched"),
        ("human_summary", "(note:"),
        ("_surg_notes (append)", "caption spelling change"),
    ],
}


def _prose(node):
    """A human-readable literal baked into this expression."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value.strip()
            # 6, not 12: " (note: " is EIGHT characters and is user-facing.
            if len(v) >= 6 and " " in v:
                return True
    return False


def _assembled(node):
    if isinstance(node, ast.Constant):
        return _prose(node)
    if isinstance(node, (ast.JoinedStr, ast.IfExp)):
        return _prose(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _prose(node)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("join", "format"):
            return _prose(node)
    return False


def _target_name(t):
    if isinstance(t, ast.Name):
        return t.id
    if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant):
        return t.slice.value
    return None


def _scope_hits(fn, path):
    """Assembled user-facing English inside ONE function's scope."""
    # Seed: names handed to a user-facing field, here only.
    flow = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value in USER_FACING:
                    flow |= {x.id for x in ast.walk(v)
                             if isinstance(x, ast.Name) and x.id not in PROMPT_NAMES}
        elif isinstance(n, ast.Assign) and _target_name(n.targets[0]) in USER_FACING:
            flow |= {x.id for x in ast.walk(n.value)
                     if isinstance(x, ast.Name) and x.id not in PROMPT_NAMES}
    # Transitive within this scope: _parts -> _joined -> _summary.
    changed = True
    while changed:
        changed = False
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and {_target_name(t) for t in n.targets} & flow:
                for x in ast.walk(n.value):
                    if (isinstance(x, ast.Name) and x.id not in flow
                            and x.id not in PROMPT_NAMES):
                        flow.add(x.id)
                        changed = True

    hits = []
    for n in ast.walk(fn):
        if isinstance(n, ast.AugAssign) and _assembled(n.value):
            nm = _target_name(n.target)
            if nm in USER_FACING or nm in flow:
                hits.append((n.lineno, f"{nm} (+=)", ast.unparse(n.value)[:82]))
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "append" and n.args
              and isinstance(n.func.value, ast.Name)
              and n.func.value.id in flow and _assembled(n.args[0])):
            hits.append((n.lineno, f"{n.func.value.id} (append)",
                         ast.unparse(n.args[0])[:82]))
        elif isinstance(n, ast.Assign) and _assembled(n.value):
            for t in n.targets:
                nm = _target_name(t)
                if nm in USER_FACING or nm in flow:
                    hits.append((n.lineno, nm, ast.unparse(n.value)[:82]))
        elif isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant) and k.value in USER_FACING
                        and _assembled(v)):
                    hits.append((k.lineno, k.value, ast.unparse(v)[:82]))
    return hits


def sweep(path):
    tree = ast.parse(open(path).read())
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            hits += _scope_hits(n, path)
    return sorted(set(hits))


if __name__ == "__main__":
    total, all_ok = 0, True
    for path in sys.argv[1:] or ["handler.py"]:
        hits = sweep(path)
        total += len(hits)
        print(f"\n=== {path}: {len(hits)} site(s) assembling user-facing English ===")
        for ln, field, expr in hits:
            print(f"  {path}:{ln}  {field}")
            print(f"      {expr}")
        # CONTROL: did it find what we already know is there?
        for label, needle in KNOWN.get(path, []):
            found = any(needle in e or needle in f for _, f, e in hits)
            if not found:
                all_ok = False
            print(f"  {'✓' if found else '✗ MISSED'} known site: {label} / {needle!r}")
    print(f"\n  {total} site(s). Each renders English to every reader, because no")
    print(f"  prompt can reach a string Python built.")
    if not all_ok:
        print("\n  ❌ THE CONTROL FAILED — the sweep cannot find sites already known")
        print("     to exist, so its other findings are not trustworthy.")
        sys.exit(1)
