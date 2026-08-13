#!/usr/bin/env python3
"""Extract named top-level defs/assignments from a module, BY AST NODE NAME.

WHY THIS EXISTS [§8]. Three certs (cert_mg_obey, cert_upscale_negotiate,
cert_adapter_contract's siblings) each carried a copy of the same brittle
extractor: slice from an anchor string, stop at "the next `def` I do not
recognise", exec the slice. It depends on MODULE LAYOUT, so any new function
placed between the anchor and the target silently shortens the block and every
lookup KeyErrors.

It truncated three times in two days — COMPONENT_OBEY, UPSCALE v1, and §4.8's
negotiated-never — and each time the fix was to append another name to a regex.
That is a maintenance tax with a failure mode that looks like a broken cert
rather than a moved function, which is the worst kind: it points at the wrong
thing.

THE RULING: extract by NAME, not by position. Ask for the nodes you want; get
exactly those nodes, wherever they live in the file. Adding, moving or removing
unrelated code cannot affect the result. A name that is genuinely gone raises
immediately and says so, which is a real regression worth failing on.

Why still not just `import handler`: importing runs handler's module-level
startup — model downloads, S3/Deepgram/Supabase probes, ~15s and network. The
certs must stay offline and instant. This keeps that property while removing the
brittleness.

    from cert_extract import extract_from
    NS = extract_from("handler.py",
                      names=["_mg_obey_enabled", "_parse_mg_requests"],
                      globals_={"re": re, "os": os})
"""
import ast
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def extract_from(module_path, names, globals_=None, strict=True):
    """Compile ONLY the named top-level nodes and return their namespace.

    names      top-level function OR assignment-target names, in any order.
    globals_   names the extracted code needs at runtime (re, os, json, …).
    strict     raise when a requested name is not found (the default — a
               missing name is a real regression, not something to shrug at).

    Dependency order is preserved by taking the nodes in SOURCE order rather
    than in the order asked for: a constant defined above a function that uses
    it must still be defined first.
    """
    path = module_path if os.path.isabs(module_path) else os.path.join(_HERE, module_path)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)

    wanted = set(names)
    picked, found = [], set()
    for node in tree.body:                      # top level only, deliberately
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in wanted:
                picked.append(node)
                found.add(node.name)
        elif isinstance(node, ast.Assign):
            hit = [t.id for t in node.targets
                   if isinstance(t, ast.Name) and t.id in wanted]
            if hit:
                picked.append(node)
                found.update(hit)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in wanted:
                picked.append(node)
                found.add(node.target.id)

    missing = wanted - found
    if missing and strict:
        raise KeyError(
            f"{os.path.basename(path)}: no top-level definition of {sorted(missing)}. "
            "The name moved, was renamed, or was deleted — which is a real change, "
            "not an extractor problem.")

    ns = dict(globals_ or {})
    ns.setdefault("__name__", "extracted")
    ns.setdefault("__file__", path)
    mod = ast.Module(body=picked, type_ignores=[])
    exec(compile(mod, f"{os.path.basename(path)}<extracted>", "exec"), ns)  # noqa: S102
    return ns
