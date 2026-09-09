#!/usr/bin/env python3
"""Every name passed to these calls is BOUND ON THE PATH THAT REACHES THE CALL.

WHY THIS EXISTS, and it is the fourth instance of the class in this repo.

`cover_unnarrated_edges(_beats, _vdur)` was added to the TRANSCRIPT branch while
`_vdur` was assigned only inside the sibling VISUAL branch. Round 43 launched and
talking_head died in the container:

    /root/agentic_editor_app.py:7361 in edit
      _beats = cover_unnarrated_edges(_beats, _vdur)
    UnboundLocalError: cannot access local variable '_vdur'

NOTHING I HAD WOULD CATCH IT:

  pyflakes      silent — the name IS bound somewhere in the function, so it is a
                perfectly legal local. Unbound-on-one-path is not its question.
  my AST smokes confirmed the call EXISTED and that its result was BOUND. Both
                were true. Neither can ask whether the ARGUMENTS are reachable
                from the branch doing the calling.
  the cert      imports the module, which only proves the module parses and its
                module-level asserts pass. This code is inside a function that
                only runs in a container, on one of two branches.

"is it called" is not "is it callable HERE". Same family as *one hop of
indirection is still scope* and *an edit above a rebinding is not an edit*: three
prior instances, all in this file, none of them mine — this one is.

THE APPROXIMATION, stated plainly. A name is treated as in scope at a call if it
is assigned (or is a parameter, comprehension target, with/for target, or import)
either earlier in the call's own block or earlier in any ENCLOSING block. A name
assigned only inside a SIBLING branch is exactly what that excludes, which is the
defect. It is deliberately conservative about control flow — it does not try to
prove a loop runs or a try succeeds — so it can report a false positive on
genuinely odd code, and it names what it found rather than asserting a count.

  python3 smoke_call_args_in_scope.py     exit 0 = every argument is reachable
"""
import ast
import os
import sys

MODULE_NAMES = set()
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "agentic_editor_app.py")

# The calls whose arguments must be reachable. Anything added to a BRANCHED code
# path belongs here — that is the only shape this failure takes.
WATCHED = ("cover_unnarrated_edges", "geometry_normalise_filter",
           "sfx_catalogue_name", "region_effect_delta", "alpha_paint_box",
           "subdivide_beats", "beat_split_candidates", "fps_verdict",
           "stream_length_verdict", "cutaway_plan", "source_to_output")


def _walk_same_scope(stmt):
    """Every node under `stmt` WITHOUT descending into a nested scope.

    ast.walk() crosses function and class boundaries, which is wrong for a
    scope question and it broke this check TWICE in a row: once in the
    module-level exemption (`ast.walk(tree)` collected every local in the file
    as a "module name") and once here — `_bound_by` on a module-level
    `def edit(...)` descended into it and reported `_vdur`, a local assigned in
    a sibling branch, as bound at module scope. Both times the check passed on
    the exact defect it was written for.

    A nested def/lambda/comprehension binds its own names in its OWN scope. The
    only name it contributes to the enclosing scope is its own.
    """
    # IF THE STATEMENT IS ITSELF A DEF, it contributes only its NAME.
    #
    # The stop-list below tests CHILDREN, so starting on a FunctionDef walked
    # straight into its body — and MODULE_NAMES, built from tree.body, therefore
    # absorbed every local in `edit`, `_vdur` included. Third time the nested
    # scope crossed a boundary in this one check: the module exemption, then
    # _bound_by's children, now its root.
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt]
    stack, out = [stmt], []
    while stack:
        n = stack.pop()
        out.append(n)
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                out.append(child)      # the definition binds its own name
                continue               # but its body is a different scope
            stack.append(child)
    return out


def _bound_by(stmt):
    """Names this statement binds IN ITS OWN SCOPE."""
    out = set()
    for n in _walk_same_scope(stmt):
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in tgts:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        out.add(x.id)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    out.add(x.id)
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if item.optional_vars is not None:
                    for x in ast.walk(item.optional_vars):
                        if isinstance(x, ast.Name):
                            out.add(x.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
    return out


def _find(node, target, chain):
    """Yield (call, chain_of_blocks) for each watched call, with its block chain.

    `chain` is the list of (block_list, index_of_enclosing_stmt) from outermost
    in, which is exactly what "earlier in this block or any enclosing block"
    needs to be evaluated.
    """
    for field, value in ast.iter_fields(node):
        items = value if isinstance(value, list) else [value]
        if not items or not all(isinstance(i, ast.stmt) for i in items if i is not None):
            continue
        block = [i for i in items if isinstance(i, ast.stmt)]
        for idx, stmt in enumerate(block):
            # A NESTED def IS A DIFFERENT SCOPE — do not descend, and do not
            # attribute its calls to the enclosing function. `build_cut` lives
            # inside `edit`, and evaluating its calls against edit's block chain
            # reported `_v0` unreachable when it is assigned on the line above,
            # inside build_cut. It is visited on its own, with its own params,
            # because every FunctionDef in the module is iterated.
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                continue
            for c in _walk_same_scope(stmt):
                if (isinstance(c, ast.Call)
                        and getattr(c.func, "id", "") == target):
                    yield c, chain + [(block, idx)]
            yield from _find(stmt, target, chain + [(block, idx)])


def main():
    tree = ast.parse(open(APP, encoding="utf-8").read())
    # Names bound at MODULE scope — only tree.body, never a nested walk.
    global MODULE_NAMES
    MODULE_NAMES = set()
    for stmt in tree.body:
        MODULE_NAMES |= _bound_by(stmt)
    problems, checked = [], 0

    # ENCLOSING FUNCTION SCOPES — closures, which Python resolves at CALL time.
    #
    # Without this the check reports every closure variable as unreachable:
    # `execute_plan` is defined at line 6912 and reads `meta`, which `edit`
    # binds at 8745, and that is CORRECT Python — a nested function sees the
    # whole enclosing scope, not the lines above its own def. The first
    # cutaway_plan call tripped exactly this and the honest fix is to model the
    # rule rather than exempt the name; an exemption is where this check has
    # been blind twice already.
    #
    # IT DOES NOT WEAKEN THE ORIGINAL CATCH. The round-43 `_vdur` defect was a
    # name bound in a SIBLING BRANCH OF THE SAME FUNCTION, and same-function
    # ordering is still evaluated line by line below. RED-proven after this
    # change, not assumed.
    _parents = {}
    def _index(node, chain):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _parents[id(ch)] = list(chain)
                _index(ch, chain + [ch])
            elif isinstance(ch, ast.ClassDef):
                _index(ch, chain)          # a class body is not a closure scope
            else:
                _index(ch, chain)
    _index(tree, [])

    def _scope_names(fn):
        out = set()
        for p in (list(fn.args.posonlyargs) + list(fn.args.args)
                  + list(fn.args.kwonlyargs)
                  + ([fn.args.vararg] if fn.args.vararg else [])
                  + ([fn.args.kwarg] if fn.args.kwarg else [])):
            out.add(p.arg)
        for st in fn.body:
            out |= _bound_by(st)
        return out

    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        params = set()
        for _anc in _parents.get(id(fn), []):
            params |= _scope_names(_anc)
        a = fn.args
        for p in (list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)
                  + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])):
            params.add(p.arg)
        for target in WATCHED:
            # ONE VERDICT PER CALL, ON ITS DEEPEST CHAIN.
            #
            # _find yields the same call once per enclosing block — the outer
            # block sees it by walking the whole `if`, the inner block sees it
            # directly — and the OUTER view is missing the inner block's own
            # bindings. Evaluating both reported `_beats` unreachable when it is
            # assigned on the line above, inside the same branch. The deepest
            # chain is the only one that describes where the call actually sits.
            _deepest = {}
            for call, chain in _find(fn, target, []):
                if len(chain) >= len(_deepest.get(id(call), (None, []))[1]):
                    _deepest[id(call)] = (call, chain)
            for call, chain in _deepest.values():
                # Names available: parameters, plus anything bound EARLIER in
                # the call's own block or in any enclosing block.
                avail = set(params)
                for block, idx in chain:
                    for stmt in block[:idx]:
                        avail |= _bound_by(stmt)
                # plus bindings earlier in the enclosing statement itself
                # (e.g. `x = 1; y = f(x)` on separate lines is covered above)
                argnames = set()
                for arg in list(call.args) + [k.value for k in call.keywords]:
                    for x in ast.walk(arg):
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                            argnames.add(x.id)
                checked += 1
                for nm in sorted(argnames):
                    if nm in avail:
                        continue
                    # MODULE SCOPE ONLY — tree.body, not ast.walk(tree).
                    #
                    # This exemption was written as ast.walk(tree), which walks
                    # EVERY Assign in the file including ones nested inside
                    # functions. So the very name this check was built to catch
                    # (`_vdur`, assigned inside a sibling branch) matched the
                    # "module-level names are fine" clause and was skipped: the
                    # check reported PASS on the exact bug, and it did so on the
                    # first RED proof, before it had ever been trusted.
                    #
                    # A check's own escape hatch is the likeliest place for it to
                    # be blind, because the hatch is written to suppress noise
                    # and noise is what a real finding looks like first.
                    if nm in MODULE_NAMES:
                        continue
                    if nm in dir(__builtins__) or nm in vars(__builtins__):
                        continue
                    problems.append(
                        f"{target}(...) at line {call.lineno} in {fn.name}(): "
                        f"argument {nm!r} is not bound on the path that reaches "
                        f"this call — it is assigned only in a sibling branch, "
                        f"or not at all")

    print(f"checked {checked} call(s) of {len(WATCHED)} watched function(s)")
    # WHAT THIS DOES NOT COVER, printed rather than left in a docstring. A name
    # assigned inside a conditional that PRECEDES the call (`if cond: x = 1`
    # then `f(x)`) is treated as bound, because deciding whether cond can be
    # false is path feasibility and this is a scope check. The round-43 defect
    # was not that shape: `_vdur` sat in a SIBLING branch, reachable on no path
    # to the call at all. Saying so is the difference between a limit and a gap.
    print("  scope only — a name bound in a conditional BEFORE the call counts "
          "as bound;\n  a name bound in a SIBLING branch does not.\n")
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
        print(f"\n{len(problems)} unreachable argument(s)")
        return 1
    if checked == 0:
        print("  [FAIL] NO watched calls found at all — the names in WATCHED no "
              "longer exist, so this check is passing on an empty set. Absence "
              "must never render as success.")
        return 1
    print("  [ok] every argument is bound on the path that reaches its call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
